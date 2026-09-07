"""Write geolocated text records as a dataset that can be uploaded as it is.

The layout is the one the Hugging Face Hub reads without configuration:
gzipped JSON Lines shards under ``data/`` and a ``README.md`` card whose front
matter declares the split. The card is a template shipped beside this module,
so prose stays prose instead of becoming string literals in code.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import asdict
from itertools import chain, islice
from pathlib import Path
from shutil import copyfile
from typing import TYPE_CHECKING, Any

from wdcgeo import ENCODING, read_text, write_text
from wdcgeo.profile import merge

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from wdcgeo.extract import GeoText

SHARD_SIZE = 250_000
"""Records per shard: small enough to stream, few enough to list."""

CARD_NAME = "README.md"
PROFILE_NAME = "profile.json"

_SHARD_MODE = "wt"

_SIZE_BANDS = (
    (1_000, "n<1K"),
    (10_000, "1K<n<10K"),
    (100_000, "10K<n<100K"),
    (1_000_000, "100K<n<1M"),
    (10_000_000, "1M<n<10M"),
    (100_000_000, "10M<n<100M"),
)
_LARGEST_BAND = "100M<n<1B"


def to_json(value: object) -> str:
    """Render ``value`` as indented JSON, leaving text outside ASCII as it is."""
    return json.dumps(value, indent=2, ensure_ascii=False)  # pragma: no mutate


def _json_line(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)  # pragma: no mutate


def size_category(count: int) -> str:
    """Return the Hugging Face size band ``count`` records fall in."""
    for limit, label in _SIZE_BANDS:
        if count < limit:
            return label
    return _LARGEST_BAND


def write_card(directory: Path, records: int, sources: Sequence[str]) -> None:
    """Write the dataset card for ``records`` records read from ``sources``."""
    template = read_text(Path(__file__).with_name("card.md"))
    card = template.format(
        records=f"{records:,}",
        size_category=size_category(records),
        sources="\n".join(f"- `{source}`" for source in sources),
    )
    write_text(directory / CARD_NAME, card)


def _chunked(records: Iterator[GeoText], size: int) -> Iterator[Iterator[GeoText]]:
    """Split a stream into runs of ``size``, without holding a run in memory."""
    for first in records:
        yield chain([first], islice(records, size - 1))


def write_dataset(
    records: Iterable[GeoText],
    directory: Path,
    sources: Sequence[str],
    *,
    shard_size: int = SHARD_SIZE,
) -> dict[str, Any]:
    """Write ``records`` and a dataset card into ``directory``, returning a manifest."""
    data = directory / "data"
    data.mkdir(parents=True, exist_ok=True)
    shards: list[str] = []
    written = 0
    for chunk in _chunked(iter(records), shard_size):
        name = f"part-{len(shards):05d}.jsonl.gz"
        with gzip.open(data / name, _SHARD_MODE, encoding=ENCODING) as handle:  # pragma: no mutate
            for record in chunk:
                handle.write(_json_line(asdict(record)) + "\n")
                written += 1
        shards.append(name)
    write_card(directory, written, sources)
    return {"records": written, "shards": shards, "card": CARD_NAME}


def assemble(parts: Sequence[Path], sources: Sequence[str], directory: Path) -> dict[str, Any]:
    """Gather the datasets and profiles of separate parts into one dataset.

    A run processes parts independently, so each writes its own shards, profile
    and manifest. Assembling renumbers the shards into one series, merges the
    profiles, and writes a single card naming the published parts rather than
    the local copies a run happened to read.
    """
    data = directory / "data"
    data.mkdir(parents=True, exist_ok=True)
    shards: list[str] = []
    records = 0
    reports: list[dict[str, Any]] = []
    for part in parts:
        for shard in sorted((part / "data").glob("*.jsonl.gz")):
            shards.append(f"part-{len(shards):05d}.jsonl.gz")
            copyfile(shard, data / shards[-1])
        reports.append(read_json(part / "profile.json"))
        records += read_json(part / "manifest.json")["records"]
    write_text(directory / PROFILE_NAME, to_json(merge(reports)) + "\n")
    write_card(directory, records, sources)
    return {"parts": len(parts), "records": records, "shards": shards, "card": CARD_NAME}


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from a UTF-8 file."""
    return json.loads(read_text(path))

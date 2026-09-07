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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from wdcgeo.extract import GeoText

SHARD_SIZE = 250_000
"""Records per shard: small enough to stream, few enough to list."""

CARD_NAME = "README.md"

_SIZE_BANDS = (
    (1_000, "n<1K"),
    (10_000, "1K<n<10K"),
    (100_000, "10K<n<100K"),
    (1_000_000, "100K<n<1M"),
    (10_000_000, "1M<n<10M"),
    (100_000_000, "10M<n<100M"),
)
_LARGEST_BAND = "100M<n<1B"


def size_category(count: int) -> str:
    """Return the Hugging Face size band ``count`` records fall in."""
    for limit, label in _SIZE_BANDS:
        if count < limit:
            return label
    return _LARGEST_BAND


def _write_card(directory: Path, records: int, sources: Sequence[str]) -> None:
    template = Path(__file__).with_name("card.md").read_text(encoding="utf-8")
    card = template.format(
        records=f"{records:,}",
        size_category=size_category(records),
        sources="\n".join(f"- `{source}`" for source in sources),
    )
    (directory / CARD_NAME).write_text(card, encoding="utf-8")


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
        with gzip.open(data / name, "wt", encoding="utf-8") as handle:
            for record in chunk:
                handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
                written += 1
        shards.append(name)
    _write_card(directory, written, sources)
    return {"records": written, "shards": shards, "card": CARD_NAME}

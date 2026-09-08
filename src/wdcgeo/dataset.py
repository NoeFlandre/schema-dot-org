"""Write geolocated text records as a dataset that can be uploaded as it is.

The layout is the one the Hugging Face Hub reads without configuration:
gzipped JSON Lines shards under ``data/`` and a ``README.md`` card whose front
matter declares the split. The card is a template shipped beside this module,
so prose stays prose instead of becoming string literals in code.
"""

from __future__ import annotations

import gzip
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from itertools import chain, islice
from pathlib import Path
from shutil import copyfile
from typing import TYPE_CHECKING, Any

from wdcgeo import ENCODING, read_text, write_text
from wdcgeo.extract import GeoText
from wdcgeo.profile import merge

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

SHARD_SIZE = 250_000
"""Records per shard: small enough to stream, few enough to list."""

CARD_NAME = "README.md"
PROFILE_NAME = "profile.json"
MANIFEST_NAME = "manifest.json"
STATS_NAME = "stats.json"
MAP_NAME = "map.png"
TYPES_NAME = "types.png"

_SHARD_MODE = "wt"
_CARD_TEMPLATE = "card.md"
_MAP_TEMPLATE = "map.md"
_TYPES_TEMPLATE = "types.md"

_SIZE_BANDS = (
    (1_000, "n<1K"),
    (10_000, "1K<n<10K"),
    (100_000, "10K<n<100K"),
    (1_000_000, "100K<n<1M"),
    (10_000_000, "1M<n<10M"),
    (100_000_000, "10M<n<100M"),
)
_LARGEST_BAND = "100M<n<1B"
_TEXT_FIELDS = ("name", "description", "address")


def to_json(value: object) -> str:
    """Render ``value`` as indented JSON, leaving text outside ASCII as it is."""
    return json.dumps(value, indent=2, ensure_ascii=False)  # pragma: no mutate


def _json_line(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)  # pragma: no mutate


class DatasetStats:
    """Aggregate statistics for the records written to the published shards."""

    def __init__(self) -> None:
        """Start all counters empty."""
        self.records = 0
        self.pages = 0
        self.hosts: set[str] = set()
        self.text_records = 0
        self.words = 0
        self.characters = 0
        self.records_with_type = 0
        self.types: Counter[str] = Counter()
        self.languages: Counter[str] = Counter()
        self.null_island = 0
        self.whole_degrees = 0
        self._previous_page: str | None = None

    def add(self, record: GeoText) -> None:
        """Fold one published record into the counters."""
        self.records += 1
        self._add_page(record.page_url)
        self.hosts.add(record.host)
        self._add_text(record)
        self._add_types(record)
        self.languages.update(record.languages)
        self._add_coordinates(record)

    def _add_page(self, page_url: str) -> None:
        if page_url != self._previous_page:
            self.pages += 1
        self._previous_page = page_url

    def _add_text(self, record: GeoText) -> None:
        values = [getattr(record, field) for field in _TEXT_FIELDS]
        present = [value for value in values if value is not None]
        self.text_records += bool(present)
        self.words += sum(len(value.split()) for value in present)
        self.characters += sum(map(len, present))

    def _add_types(self, record: GeoText) -> None:
        self.records_with_type += bool(record.types)
        self.types.update(record.types)

    def _add_coordinates(self, record: GeoText) -> None:
        self.null_island += record.latitude == 0.0 and record.longitude == 0.0
        self.whole_degrees += record.latitude.is_integer() and record.longitude.is_integer()

    def to_dict(self) -> dict[str, Any]:
        """Render the counters as deterministic JSON-ready data."""
        return {
            "records": self.records,
            "pages": self.pages,
            "hosts": len(self.hosts),
            "text": {
                "records": self.text_records,
                "words": self.words,
                "characters": self.characters,
            },
            "records_with_type": self.records_with_type,
            "types": _ranked(self.types),
            "languages": _ranked(self.languages),
            "coordinates": {
                "null_island": self.null_island,
                "whole_degrees": self.whole_degrees,
            },
        }


def _ranked(counts: Counter[str]) -> dict[str, int]:
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


@dataclass(frozen=True, slots=True)
class CardOptions:
    """Optional images and statistics used when rendering a dataset card."""

    map_image: str | None = None
    types_image: str | None = None
    stats: Mapping[str, Any] | None = None


def size_category(count: int) -> str:
    """Return the Hugging Face size band ``count`` records fall in."""
    for limit, label in _SIZE_BANDS:
        if count < limit:
            return label
    return _LARGEST_BAND


def _template(name: str) -> str:
    return read_text(Path(__file__).with_name(name))


def _map_section(map_image: str | None) -> str:
    if map_image is None:
        return ""
    return _template(_MAP_TEMPLATE).format(map_image=map_image)


def _types_section(types_image: str | None) -> str:
    if types_image is None:
        return ""
    return _template(_TYPES_TEMPLATE).format(types_image=types_image)


def _number(value: object) -> str:
    return f"{value:,}" if isinstance(value, int) else "—"


def _nested_number(stats: Mapping[str, Any], section: str, name: str) -> str:
    values = stats.get(section)
    if not isinstance(values, Mapping):
        return "—"
    return _number(values.get(name))


def _card_stats(records: int, stats: Mapping[str, Any] | None) -> dict[str, str]:
    values = {} if stats is None else stats
    types = values.get("types")
    type_labels = len(types) if isinstance(types, Mapping) else None
    input_stats = values.get("input")
    input_values = input_stats if isinstance(input_stats, Mapping) else {}
    return {
        "published_records": _number(values.get("records", records)),
        "pages": _number(values.get("pages")),
        "hosts": _number(values.get("hosts")),
        "text_records": _nested_number(values, "text", "records"),
        "words": _nested_number(values, "text", "words"),
        "characters": _nested_number(values, "text", "characters"),
        "records_with_type": _number(values.get("records_with_type")),
        "type_labels": _number(type_labels),
        "raw_records": _number(input_values.get("records")),
        "distinct_places": _number(input_values.get("distinct_places")),
    }


def write_card(
    directory: Path,
    records: int,
    sources: Sequence[str],
    options: CardOptions | None = None,
) -> None:
    """Write the dataset card for a published dataset and its source count."""
    options = CardOptions() if options is None else options
    template = _template(_CARD_TEMPLATE)
    card = template.format(
        records=f"{records:,}",
        size_category=size_category(records),
        source_count=f"{len(sources):,}",
        map_section=_map_section(options.map_image),
        types_section=_types_section(options.types_image),
        **_card_stats(records, options.stats),
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
    stats = DatasetStats()
    for chunk in _chunked(iter(records), shard_size):
        name = f"part-{len(shards):05d}.jsonl.gz"
        with gzip.open(data / name, _SHARD_MODE, encoding=ENCODING) as handle:  # pragma: no mutate
            for record in chunk:
                handle.write(_json_line(asdict(record)) + "\n")
                written += 1
                stats.add(record)
        shards.append(name)
    report = stats.to_dict()
    write_text(directory / STATS_NAME, to_json(report) + "\n")
    write_card(directory, written, sources, CardOptions(stats=report))
    return {"records": written, "shards": shards, "card": CARD_NAME, "stats": STATS_NAME}


def assemble(
    parts: Sequence[Path],
    sources: Sequence[str],
    directory: Path,
    map_image: str | None = None,
    types_image: str | None = None,
) -> dict[str, Any]:
    """Gather the datasets and profiles of separate parts into one dataset.

    A run processes parts independently, so each writes its own shards, profile
    and manifest. Assembling renumbers the shards into one series, merges the
    profiles, and writes a single card naming the published parts rather than
    the local copies a run happened to read.
    """
    data = directory / "data"
    data.mkdir(parents=True, exist_ok=True)
    shards: list[str] = []
    shard_paths: list[Path] = []
    reports: list[dict[str, Any]] = []
    for part in parts:
        for shard in sorted((part / "data").glob("*.jsonl.gz")):
            name = f"part-{len(shards):05d}.jsonl.gz"
            shards.append(name)
            target = data / name
            copyfile(shard, target)
            shard_paths.append(target)
        reports.append(read_json(part / PROFILE_NAME))
    profile = merge(reports)
    write_text(directory / PROFILE_NAME, to_json(profile) + "\n")
    stats = _stats_from_shards(shard_paths)
    input_stats = _input_stats(profile)
    if input_stats:
        stats["input"] = input_stats
    write_text(directory / STATS_NAME, to_json(stats) + "\n")
    write_card(
        directory,
        stats["records"],
        sources,
        CardOptions(map_image=map_image, types_image=types_image, stats=stats),
    )
    return {
        "parts": len(parts),
        "records": stats["records"],
        "shards": shards,
        "card": CARD_NAME,
        "stats": STATS_NAME,
    }


def _records_from_shards(paths: Sequence[Path]) -> Iterator[GeoText]:
    for path in paths:
        with gzip.open(path, "rt", encoding=ENCODING) as handle:
            for line in handle:
                yield GeoText(**json.loads(line))


def _stats_from_shards(paths: Sequence[Path]) -> dict[str, Any]:
    stats = DatasetStats()
    for record in _records_from_shards(paths):
        stats.add(record)
    return stats.to_dict()


def _input_stats(profile: Mapping[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    records = profile.get("records")
    if isinstance(records, int):
        result["records"] = records
    duplication = profile.get("duplication")
    if isinstance(duplication, Mapping):
        distinct_places = duplication.get("distinct_places")
        if isinstance(distinct_places, int):
            result["distinct_places"] = distinct_places
    return result


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from a UTF-8 file."""
    return json.loads(read_text(path))

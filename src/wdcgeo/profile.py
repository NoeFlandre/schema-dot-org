"""Aggregate geolocated text records into one profile of a corpus.

The profile is built for a corpus that does not fit in memory, so every figure
comes from a single pass in which nothing but the counters is retained. Two
figures lean on how Web Data Commons orders its dumps -- pages of a host arrive
together -- and are named for what they actually measure:

``pages``
    page URLs counted by transition, so a page interrupted by another page and
    resumed counts twice.
``duplication``
    ``consecutive_repeats`` counts records identical to the record before them,
    and ``distinct_places`` counts coordinate-and-name pairs once per run of a
    host. Both measure the site-wide markup that repeats one business across
    every page of its site, which is the dominant redundancy in this corpus.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from math import floor
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from wdcgeo.extract import GeoText

TOP_N = 25
"""How many entries each ranking keeps."""

LENGTH_LIMITS = (20, 50, 100, 250, 1000)
"""Upper bounds of the character-count buckets reported per text field."""

GRID_DEGREES = 10
"""Side of a grid cell, labelled by the coordinates of its south-west corner."""

TEXT_FIELDS = ("name", "description", "address")

STRUCTURAL_SECTIONS = frozenset({"buckets", "coordinates", "duplication", "input"})
"""Sections whose keys are fixed, so merging must not re-rank them."""

_BUCKETS = (*(f"<={limit}" for limit in LENGTH_LIMITS), f">{LENGTH_LIMITS[-1]}")


def _repeat_key(record: GeoText) -> tuple[str, float, float, str | None]:
    return (record.host, record.latitude, record.longitude, record.name)


def _bucket(length: int) -> str:
    for limit in LENGTH_LIMITS:
        if length <= limit:
            return f"<={limit}"
    return f">{LENGTH_LIMITS[-1]}"


def _cell(latitude: float, longitude: float) -> str:
    return f"{_floor_to_cell(latitude)},{_floor_to_cell(longitude)}"


def _floor_to_cell(value: float) -> int:
    return floor(value / GRID_DEGREES) * GRID_DEGREES


class Accumulator:
    """Counters for one pass over a stream of records."""

    def __init__(self) -> None:
        """Start every counter at zero."""
        self.records = 0
        self.pages = 0
        self.without_type = 0
        self.without_language = 0
        self.null_island = 0
        self.whole_degrees = 0
        self.repeats = 0
        self.distinct_places = 0
        self.hosts: Counter[str] = Counter()
        self.domains: Counter[str] = Counter()
        self.types: Counter[str] = Counter()
        self.properties: Counter[str] = Counter()
        self.languages: Counter[str] = Counter()
        self.grid: Counter[str] = Counter()
        self.fields: Counter[str] = Counter()
        self.characters: Counter[str] = Counter()
        self.buckets: dict[str, Counter[str]] = {field: Counter() for field in TEXT_FIELDS}
        self._previous: GeoText | None = None
        self._places: set[tuple[float, float, str | None]] = set()

    def add(self, record: GeoText) -> None:
        """Fold one record into the counters."""
        previous = self._previous
        self._previous = record
        self.records += 1
        if previous is None or record.page_url != previous.page_url:
            self.pages += 1
        self.hosts[record.host] += 1
        self.domains[record.host.rpartition(".")[2]] += 1
        self.types.update(record.types)
        self.without_type += not record.types
        self.properties.update(record.text_properties)
        self.languages.update(record.languages)
        self.without_language += not record.languages
        self._add_text(record)
        self._add_coordinates(record)
        self._add_duplication(record, previous)

    def tap(self, records: Iterable[GeoText]) -> Iterator[GeoText]:
        """Fold every record on its way through, leaving the stream unchanged."""
        for record in records:
            self.add(record)
            yield record

    def _add_text(self, record: GeoText) -> None:
        present = 0
        for field in TEXT_FIELDS:
            value: str | None = getattr(record, field)
            if value is None:
                continue
            present += 1
            self.fields[field] += 1
            self.characters[field] += len(value)
            self.buckets[field][_bucket(len(value))] += 1
        self.fields["any"] += present > 0
        self.fields["all"] += present == len(TEXT_FIELDS)

    def _add_coordinates(self, record: GeoText) -> None:
        self.grid[_cell(record.latitude, record.longitude)] += 1
        self.null_island += record.latitude == 0.0 and record.longitude == 0.0
        self.whole_degrees += record.latitude.is_integer() and record.longitude.is_integer()

    def _add_duplication(self, record: GeoText, previous: GeoText | None) -> None:
        if previous is not None:
            self.repeats += _repeat_key(record) == _repeat_key(previous)
            if record.host != previous.host:
                self._places = set()
        place = (record.latitude, record.longitude, record.name)
        if place not in self._places:
            self._places.add(place)
            self.distinct_places += 1

    def to_dict(self) -> dict[str, Any]:
        """Render the counters as plain JSON-ready data."""
        return {
            "records": self.records,
            "pages": self.pages,
            "hosts": len(self.hosts),
            "top_hosts": dict(self.hosts.most_common(TOP_N)),
            "top_level_domains": dict(self.domains.most_common(TOP_N)),
            "types": dict(self.types.most_common(TOP_N)),
            "records_without_type": self.without_type,
            "text_properties": dict(self.properties.most_common(TOP_N)),
            "text": {
                **{field: self._text(field) for field in TEXT_FIELDS},
                "any": self.fields["any"],
                "all": self.fields["all"],
            },
            "languages": dict(self.languages.most_common(TOP_N)),
            "records_without_language": self.without_language,
            "coordinates": {
                "null_island": self.null_island,
                "whole_degrees": self.whole_degrees,
            },
            "duplication": {
                "consecutive_repeats": self.repeats,
                "distinct_places": self.distinct_places,
            },
            "grid": dict(self.grid.most_common(TOP_N)),
        }

    def _text(self, field: str) -> dict[str, Any]:
        return {
            "records": self.fields[field],
            "characters": self.characters[field],
            "buckets": {bucket: self.buckets[field][bucket] for bucket in _BUCKETS},
        }


def _merge_pair(into: dict[str, Any], report: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in report.items():
        if isinstance(value, Mapping):
            into[key] = _merge_pair(into.get(key, {}), value)
        else:
            into[key] = into.get(key, 0) + value
    return into


def _ranked(section: dict[str, Any], name: str = "") -> dict[str, Any]:
    if name not in STRUCTURAL_SECTIONS and all(isinstance(v, int) for v in section.values()):
        ordered = sorted(section.items(), key=lambda item: (-item[1], item[0]))
        return dict(ordered[:TOP_N])
    return {
        key: _ranked(value, key) if isinstance(value, dict) else value
        for key, value in section.items()
    }


def merge(reports: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Fold profiles of separate parts into one report.

    Counts add up; every ranking is re-ranked and cut back to the top entries,
    which is why a merged ranking is exact at the head and can miss an entry
    that stayed below every part's cut. ``hosts`` adds up too, so a host that
    appears in two parts is counted twice: the figure is an upper bound.
    """
    merged: dict[str, Any] = {}
    for report in reports:
        _merge_pair(merged, report)
    return _ranked(merged)


def profile(records: Iterable[GeoText]) -> dict[str, Any]:
    """Profile ``records`` in one pass, returning JSON-ready aggregates."""
    counters = Accumulator()
    for record in records:
        counters.add(record)
    return counters.to_dict()

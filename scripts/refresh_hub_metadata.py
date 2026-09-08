"""Recompute card metadata from published JSONL shards without copying them."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import cast

from wdcgeo import write_text
from wdcgeo.corpus import stream_lines
from wdcgeo.dataset import STATS_NAME, TYPES_NAME, CardOptions, DatasetStats, to_json, write_card
from wdcgeo.extract import GeoText


def records(sources: list[str]) -> Iterator[GeoText]:
    """Stream records from local or remote JSONL.GZ sources."""
    for source in sources:
        for line in stream_lines(source):
            yield GeoText(**json.loads(line))


def dataset_stats(sources: list[str]) -> dict[str, object]:
    """Compute published-dataset statistics in one bounded-memory pass."""
    stats = DatasetStats()
    for record in records(sources):
        stats.add(record)
    return stats.to_dict()


def input_stats(profile: Mapping[str, object]) -> dict[str, int]:
    """Select the pre-dedup counts that add useful context to the card."""
    result: dict[str, int] = {}
    records_count = profile.get("records")
    if isinstance(records_count, int):
        result["records"] = records_count
    duplication = profile.get("duplication")
    if isinstance(duplication, Mapping):
        distinct_places = duplication.get("distinct_places")
        if isinstance(distinct_places, int):
            result["distinct_places"] = distinct_places
    return result


def main() -> None:
    """Refresh stats and the card for an existing Hub dataset."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sources", nargs="+", metavar="SHARD")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-count", type=int)
    parser.add_argument("--map", dest="map_image", metavar="NAME")
    parser.add_argument("--types", dest="types_image", default=TYPES_NAME, metavar="NAME")
    arguments = parser.parse_args()
    from scripts.render_types import render  # noqa: PLC0415

    stats = dataset_stats(arguments.sources)
    profile = json.loads(arguments.profile.read_text(encoding="utf-8"))
    selected_input = input_stats(profile)
    if selected_input:
        stats["input"] = selected_input
    arguments.out.mkdir(parents=True, exist_ok=True)
    write_text(arguments.out / STATS_NAME, to_json(stats) + "\n")
    source_count = arguments.source_count or len(arguments.sources)
    published_records = cast("int", stats["records"])
    render(cast("dict[str, int]", stats["types"]), arguments.out / arguments.types_image)
    write_card(
        arguments.out,
        published_records,
        [str(index) for index in range(source_count)],
        CardOptions(
            map_image=arguments.map_image,
            types_image=arguments.types_image,
            stats=stats,
        ),
    )
    print(json.dumps({"records": stats["records"], "out": str(arguments.out)}, indent=2))


if __name__ == "__main__":
    main()

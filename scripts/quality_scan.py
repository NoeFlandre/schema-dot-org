"""Scan exported records for the defects a consumer has to filter out.

The profile counts what the corpus contains; this counts what is wrong with it.
Both matter for deciding whether the geolocated text is usable, and these are
the patterns that showed up when reading actual records:

* a site publishing one value for both latitude and longitude;
* HTML entities left encoded in text, because the markup carried them that way
  and the extraction preserves what was published;
* text so short it carries no information.

Run it over the shards of an export or an assembled dataset:

    python scripts/quality_scan.py data/dataset/data/*.jsonl.gz
"""

import gzip
import json
import re
import statistics
import sys
from collections.abc import Sequence
from typing import TypedDict, cast

ENTITY = re.compile(r"&(?:amp|lt|gt|quot|#3\d|nbsp);")
TEXT_FIELDS = ("name", "description", "address")
SHORT_NAME_LIMIT = 3


class Record(TypedDict):
    """The record fields inspected by this diagnostic script."""

    latitude: float
    longitude: float
    name: str | None
    description: str | None
    address: str | None


def scan(paths: Sequence[str]) -> dict[str, object]:
    """Return defect counts over every record in ``paths``."""
    records = 0
    identical_coordinates = 0
    entities = dict.fromkeys(TEXT_FIELDS, 0)
    short_names = 0
    description_lengths = []
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                record = cast("Record", json.loads(line))
                records += 1
                identical_coordinates += record["latitude"] == record["longitude"]
                for field in TEXT_FIELDS:
                    value = record[field]
                    if value and ENTITY.search(value):
                        entities[field] += 1
                name = record["name"]
                short_names += int(bool(name) and len(name) < SHORT_NAME_LIMIT)
                if record["description"]:
                    description_lengths.append(len(record["description"]))
    description_lengths.sort()
    return {
        "records": records,
        "identical_coordinates": identical_coordinates,
        "html_entities": entities,
        "names_shorter_than_three_characters": short_names,
        "description_length": {
            "records": len(description_lengths),
            "median": statistics.median(description_lengths) if description_lengths else 0,
            "p90": description_lengths[int(len(description_lengths) * 0.9)]
            if description_lengths
            else 0,
        },
    }


def main() -> None:
    """Print the scan of the shards named on the command line."""
    print(json.dumps(scan(sys.argv[1:]), indent=2))


if __name__ == "__main__":
    main()

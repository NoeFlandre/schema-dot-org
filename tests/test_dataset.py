import gzip
import json
from dataclasses import replace

import pytest

from wdcgeo.dataset import (
    CARD_NAME,
    MAP_NAME,
    SHARD_SIZE,
    assemble,
    size_category,
    write_dataset,
)
from wdcgeo.extract import GeoText

BASE = GeoText(
    page_url="http://example.com/p/1",
    host="example.com",
    latitude=48.5,
    longitude=2.5,
    types=("Restaurant",),
    name="Cafe Zero",
    description=None,
    address="Paris",
    text_properties=("name",),
    languages=("fr",),
)
SOURCES = ["http://mirror.example.com/geo/part_0.gz", "http://mirror.example.com/geo/part_8.gz"]

SECOND = replace(
    BASE,
    page_url="http://other.example/p/2",
    host="other.example",
    latitude=0.0,
    longitude=0.0,
    types=("Restaurant", "CafeOrCoffeeShop"),
    name="Two words",
    description="three four",
    address=None,
    languages=("en", "fr"),
)


def read_shard(directory, name):
    with gzip.open(directory / "data" / name, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def test_writes_post_dedup_stats_from_records(tmp_path):
    manifest = write_dataset([BASE, SECOND], tmp_path, SOURCES)
    assert manifest["stats"] == "stats.json"
    assert json.loads((tmp_path / "stats.json").read_text(encoding="utf-8")) == {
        "records": 2,
        "pages": 2,
        "hosts": 2,
        "text": {"records": 2, "words": 7, "characters": 33},
        "records_with_type": 2,
        "types": {"Restaurant": 2, "CafeOrCoffeeShop": 1},
        "languages": {"fr": 2, "en": 1},
        "coordinates": {"null_island": 1, "whole_degrees": 1},
    }


def test_writes_one_json_object_per_record(tmp_path):
    manifest = write_dataset([BASE], tmp_path, SOURCES)
    assert manifest["records"] == 1
    assert manifest["shards"] == ["part-00000.jsonl.gz"]
    assert read_shard(tmp_path, "part-00000.jsonl.gz") == [
        {
            "page_url": "http://example.com/p/1",
            "host": "example.com",
            "latitude": 48.5,
            "longitude": 2.5,
            "types": ["Restaurant"],
            "name": "Cafe Zero",
            "description": None,
            "address": "Paris",
            "text_properties": ["name"],
            "languages": ["fr"],
        }
    ]


def test_keeps_text_readable_rather_than_escaping_it(tmp_path):
    write_dataset([replace(BASE, name="Café Zéro")], tmp_path, SOURCES)
    with gzip.open(tmp_path / "data" / "part-00000.jsonl.gz", "rt", encoding="utf-8") as handle:
        assert "Café Zéro" in handle.read()


def test_starts_a_new_shard_every_shard_size_records(tmp_path):
    manifest = write_dataset([BASE] * 5, tmp_path, SOURCES, shard_size=2)
    assert manifest["shards"] == [
        "part-00000.jsonl.gz",
        "part-00001.jsonl.gz",
        "part-00002.jsonl.gz",
    ]
    assert [len(read_shard(tmp_path, name)) for name in manifest["shards"]] == [2, 2, 1]


def test_default_shard_size_is_a_quarter_million_records():
    assert SHARD_SIZE == 250_000


def test_writes_a_card_but_no_shards_for_an_empty_stream(tmp_path):
    manifest = write_dataset([], tmp_path, SOURCES)
    assert manifest == {"records": 0, "shards": [], "card": "README.md", "stats": "stats.json"}
    assert (tmp_path / "README.md").exists()


def test_card_opens_with_hugging_face_front_matter(tmp_path):
    write_dataset([BASE], tmp_path, SOURCES)
    card = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert card.startswith("---\nlicense: cc-by-4.0\n")
    assert "\n  - split: train\n    path: data/*.jsonl.gz\n" in card


def test_card_reports_the_record_count_the_size_band_and_the_parts_read(tmp_path):
    write_dataset([BASE] * 1500, tmp_path, SOURCES, shard_size=1000)
    card = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "1,500 geolocated text records" in card
    assert "size_categories:\n- 1K<n<10K\n" in card
    for source in SOURCES:
        assert f"- `{source}`\n" in card


def test_card_documents_every_field_of_a_record(tmp_path):
    write_dataset([BASE], tmp_path, SOURCES)
    card = (tmp_path / "README.md").read_text(encoding="utf-8")
    for field in BASE.__dataclass_fields__:
        assert f"| `{field}` |" in card


@pytest.mark.parametrize(
    ("count", "label"),
    [
        (0, "n<1K"),
        (999, "n<1K"),
        (1_000, "1K<n<10K"),
        (10_000, "10K<n<100K"),
        (100_000, "100K<n<1M"),
        (1_000_000, "1M<n<10M"),
        (10_000_000, "10M<n<100M"),
        (100_000_000, "100M<n<1B"),
    ],
)
def test_size_category_uses_the_hugging_face_bands(count, label):
    assert size_category(count) == label


def part_directory(root, name, records, profile):
    directory = root / name
    write_dataset(records, directory, ["local"])
    (directory / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    (directory / "manifest.json").write_text(
        json.dumps({"records": len(records)}), encoding="utf-8"
    )
    return directory


def test_assemble_gathers_shards_profiles_and_one_card(tmp_path):
    first = part_directory(tmp_path, "part_0", [BASE], {"records": 3, "hosts": 1})
    second = part_directory(
        tmp_path, "part_7", [BASE, replace(BASE, name="Two")], {"records": 5, "hosts": 2}
    )
    out = tmp_path / "dataset"

    manifest = assemble([first, second], SOURCES, out)

    assert manifest == {
        "parts": 2,
        "records": 3,
        "shards": ["part-00000.jsonl.gz", "part-00001.jsonl.gz"],
        "card": "README.md",
    }
    assert [len(read_shard(out, name)) for name in manifest["shards"]] == [1, 2]
    assert json.loads((out / "profile.json").read_text(encoding="utf-8")) == {
        "records": 8,
        "hosts": 3,
    }
    card = (out / "README.md").read_text(encoding="utf-8")
    assert "3 geolocated text records" in card
    assert f"- `{SOURCES[0]}`\n" in card


def test_assemble_needs_no_parts_at_all(tmp_path):
    out = tmp_path / "dataset"
    assert assemble([], [], out) == {"parts": 0, "records": 0, "shards": [], "card": "README.md"}
    assert json.loads((out / "profile.json").read_text(encoding="utf-8")) == {}


def test_writes_into_a_directory_that_already_holds_a_dataset(tmp_path):
    write_dataset([BASE], tmp_path, SOURCES)
    manifest = write_dataset([BASE, replace(BASE, name="Two")], tmp_path, SOURCES)
    assert manifest["records"] == 2
    assert len(read_shard(tmp_path, "part-00000.jsonl.gz")) == 2


def test_assembles_into_a_directory_that_already_holds_a_dataset(tmp_path):
    part = part_directory(tmp_path, "part_0", [BASE], {"records": 1})
    out = tmp_path / "dataset"
    assemble([part], SOURCES, out)
    assert assemble([part], SOURCES, out)["records"] == 1


def test_card_has_no_map_section_by_default(tmp_path):
    write_dataset([BASE], tmp_path, SOURCES)
    card = (tmp_path / CARD_NAME).read_text(encoding="utf-8")
    assert "Where the records are" not in card
    # Nothing at all stands where the section would go.
    assert "\n\n## Parts read" in card


def test_card_shows_the_map_when_one_is_named(tmp_path):
    part = part_directory(tmp_path, "part_0", [BASE], {"records": 1})
    out = tmp_path / "dataset"
    assemble([part], SOURCES, out, MAP_NAME)
    card = (out / CARD_NAME).read_text(encoding="utf-8")
    assert "## Where the records are" in card
    assert f"![Density of the records over the world]({MAP_NAME})" in card
    assert card.index("Where the records are") < card.index("## Parts read")

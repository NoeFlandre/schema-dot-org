import gzip
import json
from dataclasses import replace

import pytest

from wdcgeo.dataset import SHARD_SIZE, size_category, write_dataset
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


def read_shard(directory, name):
    with gzip.open(directory / "data" / name, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


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
    assert manifest == {"records": 0, "shards": [], "card": "README.md"}
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

import gzip
import json
from dataclasses import replace
from pathlib import Path

import pytest

from wdcgeo.dataset import (
    CARD_NAME,
    MAP_NAME,
    SHARD_SIZE,
    TYPES_NAME,
    CardOptions,
    DatasetStats,
    _data_directory,
    assemble,
    size_category,
    write_card,
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
    assert list(json.loads((tmp_path / "stats.json").read_text(encoding="utf-8"))["types"]) == [
        "Restaurant",
        "CafeOrCoffeeShop",
    ]


def test_stats_count_first_empty_page_and_contiguous_runs():
    stats = DatasetStats()
    stats.add(replace(BASE, page_url=""))
    stats.add(SECOND)
    stats.add(SECOND)
    assert stats.to_dict()["pages"] == 2


def test_stats_count_coordinate_properties_for_each_record():
    stats = DatasetStats()
    stats.add(replace(BASE, latitude=0.0, longitude=2.5))
    stats.add(SECOND)
    stats.add(SECOND)
    assert stats.to_dict()["coordinates"] == {"null_island": 2, "whole_degrees": 2}


def test_stats_break_equal_count_ties_by_label(tmp_path):
    alpha = replace(BASE, types=("Alpha",), languages=("a",))
    zoo = replace(BASE, types=("Zoo",), languages=("z",))
    write_dataset([zoo, alpha], tmp_path, SOURCES)
    stats = json.loads((tmp_path / "stats.json").read_text(encoding="utf-8"))
    assert list(stats["types"]) == ["Alpha", "Zoo"]
    assert list(stats["languages"]) == ["a", "z"]


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


def test_card_reports_the_record_count_the_size_band_and_condensed_provenance(tmp_path):
    write_dataset([BASE] * 1500, tmp_path, SOURCES, shard_size=1000)
    card = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "1,500 geolocated text records" in card
    assert "size_categories:\n- 1K<n<10K\n" in card
    assert "## Parts read" not in card
    assert SOURCES[0] not in card
    assert "## Dataset statistics" in card
    assert "| Published records | 1,500 |" in card
    assert "| Words in name, description, and address | 4,500 |" in card


def test_card_renders_optional_input_stats_as_dashes(tmp_path):
    write_dataset([BASE, SECOND], tmp_path, SOURCES)
    card = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "| Published records | 2 |" in card
    assert "| Contiguous page runs represented | 2 |" in card
    assert "| Hosts represented | 2 |" in card
    assert "| Records with text | 2 |" in card
    assert "| Words in name, description, and address | 7 |" in card
    assert "| Characters in name, description, and address | 33 |" in card
    assert "| Records with a schema.org type | 2 |" in card
    assert "| Distinct schema.org type labels | 2 |" in card
    assert "| Input records before host-local deduplication | — |" in card
    assert "| Input distinct host-local locations | — |" in card


def test_card_renders_dashes_for_an_incomplete_stats_section(tmp_path):
    write_card(tmp_path, 0, [], CardOptions(stats={"text": None}))
    card = (tmp_path / CARD_NAME).read_text(encoding="utf-8")
    assert "| Published records | 0 |" in card
    assert "| Words in name, description, and address | — |" in card


def test_card_uses_stats_records_when_present(tmp_path):
    write_card(tmp_path, 7, [], CardOptions(stats={"records": 8}))
    card = (tmp_path / CARD_NAME).read_text(encoding="utf-8")
    assert "| Published records | 8 |" in card


def test_card_falls_back_to_written_records_when_stats_omit_records(tmp_path):
    write_card(tmp_path, 7, [], CardOptions(stats={"text": {}}))
    card = (tmp_path / CARD_NAME).read_text(encoding="utf-8")
    assert "| Published records | 7 |" in card


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
    first = part_directory(
        tmp_path,
        "part_0",
        [BASE],
        {"records": 3, "hosts": 1, "duplication": {"distinct_places": 2}},
    )
    second = part_directory(
        tmp_path,
        "part_7",
        [BASE, replace(BASE, name="Two")],
        {"records": 5, "hosts": 2, "duplication": {"distinct_places": 4}},
    )
    out = tmp_path / "dataset"

    manifest = assemble([first, second], SOURCES, out)

    assert manifest == {
        "parts": 2,
        "records": 3,
        "shards": ["part-00000.jsonl.gz", "part-00001.jsonl.gz"],
        "card": "README.md",
        "stats": "stats.json",
    }
    assert [len(read_shard(out, name)) for name in manifest["shards"]] == [1, 2]
    assert json.loads((out / "profile.json").read_text(encoding="utf-8")) == {
        "records": 8,
        "hosts": 3,
        "duplication": {"distinct_places": 6},
    }
    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    assert stats["records"] == 3
    assert stats["input"] == {"records": 8, "distinct_places": 6}
    card = (out / "README.md").read_text(encoding="utf-8")
    assert "3 geolocated text records" in card
    assert "| Input records before host-local deduplication | 8 |" in card
    assert "| Input distinct host-local locations | 6 |" in card


def test_assemble_needs_no_parts_at_all(tmp_path):
    out = tmp_path / "dataset"
    assert assemble([], [], out) == {
        "parts": 0,
        "records": 0,
        "shards": [],
        "card": "README.md",
        "stats": "stats.json",
    }
    assert json.loads((out / "profile.json").read_text(encoding="utf-8")) == {}


def test_writes_into_a_directory_that_already_holds_a_dataset(tmp_path):
    write_dataset([BASE, SECOND], tmp_path, SOURCES, shard_size=1)
    manifest = write_dataset([BASE, replace(BASE, name="Two")], tmp_path, SOURCES)
    assert manifest["records"] == 2
    assert len(read_shard(tmp_path, "part-00000.jsonl.gz")) == 2
    assert not (tmp_path / "data" / "part-00001.jsonl.gz").exists()


def test_assembles_into_a_directory_that_already_holds_a_dataset(tmp_path):
    part = part_directory(tmp_path, "part_0", [BASE], {"records": 1})
    out = tmp_path / "dataset"
    assemble([part], SOURCES, out)
    assert assemble([part], SOURCES, out)["records"] == 1


def test_card_has_no_map_section_by_default(tmp_path):
    write_dataset([BASE], tmp_path, SOURCES)
    card = (tmp_path / CARD_NAME).read_text(encoding="utf-8")
    assert "Where the records are" not in card
    assert "Type distribution" not in card
    assert "XXXX" not in card


def test_card_shows_the_map_when_one_is_named(tmp_path):
    part = part_directory(tmp_path, "part_0", [BASE], {"records": 1, "duplication": {}})
    out = tmp_path / "dataset"
    assemble([part], SOURCES, out, MAP_NAME, TYPES_NAME)
    card = (out / CARD_NAME).read_text(encoding="utf-8")
    assert "## Where the records are" in card
    assert f"![Density of the records over the world]({MAP_NAME})" in card
    assert "## Type distribution" in card
    assert f"![Distribution of schema.org types]({TYPES_NAME})" in card
    assert card.index("Where the records are") < card.index("Type distribution")


def test_write_dataset_uses_the_lowercase_hub_data_directory(monkeypatch, tmp_path):
    original_mkdir = Path.mkdir
    created = []

    def remember(path, *args, **kwargs):
        created.append(path.name)
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", remember)
    write_dataset([], tmp_path, SOURCES)
    assert created[-1] == "data"
    assert "DATA" not in created


def test_data_directory_reuses_the_directory_and_removes_old_shards(monkeypatch, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    stale = data / "part-00000.jsonl.gz"
    unrelated = data / "notes.jsonl.gz"
    stale.touch()
    unrelated.touch()
    original_glob = Path.glob
    patterns = []

    def remember_glob(path, pattern):
        patterns.append(pattern)
        return original_glob(path, pattern)

    monkeypatch.setattr(Path, "glob", remember_glob)
    assert _data_directory(tmp_path) == data
    assert patterns == ["part-*.jsonl.gz"]
    assert not stale.exists()
    assert unrelated.exists()


def test_assemble_reads_lowercase_part_data_directories_and_writes_one(tmp_path, monkeypatch):
    part = part_directory(tmp_path, "part_0", [BASE], {"records": 1})
    output = tmp_path / "dataset"
    original_mkdir = Path.mkdir
    original_glob = Path.glob
    created = []
    searched = []

    def remember_mkdir(path, *args, **kwargs):
        created.append(path.name)
        return original_mkdir(path, *args, **kwargs)

    def remember_glob(path, pattern):
        if path == part / "data":
            searched.append((path.name, pattern))
        return original_glob(path, pattern)

    monkeypatch.setattr(Path, "mkdir", remember_mkdir)
    monkeypatch.setattr(Path, "glob", remember_glob)
    assemble([part], SOURCES, output)
    assert created[-1] == "data"
    assert "DATA" not in created
    assert searched == [("data", "*.jsonl.gz")]


def test_assemble_reads_shards_as_utf8(tmp_path, monkeypatch):
    part = part_directory(tmp_path, "part_0", [replace(BASE, name="Café")], {"records": 1})
    opened = []
    original_open = gzip.open

    def remember_encoding(*args, **kwargs):
        opened.append(kwargs.get("encoding"))
        return original_open(*args, **kwargs)

    monkeypatch.setattr("wdcgeo.dataset.gzip.open", remember_encoding)
    assemble([part], SOURCES, tmp_path / "dataset")
    assert opened == ["utf-8"]

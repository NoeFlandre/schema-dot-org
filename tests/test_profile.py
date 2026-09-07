from dataclasses import replace

from wdcgeo.extract import GeoText
from wdcgeo.profile import TOP_N, profile

PAGE = "http://example.com/p/1"
BUCKETS = {"<=20": 0, "<=50": 0, "<=100": 0, "<=250": 0, "<=1000": 0, ">1000": 0}


BASE = GeoText(
    page_url=PAGE,
    host="example.com",
    latitude=48.5,
    longitude=2.5,
    types=(),
    name=None,
    description=None,
    address=None,
    text_properties=(),
    languages=(),
)


def record(**overrides):
    return replace(BASE, **overrides)


def test_profiles_an_empty_stream_into_the_full_schema():
    assert profile([]) == {
        "records": 0,
        "pages": 0,
        "hosts": 0,
        "top_hosts": {},
        "top_level_domains": {},
        "types": {},
        "records_without_type": 0,
        "text_properties": {},
        "text": {
            "name": {"records": 0, "characters": 0, "buckets": BUCKETS},
            "description": {"records": 0, "characters": 0, "buckets": BUCKETS},
            "address": {"records": 0, "characters": 0, "buckets": BUCKETS},
            "any": 0,
            "all": 0,
        },
        "languages": {},
        "records_without_language": 0,
        "coordinates": {"null_island": 0, "whole_degrees": 0},
        "duplication": {"consecutive_repeats": 0, "distinct_places": 0},
        "grid": {},
    }


def test_counts_records_and_the_pages_they_come_from():
    other = "http://example.com/p/2"
    got = profile([record(), record(), record(page_url=other), record()])
    assert (got["records"], got["pages"]) == (4, 3)


def test_counts_hosts_and_top_level_domains():
    got = profile(
        [
            record(host="a.example.com"),
            record(host="a.example.com"),
            record(host="b.example.org"),
        ]
    )
    assert got["hosts"] == 2
    assert got["top_hosts"] == {"a.example.com": 2, "b.example.org": 1}
    assert got["top_level_domains"] == {"com": 2, "org": 1}


def test_counts_types_and_records_that_have_none():
    got = profile(
        [
            record(types=("LocalBusiness", "Restaurant")),
            record(),
            record(types=("Restaurant",)),
            record(),
        ]
    )
    assert got["types"] == {"Restaurant": 2, "LocalBusiness": 1}
    assert got["records_without_type"] == 2


def test_counts_the_literal_properties_found_next_to_coordinates():
    got = profile(
        [
            record(text_properties=("name", "telephone")),
            record(text_properties=("name",)),
        ]
    )
    assert got["text_properties"] == {"name": 2, "telephone": 1}


def test_counts_text_coverage_per_field_and_in_combination():
    got = profile(
        [
            record(name="Cafe"),
            record(name="Cafe", description="Nice"),
            record(name="Cafe", description="Nice", address="Paris"),
            record(),
        ]
    )
    assert got["text"]["name"]["records"] == 3
    assert got["text"]["description"]["records"] == 2
    assert got["text"]["address"]["records"] == 1
    assert got["text"]["any"] == 3
    assert got["text"]["all"] == 1


def test_bucketises_and_totals_text_lengths():
    lengths = [20, 21, 50, 51, 100, 101, 250, 251, 1000, 1001]
    got = profile([record(description="x" * length) for length in lengths])
    assert got["text"]["description"]["buckets"] == {
        "<=20": 1,
        "<=50": 2,
        "<=100": 2,
        "<=250": 2,
        "<=1000": 2,
        ">1000": 1,
    }
    assert got["text"]["description"]["characters"] == sum(lengths)
    assert got["text"]["name"]["buckets"] == BUCKETS


def test_counts_language_tags_and_records_without_any():
    got = profile(
        [
            record(languages=("en", "fr")),
            record(),
            record(languages=("en",)),
            record(),
        ]
    )
    assert got["languages"] == {"en": 2, "fr": 1}
    assert got["records_without_language"] == 2


def test_bins_coordinates_into_ten_degree_grid_cells():
    got = profile(
        [
            record(latitude=48.5, longitude=2.5),
            record(latitude=41.0, longitude=9.9),
            record(latitude=-0.12, longitude=-0.12),
            record(latitude=-90.0, longitude=180.0),
        ]
    )
    assert got["grid"] == {"40,0": 2, "-10,-10": 1, "-90,180": 1}


def test_counts_suspicious_coordinates():
    got = profile(
        [
            record(latitude=0.0, longitude=0.0),
            record(latitude=48.0, longitude=2.0),
            record(latitude=48.5, longitude=2.5),
            record(latitude=0.0, longitude=2.0),
            record(latitude=0.0, longitude=3.0),
            record(latitude=48.0, longitude=2.5),
        ]
    )
    assert got["coordinates"] == {"null_island": 1, "whole_degrees": 4}


def test_keeps_only_the_top_entries_of_every_ranking():
    many = [
        record(
            host=f"h{index}.tld{index}",
            types=(f"Type{index}",),
            text_properties=(f"prop{index}",),
            languages=(f"lang{index}",),
            latitude=float(-80 + (index % 18) * 10),
            longitude=float(-180 + index * 10),
        )
        for index in range(TOP_N + 5)
    ]
    got = profile(many)
    ranked = ["top_hosts", "top_level_domains", "types", "text_properties", "languages", "grid"]
    assert [len(got[key]) for key in ranked] == [TOP_N] * len(ranked)
    assert got["hosts"] == TOP_N + 5


def test_ranks_by_frequency_not_by_first_appearance():
    got = profile([record(host="rare.example.com"), *[record(host="common.example.com")] * 2])
    assert list(got["top_hosts"]) == ["common.example.com", "rare.example.com"]


def test_counts_records_that_repeat_the_record_before_them():
    got = profile(
        [
            record(name="Cafe"),
            record(name="Cafe"),
            record(name="Cafe"),
            record(name="Other"),
            record(name="Cafe"),
        ]
    )
    assert got["duplication"]["consecutive_repeats"] == 2


def test_a_repeat_needs_the_same_host_and_the_same_coordinates():
    got = profile(
        [
            record(name="Cafe"),
            record(name="Cafe", host="other.example.com"),
            record(name="Cafe", host="other.example.com", latitude=1.0),
        ]
    )
    assert got["duplication"]["consecutive_repeats"] == 0


def test_counts_distinct_places_within_each_host():
    got = profile(
        [
            record(name="Cafe"),
            record(name="Cafe", page_url="http://example.com/p/2"),
            record(name="Cafe", latitude=1.0),
            record(name="Other"),
            record(name="Cafe", host="other.example.com"),
        ]
    )
    assert got["records"] == 5
    assert got["duplication"]["distinct_places"] == 4

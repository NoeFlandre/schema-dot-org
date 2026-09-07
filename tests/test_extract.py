import pytest

from wdcgeo.extract import GeoText, geolocated_texts
from wdcgeo.quads import parse_quads

PAGE = "http://www.cafe-zero.fr/venues/1"
OTHER_PAGE = "https://guide.example.org/p/9"
S = "http://schema.org/"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def line(subject, predicate, obj, page=PAGE):
    return f"{subject} <{predicate}> {obj} <{page}> ."


def records(*lines):
    return list(geolocated_texts(parse_quads(lines)))


def restaurant_page(latitude='"48.8584"', longitude='"2.2945"', page=PAGE):
    return [
        line("_:place", RDF_TYPE, f"<{S}Restaurant>", page),
        line("_:place", f"{S}name", '"Cafe Zero"', page),
        line("_:place", f"{S}description", '"Coffee near the tower"', page),
        line("_:place", f"{S}geo", "_:geo", page),
        line("_:geo", RDF_TYPE, f"<{S}GeoCoordinates>", page),
        line("_:geo", f"{S}latitude", latitude, page),
        line("_:geo", f"{S}longitude", longitude, page),
    ]


def test_extracts_one_record_per_geolocated_entity():
    assert records(*restaurant_page()) == [
        GeoText(
            page_url=PAGE,
            host="www.cafe-zero.fr",
            latitude=48.8584,
            longitude=2.2945,
            types=("Restaurant",),
            name="Cafe Zero",
            description="Coffee near the tower",
            address=None,
            text_properties=("description", "name"),
            languages=(),
        )
    ]


def test_reads_class_scoped_microdata_predicates():
    got = records(
        line("_:place", f"{S}Restaurant/name", '"Cafe Zero"'),
        line("_:place", f"{S}Restaurant/geo", "_:geo"),
        line("_:geo", f"{S}GeoCoordinates/latitude", '"48.0"'),
        line("_:geo", f"{S}GeoCoordinates/longitude", '"2.0"'),
    )
    assert [(r.name, r.latitude, r.longitude) for r in got] == [("Cafe Zero", 48.0, 2.0)]


def test_infers_types_from_class_scoped_predicates_without_a_type_quad():
    got = records(
        line("_:place", f"{S}Restaurant/name", '"Cafe Zero"'),
        line("_:place", f"{S}Restaurant/geo", "_:geo"),
        line("_:geo", f"{S}GeoCoordinates/latitude", '"48.0"'),
        line("_:geo", f"{S}GeoCoordinates/longitude", '"2.0"'),
    )
    assert got[0].types == ("Restaurant",)


@pytest.mark.parametrize(
    "vocabulary",
    [
        "http://schema.org/",
        "https://schema.org/",
        "http://www.schema.org/",
        "https://www.schema.org/",
    ],
)
def test_accepts_every_schema_org_vocabulary_spelling(vocabulary):
    got = records(
        line("_:place", f"{vocabulary}name", '"Cafe Zero"'),
        line("_:place", f"{vocabulary}geo", "_:geo"),
        line("_:geo", f"{vocabulary}latitude", '"48.0"'),
        line("_:geo", f"{vocabulary}longitude", '"2.0"'),
    )
    assert [(r.name, r.latitude) for r in got] == [("Cafe Zero", 48.0)]


def test_reads_coordinates_placed_directly_on_the_entity():
    got = records(
        line("_:place", RDF_TYPE, f"<{S}Hotel>"),
        line("_:place", f"{S}name", '"Hotel Nord"'),
        line("_:place", f"{S}latitude", '"51.5"'),
        line("_:place", f"{S}longitude", '"-0.12"'),
    )
    assert [(r.name, r.types, r.latitude, r.longitude) for r in got] == [
        ("Hotel Nord", ("Hotel",), 51.5, -0.12)
    ]


def test_uses_iri_subjects_as_well_as_blank_nodes():
    got = records(
        line("<http://www.cafe-zero.fr/#place>", f"{S}name", '"Cafe Zero"'),
        line("<http://www.cafe-zero.fr/#place>", f"{S}geo", "<http://www.cafe-zero.fr/#geo>"),
        line("<http://www.cafe-zero.fr/#geo>", f"{S}latitude", '"48.0"'),
        line("<http://www.cafe-zero.fr/#geo>", f"{S}longitude", '"2.0"'),
    )
    assert [r.name for r in got] == ["Cafe Zero"]


def test_reads_datatyped_coordinate_literals():
    xsd = "http://www.w3.org/2001/XMLSchema#double"
    got = records(*restaurant_page(latitude=f'"48.5"^^<{xsd}>', longitude=f'"2.5"^^<{xsd}>'))
    assert [(r.latitude, r.longitude) for r in got] == [(48.5, 2.5)]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('"48.8584"', 48.8584),
        ('"  48.8584  "', 48.8584),
        ('"48,8584"', 48.8584),
        ('"+48.8584"', 48.8584),
        ('"-48.8584"', -48.8584),
        ('"−48.8584"', -48.8584),  # noqa: RUF001 - U+2212 minus sign
        ('"48.8584°"', 48.8584),
        ('"48.8584 N"', 48.8584),
        ('"48.8584 S"', -48.8584),
        ('"48.8584n"', 48.8584),
        ('"48.8584s"', -48.8584),
        ('"0"', 0.0),
        ('"90"', 90.0),
        ('"-90"', -90.0),
    ],
)
def test_parses_messy_latitude_spellings(raw, expected):
    got = records(*restaurant_page(latitude=raw))
    assert [r.latitude for r in got] == [expected]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [('"2.2945 E"', 2.2945), ('"2.2945 W"', -2.2945), ('"180"', 180.0), ('"-180"', -180.0)],
)
def test_parses_messy_longitude_spellings(raw, expected):
    got = records(*restaurant_page(longitude=raw))
    assert [r.longitude for r in got] == [expected]


@pytest.mark.parametrize(
    "raw",
    [
        '""',
        '"   "',
        '"north"',
        '"48.8584.1"',
        '"1,234.5"',
        '"48,85,84"',
        '"NaN"',
        '"inf"',
        '"-inf"',
        '"90.1"',
        '"-90.1"',
        '"1e3"',
        '"N"',
    ],
)
def test_drops_entities_whose_latitude_is_unusable(raw):
    assert records(*restaurant_page(latitude=raw)) == []


@pytest.mark.parametrize("raw", ['"180.1"', '"-180.1"', '"east"'])
def test_drops_entities_whose_longitude_is_unusable(raw):
    assert records(*restaurant_page(longitude=raw)) == []


def test_uses_the_first_usable_coordinate_when_several_are_present():
    got = records(
        *restaurant_page(),
        line("_:geo", f"{S}latitude", '"broken"'),
        line("_:geo", f"{S}latitude", '"49.0"'),
    )
    assert [r.latitude for r in got] == [48.8584]


def test_falls_back_to_a_later_usable_coordinate():
    got = records(*restaurant_page(latitude='"broken"'), line("_:geo", f"{S}latitude", '"49.0"'))
    assert [r.latitude for r in got] == [49.0]


def test_keeps_null_island_coordinates_for_the_profiler_to_report():
    got = records(*restaurant_page(latitude='"0"', longitude='"0.0"'))
    assert [(r.latitude, r.longitude) for r in got] == [(0.0, 0.0)]


def test_requires_both_coordinates():
    without_longitude = [q for q in restaurant_page() if "longitude" not in q]
    assert records(*without_longitude) == []


def test_assembles_a_linked_postal_address_in_a_stable_order():
    got = records(
        *restaurant_page(),
        line("_:place", f"{S}address", "_:addr"),
        line("_:addr", RDF_TYPE, f"<{S}PostalAddress>"),
        line("_:addr", f"{S}addressCountry", '"FR"'),
        line("_:addr", f"{S}postalCode", '"75007"'),
        line("_:addr", f"{S}addressLocality", '"Paris"'),
        line("_:addr", f"{S}streetAddress", '"5 Avenue Anatole France"'),
    )
    assert [r.address for r in got] == ["5 Avenue Anatole France, Paris, 75007, FR"]


def test_prefers_a_literal_address_over_a_linked_one():
    got = records(
        *restaurant_page(),
        line("_:place", f"{S}address", '"5 Avenue Anatole France, Paris"'),
        line("_:place", f"{S}address", "_:addr"),
        line("_:addr", f"{S}addressLocality", '"Paris"'),
    )
    assert [r.address for r in got] == ["5 Avenue Anatole France, Paris"]


def test_falls_back_to_the_linked_address_when_the_literal_one_is_blank():
    got = records(
        *restaurant_page(),
        line("_:place", f"{S}address", '"  "'),
        line("_:place", f"{S}address", "_:addr"),
        line("_:addr", f"{S}addressLocality", '"Paris"'),
    )
    assert [r.address for r in got] == ["Paris"]


def test_reports_no_address_when_the_linked_node_has_no_usable_parts():
    got = records(
        *restaurant_page(),
        line("_:place", f"{S}address", "_:addr"),
        line("_:addr", RDF_TYPE, f"<{S}PostalAddress>"),
        line("_:addr", f"{S}telephone", '"+33 1 23 45 67 89"'),
    )
    assert [r.address for r in got] == [None]


def test_collapses_whitespace_and_ignores_blank_text():
    got = records(
        line("_:place", f"{S}name", '"   "'),
        line("_:place", f"{S}name", '"  Cafe\\n\\tZero  "'),
        line("_:place", f"{S}description", '"   "'),
        line("_:place", f"{S}latitude", '"48.0"'),
        line("_:place", f"{S}longitude", '"2.0"'),
    )
    assert [(r.name, r.description) for r in got] == [("Cafe Zero", None)]


def test_collects_the_language_tags_of_the_text_it_keeps():
    got = records(
        line("_:place", f"{S}name", '"Le Cafe"@fr'),
        line("_:place", f"{S}description", '"Un cafe"@fr'),
        line("_:place", f"{S}address", '"Paris"@en'),
        line("_:place", f"{S}latitude", '"48.0"'),
        line("_:place", f"{S}longitude", '"2.0"'),
    )
    assert [r.languages for r in got] == [("en", "fr")]


def test_lists_every_literal_property_of_the_located_entity():
    got = records(
        *restaurant_page(),
        line("_:place", f"{S}telephone", '"+33 1 23 45 67 89"'),
        line("_:place", f"{S}priceRange", '"$$"'),
        line("_:place", f"{S}review", "_:review"),
        line("_:place", f"{S}keywords", '"   "'),
    )
    assert got[0].text_properties == ("description", "name", "priceRange", "telephone")


def test_sorts_and_deduplicates_types():
    got = records(
        *restaurant_page(),
        line("_:place", RDF_TYPE, f"<{S}LocalBusiness>"),
        line("_:place", RDF_TYPE, f"<{S}Restaurant>"),
    )
    assert got[0].types == ("LocalBusiness", "Restaurant")


def test_ignores_terms_outside_the_schema_org_vocabulary():
    got = records(
        *restaurant_page(),
        line("_:place", RDF_TYPE, "<http://xmlns.com/foaf/0.1/Agent>"),
        line("_:place", "http://ogp.me/ns#title", '"Open Graph title"'),
        line("_:place", RDF_TYPE, '"not an iri"'),
        line("_:place", f"{S}", '"empty local name"'),
    )
    assert got[0].types == ("Restaurant",)
    assert got[0].text_properties == ("description", "name")


def test_ignores_a_geo_link_that_points_at_a_literal():
    got = records(
        line("_:place", f"{S}name", '"Cafe Zero"'),
        line("_:place", f"{S}geo", '"48.0, 2.0"'),
        line("_:place", f"{S}latitude", '"48.0"'),
        line("_:place", f"{S}longitude", '"2.0"'),
    )
    assert [r.name for r in got] == ["Cafe Zero"]


def test_emits_one_record_per_geo_node_on_a_page():
    got = records(
        *restaurant_page(),
        line("_:place2", f"{S}name", '"Cafe Un"'),
        line("_:place2", f"{S}geo", "_:geo2"),
        line("_:geo2", f"{S}latitude", '"49.0"'),
        line("_:geo2", f"{S}longitude", '"3.0"'),
    )
    assert [(r.name, r.latitude) for r in got] == [("Cafe Zero", 48.8584), ("Cafe Un", 49.0)]


def test_keeps_pages_apart():
    got = records(*restaurant_page(), *restaurant_page(latitude='"49.0"', page=OTHER_PAGE))
    assert [(r.page_url, r.host, r.latitude) for r in got] == [
        (PAGE, "www.cafe-zero.fr", 48.8584),
        (OTHER_PAGE, "guide.example.org", 49.0),
    ]


def test_treats_each_contiguous_run_of_a_page_as_its_own_group():
    interleaved = [
        *restaurant_page(),
        *restaurant_page(latitude='"49.0"', page=OTHER_PAGE),
        *restaurant_page(latitude='"50.0"'),
    ]
    assert [r.latitude for r in geolocated_texts(parse_quads(interleaved))] == [48.8584, 49.0, 50.0]


def test_lowercases_hosts():
    got = records(*restaurant_page(page="http://WWW.Cafe-Zero.FR/venues/1"))
    assert [r.host for r in got] == ["www.cafe-zero.fr"]


@pytest.mark.parametrize("page", ["not a url", "urn:isbn:0451450523", "http:///venues/1"])
def test_drops_pages_without_a_host(page):
    assert records(*restaurant_page(page=page)) == []


def test_reports_empty_text_for_an_entity_that_only_carries_the_geo_link():
    got = records(
        line("_:place", RDF_TYPE, f"<{S}Place>"),
        line("_:place", f"{S}geo", "_:geo"),
        line("_:geo", f"{S}latitude", '"48.0"'),
        line("_:geo", f"{S}longitude", '"2.0"'),
    )
    assert got == [
        GeoText(
            page_url=PAGE,
            host="www.cafe-zero.fr",
            latitude=48.0,
            longitude=2.0,
            types=("Place",),
            name=None,
            description=None,
            address=None,
            text_properties=(),
            languages=(),
        )
    ]


def test_yields_nothing_for_a_page_without_coordinates():
    assert records(line("_:place", f"{S}name", '"Cafe Zero"')) == []


def test_yields_nothing_for_no_quads():
    assert records() == []

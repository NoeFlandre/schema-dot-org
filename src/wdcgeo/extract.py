"""Turn a stream of Web Data Commons quads into geolocated text records.

A record pairs one usable coordinate pair with the text found on the entity it
belongs to. Getting there means coping with how schema.org is really published:

* coordinates hang off a ``GeoCoordinates`` node reached through ``geo``, or
  sit straight on the place itself;
* property IRIs come in the JSON-LD spelling (``schema.org/name``) and in the
  class-scoped Microdata spelling (``schema.org/Restaurant/name``), over four
  spellings of the vocabulary itself;
* coordinate literals carry decimal commas, degree signs, hemisphere letters,
  values out of range and values that are not numbers at all (a comma is read
  as a decimal separator unconditionally: no float spelling contains one, so a
  value that already reads as a number cannot be spoiled by the substitution);
* addresses are either one literal or a linked ``PostalAddress``.

Quads are consumed lazily, one page at a time, so a whole dump can be streamed
in constant memory. A page is a contiguous run of quads sharing a provenance
graph, which is how Web Data Commons groups its dumps; a page split across
non-adjacent runs is treated as two pages.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from wdcgeo.quads import BlankNode, Iri, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from wdcgeo.quads import Quad

SCHEMA_VOCABULARIES = (
    "http://schema.org/",
    "https://schema.org/",
    "http://www.schema.org/",
    "https://www.schema.org/",
)
"""Every spelling of the schema.org namespace seen in the corpus."""

ADDRESS_PARTS = (
    "streetAddress",
    "addressLocality",
    "addressRegion",
    "postalCode",
    "addressCountry",
)
"""The order a linked ``PostalAddress`` is flattened in."""

LATITUDE_LIMIT = 90.0
LONGITUDE_LIMIT = 180.0

_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_HEMISPHERES = {"N": 1.0, "E": 1.0, "S": -1.0, "W": -1.0}
_MINUS_SIGN = "−"  # noqa: RUF001 - U+2212, published instead of "-" by some sites
_DEGREE_SIGN = "°"

Node = Iri | BlankNode


@dataclass(frozen=True, slots=True)
class GeoText:
    """Text found next to a coordinate pair on one web page."""

    page_url: str
    host: str
    latitude: float
    longitude: float
    types: tuple[str, ...]
    name: str | None
    description: str | None
    address: str | None
    text_properties: tuple[str, ...]
    languages: tuple[str, ...]


class _Page:
    """The statements of one page, indexed by subject."""

    def __init__(self, quads: Iterable[Quad]) -> None:
        self.literals: dict[Node, dict[str, list[Literal]]] = {}
        self.links: dict[Node, dict[str, Node]] = {}
        self.types: dict[Node, set[str]] = {}
        self.geo_parents: dict[Node, Node] = {}
        for quad in quads:
            self._add(quad)

    def _add(self, quad: Quad) -> None:
        if quad.predicate.value == _RDF_TYPE:
            if isinstance(quad.obj, Iri):
                self._add_type(quad.subject, _schema_name(quad.obj.value))
            return
        parsed = _schema_property(quad.predicate.value)
        if parsed is None:
            return
        name, class_name = parsed
        self._add_type(quad.subject, class_name)
        if isinstance(quad.obj, Literal):
            self.literals.setdefault(quad.subject, {}).setdefault(name, []).append(quad.obj)
            return
        self.links.setdefault(quad.subject, {}).setdefault(name, quad.obj)
        if name == "geo":
            self.geo_parents[quad.obj] = quad.subject

    def _add_type(self, subject: Node, name: str | None) -> None:
        if name is not None:
            self.types.setdefault(subject, set()).add(name)

    def values(self, node: Node, name: str) -> Sequence[Literal]:
        """Return the literals ``node`` carries for property ``name``."""
        return self.literals.get(node, {}).get(name, ())


class _Text:
    """Picks the first usable string per property, remembering language tags."""

    def __init__(self) -> None:
        self.languages: set[str] = set()

    def take(self, values: Sequence[Literal]) -> str | None:
        """Return the first non-blank value, recording its language tag."""
        for literal in values:
            cleaned = _clean(literal.value)
            if cleaned is None:
                continue
            if literal.language is not None:
                self.languages.add(literal.language)
            return cleaned
        return None


def _schema_property(iri: str) -> tuple[str, str | None] | None:
    """Split a schema.org property IRI into its property and owning class."""
    for vocabulary in SCHEMA_VOCABULARIES:
        if iri.startswith(vocabulary):
            class_name, _, name = iri[len(vocabulary) :].rpartition("/")
            return (name, class_name or None) if name else None
    return None


def _schema_name(iri: str) -> str | None:
    """Return the local name of a schema.org IRI, or ``None`` for other vocabularies."""
    parsed = _schema_property(iri)
    return None if parsed is None else parsed[0]


def _clean(text: str) -> str | None:
    """Collapse whitespace, returning ``None`` for text that carries nothing."""
    return " ".join(text.split()) or None


def _coordinate(text: str, limit: float) -> float | None:
    """Read one coordinate, or return ``None`` if it is not a usable number."""
    cleaned = text.strip().replace(_MINUS_SIGN, "-").replace(_DEGREE_SIGN, "")
    hemisphere = _HEMISPHERES.get(cleaned[-1:].upper())
    if hemisphere is not None:
        cleaned = cleaned[:-1].strip()
    cleaned = cleaned.replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if hemisphere is not None:
        value = hemisphere * abs(value)
    if not isfinite(value) or abs(value) > limit:
        return None
    return value


def _first_coordinate(values: Sequence[Literal], limit: float) -> float | None:
    for literal in values:
        value = _coordinate(literal.value, limit)
        if value is not None:
            return value
    return None


def _address(page: _Page, entity: Node, text: _Text) -> str | None:
    literal = text.take(page.values(entity, "address"))
    if literal is not None:
        return literal
    node = page.links.get(entity, {}).get("address")
    if node is None:
        return None
    parts = (text.take(page.values(node, part)) for part in ADDRESS_PARTS)
    return ", ".join(part for part in parts if part is not None) or None


def _text_properties(page: _Page, entity: Node) -> tuple[str, ...]:
    carried = page.literals.get(entity, {}).items()
    return tuple(sorted(name for name, values in carried if any(_clean(v.value) for v in values)))


def _page_records(quads: list[Quad]) -> Iterator[GeoText]:
    page_url = quads[0].graph.value
    host = urlsplit(page_url).hostname or None
    if host is None:
        return
    page = _Page(quads)
    for node in page.literals:
        latitude = _first_coordinate(page.values(node, "latitude"), LATITUDE_LIMIT)
        longitude = _first_coordinate(page.values(node, "longitude"), LONGITUDE_LIMIT)
        if latitude is None or longitude is None:
            continue
        entity = page.geo_parents.get(node, node)
        text = _Text()
        yield GeoText(
            page_url=page_url,
            host=host,
            latitude=latitude,
            longitude=longitude,
            types=tuple(sorted(page.types.get(entity, ()))),
            name=text.take(page.values(entity, "name")),
            description=text.take(page.values(entity, "description")),
            address=_address(page, entity, text),
            text_properties=_text_properties(page, entity),
            languages=tuple(sorted(text.languages)),
        )


def _pages(quads: Iterable[Quad]) -> Iterator[list[Quad]]:
    group: list[Quad] = []
    for quad in quads:
        if group and quad.graph != group[0].graph:
            yield group
            group = []
        group.append(quad)
    if group:
        yield group


def geolocated_texts(quads: Iterable[Quad]) -> Iterator[GeoText]:
    """Yield one :class:`GeoText` per geolocated entity, page by page."""
    for page in _pages(quads):
        yield from _page_records(page)


def deduplicate(records: Iterable[GeoText]) -> Iterator[GeoText]:
    """Drop records repeating a coordinate-and-name pair already seen on their host.

    Site-wide markup republishes one business on every page of its site, so the
    raw stream is mostly repetition. Records arrive grouped by host, so keeping
    only the places of the current host bounds what has to be remembered; a host
    that comes back later starts over.
    """
    host: str | None = None
    places: set[tuple[float, float, str | None]] = set()
    for record in records:
        if record.host != host:
            host = record.host
            places = set()
        place = (record.latitude, record.longitude, record.name)
        if place not in places:
            places.add(place)
            yield record

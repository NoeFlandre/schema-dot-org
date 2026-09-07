import pytest

from wdcgeo.quads import BlankNode, Iri, Literal, Quad, parse_line, parse_quads

PAGE = "http://example.com/venues/1"


def test_parses_an_all_iri_quad():
    line = f"<http://example.com/a> <http://schema.org/geo> <http://example.com/b> <{PAGE}> .\n"
    assert parse_line(line) == Quad(
        subject=Iri("http://example.com/a"),
        predicate=Iri("http://schema.org/geo"),
        obj=Iri("http://example.com/b"),
        graph=Iri(PAGE),
    )


def test_parses_blank_nodes_in_subject_and_object():
    line = f"_:node1 <http://schema.org/geo> _:node2 <{PAGE}> ."
    quad = parse_line(line)
    assert quad is not None
    assert quad.subject == BlankNode("node1")
    assert quad.obj == BlankNode("node2")


def test_parses_plain_literal():
    quad = parse_line(f'_:n <http://schema.org/name> "Cafe Zero" <{PAGE}> .')
    assert quad is not None
    assert quad.obj == Literal("Cafe Zero")
    assert quad.obj.language is None
    assert quad.obj.datatype is None


def test_parses_literal_with_language_tag():
    quad = parse_line(f'_:n <http://schema.org/name> "Le Cafe"@fr-FR <{PAGE}> .')
    assert quad is not None
    assert quad.obj == Literal("Le Cafe", language="fr-FR")


def test_parses_literal_with_datatype():
    line = (
        f'_:n <http://schema.org/latitude> "48.85"'
        f"^^<http://www.w3.org/2001/XMLSchema#double> <{PAGE}> ."
    )
    quad = parse_line(line)
    assert quad is not None
    assert quad.obj == Literal("48.85", datatype="http://www.w3.org/2001/XMLSchema#double")


@pytest.mark.parametrize(
    ("escaped", "decoded"),
    [
        (r"a\"b", 'a"b'),
        (r"a\\b", "a\\b"),
        (r"a\nb", "a\nb"),
        (r"a\rb", "a\rb"),
        (r"a\tb", "a\tb"),
        (r"a\bb", "a\bb"),
        (r"a\fb", "a\fb"),
        (r"aéb", "aéb"),
        (r"a\U0001F600b", "a\U0001f600b"),
    ],
)
def test_decodes_literal_escapes(escaped, decoded):
    quad = parse_line(f'_:n <http://schema.org/name> "{escaped}" <{PAGE}> .')
    assert quad is not None
    assert quad.obj == Literal(decoded)


def test_decodes_escapes_in_iri():
    quad = parse_line(rf"<http://example.com/a b> <http://schema.org/geo> _:n <{PAGE}> .")
    assert quad is not None
    assert quad.subject == Iri("http://example.com/a b")


def test_keeps_a_period_inside_a_literal():
    quad = parse_line(f'_:n <http://schema.org/name> "A. B ." <{PAGE}> .')
    assert quad is not None
    assert quad.obj == Literal("A. B .")


@pytest.mark.parametrize(
    "line",
    [
        "",
        "   ",
        "# a comment",
        f"<http://example.com/a> <http://schema.org/geo> _:n <{PAGE}>",  # no terminator
        f"<http://example.com/a> <http://schema.org/geo> _:n <{PAGE}> . junk",  # trailing junk
        "<http://example.com/a> <http://schema.org/geo> _:n .",  # no graph
        f"<http://example.com/a <http://schema.org/geo> _:n <{PAGE}> .",  # unterminated iri
        f'_:n <http://schema.org/name> "open <{PAGE}> .',  # unterminated literal
        f'"lit" <http://schema.org/geo> _:n <{PAGE}> .',  # literal subject
        f"_:n _:p _:n <{PAGE}> .",  # blank predicate
        f'_:n "p" _:n <{PAGE}> .',  # literal predicate
        "_:n <http://schema.org/geo> _:n _:g .",  # blank graph
        '_:n <http://schema.org/geo> _:n "g" .',  # literal graph
        rf'_:n <http://schema.org/name> "a\qb" <{PAGE}> .',  # unknown escape
        rf'_:n <http://schema.org/name> "a\u00zzb" <{PAGE}> .',  # bad unicode escape
        rf'_:n <http://schema.org/name> "trailing\\" <{PAGE}> ',  # no terminator after escape
        r'_:n <http://schema.org/name> "cut off\\' + "\n",  # truncated escape
        '_:n <http://schema.org/name> "a\\',  # backslash at end of line
        r'_:n <http://schema.org/name> "a\u00',  # unicode escape cut off by line end
        rf'_:n <http://schema.org/name> "a\u00" <{PAGE}> .',  # non-hex unicode escape
        f'_:n <http://schema.org/name> "x"@ <{PAGE}> .',  # empty language tag
        f'_:n <http://schema.org/name> "x"^^ <{PAGE}> .',  # datatype not an iri
        f'_:n <http://schema.org/name> "x"^ <{PAGE}> .',  # lone caret
        f"_:n <http://schema.org/geo> _: <{PAGE}> .",  # empty blank node label
        f"_ <http://schema.org/geo> _:n <{PAGE}> .",  # blank node without colon
    ],
)
def test_rejects_malformed_lines(line):
    assert parse_line(line) is None


def test_parse_quads_streams_valid_lines_and_skips_the_rest():
    lines = [
        f'_:n <http://schema.org/name> "one" <{PAGE}> .\n',
        "garbage\n",
        f'_:n <http://schema.org/name> "two" <{PAGE}> .\n',
    ]
    assert [quad.obj for quad in parse_quads(lines)] == [Literal("one"), Literal("two")]


@pytest.mark.parametrize("line", ["_:n", '_:n <http://schema.org/name> "x"@en'])
def test_rejects_a_line_that_ends_where_a_token_ends(line):
    assert parse_line(line) is None

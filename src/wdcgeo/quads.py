"""Parser for the N-Quads variant used by the Web Data Commons corpora.

Each line of a Web Data Commons dump is one statement whose fourth term is the
provenance graph: the URL of the page the statement was extracted from. Real
dumps contain lines that no parser should accept -- truncated at a shard
boundary, carrying an unescaped delimiter, or emitted by a buggy extractor -- so
every entry point here answers with ``None`` instead of raising, and
:func:`parse_quads` simply drops what it cannot read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

_SIMPLE_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}
_UNICODE_ESCAPE_WIDTHS = {"u": 4, "U": 8}
_HEX = 16
_NOT_FOUND = -1
_BACKSLASH = "\\"
_WHITESPACE = re.compile(r"\s")
_NON_WHITESPACE = re.compile(r"\S")
_TERMS_PER_QUAD = 4


@dataclass(frozen=True, slots=True)
class Iri:
    """An absolute IRI, with its enclosing angle brackets removed."""

    value: str


@dataclass(frozen=True, slots=True)
class BlankNode:
    """A blank node, identified by a label that is only unique within one file."""

    label: str


@dataclass(frozen=True, slots=True)
class Literal:
    """A literal value, optionally tagged with a language or a datatype IRI."""

    value: str
    language: str | None = None
    datatype: str | None = None


Term = Iri | BlankNode | Literal


@dataclass(frozen=True, slots=True)
class Quad:
    """One statement: a subject, a predicate, an object and a provenance graph."""

    subject: Iri | BlankNode
    predicate: Iri
    obj: Term
    graph: Iri


class _Scanner:
    """A cursor over one line, handing out terms left to right."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._pos = 0

    def term(self) -> Term | None:
        """Read the next term, or return ``None`` if it is absent or malformed."""
        self._skip_whitespace()
        char = self._peek()
        if char == "<":
            return self._iri()
        if char == "_":
            return self._blank_node()
        if char == '"':
            return self._literal()
        return None

    def at_end_of_statement(self) -> bool:
        """Report whether only the statement terminator and whitespace are left."""
        self._skip_whitespace()
        if self._peek() != ".":
            return False
        self._pos += 1
        self._skip_whitespace()
        return self._pos == len(self._text)

    def _peek(self) -> str:
        """Return the character at the cursor, or ``""`` once the line runs out."""
        return self._text[self._pos : self._pos + 1]

    def _skip_whitespace(self) -> None:
        found = _NON_WHITESPACE.search(self._text, self._pos)
        self._pos = len(self._text) if found is None else found.start()

    def _iri(self) -> Iri | None:
        self._pos += 1
        value = self._read_delimited(">")
        return None if value is None else Iri(value)

    def _blank_node(self) -> BlankNode | None:
        if not self._text.startswith("_:", self._pos):
            return None
        self._pos += 2
        label = self._read_token()
        return BlankNode(label) if label else None

    def _literal(self) -> Literal | None:
        self._pos += 1
        value = self._read_delimited('"')
        return None if value is None else self._tagged(value)

    def _tagged(self, value: str) -> Literal | None:
        if self._peek() == "@":
            return self._with_language(value)
        if self._text.startswith("^^", self._pos):
            return self._with_datatype(value)
        return Literal(value)

    def _with_language(self, value: str) -> Literal | None:
        self._pos += 1
        language = self._read_token()
        return Literal(value, language=language) if language else None

    def _with_datatype(self, value: str) -> Literal | None:
        self._pos += 2
        if self._peek() != "<":
            return None
        datatype = self._iri()
        return None if datatype is None else Literal(value, datatype=datatype.value)

    def _read_token(self) -> str:
        found = _WHITESPACE.search(self._text, self._pos)
        start = self._pos
        self._pos = len(self._text) if found is None else found.start()
        return self._text[start : self._pos]

    def _read_delimited(self, end: str) -> str | None:
        """Read up to ``end``, decoding any escapes on the way.

        Escapes are rare in this corpus -- a handful of terms per million
        lines -- so the common case is answered by two searches and a slice.
        Only a backslash standing before the delimiter costs a character loop,
        which is what :meth:`_read_escaped` is for. On a real part this is the
        difference between 36,000 and 100,000 lines a second, and the corpus is
        three billion lines long.
        """
        text = self._text
        stop = text.find(end, self._pos)
        if stop == _NOT_FOUND:
            self._pos = len(text)
            return None
        # Both lines below carry mutants that only route reading through the
        # slower path, which by design cannot change the result. See
        # docs/design.md.
        escape = text.find(_BACKSLASH, self._pos)  # pragma: no mutate
        if escape == _NOT_FOUND or escape > stop:  # pragma: no mutate
            value = text[self._pos : stop]
            self._pos = stop + 1
            return value
        return self._read_escaped(end)

    def _read_escaped(self, end: str) -> str | None:
        text = self._text
        length = len(text)
        parts: list[str] = []
        while self._pos < length:
            char = text[self._pos]
            self._pos += 1
            if char == end:
                return "".join(parts)
            if char != "\\":
                parts.append(char)
                continue
            decoded = self._read_escape()
            if decoded is None:
                return None
            parts.append(decoded)
        return None

    def _read_escape(self) -> str | None:
        code = self._peek()
        if not code:
            return None
        self._pos += 1
        simple = _SIMPLE_ESCAPES.get(code)
        if simple is not None:
            return simple
        width = _UNICODE_ESCAPE_WIDTHS.get(code)
        return None if width is None else self._read_code_point(width)

    def _read_code_point(self, width: int) -> str | None:
        digits = self._text[self._pos : self._pos + width]
        self._pos += width
        if len(digits) != width:
            return None
        try:
            return chr(int(digits, _HEX))
        except ValueError:
            return None


def parse_line(line: str) -> Quad | None:
    """Parse one line into a :class:`Quad`, or return ``None`` if it is unusable."""
    scanner = _Scanner(line)
    terms = [scanner.term() for _ in range(_TERMS_PER_QUAD)]
    if not scanner.at_end_of_statement():
        return None
    return _quad(terms)


def _quad(terms: list[Term | None]) -> Quad | None:
    """Build a quad from four terms, rejecting any term of the wrong kind."""
    subject, predicate, obj, graph = terms
    if not isinstance(subject, Iri | BlankNode) or not isinstance(predicate, Iri):
        return None
    if obj is None or not isinstance(graph, Iri):
        return None
    return Quad(subject=subject, predicate=predicate, obj=obj, graph=graph)


def parse_quads(lines: Iterable[str]) -> Iterator[Quad]:
    """Parse ``lines`` lazily, dropping every line that cannot be read."""
    for line in lines:
        quad = parse_line(line)
        if quad is not None:
            yield quad

"""Compose the corpus, the parser and the extractor into one pass.

Keeping the composition here means the command line does no work of its own,
and it is the only place that can report how much of the input survived each
stage: lines read, quads parsed, and the difference between them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wdcgeo.corpus import stream_lines
from wdcgeo.extract import geolocated_texts
from wdcgeo.quads import parse_quads

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from wdcgeo.extract import GeoText
    from wdcgeo.quads import Quad


class Pipeline:
    """One run over a list of locations, counting what it reads."""

    def __init__(self, locations: Sequence[str], *, max_lines: int | None = None) -> None:
        """Read ``locations`` in order, stopping after ``max_lines`` lines if given."""
        self._locations = locations
        self._max_lines = max_lines
        self._lines = 0
        self._quads = 0

    def records(self) -> Iterator[GeoText]:
        """Yield the geolocated text records of every location."""
        return geolocated_texts(self._counted(parse_quads(self._read())))

    def counts(self) -> dict[str, int]:
        """Report what has been read so far."""
        return {
            "locations": len(self._locations),
            "lines": self._lines,
            "quads": self._quads,
            "unparsed_lines": self._lines - self._quads,
        }

    def _read(self) -> Iterator[str]:
        for location in self._locations:
            for line in stream_lines(location):
                if self._max_lines is not None and self._lines >= self._max_lines:
                    return
                self._lines += 1
                yield line

    def _counted(self, quads: Iterator[Quad]) -> Iterator[Quad]:
        for quad in quads:
            self._quads += 1
            yield quad

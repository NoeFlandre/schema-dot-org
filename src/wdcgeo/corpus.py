"""Locate and stream the parts of the published GeoCoordinates subset.

The 2024-12 subset is 237 gzipped parts of roughly 140 MB each -- 33 GB and
3.18 billion quads in total, more than fits on the disk of the machine that
usually wants to read it. So a part is never stored: it is streamed straight
from the mirror, decompressed on the way past, and handed over line by line.
Local paths work the same way, which is what the test suite and a cached run
use. Whether a location is compressed is decided by its ``.gz`` suffix, the
naming the mirror uses.
"""

from __future__ import annotations

import gzip
from contextlib import contextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import IO, TYPE_CHECKING
from urllib.request import urlopen

from wdcgeo import ENCODING

if TYPE_CHECKING:
    from collections.abc import Iterator

DEFAULT_BASE_URL = (
    "https://data.dws.informatik.uni-mannheim.de"
    "/structureddata/2024-12/quads/classspecific/GeoCoordinates"
)
"""Where the Web Data Commons 2024-12 GeoCoordinates subset is published."""

PART_COUNT = 237
"""How many parts that subset is split into."""

_URL_SCHEMES = ("http://", "https://")
_DECODE_ERRORS = "replace"


def part_url(index: int, base_url: str = DEFAULT_BASE_URL) -> str:
    """Return the URL of part ``index`` of the subset."""
    return f"{base_url}/part_{index}.gz"


@contextmanager
def _opened(location: str) -> Iterator[IO[bytes]]:
    if location.startswith(_URL_SCHEMES):
        with urlopen(location) as response:  # noqa: S310 - scheme checked above
            yield response
    else:
        with Path(location).open("rb") as handle:
            yield handle


def stream_lines(location: str) -> Iterator[str]:
    """Yield the lines of a part, from a URL or a path, gzipped or plain."""
    with _opened(location) as raw:
        stream = gzip.GzipFile(fileobj=raw) if location.endswith(".gz") else raw
        # The encoding is stated rather than inherited from the locale; see
        # tests/test_cli.py for the run that proves it. Mutating it away is
        # invisible in a UTF-8 environment, hence the pragma.
        text = TextIOWrapper(stream, encoding=ENCODING, errors=_DECODE_ERRORS)  # pragma: no mutate
        yield from text

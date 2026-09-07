"""Tools for mining geolocated text from the Web Data Commons schema.org corpus.

Every file this package reads or writes is UTF-8, whatever the locale of the
machine it runs on: the corpus is published as UTF-8, and a dataset that
travels has to be readable where it lands. Text file access goes through the
two helpers below so that the encoding is stated once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

ENCODING = "utf-8"


def read_text(path: Path) -> str:
    """Read a UTF-8 text file, whatever the locale says."""
    return path.read_text(encoding=ENCODING)  # pragma: no mutate


def write_text(path: Path, text: str) -> None:
    """Write a UTF-8 text file, whatever the locale says."""
    path.write_text(text, encoding=ENCODING)  # pragma: no mutate

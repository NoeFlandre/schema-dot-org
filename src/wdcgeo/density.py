"""Bin record coordinates onto an equirectangular grid.

A map of where the corpus actually is needs one number per patch of the world,
and thirteen million points are too many to draw one by one. So they are
counted into cells of a fixed size -- a quarter of a degree by default, giving
a 1440 by 720 grid -- and only populated cells are kept, because most of the
world has none.

Rows run north to south and columns west to east, which is the orientation an
image wants: cell (0, 0) is the north-west corner of the world. The poles and
the dateline fall exactly on a grid edge, so they are held inside the last
cell rather than one step outside it.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

CELLS_PER_DEGREE = 4
"""Cells per degree: a quarter-degree grid, about 28 km at the equator."""

_LATITUDE_SPAN = 180
_LONGITUDE_SPAN = 360


def grid_shape(cells_per_degree: int) -> tuple[int, int]:
    """Return the number of rows and columns at this resolution."""
    return (_LATITUDE_SPAN * cells_per_degree, _LONGITUDE_SPAN * cells_per_degree)


def cell(latitude: float, longitude: float, cells_per_degree: int) -> tuple[int, int]:
    """Return the row and column the given coordinates fall in."""
    rows, columns = grid_shape(cells_per_degree)
    row = int((90.0 - latitude) * cells_per_degree)
    column = int((longitude + 180.0) * cells_per_degree)
    return (min(row, rows - 1), min(column, columns - 1))


def density(
    points: Iterable[tuple[float, float]], cells_per_degree: int
) -> dict[tuple[int, int], int]:
    """Count how many of ``points`` fall in each populated cell."""
    counts: Counter[tuple[int, int]] = Counter()
    for latitude, longitude in points:
        counts[cell(latitude, longitude, cells_per_degree)] += 1
    return dict(counts)

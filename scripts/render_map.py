"""Render the records of a dataset as a density map.

Thirteen million points cannot be drawn one at a time, so `wdcgeo.density`
counts them into quarter-degree cells and this draws the cells. The scale is
logarithmic because the distribution is: one city block of Paris holds more
records than most countries.

Colour follows one rule -- magnitude takes a single hue, light to dark, never a
rainbow -- so the ramp is the blue sequential scale, and an empty cell keeps the
surface colour rather than taking the lightest step. No coastline is drawn: with
this many records the outlines are the data, and anything we drew on top would
be claiming a precision the corpus does not have.

    python scripts/render_map.py data/dataset/data/*.jsonl.gz --out data/dataset/map.png
"""

import argparse
import gzip
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm  # noqa: E402

from wdcgeo.density import CELLS_PER_DEGREE, density, grid_shape  # noqa: E402

# The blue sequential ramp, steps 100 to 700: one hue, light to dark.
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#52514e"
GRATICULE = "#e6e5e1"


def read_points(paths):
    """Yield the coordinates of every record in the given shards."""
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                yield (record["latitude"], record["longitude"])


def build_grid(paths, cells_per_degree):
    """Return a counts array and the number of records that went into it."""
    counts = density(read_points(paths), cells_per_degree)
    rows, columns = grid_shape(cells_per_degree)
    grid = np.zeros((rows, columns), dtype=np.int64)
    for (row, column), value in counts.items():
        grid[row, column] = value
    return grid, int(grid.sum())


def render(grid, records, out, cells_per_degree):
    """Draw the grid to ``out`` as a PNG."""
    figure, axes = plt.subplots(figsize=(16, 8.6), dpi=110)
    figure.patch.set_facecolor(SURFACE)
    axes.set_facecolor(SURFACE)

    for longitude in range(-180, 181, 30):
        axes.axvline(longitude, color=GRATICULE, linewidth=0.6, zorder=1)
    for latitude in range(-90, 91, 30):
        axes.axhline(latitude, color=GRATICULE, linewidth=0.6, zorder=1)

    colours = LinearSegmentedColormap.from_list("wdcgeo-blue", RAMP)
    colours.set_bad("none")  # an empty cell keeps the surface, and the graticule shows
    shown = np.ma.masked_equal(grid, 0)
    image = axes.imshow(
        shown,
        extent=(-180, 180, -90, 90),
        origin="upper",
        cmap=colours,
        norm=LogNorm(vmin=1, vmax=max(int(grid.max()), 2)),
        interpolation="nearest",
        zorder=2,
    )

    axes.set_xlim(-180, 180)
    axes.set_ylim(-90, 90)
    axes.set_xticks(range(-180, 181, 60))
    axes.set_yticks(range(-90, 91, 30))
    axes.set_xticklabels([f"{abs(v)}°{'' if v == 0 else 'E' if v > 0 else 'W'}" for v in range(-180, 181, 60)])
    axes.set_yticklabels([f"{abs(v)}°{'' if v == 0 else 'N' if v > 0 else 'S'}" for v in range(-90, 91, 30)])
    axes.tick_params(colors=MUTED, labelsize=9, length=0)
    for spine in axes.spines.values():
        spine.set_visible(False)

    cell_size = 1 / cells_per_degree
    axes.text(
        0,
        1.055,
        f"{records:,} geolocated text records from the Web Data Commons"
        " schema.org GeoCoordinates subset",
        transform=axes.transAxes,
        color=INK,
        fontsize=13.5,
        va="bottom",
    )
    axes.text(
        0,
        1.012,
        "Equirectangular projection. No coastline is drawn: the outlines are the data.",
        transform=axes.transAxes,
        color=MUTED,
        fontsize=9.5,
        va="bottom",
    )

    bar = figure.colorbar(image, ax=axes, fraction=0.022, pad=0.012, shrink=0.82)
    bar.outline.set_visible(False)
    bar.ax.tick_params(colors=MUTED, labelsize=9, length=0)
    bar.set_label(f"records per {cell_size:g}° cell", color=MUTED, fontsize=9.5)

    figure.tight_layout()
    figure.savefig(out, facecolor=SURFACE, bbox_inches="tight")
    plt.close(figure)


def main():
    """Render the shards named on the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("shards", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cells-per-degree", type=int, default=CELLS_PER_DEGREE)
    arguments = parser.parse_args()
    grid, records = build_grid(arguments.shards, arguments.cells_per_degree)
    render(grid, records, arguments.out, arguments.cells_per_degree)
    populated = int((grid > 0).sum())
    rows, columns = grid.shape
    print(
        json.dumps(
            {
                "records": records,
                "populated_cells": populated,
                "share_of_world": round(populated / (rows * columns), 4),
                "busiest_cell": int(grid.max()),
                "out": str(arguments.out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

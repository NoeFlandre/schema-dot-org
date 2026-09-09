"""Render the distribution of schema.org type assignments in a dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

TOP_N = 40
BLUE = "#256abf"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#52514e"


def read_types(path: Path) -> dict[str, int]:
    """Read the complete type-count mapping from ``stats.json``."""
    report = json.loads(path.read_text(encoding="utf-8"))
    return {name: int(count) for name, count in report["types"].items()}


def shown_types(counts: dict[str, int]) -> list[tuple[str, int]]:
    """Keep the largest labels and fold the remainder into ``Other``."""
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    visible = ordered[:TOP_N]
    remainder = sum(count for _, count in ordered[TOP_N:])
    if remainder:
        visible.append(("Other", remainder))
    return visible


def _format_count(value: float, _position: float) -> str:
    return f"{int(value):,}"


def render(counts: dict[str, int], output: Path) -> list[tuple[str, int]]:
    """Draw the type distribution and return the bars that were rendered."""
    visible = shown_types(counts)
    labels = [label for label, _ in reversed(visible)]
    values = [count for _, count in reversed(visible)]
    height = max(4.0, 0.34 * len(labels) + 1.4)
    figure, axes = plt.subplots(figsize=(10.5, height), dpi=160)
    figure.patch.set_facecolor(SURFACE)
    axes.set_facecolor(SURFACE)
    if values:
        axes.barh(labels, values, color=BLUE, height=0.68)
        axes.set_xscale("log")
        axes.xaxis.set_major_formatter(FuncFormatter(_format_count))
        for index, value in enumerate(values):
            axes.text(value * 1.08, index, f"{value:,}", va="center", color=INK, fontsize=8.5)
    else:
        axes.text(0.5, 0.5, "No type assignments", ha="center", va="center", color=MUTED)
    axes.set_xlabel("records carrying the type", color=MUTED)
    axes.set_title("Schema.org type distribution", loc="left", color=INK, pad=14)
    axes.tick_params(axis="both", colors=MUTED, labelsize=9, length=0)
    axes.grid(axis="x", color="#e6e5e1", linewidth=0.6)
    axes.set_axisbelow(True)
    for spine in axes.spines.values():
        spine.set_visible(False)
    figure.tight_layout()
    figure.savefig(output, facecolor=SURFACE, bbox_inches="tight")
    plt.close(figure)
    return visible


def main() -> None:
    """Render a type chart from a generated stats file."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("stats", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    counts = read_types(arguments.stats)
    visible = render(counts, arguments.out)
    print(
        json.dumps(
            {
                "type_labels": len(counts),
                "type_assignments": sum(counts.values()),
                "bars": len(visible),
                "out": str(arguments.out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

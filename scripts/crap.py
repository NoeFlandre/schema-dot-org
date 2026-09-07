"""Fail if any function scores CRAP 6 or higher.

CRAP -- Change Risk Anti-Patterns -- combines how branchy a function is with
how much of it the tests actually run:

    CRAP(f) = complexity(f)^2 * (1 - coverage(f))^3 + complexity(f)

A simple function is cheap to change however well it is tested; a branchy one
is only safe to change if the tests cover it. Complexity comes from radon,
per-function coverage from the statement coverage of the lines the function
spans. Run it after a coverage run that writes JSON:

    uv run pytest --cov=wdcgeo --cov-report=json
    uv run python scripts/crap.py
"""

import json
import subprocess
import sys
from pathlib import Path

THRESHOLD = 6.0
SOURCE = "src/wdcgeo"
COVERAGE_REPORT = Path("coverage.json")


def crap(complexity, coverage):
    """Return the CRAP score of a function of this complexity and coverage."""
    return complexity**2 * (1 - coverage) ** 3 + complexity


def span_coverage(measured, start, end):
    """Return the share of statements between ``start`` and ``end`` that ran."""
    executed = sum(1 for line in measured["executed_lines"] if start <= line <= end)
    missing = sum(1 for line in measured["missing_lines"] if start <= line <= end)
    statements = executed + missing
    if statements == 0:
        return 1.0
    return executed / statements


def scores(coverage_report, blocks):
    """Return (score, complexity, coverage, where) for every function, worst first."""
    rows = []
    for path, found in blocks.items():
        measured = coverage_report["files"][path]
        for block in found:
            if block["type"] == "class":
                continue
            coverage = span_coverage(measured, block["lineno"], block["endline"])
            score = crap(block["complexity"], coverage)
            where = f"{path}:{block['lineno']} {block['name']}"
            rows.append((score, block["complexity"], coverage, where))
    rows.sort(reverse=True)
    return rows


def main():
    """Report the worst scores and fail if any reaches the threshold."""
    radon = subprocess.run(
        [sys.executable, "-m", "radon", "cc", "-s", "-j", SOURCE],
        capture_output=True,
        text=True,
        check=True,
    )
    rows = scores(json.loads(COVERAGE_REPORT.read_text(encoding="utf-8")), json.loads(radon.stdout))
    for score, complexity, coverage, where in rows[:5]:
        print(f"{score:6.2f}  cc={complexity:<3d} coverage={coverage:7.2%}  {where}")
    over = [row for row in rows if row[0] >= THRESHOLD]
    print(f"{len(rows)} functions, worst CRAP {rows[0][0]:.2f}, {len(over)} at or above {THRESHOLD}")
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())

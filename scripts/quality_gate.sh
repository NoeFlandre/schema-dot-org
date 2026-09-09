#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

UV=(uv run --locked)
BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/wdcgeo-quality.XXXXXX")"
MUTATION_OUTPUT="$(mktemp "${TMPDIR:-/tmp}/wdcgeo-mutmut.XXXXXX")"

cleanup() {
  rm -rf "$BUILD_DIR" "$MUTATION_OUTPUT"
}
trap cleanup EXIT

uv lock --check
bash -n scripts/*.sh
"${UV[@]}" ruff format --check
"${UV[@]}" ruff check
"${UV[@]}" ty check
"${UV[@]}" wdcgeo --help >/dev/null
COVERAGE_FILE="$BUILD_DIR/.coverage" "${UV[@]}" pytest --cov=wdcgeo --cov-report=term-missing --cov-report=json:"$BUILD_DIR/coverage.json"
"${UV[@]}" python scripts/crap.py --coverage "$BUILD_DIR/coverage.json"
uv build --out-dir "$BUILD_DIR/dist"
"${UV[@]}" mkdocs build --strict --site-dir "$BUILD_DIR/site"

MUTATION_DIR="$BUILD_DIR/mutation"
mkdir -p "$MUTATION_DIR"
rsync -a \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='data/' \
  --exclude='site/' \
  --exclude='mutants/' \
  --exclude='__pycache__/' \
  --exclude='.pytest_cache/' \
  --exclude='.ruff_cache/' \
  --exclude='.coverage*' \
  --exclude='coverage.json' \
  --exclude='dist/' \
  "$ROOT/" "$MUTATION_DIR/"
(
  cd "$MUTATION_DIR"
  uv run --locked mutmut run
  uv run --locked mutmut results
) | tee "$MUTATION_OUTPUT"
if grep -Eq ': (survived|no tests|suspicious|check was interrupted by user|segfault|not checked)$' "$MUTATION_OUTPUT"; then
  echo "Mutation testing reported a non-killed, non-timeout status." >&2
  exit 1
fi

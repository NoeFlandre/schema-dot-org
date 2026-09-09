#!/usr/bin/env bash
# Profile and export a stratified sample of the GeoCoordinates subset.
#
# The subset is 237 parts and roughly 24 core-hours of parsing, so a run takes
# every STRIDE-th part instead: whole parts, spread evenly. Each part writes its
# own dataset and profile, which `wdcgeo merge` folds into one report.
#
# Downloads run one at a time because the mirror answers 429 to parallel
# fetches; parsing then runs WORKERS-way parallel over the local copies, and
# each copy is deleted as soon as its part is done.
#
# Usage: scripts/run_sample.sh [STRIDE] [WORKERS]
set -euo pipefail

STRIDE="${1:-7}"
WORKERS="${2:-4}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="https://data.dws.informatik.uni-mannheim.de/structureddata/2024-12/quads/classspecific/GeoCoordinates"
CACHE="$ROOT/data/cache"
OUT="$ROOT/data/parts"
LOGS="$ROOT/data/logs"

mkdir -p "$CACHE" "$OUT" "$LOGS"
PARTS=$(seq 0 "$STRIDE" 236)

echo "== downloading $(echo "$PARTS" | wc -w) parts"
for part in $PARTS; do
  target="$CACHE/part_$part.gz"
  [ -s "$target" ] && continue
  curl -sS --fail --retry 8 --retry-delay 15 --retry-all-errors --max-time 1800 \
    "$BASE/part_$part.gz" -o "$target" || echo "download of part $part failed" >&2
  sleep 2
done

process_part() {
  part="$1"
  source="$CACHE/part_$part.gz"
  [ -s "$source" ] || { echo "part $part missing" >&2; return 1; }
  if (cd "$ROOT" && uv run --locked wdcgeo export "$source" --out "$OUT/part_$part") \
      > "$LOGS/part_$part.manifest.json" 2> "$LOGS/part_$part.err"; then
    rm -f "$source"
    echo "part $part done"
  else
    echo "part $part failed" >&2
    return 1
  fi
}
export -f process_part
export CACHE OUT LOGS ROOT

echo "== processing with $WORKERS workers"
echo "$PARTS" | tr ' ' '\n' | xargs -P "$WORKERS" -I{} bash -c 'process_part {}'
echo "== done"

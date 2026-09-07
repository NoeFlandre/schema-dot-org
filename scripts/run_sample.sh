#!/usr/bin/env bash
# Profile and export a stratified sample of the GeoCoordinates subset.
#
# The subset is 237 parts and roughly 24 core-hours of parsing, so a run takes
# every STRIDE-th part instead: whole parts, spread evenly, processed in
# parallel. Each part writes its own dataset and profile, which `wdcgeo merge`
# folds into one report afterwards.
#
# Usage: scripts/run_sample.sh [STRIDE] [WORKERS]
set -uo pipefail

STRIDE="${1:-7}"
WORKERS="${2:-4}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/data/parts"
LOGS="$ROOT/data/logs"
WDCGEO="$ROOT/.venv/bin/wdcgeo"

mkdir -p "$OUT" "$LOGS"

process_part() {
  part="$1"
  for attempt in 1 2 3; do
    if "$WDCGEO" export --part "$part" --out "$OUT/part_$part" \
        > "$LOGS/part_$part.manifest.json" 2> "$LOGS/part_$part.err"; then
      echo "part $part done (attempt $attempt)"
      return 0
    fi
    echo "part $part failed (attempt $attempt)" >&2
    sleep $((attempt * 10))
  done
  return 1
}

export -f process_part
export OUT LOGS WDCGEO

seq 0 "$STRIDE" 236 | xargs -P "$WORKERS" -I{} bash -c 'process_part {}'

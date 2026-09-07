#!/usr/bin/env bash
# Profile and export every part of the GeoCoordinates subset.
#
# The subset is 33 GB compressed and the disk here is smaller than that, so
# downloads and parsing are interleaved: a downloader keeps at most CACHE parts
# on disk, workers take them as they land, and each copy is deleted the moment
# its part is exported. Parts already exported are skipped, so a run can be
# stopped and resumed, and a stride sample already on disk is reused rather
# than recomputed.
#
# The mirror answers 429 to parallel fetches, so downloads stay sequential;
# parsing is what gets the cores.
#
# Usage: scripts/run_corpus.sh [WORKERS] [CACHE]
set -uo pipefail

WORKERS="${1:-4}"
CACHE="${2:-8}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="https://data.dws.informatik.uni-mannheim.de/structureddata/2024-12/quads/classspecific/GeoCoordinates"
PARTS=237
CACHE_DIR="$ROOT/data/cache"
OUT="$ROOT/data/parts"
LOGS="$ROOT/data/logs"
WDCGEO="$ROOT/.venv/bin/wdcgeo"

mkdir -p "$CACHE_DIR" "$OUT" "$LOGS"

pending() {
  for part in $(seq 0 $((PARTS - 1))); do
    [ -f "$OUT/part_$part/manifest.json" ] || echo "$part"
  done
}

TODO=$(pending)
echo "== $(echo "$TODO" | wc -w) parts to do, $WORKERS workers, cache of $CACHE"

download_all() {
  for part in $TODO; do
    target="$CACHE_DIR/part_$part.gz"
    [ -s "$target" ] && continue
    # Wait for a worker to free a slot before fetching the next part.
    while [ "$(ls "$CACHE_DIR" | wc -l)" -ge "$CACHE" ]; do sleep 10; done
    curl -sS --fail --retry 8 --retry-delay 15 --retry-all-errors --max-time 1800 \
      "$BASE/part_$part.gz" -o "$target.tmp" \
      && mv "$target.tmp" "$target" \
      || { rm -f "$target.tmp"; echo "download of part $part failed" >&2; }
  done
  echo "== downloads done"
}

process_part() {
  part="$1"
  source="$CACHE_DIR/part_$part.gz"
  # The downloader may still be several parts behind; wait for this one.
  for _ in $(seq 1 360); do
    [ -s "$source" ] && break
    sleep 10
  done
  [ -s "$source" ] || { echo "part $part never arrived" >&2; return 1; }
  if "$WDCGEO" export "$source" --out "$OUT/part_$part" \
      > "$LOGS/part_$part.manifest.json" 2> "$LOGS/part_$part.err"; then
    rm -f "$source"
    echo "part $part done"
  else
    echo "part $part failed" >&2
    return 1
  fi
}
export -f process_part
export CACHE_DIR OUT LOGS WDCGEO

download_all &
DOWNLOADER=$!
echo "$TODO" | tr ' ' '\n' | xargs -P "$WORKERS" -I{} bash -c 'process_part {}'
wait "$DOWNLOADER" 2>/dev/null
echo "== done, $(ls -d "$OUT"/part_*/ | wc -l) parts exported"

# Using the tools

## Install

```bash
uv sync
```

That is the whole setup: `wdcgeo` has no runtime dependencies beyond the
standard library, and the development tools (ruff, ty, pytest, mutmut, mkdocs)
come from the `dev` group.

## Profile a part

```bash
uv run wdcgeo profile --part 0
```

Streams part 0 straight from the mirror and prints a JSON profile. Nothing is
written to disk. Add `--max-lines 2000000` for a quick look — around a minute —
or `--out profile.json` to write the report to a file instead of stdout.

Any path or URL works as a source, so a local copy or the published sample can
be read the same way:

```bash
curl -O https://data.dws.informatik.uni-mannheim.de/structureddata/2024-12/quads/classspecific/GeoCoordinates/GeoCoordinates_sample.txt
uv run wdcgeo profile GeoCoordinates_sample.txt
```

## Export records as a dataset

```bash
uv run wdcgeo export --part 0 --out dataset/part_0
```

Writes gzipped JSON Lines shards under `dataset/part_0/data/`, a Hugging Face
dataset card, the profile of everything read (`profile.json`) and the manifest
of what was written (`manifest.json`). Records are deduplicated on the way out:
a coordinate-and-name pair is kept once per host. The profile describes the
stream *before* deduplication, so the redundancy stays visible.

## Run a sample of the corpus

The corpus is roughly 24 core-hours of parsing, so a run takes whole parts
spread evenly across the 237:

```bash
scripts/run_sample.sh 7 4     # every 7th part, 4 workers
```

Downloads run one at a time (the mirror answers `429` to parallel fetches) into
`data/cache/`, each part is deleted once parsed, and every part writes its own
dataset under `data/parts/part_N/`.

`STRIDE` is the only knob that changes the scope of a run:

| stride | parts | share of corpus | rough wall clock at 4 workers |
| --- | --- | --- | --- |
| 24 | 10 | 4% | 16 min |
| 7 | 34 | 14% | 55 min |
| 3 | 79 | 33% | 2 h |
| 1 | 237 | 100% | 6 h |

The published figures in [Findings](findings.md) come from `STRIDE=7`. Widening
the run needs no code change: rerun with a smaller stride, then assemble.

## Assemble a run into one dataset

```bash
uv run wdcgeo assemble --from data/parts $(seq 0 7 236 | sed 's/^/--part /') --out data/dataset
```

Renumbers every part's shards into one series, merges the per-part profiles into
one `profile.json`, and writes a single card that names the *published* part
URLs rather than the local copies the run happened to read.

## Merge profiles only

```bash
uv run wdcgeo merge data/parts/*/profile.json --out merged.json
```

Counts add up; rankings are re-ranked and cut back to the top 25, so a merged
ranking is exact at the head and can miss an entry that stayed below every
part's cut.

## Upload to the Hub

The assembled directory is already in the layout the Hub reads, so the upload is
one command:

```bash
uv run --with huggingface_hub hf upload NoeFlandre/schema-dot-org data/dataset . --repo-type dataset
```

## Corpus-wide domain statistics

```bash
curl -O https://data.dws.informatik.uni-mannheim.de/structureddata/2024-12/quads/classspecific/GeoCoordinates/GeoCoordinates_domain_stats.csv
uv run python scripts/domain_stats.py GeoCoordinates_domain_stats.csv
```

This side file covers every domain in the subset, so it answers corpus-wide
questions in eight seconds without parsing a single quad.

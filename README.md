# wdcgeo — geolocated text from Web Data Commons

What text does the web publish next to coordinates, and is there enough of it
to be useful? This repository answers that for the `GeoCoordinates`
class-specific subset of the
[Web Data Commons schema.org series, release 2024-12](https://webdatacommons.org/structureddata/2024-12/stats/schema_org_subsets.html)
— 3.18 billion quads, 25.3 million pages, 567,265 hosts, 33 GB gzipped — and
ships the tools that produced the answer.

The whole subset was read: **51,654,798 geolocated text records over 12,427,530
distinct places**, from 3,183,190,155 lines, with 22,208 the parser could not
read.

![Density of every record over the world](docs/map.png)

```bash
uv sync --locked
uv run wdcgeo profile --part 0 --max-lines 2000000   # 15 seconds, no disk used
```

- **[Documentation](docs/index.md)** — what the corpus holds, what the sample
  found, how to run it, and how it is built.
- **Data** — <https://huggingface.co/datasets/NoeFlandre/schema-dot-org>

## What it does

`wdcgeo` streams parts of the subset straight from the mirror, parses the
corpus dialect of N-Quads, pairs every usable coordinate pair with the text
published next to it on the same page, and either profiles the result or writes
it out as a Hub-ready dataset.

```bash
uv run wdcgeo profile  --part 0                       # JSON profile of a part
uv run wdcgeo export   --part 0 --out dataset/part_0  # shards + card + profile
uv run wdcgeo merge    data/parts/*/profile.json      # fold profiles into one
uv run wdcgeo assemble --from data/parts --part 0 --out data/dataset
scripts/run_corpus.sh 4 8                             # all 237 parts, 4 workers
```

The interesting part is not the plumbing but what the corpus turns out to be
like: a `GeoCoordinates` entity is almost always bare, so only 3.3% of records
get their text from it and the rest comes from the parent entity that links to
it; property IRIs come in two spellings and dropping one loses every Microdata
page; and site-wide markup repeats one business across every page of its host,
so raw record counts overstate the corpus fourfold.
[Findings](docs/findings.md) has the numbers, and what a 14% sample of the same
corpus got wrong.

## Development

```bash
uv sync --locked
bash scripts/quality_gate.sh                 # the complete local/CI gate
uv run --locked mkdocs serve
```

The quality gate discovers the configured Python scope automatically and runs
formatting, linting, strict typing, 100% line and branch coverage, CRAP below
6, mutation testing with no surviving mutants, a wheel/sdist build, and a
strict documentation build. Mutation timeouts are retained only for the
scanner-loop mutants documented in [Design and quality](docs/design.md).

Written test-first throughout, with mutation testing as the real gate on the
tests and CRAP as the gate on how branchy any one function may get. [Design and quality](docs/design.md) explains the module boundaries and
the three design changes mutation testing forced.

## Licence

Apache 2.0, see [LICENSE](LICENSE). The underlying markup belongs to the
crawled sites; Web Data Commons distributes the extraction under the terms on
its own site.

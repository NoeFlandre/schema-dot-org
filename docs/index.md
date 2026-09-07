# Overview

What text does the web publish next to coordinates, and is there enough of it to
be useful? This project answers that for the `GeoCoordinates` class-specific
subset of the
[Web Data Commons schema.org series, release 2024-12](https://webdatacommons.org/structureddata/2024-12/stats/schema_org_subsets.html),
and ships the tools that produced the answer.

The subset is 3,183,190,155 quads over 25,257,059 pages and 567,265 hosts, 33 GB
gzipped in 237 parts. This run read **34 of those parts — 455,515,197 lines,
14.3% of the corpus** — and got **7,380,861 geolocated text records covering
1,938,332 distinct places**, with **4 lines the parser could not read**.

## What was learned

* **The text is not on the class the subset is named after.** 95.7% of domains
  publish nothing but `latitude` and `longitude` on their `GeoCoordinates`
  entities. The name, address and description live on the parent entity that
  points at them with `schema:geo`; 97.2% of records here come from that parent.
  A pipeline that reads the coordinate node alone recovers almost no text.
* **Names and addresses are near-universal, prose is not.** 87.1% of records
  carry a name, 86.4% an address, 21.4% a description — and the descriptions
  are substantial where they exist, a median of 182 characters.
* **Redundancy dominates.** 7.4M records are 1.9M distinct places, because
  site-wide markup republishes one business on every page of its site. Raw
  counts overstate the corpus roughly fourfold, and a train/test split made
  before deduplicating is worthless.
* **Coverage is Europe and North America**, and 89.8% of records carry no
  language tag.
* **The format is clean.** Four unreadable lines in 455 million.

[Findings](findings.md) has the numbers and what they mean for a given task;
[the corpus](corpus.md) describes what is published and how.

## The tools

```bash
uv sync
uv run wdcgeo profile --part 0 --max-lines 2000000   # a minute, no disk used
```

`wdcgeo` streams parts of the subset straight from the mirror, parses the corpus
dialect of N-Quads, pairs every usable coordinate pair with the text published
next to it on the same page, and either profiles the result or writes it out as
a Hub-ready dataset. See [using the tools](usage.md), and
[design and quality](design.md) for how it is built and gated.

## The data

<https://huggingface.co/datasets/NoeFlandre/schema-dot-org> — the 1,938,332
deduplicated records of this run, with the merged profile beside them.

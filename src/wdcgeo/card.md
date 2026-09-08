---
license: cc-by-4.0
language:
- en
task_categories:
- text-classification
- token-classification
- text-retrieval
tags:
- geospatial
- schema.org
- web-data-commons
size_categories:
- {size_category}
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*.jsonl.gz
---

# Geolocated text from the Web Data Commons schema.org GeoCoordinates subset

{records} geolocated text records, extracted from the class-specific
GeoCoordinates subset of the Web Data Commons schema.org data set series
(release 2024-12). Each record pairs one coordinate pair published on a web page
with the text published next to it on that same page.

Each source stream is deduplicated by host-local runs: a coordinate-and-name
pair is kept once per contiguous host run. A host returning in a later part may
contribute another copy. Coordinates are kept exactly as published, including
0/0 and whole-degree values, so quality filtering stays the consumer's choice.

## Dataset statistics

| statistic | value |
| --- | ---: |
| Published records | {published_records} |
| Contiguous page runs represented | {pages} |
| Hosts represented | {hosts} |
| Records with text | {text_records} |
| Words in name, description, and address | {words} |
| Characters in name, description, and address | {characters} |
| Records with a schema.org type | {records_with_type} |
| Distinct schema.org type labels | {type_labels} |
| Input records before host-local deduplication | {raw_records} |
| Input distinct host-local locations | {distinct_places} |

{map_section}{types_section}

## Fields

| field | type | meaning |
| --- | --- | --- |
| `page_url` | string | page the statements were extracted from |
| `host` | string | host of `page_url`, lowercased |
| `latitude` | float | degrees north, in `[-90, 90]` |
| `longitude` | float | degrees east, in `[-180, 180]` |
| `types` | list of string | schema.org types of the located entity |
| `name` | string or null | `schema:name` of the located entity |
| `description` | string or null | `schema:description` of the located entity |
| `address` | string or null | `schema:address`, flattened when a `PostalAddress` is linked |
| `text_properties` | list of string | every schema.org property of the entity carrying a literal |
| `languages` | list of string | language tags on the text that was kept |

## Provenance

Extracted with [wdcgeo](https://github.com/NoeFlandre/schema-dot-org). The
markup is published by the crawled sites and collected by the Web Data Commons
project, which distributes the extraction under the terms stated on
<https://webdatacommons.org/structureddata/>. The input was read from
{source_count} source part(s). `profile.json` reports aggregate statistics
before deduplication; `stats.json` describes the published records after
deduplication.

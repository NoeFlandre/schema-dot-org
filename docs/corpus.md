# The corpus

## What the subset is

Web Data Commons extracts the structured markup embedded in the Common Crawl
web corpus. From that extraction it publishes *class-specific subsets*: for a
chosen schema.org class, every page containing an instance of the class, with
**all** the data found on those pages, not only the class itself. This project
reads the `GeoCoordinates` subset of the
[2024-12 release](https://webdatacommons.org/structureddata/2024-12/stats/schema_org_subsets.html).

| | |
| --- | --- |
| Quads | 3,183,190,155 |
| Pages (URLs) | 25,257,059 |
| Hosts | 567,265 |
| Download size | 33.28 GB, gzipped, in 237 parts |
| `GeoCoordinates` entities | 53,608,277 |

The classes that appear most in the subset are not `GeoCoordinates` itself but
its neighbours on the same pages: `ListItem` (73.5M quads), `PostalAddress`
(53.0M), `GeoCoordinates` (50.5M), `OpeningHoursSpecification` (32.4M) and
`Offer` (31.6M). That is the whole point of a class-specific subset, and the
reason there is text to mine: a page carrying coordinates also carries the
business the coordinates belong to.

## How it is published

Everything lives under one directory on the Mannheim mirror:

```
https://data.dws.informatik.uni-mannheim.de/structureddata/2024-12/quads/classspecific/GeoCoordinates/
├── part_0.gz … part_236.gz          # the corpus, ~140 MB each
├── GeoCoordinates_sample.txt        # 1,000 lines, uncompressed
├── GeoCoordinates_lookup.csv        # 19.8 MB
└── GeoCoordinates_domain_stats.csv  # 35.7 MB, one row per domain
```

!!! note "The mirror rate-limits parallel downloads"
    Fetching several parts at once earns `HTTP 429`. Downloads have to run one
    at a time; parsing is what deserves the parallelism, and it can run over
    local copies. `scripts/run_sample.sh` is built that way.

## The quad format

Each line is an N-Quads statement whose fourth term is the page the statement
was extracted from. Real lines from `GeoCoordinates_sample.txt`:

```
_:nb0282a78e35f4d7998a4c8f4d4e439c0xb0 <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://schema.org/WebSite> <https://tn-autoinsurancequote.com/>   .
_:nb0282a78e35f4d7998a4c8f4d4e439c0xb1 <http://schema.org/brand> "State Farm" <https://tn-autoinsurancequote.com/>   .
```

Three details matter to a parser:

* Statements about one page are contiguous, which is what lets a reader group
  pages in constant memory.
* Subjects are usually blank nodes, whose labels are unique to a file and not
  to the corpus, so entities can only be joined *within* a page.
* The terminator is preceded by padding whitespace, and the file will contain
  lines that no parser should accept. `wdcgeo` drops what it cannot read and
  reports how many lines that was.

## Two spellings of the same vocabulary

The extractor emits JSON-LD properties under their plain IRI and Microdata
properties under a class-scoped one:

| markup | predicate for `name` |
| --- | --- |
| JSON-LD | `http://schema.org/name` |
| Microdata | `http://schema.org/Restaurant/name` |

Reading only the first spelling silently loses every Microdata page. `wdcgeo`
accepts both, over four spellings of the namespace itself (`http` / `https`,
with and without `www.`), and takes the class segment of the second spelling as
an extra type declaration, so a page without an `rdf:type` quad still reports
what it is about.

## Where the text is, and where it is not

`GeoCoordinates_domain_stats.csv` gives the properties each domain publishes on
its `GeoCoordinates` entities, for every domain in the subset. Counting domains
rather than sampling:

| property on the `GeoCoordinates` node | domains | share of 567,265 |
| --- | --- | --- |
| `latitude` | 560,435 | 98.8% |
| `longitude` | 560,254 | 98.8% |
| `address` | 7,479 | 1.3% |
| `name` | 7,477 | 1.3% |
| `postalCode` | 5,214 | 0.9% |
| `description` | 4,091 | 0.7% |
| `elevation` | 446 | 0.1% |

542,614 domains — 95.7% — publish **nothing but** `latitude` and `longitude` on
those entities.

!!! warning "The consequence for anyone mining this subset"
    A `GeoCoordinates` instance is almost always bare. Reading the class the
    subset is named after yields coordinates and no text at all. The text lives
    on the *parent* entity that links to it with `schema:geo` — the
    `Restaurant`, `Hotel` or `LocalBusiness` — which is why extraction has to
    walk that link backwards, and why this project's records are keyed on the
    parent rather than on the coordinate node.

Domain sizes are extremely skewed: the median domain contributes 180 quads to
the subset, the 90th percentile 5,563, the 99th 81,754, and the largest single
domain 34,126,299. Any sample dominated by a handful of hosts is not a sample
of the web.

# Findings

## Scope of this run

Everything below comes from **34 of the subset's 237 parts** — every 7th part,
so the sample is spread evenly rather than taken from one end:

| | this run | whole subset |
| --- | --- | --- |
| Parts | 34 | 237 |
| Lines read | 455,515,197 | 3,183,190,155 |
| Share | **14.3%** | 100% |
| Hosts seen | ≤ 80,162 | 567,265 |

Widening the sample needs no code change — `scripts/run_sample.sh 3` for a
third of the corpus, `1` for all of it — so every figure here is reproducible at
a larger scale by rerunning and reassembling. Host counts add up across parts,
so a host appearing in two parts is counted twice: read them as upper bounds.
Everything else is an exact count over what was read.

The one whole-corpus source used here is
`GeoCoordinates_domain_stats.csv`, which covers all 567,265 domains and needs
no parsing.

## What a page-by-page read yields

| | |
| --- | --- |
| Lines read | 455,515,197 |
| Lines the parser could not read | **4** |
| Geolocated text records | 7,380,861 |
| Pages that produced at least one | 3,524,198 |
| Distinct places | 1,938,332 |

Four unreadable lines in 455 million is the headline result for the format
itself: the corpus is clean, and a parser that gives up on a bad line loses
nothing measurable. Scaled to the full subset, a complete run would yield
roughly **51 million records and 13.5 million distinct places** — close to the
53.6 million `GeoCoordinates` entities the corpus reports, which is the
cross-check that the extraction is not quietly dropping a class of pages.

## The text is not where the class is

Corpus-wide, 98.8% of domains publish `latitude` and `longitude` on their
`GeoCoordinates` entities, 1.3% a `name`, 0.7% a `description`, and **95.7%
publish nothing else at all** ([the corpus](corpus.md#where-the-text-is-and-where-it-is-not)).
Read the class the subset is named after and you get coordinates and no text.

This run confirms it from the other side: of 7.4M records, only 207,548 (2.8%)
are located by a node that is *itself* the entity carrying the text. In the
other 97.2%, the text lives on a parent — a `Place`, `LocalBusiness`,
`SingleFamilyResidence` — that points at the coordinates with `schema:geo`.
**Any pipeline that does not walk that link backwards recovers almost none of
the geolocated text in this corpus.**

## How much text, and of what length

| field | records | share | mean chars | median | p90 |
| --- | --- | --- | --- | --- | --- |
| `name` | 6,432,044 | 87.1% | 26 | — | — |
| `address` | 6,375,642 | 86.4% | 47 | — | — |
| `description` | 1,578,507 | 21.4% | 317 | 182 | 992 |
| any of the three | 6,924,890 | **93.8%** | | | |
| all three | 1,336,729 | 18.1% | | | |

Name and address are near-universal and short; a name is a shop sign, an
address is one line. Description is the only field carrying prose, it is present
on a fifth of records, and where present it is substantial — a median of 182
characters and a tenth of them over 992.

So the answer to "is there enough text?" depends entirely on the task:

* **Plenty** for anything keyed on a short label: geocoding a name, matching a
  business to a place, address parsing, name-based entity linking. 6.4M records
  with a name and a coordinate pair, from a seventh of the corpus.
* **Enough** for text-to-location modelling on prose: 1.58M descriptions with
  coordinates here, so ~11M over the whole subset — a real corpus, if a
  fifth-of-the-data one.
* **Thin** for anything needing several fields at once: only 18.1% carry name,
  address *and* description together.

## What the places are

| type | records | | property beside the coordinates | records |
| --- | --- | --- | --- | --- |
| `Place` | 1,832,819 | | `name` | 6,432,044 |
| `LocalBusiness` | 1,561,930 | | `telephone` | 3,500,129 |
| `SingleFamilyResidence` | 708,185 | | `priceRange` | 1,865,295 |
| `LegalService` | 386,591 | | `description` | 1,578,507 |
| `Store` | 296,413 | | `email` | 671,339 |
| `GeoCoordinates` (bare) | 207,548 | | `openingHours` | 543,710 |
| `Organization` | 184,639 | | `containedIn` | 286,658 |
| `Airport` | 183,535 | | `paymentAccepted` | 255,574 |
| `Church` | 158,231 | | `iataCode` | 179,995 |
| `Event` | 140,996 | | `startDate` | 140,996 |

This is a commercial corpus, not a gazetteer. It is shops, lawyers, estate
agents and churches — the places that publish structured markup because it
helps them get found. Airports arrive as a block (`iataCode` matches `Airport`
exactly), as do events (`startDate` matches `Event` exactly), which is what a
class-specific subset looks like: whole sites of one shape at a time.

## Redundancy is the dominant property

7,380,861 records collapse to **1,938,332 distinct places** — 26.3%. Of the
records, 2,683,966 are byte-identical to the record immediately before them.

The cause is site-wide markup: a business puts its `LocalBusiness` block in the
page footer, and the crawl sees it once per page. `lawyers.oyez.org` accounts
for 330,348 records, `immobilier.lefigaro.fr` for 304,668, and its sister
`proprietes.lefigaro.fr` for 197,494.

Two consequences, and they are the practical ones:

* **Raw record counts overstate this corpus by roughly 4×.** Anything reported
  per record — including "millions of geolocated texts" — should be read per
  distinct place.
* **Deduplicate before splitting train and test**, or the same business appears
  on both sides thousands of times and every metric is inflated. The exported
  dataset is already deduplicated per host for this reason.

## Where on Earth

| 10° cell (SW corner) | records | roughly |
| --- | --- | --- |
| 40N, 0E | 977,842 | France, Spain, Italy |
| 40N, 80W | 654,695 | US north-east |
| 30N, 90W | 379,774 | US south |
| 50N, 0E | 369,852 | England, Benelux |
| 40N, 90W | 364,840 | US midwest |
| 50N, 10E | 348,686 | Germany, Poland |

By TLD: `.com` 3,081,215, then `.fr` 731,610, `.org` 585,689, `.info` 293,678,
`.pl` 281,263, `.au` 198,002, `.de` 180,234, `.edu` 156,316.

Coverage is Europe and North America. Africa, South Asia and most of Latin
America are close to absent, and no amount of extra sampling fixes that — it is
what the web publishes, and it is a hard limit on using this corpus to train
anything expected to work globally.

## Language is mostly unmarked

6,631,520 records (89.8%) carry no language tag at all. Where a tag exists it is
`fr` (367,361), `en` (102,980), `ru` (34,055), `en-US` (29,039), `de` (23,215),
`es` (17,543) — and the spellings are inconsistent (`en-US`, `en-us`, `en-gb`
all occur). Anything language-aware has to detect the language from the text
rather than trust the markup.

## Defects to filter, measured

Over the 1,938,332 distinct exported records:

| defect | records | share |
| --- | --- | --- |
| Identical `latitude` and `longitude` | 43,391 | 2.24% |
| HTML entities left encoded in `description` | 29,165 | 5.4% of descriptions |
| HTML entities left encoded in `name` | 14,894 | 0.8% |
| Coordinates at 0/0 (over all records) | 113,643 | 1.54% |
| Coordinates on a whole degree (over all records) | 117,851 | 1.60% |
| `name` shorter than three characters | 1,168 | 0.06% |

None of these are filtered out by the extraction, deliberately: a value that is
published is reported, and what counts as usable depends on the task. A
plausible cleaning pass — drop 0/0, drop identical coordinates, unescape
entities — costs under 4% of records.

Whole-degree coordinates deserve a note: 1.6% of records place a business at an
exact integer latitude *and* longitude, which on the ground is a rounding to
about 100 km. They are not obviously wrong in the way 0/0 is, which makes them
the more dangerous kind of bad data.

## What this corpus is, in one paragraph

A very large, very redundant, Western-skewed directory of commercial places,
where the coordinates are reliable and machine-published, the names and
addresses are short and near-universal, prose exists on a fifth of records, and
the text never lives on the entity the subset is named after. It is a strong
source for geocoding, place matching and address work, a usable one for
text-to-location modelling, and a poor one for anything needing global
coverage or per-record language metadata.

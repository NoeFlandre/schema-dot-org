# Findings

## Scope

The whole subset: **all 237 parts, 3,183,190,155 lines** — exactly the quad count
Web Data Commons publishes for it, which is the first check that nothing was
skipped.

| | |
| --- | --- |
| Lines read | 3,183,190,155 |
| Quads parsed | 3,183,167,947 |
| Lines the parser could not read | **22,208** (0.0007%) |
| Geolocated text records | 51,654,798 |
| Pages that produced at least one | 24,107,233 |
| **Distinct places** | **12,427,530** |
| Hosts | ≤ 578,360 |

The host figure adds up across parts, so a host appearing in two parts is
counted twice: it is an upper bound, and its closeness to the 567,265 hosts the
corpus reports says few hosts straddle a part boundary. Every other figure is an
exact count over the entire corpus.

## Where the records are

![Density of every record over the world](map.png)

Every one of the 12.4 million distinct places, counted into quarter-degree cells
on a logarithmic scale. No coastline is drawn — the outlines are the data, which
is the most direct statement of coverage available: where the map is blank, the
web publishes no geolocated markup.

Populated cells cover **9.5% of the world's surface**, and the busiest single
quarter-degree cell holds 143,066 records.

| 10° cell (SW corner) | records | roughly |
| --- | --- | --- |
| 40N, 80W | 5,406,826 | US north-east |
| 40N, 0E | 3,942,745 | France, Spain, Italy |
| 30N, 90W | 2,719,553 | US south |
| 50N, 10W | 2,687,813 | Britain and Ireland |
| 50N, 0E | 2,492,352 | Benelux, north Germany |
| 40N, 90W | 2,349,394 | US midwest |

Europe and North America dominate, but at full scale the rest of the world is
present rather than absent: India, Japan, coastal Brazil, the South African
coast, the Australian seaboard and the Gulf all resolve clearly. What the map
shows that a table cannot is *how* the data thins — not country by country but
along roads and coastlines, because what is mapped is commerce, not land.

The faint straight lines crossing the Pacific and the Indian Ocean are not
noise in the drawing. They are records whose coordinates interpolate between two
real places — the signature of a site publishing a route rather than a location.

## The text is not where the class is

Corpus-wide, 98.8% of domains publish `latitude` and `longitude` on their
`GeoCoordinates` entities, 1.3% a `name`, 0.7% a `description`, and **95.7%
publish nothing else at all**
([the corpus](corpus.md#where-the-text-is-and-where-it-is-not)).

The full read confirms it from the other side: of 51.7M records, only 1,708,844
— **3.3%** — are located by a node that also carries the text. In the other
96.7%, the text lives on a parent entity that points at the coordinates with
`schema:geo`.

!!! warning "The one thing to take away"
    Read the class the subset is named after and you get coordinates and no
    text. A pipeline that does not walk `schema:geo` backwards to the parent
    recovers 3% of what is there.

## How much text, and of what length

| field | records | share | mean chars | median | p90 |
| --- | --- | --- | --- | --- | --- |
| `name` | 44,364,198 | 85.9% | 25 | — | — |
| `address` | 42,765,156 | 82.8% | 48 | — | — |
| `description` | 11,290,348 | 21.9% | 311 | 168 | 980 |
| any of the three | 47,881,709 | **92.7%** | | | |
| all three | 10,329,499 | 20.0% | | | |

In total: **1.09 billion characters of names, 2.05 billion of addresses and 3.51
billion of descriptions**, each paired with a coordinate.

Deduplicated, 4,051,148 distinct places carry a description — 32.6% of them,
higher than the 21.9% of raw records, because the site-wide markup that inflates
the record count is mostly name-and-address footers without prose.

What that supports:

* **Geocoding, place matching, address parsing, name-based entity linking.**
  44M name-and-coordinate pairs, 12.4M of them distinct places. This is the
  strongest use of the corpus by a wide margin.
* **Text-to-location modelling on prose.** 4M distinct descriptions with
  coordinates, a median of 168 characters and a tenth over 980. A real corpus.
* **Anything needing several fields at once is thinner**: 20.0% carry name,
  address and description together.

## What the places are

| type | records | | property beside the coordinates | records |
| --- | --- | --- | --- | --- |
| `Place` | 16,189,602 | | `name` | 44,364,198 |
| `LocalBusiness` | 11,012,019 | | `telephone` | 24,399,276 |
| `LegalService` | 2,401,449 | | `priceRange` | 11,619,164 |
| `Airport` | 2,352,844 | | `description` | 11,290,348 |
| `SingleFamilyResidence` | 2,329,481 | | `email` | 5,051,765 |
| `GeoCoordinates` (bare) | 1,708,844 | | `openingHours` | 3,786,430 |
| `Store` | 1,658,749 | | `iataCode` | 2,318,583 |
| `Organization` | 1,216,802 | | `image` | 1,687,231 |
| `Hotel` | 1,056,589 | | `paymentAccepted` | 1,627,167 |
| `House` | 810,800 | | `numberOfBathroomsTotal` | 1,214,016 |

A commercial directory, not a gazetteer: shops, lawyers, hotels, car dealers and
houses for sale — the places that publish structured markup because it helps
them get found. Two verticals arrive as whole blocks, and the property counts
give them away: `iataCode` (2,318,583) tracks `Airport` (2,352,844), and
`numberOfBathroomsTotal` (1,214,016) tracks the residential listings. Real
estate and air travel are, between them, a tenth of this corpus.

## Redundancy is the dominant property

51,654,798 records collapse to **12,427,530 distinct places** — 24.1%. Of the
records, 18,382,886 are identical to the record immediately before them.

The cause is site-wide markup: one business in a page footer, seen once per
crawled page. The largest single contributors are `www.justia.com` (1,179,591
records), `www.wowdeals.me` (731,021), `news.veteranownedbusiness.com` (549,400)
and `transit.navitime.com` (522,600).

* **Raw record counts overstate this corpus roughly fourfold.** Report per
  distinct place.
* **Deduplicate before splitting train and test.** Otherwise one business lands
  on both sides thousands of times and every metric is inflated. The published
  dataset is deduplicated per host for exactly this reason.

## Language is mostly unmarked

46,121,737 records — **89.3%** — carry no language tag. Where a tag exists:
`en` (1,756,440), `ar` (592,625), `fr` (486,693), `ru` (481,443), `de`
(411,258), `en-US` (334,955), and the spellings are inconsistent (`en-US`,
`en-us`, `en-gb` all occur). Anything language-aware has to detect the language
from the text rather than trust the markup.

By TLD: `.com` 26,977,614 (52%), then `.org` 2,243,257, `.uk` 1,684,349, `.fr`
1,674,865, `.de` 1,610,074, `.ru` 1,153,510, `.au` 1,099,022, `.ca` 1,087,108,
`.pl` 1,085,510.

## Defects to filter, measured

Over the 12,427,530 distinct records of the published dataset:

| defect | records | share |
| --- | --- | --- |
| Identical `latitude` and `longitude` | 151,225 | 1.22% |
| HTML entities left encoded in `description` | 183,663 | 4.5% of descriptions |
| HTML entities left encoded in `name` | 126,463 | 1.02% |
| Coordinates at 0/0 (over all records) | 402,848 | 0.78% |
| Coordinates on a whole degree (over all records) | 427,824 | 0.83% |
| `name` shorter than three characters | 8,204 | 0.07% |

Nothing is filtered out by the extraction, deliberately: a published value is
reported, and what counts as usable depends on the task. A plausible cleaning
pass — drop 0/0, drop identical coordinates, unescape entities — costs under 3%
of records.

Whole-degree coordinates deserve a note: 0.83% of records sit on an exact
integer latitude *and* longitude, which is a rounding to about 100 km. They are
not obviously wrong the way 0/0 is, which makes them the more dangerous kind of
bad data.

## What a 14% sample got right, and wrong

An earlier run read every 7th part — 14.3% of the corpus — and its estimates are
worth keeping as a note on how far a stratified sample of this corpus can be
trusted:

| figure | 14% sample, scaled | whole corpus | error |
| --- | --- | --- | --- |
| Records | ~51,000,000 | 51,654,798 | −1% |
| Distinct places | ~13,500,000 | 12,427,530 | +9% |
| `name` share | 87.1% | 85.9% | +1.2 pt |
| `description` share | 21.4% | 21.9% | −0.5 pt |
| `address` share | 86.4% | 82.8% | +3.6 pt |

The aggregate shares were reliable to a point or two. What the sample got badly
wrong was every *ranking* whose tail matters: it put `.fr` second among TLDs on
the strength of one large French property site, and it did not see Arabic at all
— `ar` is the second most tagged language in the whole corpus and absent from
the sample's top ten. Heavy-tailed distributions do not sample well: for
coverage questions, read the whole thing.

## What this corpus is, in one paragraph

A 51-million-record, fourfold-redundant, Western-weighted commercial directory
of the world, where coordinates are machine-published and reliable, names and
addresses are short and near-universal, prose exists on a fifth of records, and
the text never lives on the entity the subset is named after. It is a strong
source for geocoding, place matching and address work, a usable one for
text-to-location modelling, and a poor one for per-record language metadata or
for anything that needs the parts of the world where commerce does not publish.

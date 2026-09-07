# Design and quality

## Deep modules, thin edges

Each module hides one hard thing behind a small interface. The interface is
what the next module up needs, and nothing else.

| module | interface | what it absorbs |
| --- | --- | --- |
| `quads` | `parse_line`, `parse_quads` | a hand-written scanner for the corpus dialect of N-Quads: escapes, language tags, datatype IRIs, padding, and every way a line can be broken |
| `extract` | `geolocated_texts`, `deduplicate` | page grouping, both schema.org property spellings, walking `geo` backwards to the parent entity, coordinate spellings, `PostalAddress` flattening, per-host redundancy |
| `profile` | `profile`, `Accumulator`, `merge` | single-pass aggregation in bounded memory, and merging the reports of parts processed apart |
| `corpus` | `part_url`, `stream_lines` | where the subset lives, and streaming a part from a URL or a path, gzipped or plain |
| `dataset` | `write_dataset`, `assemble`, `write_card` | the Hub's on-disk layout, shard rotation, and the card |
| `pipeline` | `Pipeline.records`, `Pipeline.counts` | composing the four above, and counting what survived each stage |
| `cli` | `main` | argument parsing and printing, and nothing else |

The command line holds no logic: it resolves arguments to locations, hands them
to `Pipeline`, and prints what comes back. `profile.Accumulator.tap` is what
lets one pass do two jobs — profile every record while only the distinct ones
reach the shards — without either module knowing about the other.

## Test-first, always

Every module here was written the same way: a test file first, run to watch it
fail on the missing import (RED), then the implementation until it passes
(GREEN). The commit history follows the cycles.

```bash
uv run pytest                     # 190 tests
uv run pytest --cov=wdcgeo        # 100% of lines and branches, enforced
uv run ruff format src tests
uv run ruff check src tests       # every rule ruff has, minus documented exceptions
uv run ty check
uv run mutmut run && uv run mutmut results
```

Coverage is gated at 100% of lines *and* branches. It is a floor, not a goal:
it says every line ran, never that anything was checked.

## Mutation testing, and what it changed

`mutmut` rewrites the source one edit at a time and reruns the suite. A mutant
that survives is a behaviour no test pins down. The gate here is **zero
survivors** over `src/wdcgeo/`: of 1,125 mutants, 1,122 are killed by a failing
assertion and 3 by timeout.

It earned its keep by changing the design, not just by adding tests:

* **A redundant condition in coordinate parsing.** `if "," in cleaned and "."
  not in cleaned` guarded a comma-to-dot substitution. No input could
  distinguish the guarded version from the unguarded one — no float spelling
  contains a comma, so the substitution cannot spoil a value that already
  parses. The guard was deleted, not covered.
* **Unobservable sentinels, twice.** Separate `_page`, `_host` and `_previous`
  fields initialised to `None` could each be mutated to `""` with no visible
  effect. They collapsed into one reference to the previous record, which a
  mutant cannot replace with a string without the next attribute access
  failing. `deduplicate` had the same sentinel and lost it the same way. One
  piece of state replaced three; a dead initialiser became load-bearing.
* **A default argument no caller could observe.** `_ranked(section, name="")`
  had a default that only the top-level call used, and any other string behaved
  identically. Splitting the function in two removed the argument.

Three mutants are killed by timeout rather than by an assertion: each moves the
scanner's cursor backwards or resets it, so the scanner loops forever. A mutant
that hangs the suite is detected, which is what being killed means here. Two
others used to "die" the same way for a bad reason — they ignored
`--max-lines 0` and started a real 140 MB download until the run timed out. A
guard in `tests/conftest.py` now denies every host but the local test server,
so those mutants fail on an assertion and the suite is provably offline.

### Text that is only ever printed

Prose in string literals becomes a wall of survivors, so it is kept out of code
where possible and pinned where not:

* the dataset card is a template file beside the module;
* every command-line help string is a module constant, and the exact `--help`
  output of all five commands is asserted verbatim. Program name, metavars and
  layout are the published interface; 93 mutants were hiding in that wiring.

### The five suppressed mutants

Five lines carry `# pragma: no mutate`, and each carries only an encoding
argument. Mutating `encoding="utf-8"` to `encoding=None`, to the alias
`"UTF-8"`, or to nothing at all is unobservable in-process, because the
machine's own default encoding is UTF-8 — the mutant and the original do the
same thing.

Rather than accept them, the property is tested where it can be seen: one test
runs a full export in a subprocess under `LC_ALL=C` with locale coercion and
UTF-8 mode disabled, where the default encoding really is ASCII. Left to the
locale, that run raises `UnicodeDecodeError` on the corpus or writes mojibake
into the dataset. `mutmut` mutates in-process and cannot reach a subprocess, so
it cannot see that test kill anything — hence the pragma rather than a silent
survivor. Every other literal was hoisted off those five lines first
(`ENCODING`, `_SHARD_MODE`, `_DECODE_ERRORS`, `PROFILE_NAME`, and the text
helpers in `wdcgeo/__init__.py`), so the suppression covers nothing else.

## YAGNI, held to

Things deliberately not built, and why:

* **No resume, no retry, no progress bar in the library.** `curl --retry` in the
  run script already does the retrying, and the library stays a library.
* **No download command.** `stream_lines` reads a URL as readily as a path, so
  storing a part first is a choice the caller makes, not a feature.
* **No Parquet, no `datasets` dependency.** Gzipped JSON Lines is what the Hub
  reads without configuration, and the standard library writes it.
* **No coordinate reverse geocoding, no language detection, no text cleaning
  beyond whitespace.** Those are decisions for whoever consumes the records;
  making them here would destroy information the profile is meant to expose.
* **No DMS coordinate parsing** (`48°51'29"N`). Not seen in the corpus so far;
  the profile would show it as unusable coordinates if it were common.
* **Null-island and whole-degree coordinates are kept.** Dropping them would
  hide a known corpus problem that the profile measures instead.

## Scripts are not library code

`scripts/` holds two runnable things — `run_sample.sh`, which orchestrates a
run, and `domain_stats.py`, which summarises a side file. They are deliberately
outside `src/`: they are not imported, not covered by the coverage gate and not
mutated, because they encode how *this* exploration was run rather than
behaviour anyone depends on.

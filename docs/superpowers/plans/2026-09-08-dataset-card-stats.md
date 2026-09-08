# Dataset Card Statistics and Type Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`-`) syntax for tracking.

**Goal:** Replace the long dataset-card source list with concise provenance, add reproducible post-dedup statistics and a type-distribution plot, then publish verified metadata to GitHub and Hugging Face.

**Architecture:** Keep `profile.json` as the pre-dedup corpus profile. Add a bounded `DatasetStats` accumulator for published JSONL records; `write_dataset` updates it while writing, and `assemble` recomputes it by streaming assembled shards so cross-part page and host counts are exact. The card template contains prose and table labels; values come from `stats.json`. A script outside `src/` renders the type chart from complete type counts.

**Tech Stack:** Python standard library in `src/wdcgeo/`, pytest/coverage/mutmut/CRAP for library gates, matplotlib in `scripts/render_types.py`, `uv`, and `hf upload` for metadata publication.

---

### Task 1: Define and test post-dedup dataset statistics

**Files:**
- Modify: `src/wdcgeo/dataset.py`
- Modify: `tests/test_dataset.py`

- [ ] **Step 1: Write the failing statistics test**

Add a second fixture record and a test that exercises `write_dataset`:

```python
SECOND = replace(
    BASE,
    page_url="http://other.example/p/2",
    host="other.example",
    latitude=0.0,
    longitude=0.0,
    types=("Restaurant", "CafeOrCoffeeShop"),
    name="Two words",
    description="three four",
    address=None,
    languages=("en", "fr"),
)


def test_writes_post_dedup_stats_from_records(tmp_path):
    manifest = write_dataset([BASE, SECOND], tmp_path, SOURCES)
    assert manifest["stats"] == "stats.json"
    assert json.loads((tmp_path / "stats.json").read_text(encoding="utf-8")) == {
        "records": 2,
        "pages": 2,
        "hosts": 2,
        "text": {"records": 2, "words": 7, "characters": 33},
        "records_with_type": 2,
        "types": {"Restaurant": 2, "CafeOrCoffeeShop": 1},
        "languages": {"en": 1, "fr": 1},
        "coordinates": {"null_island": 1, "whole_degrees": 1},
    }
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run pytest tests/test_dataset.py::test_writes_post_dedup_stats_from_records -q
```

Expected: FAIL because `write_dataset` does not emit `stats.json`.

- [ ] **Step 3: Implement the minimal accumulator and writer integration**

Add `STATS_NAME = "stats.json"` and a `DatasetStats` class in `src/wdcgeo/dataset.py`. Its `add` method must count page transitions, distinct hosts, present text fields, whitespace-delimited words, characters, non-empty types, every type label, language tags, null-island coordinates, and whole-degree coordinate pairs. Split text, type, coordinate, and page updates into helpers so no function exceeds the CRAP threshold. Update `write_dataset` to update the accumulator while writing each record, serialize `stats.json`, and include `"stats": STATS_NAME` in its manifest.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the same focused pytest command. Expected: PASS.

- [ ] **Step 5: Run the existing dataset tests**

Run:

```bash
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run pytest tests/test_dataset.py --cov=wdcgeo.dataset
```

Expected: all dataset tests pass and the changed module reaches 100% line and branch coverage.

- [ ] **Step 6: Commit the stats contract**

```bash
git add src/wdcgeo/dataset.py tests/test_dataset.py
git commit -m "feat: profile published dataset shards"
```

### Task 2: Replace the long card section and add the statistics/type sections

**Files:**
- Modify: `src/wdcgeo/dataset.py`
- Modify: `src/wdcgeo/card.md`
- Create: `src/wdcgeo/types.md`
- Modify: `tests/test_dataset.py`

- [ ] **Step 1: Add failing card assertions**

Update the card tests to require all of the following after `write_dataset`:

```python
assert "## Parts read" not in card
assert SOURCES[0] not in card
assert "## Dataset statistics" in card
assert "| Published records | 2 |" in card
assert "| Pages represented | 2 |" in card
assert "| Words in name, description, and address | 7 |" in card
assert "| Raw records before host-local deduplication | — |" in card
```

Add an assemble test that writes two part directories, calls `assemble(..., TYPES_NAME)`, and asserts the merged stats file and card contain the combined record count, input-profile raw record count, and input-profile distinct-location count. Add a test that `types_image=None` omits `Type distribution` and a named type image adds the image section.

- [ ] **Step 2: Run the updated card tests and verify RED**

Run:

```bash
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run pytest tests/test_dataset.py -q
```

Expected: FAIL because the card still renders `## Parts read`, has no statistics table, and `assemble` has no type-image argument.

- [ ] **Step 3: Implement template-driven card rendering**

Change `write_card` to accept computed stats and an optional `types_image`. Keep table labels and explanatory prose in `card.md`; pass only formatted values from Python. Use assembled profile `records` and `duplication.distinct_places` under clearly labeled input rows when available, and render `—` for optional part-level values. Replace the source list with a concise provenance sentence containing only the source-part count. Add `types_section` beside the existing map section.

Create `src/wdcgeo/types.md` containing the embedded image and the concise statement that the plot shows type assignments, the top 20 labels, and an “Other” remainder.

- [ ] **Step 4: Make assembly recompute stats from final shards**

In `assemble`, collect copied shard paths, stream every JSONL record back into `DatasetStats`, attach merged pre-dedup profile values under an `input` key, write `stats.json`, and then write the card. Return the stats filename in the manifest. Preserve existing pre-dedup `profile.json` output and map behavior.

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run:

```bash
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run pytest tests/test_dataset.py -q
```

Expected: all dataset tests pass.

- [ ] **Step 6: Commit the card and assembly changes**

```bash
git add src/wdcgeo/dataset.py src/wdcgeo/card.md src/wdcgeo/types.md tests/test_dataset.py
git commit -m "feat: add computed dataset card statistics"
```

### Task 3: Add the type plot command and update CLI goldens

**Files:**
- Modify: `src/wdcgeo/cli.py`
- Create: `scripts/render_types.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Update the CLI golden test first**

Add the `--types NAME` option to the expected `assemble --help` text and test that `main(["assemble", "--help"])` exposes it. Keep all other help text byte-for-byte unchanged.

- [ ] **Step 2: Run the CLI golden and verify RED**

Run:

```bash
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run pytest tests/test_cli.py -q
```

Expected: FAIL because the parser does not yet expose `--types`.

- [ ] **Step 3: Implement the CLI option**

Add `TYPES_HELP`, parse `--types` into `types_image`, and pass it as the final optional image name to `assemble`. Do not add data-processing logic to the CLI.

- [ ] **Step 4: Run the CLI tests and verify GREEN**

Run the same CLI pytest command. Expected: all CLI tests pass.

- [ ] **Step 5: Implement the plotting script**

Create `scripts/render_types.py` with:

```bash
uv run python scripts/render_types.py data/dataset/stats.json --out data/dataset/types.png
```

It must read the complete `types` mapping from `stats.json`, sort by count, draw the 20 most frequent labels horizontally, aggregate the rest as `Other`, annotate counts, use a readable single-hue design, save a deterministic PNG with the non-interactive matplotlib backend, and print a compact JSON summary. Keep it outside `src/` so matplotlib remains dev-only.

- [ ] **Step 6: Commit the CLI and plot**

```bash
git add src/wdcgeo/cli.py scripts/render_types.py tests/test_cli.py
git commit -m "feat: render dataset type distribution"
```

### Task 4: Refresh documentation and add a reproducible Hub metadata refresh path

**Files:**
- Modify: `docs/design.md`
- Create: `scripts/refresh_hub_metadata.py`
- Modify: `README.md` only if generated card/stat semantics require a current command example

- [ ] **Step 1: Document the metadata contract**

Document that `profile.json` remains pre-dedup, `stats.json` describes published rows, and `types.png` is rendered from complete type counts. State that page counts are stream transitions and word counts cover `name`, `description`, and `address`.

- [ ] **Step 2: Implement the refresh script**

Create `scripts/refresh_hub_metadata.py` to accept JSONL.GZ paths or URLs, stream them one at a time through `DatasetStats`, read the existing pre-dedup `profile.json`, attach input counts, write `stats.json`, render the card through the normal template writer, and leave existing data shards untouched. It must accept a source-part count without embedding individual part URLs in the card.

- [ ] **Step 3: Run a local smoke refresh**

Create a temporary two-shard fixture from the test records, run the script, and verify generated `stats.json`, card, and type-plot input. Do not use the 33 GB corpus for the test.

- [ ] **Step 4: Commit reproducibility and documentation changes**

```bash
git add docs/design.md scripts/refresh_hub_metadata.py README.md
git commit -m "docs: describe published dataset metadata"
```

### Task 5: Run all quality gates and publish

**Files:**
- No further source changes unless a verification failure requires a RED→GREEN fix.

- [ ] **Step 1: Format and run the complete local test gate**

```bash
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run ruff format src tests
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run pytest --cov=wdcgeo
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run ruff check src tests
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run ty check
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run python scripts/crap.py
```

Expected: 100% line and branch coverage, Ruff clean, ty clean, and every function below CRAP 6.

- [ ] **Step 2: Run mutation testing to zero survivors**

```bash
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run mutmut run
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run mutmut results
```

Expected: zero surviving mutants. If any survive, add or correct a behavior test or simplify the design; never loosen the gate.

- [ ] **Step 3: Build documentation**

```bash
UV_CACHE_DIR=/private/tmp/schema-dot-org-uv-cache uv run mkdocs build --strict
```

Expected: successful strict build.

- [ ] **Step 4: Compute real metadata from current Hub shards**

Use the refresh script against every current `NoeFlandre/schema-dot-org` `data/*.jsonl.gz` shard, retaining bounded memory and no local full-dataset copy where possible. Reuse the existing Hub `profile.json` for explicitly labeled pre-dedup rows, render `types.png`, and inspect the final `README.md` for the absence of `## Parts read`, the statistics table, and both image sections.

- [ ] **Step 5: Verify generated artifacts locally**

Check that `stats.json` record count equals rows streamed, type-count sum equals type assignments, `types.png` is a non-empty PNG, and card values match `stats.json` rather than hard-coded numbers.

- [ ] **Step 6: Push GitHub code and verify the remote ref**

Merge the feature branch into `main`, push `main` to `origin`, and verify `git ls-remote origin refs/heads/main` equals local `HEAD`. Preserve published HF data shards.

- [ ] **Step 7: Upload only metadata artifacts to Hugging Face**

From the generated artifact directory, run:

```bash
hf upload NoeFlandre/schema-dot-org README.md README.md --repo-type dataset --commit-message "Update dataset card statistics and type plot"
hf upload NoeFlandre/schema-dot-org stats.json stats.json --repo-type dataset --commit-message "Publish computed dataset statistics"
hf upload NoeFlandre/schema-dot-org types.png types.png --repo-type dataset --commit-message "Add dataset type distribution plot"
```

Verify with `hf datasets info NoeFlandre/schema-dot-org` and a fresh metadata download that the new card, `stats.json`, and `types.png` are present and the existing `data/*.jsonl.gz` shard count is unchanged.

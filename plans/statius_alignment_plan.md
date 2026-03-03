# Plan: Statius Alignment Pipeline

## Context

We need to align Statius (Thebaid, Achilleid, Silvae) using the Latin text from Perseus `canonical-latinLit/data/phi1020/` and the public-domain English translation by J.H. Mozley (Loeb, 1928 — PD since 2024 under 95-year rule). The English is sourced from Wikisource (CC BY-SA), which has hand-transcribed Mozley text for Thebaid and Achilleid.

This is the first Latin alignment, following the Diodorus Siculus Greek alignment pipeline (`scripts/alignment/`). The pipeline is kept in a separate directory so Diodorus work is not disturbed.

## Core Approach: English-Driven with Latin Milestones

Same pattern as Diodorus (see `scripts/alignment/08_generate_perseus_tei.py`):

1. **Mozley's English is the driver** — his paragraph structure provides the TEI skeleton
2. The DP alignment determines which Latin line ranges correspond to each English paragraph
3. Latin line references (e.g. `book.line`) are inserted as `<milestone>` elements within Mozley's English paragraphs
4. The final TEI preserves every Mozley paragraph in its original position

In Diodorus: Booth's English paragraphs are the structure, Greek `chapter.section` refs are milestones.
In Statius: Mozley's English paragraphs are the structure, Latin `book.line` refs are milestones.

**Verse challenge:** Latin verse lines (~40 chars) are too short for embedding similarity. They must be pre-grouped into ~10-line passages (~400 chars) as DP alignment units. But the milestones still record individual line numbers, not passage boundaries.

## Scope

**Phase 1:** Thebaid (12 books) + Achilleid (2 books) — both on Theoi.com
**Phase 2 (future):** Silvae (5 books) — blocked. Theoi.com does not host the Silvae. The only digital Mozley Silvae is OCR from Archive.org (unusable). Wikisource has a stub page but no transcribed text. Requires a hand transcription of Mozley's Silvae from the scanned Loeb (Archive.org) before alignment can proceed.

New scripts in `scripts/alignment_statius/`. New outputs in `output/statius/`. Reuses `models/latin-embedding/` (92.6% Top-1).

---

## Scripts (9 files in `scripts/alignment_statius/`)

### Step 1: `01_scrape_mozley.py` — Fetch English from Wikisource

- Fetch Thebaid Books 1-12 and Achilleid Books 1-2 from Wikisource (CC BY-SA)
- Uses MediaWiki parse API to get clean HTML, extracts `<p>` elements with BeautifulSoup
- Save to `data-sources/statius_mozley/thebaid_raw.json` and `achilleid_raw.json`
- Structure: `{"source": "...", "license": "CC BY-SA", "books": [{"book": 1, "paragraphs": [{"text": "...", "char_count": N}]}]}`
- Rate-limit requests (1s delay between pages)
- Cache locally — only fetch if files don't exist

**Wikisource pages:** `Statius_(Mozley_1928)_v1/Thebaid/Book_1` through `Book_4` (vol 1), `Statius_(Mozley_1928)_v2/Thebaid/Book_5` through `Book_12` and `Achilleid/Book_1`, `Book_2` (vol 2)

### Step 2: `02_extract_latin_tei.py` — Extract Latin verse from Perseus TEI

- Adapted from `scripts/alignment/02_extract_perseus.py`
- Parse `data/phi1020/phi001/` (Thebaid) and `phi003/` (Achilleid)
- Extract verse lines from `<l n="...">` elements within `<div subtype="book">`
- Output: `output/statius/latin_extracted.json`
- Each line preserves its `n` attribute (line number) for milestones

**Perseus TEI structure (phi1020):**
- `phi001` = Thebaid: `div[@subtype="book"]` → `l[@n]` (12 books, ~9,742 lines)
- `phi003` = Achilleid: same structure (2 books, ~1,127 lines)

### Step 3: `03_normalise_mozley.py` — Light English normalisation

- Adapted from `scripts/alignment/03_normalise_booth.py`
- Much simpler than Booth: Mozley is modern English (1928), no archaic spelling
- Normalise whitespace, strip any HTML artifacts, fix encoding oddities
- Output: `output/statius/mozley_normalised.json`

### Step 4: `04_segment_latin_lines.py` — Group verse lines into alignment passages

Pre-groups consecutive Latin verse lines into passages (~8-12 lines) as alignment units for the DP. This step is needed because individual lines (~40 chars) are too short for meaningful embedding similarity. Each passage records the line range it covers (e.g. lines 1-10) so milestones can trace back to individual lines.

- Segmentation heuristic: accumulate lines until 8+ lines reached, then break at the next sentence boundary (line ending with `.` `?` `!`)
- Output: `output/statius/latin_passages.json`
- Structure: passages with `first_line`, `last_line`, concatenated `text`, `char_count`

### Step 5: `05_align_books.py` — Match Latin books to Mozley books

- Straightforward 1:1 mapping (Thebaid 1-12, Achilleid 1-2)
- Validates both sides exist; counts passages and paragraphs per book
- Output: `output/statius/book_alignment.json`

### Step 6: `06_embed_and_align.py` — Segmental DP alignment (English-driven)

- Adapted from `scripts/alignment/05_embed_and_align.py`
- Uses `models/latin-embedding/` (v2, 92.6% accuracy)
- Per book: embeds Latin passages and English paragraphs, runs segmental DP
- DP groups 1-5 Latin passages onto 1-2 English paragraphs (same as Diodorus)
- **Records one alignment per Latin passage** pointing to its matched English paragraph(s)
- The English paragraphs are the fixed structure; the DP finds where Latin passages attach
- Output: `output/statius/section_alignments.json`, `section_alignments.tsv`

### Step 7: `07_entity_anchors.py` — Validate with named entities

- Adapted from `scripts/alignment/06_entity_anchors.py`
- Simplified vs Diodorus: Latin names pass nearly directly to English (Achilles → Achilles, Thebae → Thebes) — no Greek transliteration needed
- Latin NER: regex for capitalised Latin words
- English NER: spaCy `en_core_web_sm`
- Cross-lingual matching: direct string + simple Latin→English name mapping (e.g. -ae → -e)
- Output: `output/statius/entity_validated_alignments.json`

### Step 8: `08_generate_outputs.py` — Final TEI + reports (English-driven output)

- Adapted from `scripts/alignment/07_generate_outputs.py` + `08_generate_perseus_tei.py`
- **TEI structure follows Mozley** — each Mozley paragraph emitted in order
- Latin line milestones placed before the English paragraph they correspond to: `<milestone unit="line" n="book.first_line"/>`
- Generates:
  - `output/statius/alignment_statius_perseus.xml` — TEI standoff alignment
  - `output/statius/alignment_statius_perseus.tsv` — tabular format
  - `output/statius/alignment_report.md` — quality report
  - `output/statius/phi1020.phi001.perseus-eng80.xml` — Perseus-compatible TEI (Thebaid)
  - `output/statius/phi1020.phi003.perseus-eng80.xml` — Perseus-compatible TEI (Achilleid)
- CTS URN: `urn:cts:latinLit:phi1020.phi001.perseus-eng80` (28 = Mozley 1928)

### `run_statius_pipeline.sh` — Run all steps sequentially

---

## Files Created

| File | Description |
|---|---|
| `scripts/alignment_statius/01_scrape_mozley.py` | Fetch + parse Theoi.com HTML |
| `scripts/alignment_statius/02_extract_latin_tei.py` | Extract Latin verse from Perseus TEI |
| `scripts/alignment_statius/03_normalise_mozley.py` | Light English normalisation |
| `scripts/alignment_statius/04_segment_latin_lines.py` | Group verse lines into alignment passages |
| `scripts/alignment_statius/05_align_books.py` | Book-level matching |
| `scripts/alignment_statius/06_embed_and_align.py` | English-driven segmental DP alignment |
| `scripts/alignment_statius/07_entity_anchors.py` | Entity-based validation |
| `scripts/alignment_statius/08_generate_outputs.py` | Final TEI (English structure + Latin milestones) |
| `scripts/alignment_statius/run_statius_pipeline.sh` | Run all steps |
| `plans/statius_alignment_plan.md` | This plan |

## Directory Layout

```
data-sources/statius_mozley/       # Cached Theoi.com HTML + parsed JSON
output/statius/                    # All intermediate + final outputs
scripts/alignment_statius/         # All scripts (separate from Diodorus)
```

## Dependencies

- Same venv (`.venv`): lxml, beautifulsoup4, requests, sentence-transformers, spacy, rapidfuzz, unidecode
- Model: `models/latin-embedding/` (already trained, 92.6% Top-1)
- Data: `data-sources/perseus/canonical-latinLit/data/phi1020/` (already cloned)

## Verification

1. After step 1: check JSON files — 12 Thebaid books, 2 Achilleid books of paragraphs
2. After step 2: check line counts — ~9,742 Thebaid + ~1,127 Achilleid lines
3. After step 4: check passage count — ~800-1,200 Thebaid passages (~10 lines each)
4. After step 6: check alignment — every English paragraph should have Latin line milestones; target mean similarity > 0.5
5. After step 7: entity overlap score distribution
6. After step 8: XML well-formedness; every Latin line number covered by a milestone

## Risk: Verse-to-Prose Alignment Quality

Diodorus aligned prose-to-prose (~200 char sections both sides). Statius is verse-to-prose:

- Latin verse has enjambment (sentences span multiple lines)
- Mozley's prose may reorder content for readability

**Mitigation:** Step 4 groups lines at sentence boundaries to create ~400-char passages comparable to English paragraphs. If quality is low, adjust group size (try 15 lines) or tighten the DP banding constraint.

---
name: add-work
description: Analyse feasibility and add a new ancient work to the pipeline given an English translation
argument-hint: <english-source-path-or-gutenberg-id>
effort: max
---

# Add a new work to the diodorus pipeline

You are adding a new English translation to pair with an existing Greek-only
(or Latin-only) text in Perseus or First1KGreek. The user is providing you
with an English translation source. Your job is to analyse feasibility, then
if viable, create the work directory with config.json, extract_greek.py, and
extract_english.py.

The argument is: $ARGUMENTS

## CRITICAL RULES (from CLAUDE.md — never break these)

- Never lose or reorder any Greek or English text
- All source text must appear in the output
- All text must be in strict original order
- Do NOT work on texts that already have English in Perseus or First1KGreek
- Always use a venv and never run --break-system-packages
- Never modify anything outside this project folder
- Never run rm -rf

## Phase 1: Analyse the English source

Read the English source file. If the argument is a Gutenberg ID (a number),
find it in `data-sources/gutenberg/pg_catalog.csv` first, then download it:

```
curl -sL "https://www.gutenberg.org/cache/epub/<ID>/pg<ID>.txt" \
  -o data-sources/gutenberg/<name>/<filename>.txt
```

Determine:

1. **What work is this a translation of?** Identify the ancient author and
   work title. Look for the translator name and date on the title page.

2. **What is the text structure?** Analyse the English text for:
   - Book/chapter/section hierarchy (numbered divisions)
   - Section numbering scheme (Roman numerals, Arabic numbers, named chapters)
   - Headers, appendices, indices to strip
   - Gutenberg header/footer markers to remove
   - Encoding issues (long-s, early-modern spelling, smart quotes)
   - Commentary mixed with translation text (common in older editions)
   - Speaker labels (for dramatic works)
   - **Footnote format**: identify which pattern is used (indented `[A]` blocks,
     FOOTNOTES sections per chapter/book/end-of-file, inline `[Footnote N: ...]`,
     or none). Count how many footnotes exist. Sample 2-3 to confirm
     `strip_notes()` will parse them correctly. This is a common source of bugs.

3. **Section count and granularity**: How many sections does the English have?
   What level of granularity (per-sentence, per-paragraph, per-chapter)?

Report these findings clearly before proceeding.

## Phase 2: Find the source language text

Search for the corresponding Greek or Latin text:

1. Check Perseus: `ls data-sources/perseus/canonical-greekLit/data/` for the
   TLG ID, or `data-sources/perseus/canonical-latinLit/data/` for Latin PHI ID.

2. Check First1KGreek: `ls data-sources/greek_corpus/First1KGreek/data/` for
   the TLG ID.

3. If you don't know the TLG/PHI ID, search by author name in the directory
   listings or grep the `__cts__.xml` catalog files.

4. **Check for existing English**: Look inside the source data directory for
   files with `eng` in the filename. If an English translation already exists
   in Perseus or First1KGreek, STOP — this work is out of scope for the
   project. Report this to the user.

5. **Check not already done**: Look in `scripts/works/` for an existing work
   directory that covers this author/work. If it exists, STOP and report.

Once found, read the source TEI XML to determine:
- The XML structure (div hierarchy: book/chapter/section)
- How sections are numbered (the `n` attribute on div elements)
- The edition identifier (filename stem, e.g., `tlg0562.tlg001.perseus-grc2`)
- Total section count and granularity
- Namespace usage (TEI `{http://www.tei-c.org/ns/1.0}` or bare)

## Phase 3: Feasibility assessment

Before writing any code, report a feasibility assessment:

### Alignment viability

| Factor | Value | Notes |
|--------|-------|-------|
| English sections | N | |
| Source sections | N | |
| Section ratio | N:1 | Ideal < 5:1 |
| CTS ref compatibility | high/medium/low | Do numbering schemes match? |
| Structural match | good/partial/poor | Same book/chapter divisions? |
| Translation style | literal/paraphrase | Older = more paraphrase |
| Commentary contamination | none/some/heavy | Mixed with translation? |
| Footnote format | none/indented/FOOTNOTES/inline | Which pattern? How many? |
| Recommended alignment_mode | dp/pairwise | Sequential → dp, non-sequential → pairwise |
| Feasibility rating | EASY/MODERATE/HARD | |

### Key risks

List specific risks: numbering mismatches, missing books, commentary that
needs stripping, encoding issues, verse-to-prose domain gap, etc.

### Recommended approach

Which existing work's extraction scripts to use as a template, and what
modifications are needed.

**Wait for user confirmation before proceeding to Phase 4.**

## Phase 4: Create the work

### 4a. Download / place the English source

If not already done, download and save the English text to `data-sources/`.
Add the source to `LICENSE.txt`.

### 4b. Create work directory

Create `scripts/works/<name>/` with three files:

#### config.json

Use the appropriate template. Key decisions:
- `alignment_mode`: `"dp"` for sequential prose/verse, `"pairwise"` for
  non-sequential (fables, epigrams, disconnected fragments)
- `multi_work`: `true` only if one config covers multiple CTS works
- `source_language`: `"greek"` or `"latin"`
- `greek_source.type`: `"perseus"` or `"first1kgreek"`

Reference configs to copy from:
- Simple Gutenberg prose: `scripts/works/marcus/config.json`
- First1KGreek source: `scripts/works/aesop/config.json`
- Multi-work: `scripts/works/iamblichus/config.json`
- Latin source: `scripts/works/statius/config.json`
- Pairwise mode: `scripts/works/aesop/config.json`

#### extract_greek.py (or extract_latin.py)

Parse the source TEI XML into `build/<name>/greek_sections.json`.

Reference scripts to copy from:
- Perseus prose with book/chapter/section: `scripts/works/marcus/extract_greek.py`
- Perseus with complex hierarchy: `scripts/works/diodorus/extract_greek.py`
- First1KGreek: `scripts/works/aesop/extract_greek.py`
- Latin: `scripts/works/statius/extract_latin.py`

Key patterns:
- `PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent`
- Output to `PROJECT_ROOT / "build" / "<name>" / "greek_sections.json"`
- `mkdir(parents=True, exist_ok=True)` on output dir
- Strip namespace: `tag = str(elem.tag).split("}")[-1]`
- Walk parent hierarchy for book/chapter numbers
- Include `edition` field from XML filename stem
- Sort sections by CTS ref components

#### extract_english.py

Parse the English text into `build/<name>/english_sections.json`.

Reference scripts to copy from:
- Gutenberg plain text with numbered sections: `scripts/works/marcus/extract_english.py`
- Gutenberg with chapter structure: `scripts/works/theophrastus/extract_english.py`
- TEI XML English: `scripts/works/diodorus/extract_english.py`
- Dramatic works with speakers: `scripts/works/hickie_extract_play.py`

Key patterns:
- Strip Gutenberg `*** START/END ***` markers
- Normalise encoding: UTF-8 BOM, CRLF, smart quotes
- `book` field must use same values as Greek extraction
- `cts_ref` should match Greek numbering scheme where possible

#### Footnote handling (important — get this right)

Footnotes have caused bugs in multiple works (Arrian, Achilles Tatius,
Iamblichus, Theophrastus). The core issue: if you truncate or strip the
FOOTNOTES section from the raw text *before* `strip_notes()` processes it,
the footnote bodies are lost and TEI output gets empty `<note/>` elements.

`strip_notes()` from `scripts/pipeline/strip_notes.py` handles three formats:
1. **Indented blocks**: 4+ spaces followed by `[A]`, `[B]`, `[1]` (e.g., Long's Marcus)
2. **FOOTNOTES sections**: End-of-chapter blocks with `[Footnote N: text]` or `[N]` markers
3. **Inline sidenotes**: `[Sidenote: ...]` markers

The correct pattern — used in the fixed Arrian extraction — is:

```python
# 1. Parse the FOOTNOTES section FIRST to extract bodies
footnotes_pos = text.find("\nFOOTNOTES:\n")
if footnotes_pos == -1:
    footnotes_pos = text.find("\nFOOTNOTES\n")
footnote_bodies = {}
if footnotes_pos != -1:
    footnotes_text = text[footnotes_pos:]
    _, parsed_notes = strip_notes(footnotes_text)
    for note in parsed_notes:
        footnote_bodies[note["marker"]] = note["text"]
    # THEN remove the section from main text
    text = text[:footnotes_pos]

# 2. For each section, strip inline markers AND attach FOOTNOTES bodies
clean, notes = strip_notes(section_body)
for m in re.finditer(r'\[(\d+)\]', section_body):
    marker = f"[{m.group(1)}]"
    if marker in footnote_bodies:
        existing = [n for n in notes if n["marker"] == marker]
        if existing:
            if not existing[0]["text"]:
                existing[0]["text"] = footnote_bodies[marker]
        else:
            notes.append({"marker": marker, "text": footnote_bodies[marker]})
```

The output must always include:
- `text`: full original text with footnote markers preserved (e.g., `[1]`)
- `text_for_embedding`: clean text with markers and bodies removed
- `notes`: list of `{"marker": "[1]", "text": "footnote body"}` dicts

Common footnote formats to watch for across Gutenberg texts:
- **Per-chapter FOOTNOTES section** (Arrian, Achilles Tatius): appears after
  each chapter's text
- **Per-book FOOTNOTES section** (some editions): one block at end of each book
- **End-of-file FOOTNOTES** (some editions): single block at the very end
- **Inline `[Footnote N: ...]`** (older Gutenberg formatting): embedded in text
- **Lettered notes `[A]`, `[B]`** (Marcus Long): indented blocks with letter markers
- **No footnotes** (some editions): nothing to do, but verify — don't assume

When analysing the English source in Phase 1, explicitly identify which
footnote format is used and how many footnotes exist. Sample a few to confirm
`strip_notes()` handles them correctly before writing the extraction script.

### Output format (both scripts)

```json
{
  "sections": [
    {
      "book": "1",
      "section": "3",
      "cts_ref": "1.3",
      "edition": "tlg0000.tlg001.perseus-grc2",
      "text": "Full section text...",
      "text_for_embedding": "Clean text for embeddings...",
      "notes": [{"marker": "[1]", "text": "Footnote body"}],
      "char_count": 456
    }
  ]
}
```

The `book` field is the grouping key for DP alignment. The `cts_ref` must be
unique across all sections.

## Phase 5: Test extraction

Run the extraction scripts individually first:

```bash
source .venv/bin/activate
python scripts/works/<name>/extract_greek.py
python scripts/works/<name>/extract_english.py
```

Verify:
- Both scripts complete without errors
- Section counts are reasonable (report them)
- Book values overlap between Greek and English
- CTS refs have compatible structure
- No empty sections or missing text
- Sample a few sections from each to confirm text quality

If extraction fails or produces bad output, fix the scripts before proceeding.

## Phase 6: Run the pipeline

```bash
source .venv/bin/activate
python scripts/pipeline/run.py <name>
```

This runs: extract → embed → align → score → generate outputs → integrity check.

Report the results:
- Did integrity checks pass?
- What are the quality metrics (green/yellow/red percentages, average score)?
- Any warnings or errors?

## Phase 7: Verify output

Check the generated files in `build/<name>/`:
- Open the SVG quality map — describe the color distribution
- Sample the HTML parallel text — spot-check 3-5 alignments
- Report any obvious misalignments

If quality is poor (avg < 0.3), diagnose the cause using the assessment from
Phase 3 and suggest fixes.

## Phase 8: Update documentation

- Add the work to `LICENSE.txt` with source and translator info
- Update `plans/easy_works_implementation.md` with the new work's details

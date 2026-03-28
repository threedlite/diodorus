never modify anything on the system or outside this folder.
only the user can run brew.
always use a venv and never run --break-system-packages
always be thoughtful, thorough, and truthful with yourself about what you did and didnt do
always document your plans in md files in the project
always update md doc files if something changes
dont be lazy; be thorough and careful
avoid quick fixes; make fixes as general as possible
never run rm -rf


CRITICAL: Never lose or reorder any Greek or English text. This is an absolute rule.


## Project goal
Add English translations to ancient Greek works that currently only have Greek
text in Perseus and First1KGreek. We use Gutenberg and Wikisource as the source of public domain/CC-BY-SA
English translations to pair with Greek-only texts. Do NOT work on texts that
already have English in Perseus or First1KGreek — that is not the point.

## Alignment rules (NEVER BREAK)
1. All source text must appear in the output — no text may be skipped or dropped
2. All text must be in strict original order — no reordering ever
3. Alignment quality between Greek and English sections is best-effort — imprecise
   matches are acceptable, but every section of both source and target must be
   present and in order
4. The quality map must honestly report unmatched and low-confidence sections

## Pipeline overview

`scripts/pipeline/run.py --all` runs all 35 works through:
extract → align → score → generate outputs → integrity check → publish to `final/`

### Alignment algorithm (`scripts/pipeline/align.py`)

1. **CTS ref matching** — match by section number (exact → parent → split-from →
   prefix → chapter-sibling). Chapter-sibling: when Greek `11.8.2` has no match,
   checks if there's exactly one English section in chapter `11.8.*`.
2. **CTS-first alignment** — when CTS covers >50% of a book:
   - CTS matches become fixed pairs (match_type: `cts_aligned`)
   - Gaps between CTS anchors are filled by DP sub-problems
   - Small gaps (≤3 sections) are assigned to nearest English, not DP'd
   - Replaces the old 100%-only CTS override
3. **Two-pass embedding DP** (for books with <50% CTS):
   - First pass: embedding cosine + entity overlap
   - Build PMI-weighted Greek→English lexical table from first-pass alignment
   - Second pass: embedding + combined entity/lexical matrix
4. **Refinement** — split English text at sentence boundaries to match multiple
   Greek sections. Match_type tagged as `cts_refined` or `dp_refined`.

### Scoring formula (`scripts/pipeline/entity_anchors.py`)

Two paths depending on match provenance:

**CTS-confirmed matches** (`cts_aligned` / `cts_refined`):
```
content = max(primary, embedding_cosine)    # full embedding weight
score = content × length_penalty
score = max(score, 0.5)                     # CTS floor: never below yellow
No sharing penalty, no length veto
```

**DP-only matches** (`dp_aligned` / `dp_refined`):
```
primary = max(entity, lexical, speaker)
content = primary if ≥0.3, else max(primary, embedding×0.5), else embedding
score = content × length_penalty
if non-1:1 and not refined: score *= 1/sqrt(sharing_count)
if length_pen < 0.1 and entity < 0.3 and sim < 0.99: score = 0 (no_match)
```

Thresholds: green ≥ 0.50, yellow ≥ 0.20, red < 0.20
Lexical normalization: auto-calculated P95 per work

### Key files

- `scripts/pipeline/lexical_overlap.py` — PMI-based bilingual lexical overlap
- `scripts/build_lexicon.py` — builds `build/global_lexical_table.pkl` (40K Greek words)
- `scripts/word_count_report.py` — generates `final/word_count_comparison.md`
- `scripts/alignment_quality_map.py` — clickable SVG quality maps
- `plans/` — design docs, analysis, rollout notes

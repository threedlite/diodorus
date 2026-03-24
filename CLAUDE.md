never modify anything on the system or outside this folder.
only the user can run brew.
always use a venv and never run --break-system-packages
always be thoughtful, thorough, and truthful with yourself about what you did and didnt do
always document your plans in md files in the project
always update md doc files if something changes
dont be lazy; be thorough and careful
avoid quick fixes; make fixes as general as possible
never run rm -rf


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

1. **CTS ref matching** — match by section number (exact → parent → split-from → prefix)
2. **Two-pass embedding DP** — segmental DP with entity + lexical matrix
   - First pass: embedding cosine + entity overlap
   - Build PMI-weighted Greek→English lexical table from first-pass alignment
   - Second pass: embedding + combined entity/lexical matrix
3. **Refinement** — split English text at sentence boundaries to match multiple Greek sections
4. **CTS override** — when CTS covers 100%, use it instead of DP

### Scoring formula (`scripts/pipeline/entity_anchors.py`)

```
lex_norm = min(1.0, lexical_score / 0.25)

score = (1 - ent_weight) × (0.4 × embedding_cosine
                           + 0.3 × lex_norm
                           + 0.3 × length_ratio_penalty)
      + ent_weight × entity_overlap

if non-1:1 and not refined: score *= 1/sqrt(sharing_count)
combined_score = min(1.0, score)
```

- **embedding_cosine**: cross-lingual embedding similarity (custom ancient-greek model)
- **lex_norm**: PMI-weighted bilingual word overlap (from global lexicon, 40K entries)
- **length_ratio_penalty**: Gaussian on char-ratio deviation from expected
- **entity_overlap**: proper name transliteration matching (evidence-adaptive weight)
- **sharing penalty**: 1/sqrt(N) for non-1:1 mappings not split by refinement

Thresholds: green ≥ 0.50, yellow ≥ 0.25, red < 0.25

### Key files

- `scripts/pipeline/lexical_overlap.py` — PMI-based bilingual lexical overlap
- `scripts/build_lexicon.py` — builds `build/global_lexical_table.pkl` (40K Greek words)
- `scripts/word_count_report.py` — generates `final/word_count_comparison.md`
- `scripts/alignment_quality_map.py` — clickable SVG quality maps
- `plans/` — design docs, analysis, rollout notes

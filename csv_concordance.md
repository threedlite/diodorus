# CSV Concordance Export from the Synthetic Lexical Table

## Background

The alignment pipeline maintains a synthetic Greek→English dictionary in
`build/global_lexical_table.pkl` (22 MB pickle). It contains **89,447 Greek
headwords** mapped to **700,649 translation pairs**, built from ~52,910 aligned
section pairs across Perseus and the project's 35 works using PMI-weighted
co-occurrence statistics. This dictionary is currently opaque — only accessible
via Python pickle loading — making it difficult to inspect, audit, share, or
reuse outside the pipeline.

## Goal

Produce a human-readable CSV concordance (`build/greek_english_concordance.csv`) that
exposes every Greek word and its weighted English translation candidates,
suitable for:

1. **Auditing** — spot-check translation quality, find corpus bias artifacts
2. **Scholarship** — a reusable Greek→English frequency-weighted concordance derived
   from aligned historical prose
3. **Downstream tools** — import into spreadsheets, databases, or other NLP
   pipelines without Python pickle dependency
4. **Documentation** — make the "synthetic dictionary" a visible, reviewable
   project artifact

## Proposed CSV Schema

```
greek,english,weight,rank,cooccur_count,greek_idf
```

| Column          | Type    | Description |
|-----------------|---------|-------------|
| `greek`         | string  | Greek word form as extracted (no lemmatization) |
| `english`       | string  | English translation candidate |
| `weight`        | float   | Normalized PMI weight (0.0–1.0, per Greek word) |
| `rank`          | int     | Rank among translations for this Greek word (1 = best) |
| `cooccur_count` | int     | Raw co-occurrence count before PMI weighting |
| `greek_idf`     | float   | IDF of the Greek word (higher = rarer/more informative) |

### Example rows

```csv
greek,english,weight,rank,cooccur_count,greek_idf
θάνατος,death,0.5098,1,847,4.21
θάνατος,penalty,0.0712,2,203,4.21
θάνατος,life,0.1064,3,312,4.21
ναῦς,ships,0.3095,1,524,5.67
ναῦς,fleet,0.2110,2,301,5.67
στρατηγός,general,0.3491,1,612,5.12
πόλις,city,0.4200,1,1893,3.05
```

### Sort order

Primary: `greek` (alphabetical by Unicode codepoint), secondary: `rank` (ascending).
This groups all translations for a word together and lists the best first.

## Filtering options

The export script should support optional CLI flags to produce slimmer variants:

| Flag | Default | Effect |
|------|---------|--------|
| `--min-weight` | 0.01 | Drop translations below this weight |
| `--min-cooccur` | 3 | Drop pairs seen fewer than N times |
| `--max-rank` | 10 | Keep only top-K translations per word (already capped at 10 in build) |
| `--top-only` | off | If set, emit only rank-1 translation per word |

With defaults, the full concordance would contain all ~700K rows. With
`--min-weight 0.05 --max-rank 5`, a more practical ~200K-row subset.

## Additional output: summary statistics header

The CSV should include a comment header (lines starting with `#`) with build
metadata:

```
# Greek-English Concordance — auto-generated from global_lexical_table.pkl
# Generated: 2026-04-04
# Source pairs: 52910 (Perseus + 35 aligned works)
# Greek headwords: 89447
# Translation pairs: 700649
# PMI threshold: >0, min cooccur: 3, max translations: 10
# WARNING: Forms are uninflected surface forms, not lemmas
```

## Implementation plan

### New script: `scripts/export_concordance.py`

1. Load `build/global_lexical_table.pkl` (the existing pickle)
2. Optionally reload raw co-occurrence counts from `build_lexicon.py` internals
   to populate `cooccur_count` — or store counts in the pickle at build time
   (requires a small change to `build_lexicon.py` to preserve raw counts
   alongside normalized weights)
3. Iterate `src2en` dict, join with `src_idf`, rank translations per word
4. Write CSV with Python `csv` module (proper quoting for any edge cases)
5. Print summary statistics to stderr

### Change to `build_lexicon.py`

Add `cooccur_counts` to the saved pickle so the export can include raw counts
without re-deriving them. This is a backward-compatible addition (existing code
that loads only `src2en`, `src_idf`, `en_idf` still works via `.get()`).

### Integration

- Add `export-concordance` as a pipeline step (optional, not in the default
  `--all` path since it's a reporting artifact)
- Output to `build/greek_english_concordance.csv`
- Optionally copy a filtered version to `final/` for publication

## Known limitations to document

1. **No lemmatization** — inflected forms appear as separate entries (e.g.,
   θανάτου, θάνατον, θανάτῳ are all separate from θάνατος). This is a feature
   for alignment purposes but a limitation for concordance use.
2. **Corpus bias** — the concordance reflects the genres present in the corpus
   (heavily historical prose: Diodorus, Dionysius, Procopius). Philosophical or
   poetic vocabulary is underrepresented.
3. **Co-occurrence ≠ translation** — PMI captures statistical association, not
   verified translation equivalence. High-weight pairs are *likely* translations
   but include some semantic-field associations (e.g., θάνατος→life).
4. **No part-of-speech tagging** — nouns, verbs, adjectives, and particles are
   mixed without distinction.

## Implementation status

**Completed 2026-04-04.** All changes implemented and tested:

- `scripts/pipeline/lexical_overlap.py` — `build_lexical_table()` now returns
  4 values (added `cooccur` Counter as 4th return)
- `scripts/build_lexicon.py` — saves `cooccur` in the pickle alongside existing
  `src2en`, `src_idf`, `en_idf`
- `scripts/pipeline/entity_anchors.py`, `scripts/pipeline/align.py` — updated
  call sites to handle 4 return values (`*_` unpacking)
- `scripts/export_concordance.py` — new script, ~90 lines

### Output

- `build/greek_english_concordance.csv` — 573,351 rows, 86,200 Greek headwords
- Built from 63,407 aligned pairs (29,880 Perseus + 9,401 First1KGreek + 24,126 project works)

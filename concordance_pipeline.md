# Greek-English Concordance Pipeline

A fully statistical pipeline that builds a Greek-English concordance with
synthetic lemma groupings from parallel text corpora. No hardcoded
morphological rules — all affixes, stems, and grouping decisions are
discovered from the data.

## How to run

```bash
# Full rebuild (order matters):
python scripts/build_lexicon.py              # 1. Lexical table + reverse index
python scripts/build_greek_contexts.py       # 2. Distributional context vectors
python scripts/build_synthetic_lemmas.py     # 3. Synthetic lemma groups
python scripts/export_concordance.py         # 4. CSV concordance

# Lookup tool (uses build artifacts):
python scripts/lookup.py love
python scripts/lookup.py death
python scripts/lookup.py war --top 20
```

Steps 1-3 produce pickles in `build/`. Step 4 exports the final CSV to the
project root. The lookup tool reads the pickles directly.

## Data sources

| Source | Works | Aligned pairs |
|---|---:|---:|
| Perseus (canonical-greekLit) | 500 | 29,880 |
| First1KGreek | 40 | 9,401 |
| Project aligned works | 35 | 24,126 |
| **Total** | **575** | **63,407** |

## Pipeline steps

### Step 1: Build lexical table (`build_lexicon.py`)

Collects Greek-English section pairs from all three sources. For each pair,
extracts Greek and English content words, counts co-occurrences, and computes
PMI (pointwise mutual information) to identify statistically significant
word associations.

**Outputs:**
- `build/global_lexical_table.pkl` — PMI-weighted Greek→English dictionary
  (86K+ Greek headwords, 580K+ translation pairs), plus raw co-occurrence
  counts and source statistics
- `build/en2gr_index.pkl` — unfiltered English→Greek reverse index (36K
  English words) for the lookup tool. Built without English stopword
  filtering so common words like "death", "war", "city" are included.
- `build/stopwords.pkl` — corpus-derived stopwords (words in >10% of sections)

**Key parameters:**
- `min_cooccur=3` — minimum co-occurrence count
- `max_translations=10` — top-K translations per Greek word
- `min_weight=0.005` — minimum normalized PMI weight
- `idf_cap_percentile=90` — cap IDF at 90th percentile

### Step 2: Build context vectors (`build_greek_contexts.py`)

Scans ALL Greek text (not just parallel pairs) to build distributional
context vectors. For each Greek content word, records which other Greek
words appear within a ±5 word window.

**Processing:**
1. Extract Greek text from Perseus, First1KGreek, and aligned works
   (335K+ sections)
2. Count word co-occurrences within window
3. Apply PPMI weighting (positive pointwise mutual information)
4. Reduce to 200 dimensions via truncated SVD

**Output:** `build/greek_contexts.pkl` — 351K words × 200 dimensions

### Step 3: Build synthetic lemmas (`build_synthetic_lemmas.py`)

Six-phase unsupervised pipeline:

**Phase 1 — Bootstrap LCS clusters:**
Pairwise longest-common-substring + translation cosine scoring with
accent-insensitive matching (diacritics stripped via Unicode NFD).
4-gram candidate index on base letters. Suffix-end filter rejects pairs
sharing only a grammatical ending. Character-weighted scoring when
LCS ratio ≥ 0.8. Pairwise cluster validation (must match every member).

**Phase 2 — Discover affixes:**
From bootstrap clusters, extract suffixes (word endings that differ
between members) and prefixes (word beginnings that differ). Top 5%
by frequency become the affix inventory. ~200 suffixes and ~300 prefixes
discovered, including all standard Greek case/number/tense endings.

**Phase 3 — Unsupervised stemming:**
Strip longest matching suffix from each word's base letters, group by
stem. Prefix stripping as rescue for words that don't stem with suffix
alone. Minimum stem length: 4 base characters. Groups validated with
translation cosine to the centroid (split threshold 0.15).

**Phase 4 — Merge:**
Bootstrap clusters form the foundation. Stem groups add ungrouped words
to matching clusters or create new ones.

**Phase 5 — Distributional merge:**
Two sub-passes using the context vectors from step 2:
1. Singleton rescue: ungrouped words → cluster representatives
   (distributional cosine ≥ 0.55, LCS ≥ 3 base chars)
2. Small cluster merge: clusters ≤ 5 members → larger clusters
   (distributional cosine ≥ 0.60 between representatives)
Both passes apply suffix-end and discovered-suffix filters.

**Phase 6 — Output.**

**Outputs:**
- `build/synthetic_lemmas.pkl` — lemma_map (word → representative) and
  confidence scores
- `build/synthetic_lemmas.csv` — lemma index with forms and top English

### Step 4: Export concordance (`export_concordance.py`)

Reads the lexical table and lemma pickles, exports a human-readable CSV
sorted by Greek locale (Unicode Collation Algorithm via `pyuca`).

**Output:** `greek_english_concordance.csv` at project root

**CSV schema:**

| Column | Type | Description |
|---|---|---|
| `greek` | string | Greek word form (uninflected surface form) |
| `english` | string | English translation candidate |
| `weight` | float | Normalized PMI weight (0.0–1.0) |
| `rank` | int | Rank among translations for this word (1 = best) |
| `cooccur_count` | int | Raw co-occurrence count |
| `greek_idf` | float | Inverse document frequency |
| `synthetic_lemma` | string | Representative form of lemma group |
| `synthetic_lemma_confidence` | float | Confidence score (blank if ungrouped) |

**CLI flags:** `--min-weight`, `--min-cooccur`, `--max-rank`, `--top-only`, `--output`

### Lookup tool (`lookup.py`)

Given an English word, finds all Greek equivalents grouped by synthetic
lemma, with senses.

Uses PMI-pruned translations first (high quality). Falls back to the
unfiltered reverse index (`en2gr_index.pkl`) with PMI scoring for common
English words that were stopword-filtered from the main table.

## Current numbers

- **86,969** Greek headwords in the concordance
- **582,858** translation pair rows in the CSV
- **17,553** synthetic lemma groups covering 50,974 words (59%)
- **202** suffixes and **298** prefixes discovered from data
- **351,725** Greek words with distributional vectors (200 dims)
- **36,197** English words in the reverse lookup index

## Design principles

1. **No hardcoded morphology.** All affixes, stems, stopwords, and grouping
   rules are discovered from corpus statistics. The pipeline works on any
   language pair without modification.

2. **Statistical throughout.** PMI for translation weights, PPMI + SVD for
   distributional vectors, frequency-based affix discovery, centroid-based
   group validation.

3. **Multi-pass approach.** Each pass catches different patterns:
   - LCS for regular inflections (θάνατος/θανάτου)
   - Stemming for broader paradigms (all case forms)
   - Distributional for augments and prefix changes (ἠγάπησεν/ἀγαπῶν)

4. **Conservative validation.** Pairwise requirement for bootstrap clusters,
   centroid splitting for stem groups, suffix filters everywhere. Prefer
   missing a valid grouping over making a false merge.

## Known limitations

1. **Corpus bias.** The concordance reflects the genres present (heavily
   historical prose: Diodorus, Dionysius, Procopius). Philosophical or
   poetic vocabulary is underrepresented.

2. **Co-occurrence ≠ translation.** PMI captures statistical association,
   not verified equivalence. Some high-weight pairs are semantic-field
   associations rather than true translations.

3. **Augmented verbs partially ungrouped.** The distributional merge catches
   some (ἠγάπησεν → ἀγαπῶν) but many augmented forms remain in separate
   small clusters rather than joining the main cluster.

4. **No part-of-speech distinction.** Nouns, verbs, adjectives, and particles
   are mixed. The synthetic lemma groups sometimes merge related nouns and
   verbs (e.g., φιλοσοφία and φιλοσοφεῖν in the same group).

## File inventory

### Scripts
| Script | Purpose |
|---|---|
| `scripts/build_lexicon.py` | Build lexical table + reverse index |
| `scripts/build_greek_contexts.py` | Build distributional context vectors |
| `scripts/build_synthetic_lemmas.py` | Build synthetic lemma groups |
| `scripts/export_concordance.py` | Export CSV concordance |
| `scripts/lookup.py` | English→Greek reverse lookup |

### Exploration scripts (not part of the pipeline)
| Script | Purpose |
|---|---|
| `scripts/explore_lemma_pairs.py` | Compare character similarity metrics |
| `scripts/explore_lemma_combinations.py` | Test nonlinear score combinations |
| `scripts/explore_distributional.py` | Validate distributional similarity |

### Build artifacts
| File | Description |
|---|---|
| `build/global_lexical_table.pkl` | PMI-weighted Greek→English dictionary |
| `build/en2gr_index.pkl` | Unfiltered English→Greek reverse index |
| `build/greek_contexts.pkl` | Distributional context vectors (351K × 200) |
| `build/synthetic_lemmas.pkl` | Lemma map and confidence scores |
| `build/synthetic_lemmas.csv` | Lemma index (human-readable) |
| `build/stopwords.pkl` | Corpus-derived stopwords |
| `greek_english_concordance.csv` | Final concordance CSV (project root) |

### Design documents
| File | Purpose |
|---|---|
| `plans/unsupervised_stemming.md` | Original stemming proposal |
| `plans/lookup_index.md` | Reverse index design |
| `plans/lexicon_analysis.md` | Early lexicon quality analysis |

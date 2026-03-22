# Diodorus Project Documentation

## Purpose

Add public domain English translations to ancient Greek (and Latin) works that
currently exist only in the source language in the Perseus Digital Library and
First Thousand Years of Greek (First1KGreek) corpora.

We use Project Gutenberg, Wikisource, and EEBO-TCP as sources of freely available
English translations. The pipeline aligns source-language sections to English
sections using cross-lingual sentence embeddings, then produces structured TEI XML,
quality heatmaps, and parallel text HTML for each work.

We do NOT work on texts that already have English translations in Perseus or
First1KGreek — that is not the point of this project.

## Licensing

All sources must be **Public Domain / CC0** or **CC-BY-SA 4.0**. We do not use
CC-BY-NC or any non-commercial-only licensed material. Perseus CC-BY-SA 4.0
drives the output license: all outputs are CC-BY-SA 4.0. See `LICENSE.txt` for
full per-source attribution.

## Alignment Rules (NEVER BREAK)

1. All source text must appear in the output — no text may be skipped or dropped
2. All text must be in strict original order — no reordering ever
3. Alignment quality is best-effort — imprecise matches are acceptable, but every
   section of both source and target must be present and in order
4. The quality map must honestly report unmatched and low-confidence sections
5. Integrity checks with text hashing verify these rules at the end of every build
6. If any integrity check fails, the build halts and no files are published to `final/`

---

## Completed Works

| Author | Work | Source | English | CTS ID | High | Med | Low | Avg |
|--------|------|--------|---------|--------|:---:|:---:|:---:|:---:|
| Dionysius of Hal. | De Compositione Verborum | Perseus | Gutenberg #50212 (Roberts 1910) | tlg0081.tlg012 | 88% | 12% | 0% | 0.789 |
| Marcus Aurelius | Meditations | Perseus | Gutenberg #15877 (Long 1862) | tlg0562.tlg001 | 75% | 25% | 0% | 0.662 |
| Iamblichus | De Mysteriis | First1KGreek | Gutenberg #72815 (Taylor 1821) | tlg2023.tlg006 | 73% | 27% | 0% | 0.634 |
| Iamblichus | Life of Pythagoras | First1KGreek | Gutenberg #63300 (Taylor 1818) | tlg2023.tlg001 | 58% | 35% | 7% | 0.584 |
| Statius | Thebaid + Achilleid | Perseus | Wikisource (Mozley 1928) | phi1020.phi001/003 | 21% | 77% | 2% | 0.526 |
| Diodorus Siculus | Bibliotheca Historica | Perseus | OTA A36034 (Booth 1700) | tlg0060.tlg001 | 36% | 51% | 13% | 0.516 |
| Aesop | Fables | First1KGreek | Gutenberg #21 (Townsend 1867) | tlg0096.tlg002 | 17% | 69% | 14% | 0.455 |

### Per-work notes

**Diodorus Siculus** — Lowest scores due to Booth's 1700 translation style: long
flowing paragraphs (avg 1,366 chars in later books) covering many short Greek
sections (avg 305 chars), requiring groups of 7+ sections. Books 13 and 20 are
weakest (~40% low confidence). The DP `max_source` auto-scales per book based on
the section ratio. Early-modern spelling is normalised (long-s, doth→does, etc.).

**Statius** — First Latin work aligned. Verse presents a unique challenge: Latin
lines (~40 chars) are too short for meaningful embeddings, so lines are pre-grouped
into ~10-line passages before DP alignment. English structure (Mozley's prose
paragraphs) drives the output; Latin line references become milestone markers.
Silvae excluded (no Mozley text available). Uses the Latin embedding model.

**Aesop** — Uses pairwise matching instead of sequential DP because fables are
self-contained units in arbitrary order. Greek has 522 fables (including variants
like 4, 4b, 4c); Townsend has 311. `many_to_one=True` allows all Greek variants
to match the same English fable. The embedding model works well for fable-length
texts (~500 chars average).

**Dionysius** — Best alignment quality. 26 Greek sections map 1:1 to 26 English
chapters. The Gutenberg source (#50212) is actually a bilingual edition with
side-by-side columns; we extract only the English. Perseus Greek uses a different
edition (Usener/Radermacher Teubner 1904) than Gutenberg (Roberts Macmillan 1910).

## Planned Works

| # | Author | Work | Source | English | Feasibility | Notes |
|---|--------|------|--------|---------|-------------|-------|
| 1 | Hippolytus | Refutatio | F1K tlg2115 | Gut #65478/#67116 (Legge) | MODERATE | 9 books (2-3 lost), 285ch, 1419sec. Strong entity names. |
| 2 | Plotinus | Enneads | F1K tlg2000 | Gut #42930-42933 (Guthrie 4 vols) | MODERATE | 6 Enneads, 54 tractates, 653sec. Risk: Guthrie chronological order ≠ traditional Ennead order. |
| 3 | Procopius | Wars I-VI | Perseus tlg4029 | Gut #16764-20298 (Dewing Loeb) | MODERATE | Same Dewing Loeb edition both sides — ideal. Large (3 vols). Late Greek (6th c.) may reduce model quality. |
| 4 | Procopius | Secret History | Perseus tlg4029 | Gut #12916 (anon. 1896) | MODERATE | Different translator from Greek source. |
| 5 | Origen | Contra Celsum | F1K tlg2042 | Gut #70561/#70693 (Crombie) | HARD | Must identify which of 47 F1K works the 2-vol English covers. Old translation (1869). |
| 6 | Clement of Alexandria | Protrepticus | Perseus tlg0555 | Gut #71937 (Wilson 1867) | HARD | Structural mismatch — Wilson based on older Greek editions. Start with Protrepticus only. |

## Not Feasible

| Author | Work | Why |
|--------|------|-----|
| Archimedes | Mathematical works | Only 1/13 works has English. Mathematical/geometric text incompatible with embedding model. |
| Pythagoras | Golden Verses / Epistles | Work mismatch — F1K has Epistles (tlg0632/tlg002), Gutenberg has Golden Verses (#69174). |
| Arrian | Indica | Gutenberg #66388 is McCrindle compilation from 5 authors, not standalone Indica. |

## Scaling Potential

Perseus has 56 Greek-only and ~40 Latin-only works that could potentially be
aligned. The Gutenberg full catalog (89k entries, cached at
`data-sources/gutenberg/pg_catalog.csv`) was cross-referenced against all 267
First1KGreek authors not in Perseus and all 100 Perseus authors. The project's
marginal cost per new work is 4-10 hours once extraction scripts are written.

### EEBO-TCP Latin Sources (identified but not yet used)

EEBO-TCP (Early English Books Online Text Creation Partnership) provides CC0
TEI P5 XML of pre-1700 English translations. High-value finds:

| Work | EEBO ID | Notes |
|------|---------|-------|
| Terence (all 6 comedies) | A64394 | Bilingual Latin+English! Hoole 1676. |
| Seneca tragedies (all 10) | A11909 | Newton 1581. Complete. |
| Seneca prose (comprehensive) | A11899 | Lodge 1614. |
| Cicero letters | A18843 | |
| Martial | A52102 | |

---

## Project Structure

```
scripts/
  pipeline/                   # Generic pipeline (shared across all works)
    run.py                    # Entry point: python scripts/pipeline/run.py <work>
    align.py                  # Embed & align (DP or pairwise)
    entity_anchors.py         # Entity-based validation
    generate_outputs.py       # TEI XML, TSV, report
    generate_perseus_tei.py   # Perseus-compatible TEI translation
    generate_parallel_text.py # Side-by-side HTML
  works/                      # Per-work config + extraction scripts
    <name>/
      config.json             # Work metadata, paths, options
      extract_greek.py        # Source text extraction (unique per work)
      extract_english.py      # English text extraction (unique per work)
  align_core.py               # DP + pairwise algorithms
  alignment_quality_map.py    # SVG/TXT/TSV heatmap generator
  verify_alignment_integrity.py  # Hash-verified integrity checks
  publish_to_final.py         # Copy verified outputs to final/
  embedding/                  # Greek embedding training (s01-s07)
  embedding_latin/            # Latin embedding training

data-sources/                 # Input data (gitignored)
  perseus/                    # canonical-greekLit (100 authors) + canonical-latinLit
  greek_corpus/               # First1KGreek (311 authors)
  booth/                      # Booth 1700 TEI XML (OTA A36034)
  statius_mozley/             # Mozley 1928 from Wikisource
  gutenberg/                  # Downloads + pg_catalog.csv (89k entries)

models/                       # Trained models (gitignored)
  ancient-greek-embedding/    # XLM-R fine-tuned (~1 GB)
  latin-embedding/            # XLM-R fine-tuned (~1 GB)

build/<work_name>/            # Per-work build artifacts (gitignored)

final/                        # Verified deliverables (gitignored)
```

## How to Run

```bash
source .venv/bin/activate
python scripts/pipeline/run.py marcus       # one work
python scripts/pipeline/run.py --all        # all works
python scripts/pipeline/run.py --list       # list available
```

### Pipeline steps (per work)

| Step | Script | Description |
|------|--------|-------------|
| 1 | `works/<name>/extract_greek.py` | Extract source text from TEI XML |
| 2 | `works/<name>/extract_english.py` | Extract English from Gutenberg/OTA/Wikisource |
| 3 | `pipeline/align.py` | Embed with trained model, run DP or pairwise alignment |
| 4 | `pipeline/entity_anchors.py` | Validate with transliteration + fuzzy name matching |
| 5 | `pipeline/generate_outputs.py` | TEI standoff XML + TSV + quality report |
| 6 | `pipeline/generate_perseus_tei.py` | Perseus-compatible TEI translation with milestones |
| 7 | `pipeline/generate_parallel_text.py` | Side-by-side HTML (source left, English right) |
| 8 | `alignment_quality_map.py` | SVG heatmap per CTS work |
| 9 | `verify_alignment_integrity.py` | Hash verification, completeness, ordering |
| 10 | `publish_to_final.py` | Copy to `final/` (only if step 9 passes) |

## How to Add a New Work

### Step 1: Identify sources

Check that the work meets the criteria:
- Source language text exists in Perseus (`data-sources/perseus/`) or
  First1KGreek (`data-sources/greek_corpus/First1KGreek/`) **without** an
  existing English translation
- A public domain English translation exists on Project Gutenberg
  (search `data-sources/gutenberg/pg_catalog.csv`) or Wikisource or EEBO-TCP
- The English translation license is Public Domain or CC-BY-SA 4.0
  (not CC-BY-NC)

### Step 2: Download the English text

```bash
mkdir -p data-sources/gutenberg/<name>
curl -sL "https://www.gutenberg.org/cache/epub/<ID>/pg<ID>.txt" \
  -o data-sources/gutenberg/<name>/<filename>.txt
```

Add the source to `LICENSE.txt`.

### Step 3: Create work directory

```bash
mkdir -p scripts/works/<name>
```

Create three files:

#### `config.json`
```json
{
  "name": "<name>",
  "author": "Author Name",
  "work_title": "Work Title",
  "source_language": "greek",
  "alignment_mode": "dp",
  "greek_source": {
    "type": "perseus",
    "tlg_id": "tlg0000",
    "work_id": "tlg001"
  },
  "english_source": {
    "type": "gutenberg",
    "ebook_id": 12345,
    "translator": "Translator Name",
    "date": 1900
  },
  "output_dir": "build/<name>",
  "cts_urn_prefix": "urn:cts:greekLit:tlg0000.tlg001"
}
```

Config options:
- `alignment_mode`: `"dp"` for sequential prose/verse, `"pairwise"` for
  non-sequential units (fables, epigrams, fragments)
- `pairwise_many_to_one`: `true` if multiple source sections are variants of
  the same text (e.g. Aesop fable 4 / 4b / 4c)
- `multi_work`: `true` if the config covers multiple CTS works in one pipeline
  run (e.g. Iamblichus Life of Pythagoras + De Mysteriis)
- `source_language`: `"greek"` or `"latin"` (determines which embedding model)
- `greek_source.type`: `"perseus"` or `"first1kgreek"`
- `greek_source.work_ids`: list of work IDs for multi-work configs

#### `extract_greek.py` (or `extract_latin.py`)

Parse the source TEI XML and produce `build/<name>/greek_sections.json`.
Use an existing work as a template (e.g. `scripts/works/marcus/extract_greek.py`
for Perseus prose, `scripts/works/aesop/extract_greek.py` for First1KGreek).

Key points:
- Set `PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent`
  (4 levels up from `scripts/works/<name>/`)
- Output to `PROJECT_ROOT / "build" / "<name>" / "greek_sections.json"`
- Create output directory with `mkdir(parents=True, exist_ok=True)`

#### `extract_english.py`

Parse the Gutenberg plain text and produce `build/<name>/english_sections.json`.
Use an existing work as template (e.g. `scripts/works/marcus/extract_english.py`
for numbered sections, `scripts/works/dionysius/extract_english.py` for chapters).

Key points:
- Split the text into sections that correspond to the source structure
- Handle Gutenberg headers/footers (skip `*** START/END ***` markers)
- Normalise encoding issues (BOM, `\r\n`, smart quotes)
- Remove footnotes if present

#### Output format (both scripts)

```json
{
  "sections": [
    {
      "book": "1",
      "section": "3",
      "cts_ref": "1.3",
      "edition": "tlg0000.tlg001.perseus-grc2",
      "text": "Full text of the section...",
      "char_count": 456
    }
  ]
}
```

The `book` field is the grouping key for DP alignment — all sections with the
same `book` value are aligned together. The `cts_ref` field must be unique
across all sections. For multi-work configs, add a `"work": "Work Name"` field.

### Step 4: Run

```bash
source .venv/bin/activate
python scripts/pipeline/run.py <name>
```

The pipeline will:
1. Run your extraction scripts
2. Embed and align (auto-selects DP or pairwise from config)
3. Validate with entity anchors
4. Generate all output files (TEI XML, SVG, HTML)
5. Run integrity checks (hash verification)
6. Publish to `final/` if all checks pass

### Step 5: Verify

Check the quality map SVG in `final/` — open it in a browser. Check the parallel
text HTML to spot-check alignments visually. Low-confidence regions will show as
red in the SVG and as highlighted rows in the HTML.

If the alignment quality is poor, common causes:
- **High section ratio** (many source sections per English paragraph): the DP
  `max_source` auto-scales but very high ratios (>5:1) reduce embedding quality
- **Translation heavily paraphrases**: older translations (pre-1800) tend to
  paraphrase more, reducing embedding similarity
- **Structural mismatch**: different edition numbering between source and English
  — check that both `book` fields use the same values
- **Wrong alignment mode**: if sections are non-sequential (fables, epigrams),
  use `"alignment_mode": "pairwise"` instead of `"dp"`

### Step 6: Update documentation

- Add the work to the Completed Works table in this file
- Add the English source to `LICENSE.txt`

---

## Output File Naming

All deliverable files use CTS identifiers. For each CTS work, three files share
the same stem:

```
<cts_work_id>.perseus-eng80.xml   — Perseus-compatible TEI translation
<cts_work_id>.perseus-eng80.svg   — Quality heatmap
<cts_work_id>.perseus-eng80.html  — Parallel text (source left, English right)
```

Plus one CTS catalog fragment per work:
```
__cts__eng80_<work_name>.xml
```

The `eng80` suffix is a conventional identifier for auto-generated English editions.

### Current deliverables in `final/`

| CTS ID | Author | Work |
|--------|--------|------|
| tlg0060.tlg001 | Diodorus Siculus | Bibliotheca Historica |
| tlg0081.tlg012 | Dionysius of Halicarnassus | De Compositione Verborum |
| tlg0096.tlg002 | Aesop | Fabulae |
| tlg0562.tlg001 | Marcus Aurelius | Ad Se Ipsum (Meditations) |
| tlg2023.tlg001 | Iamblichus | De Vita Pythagorica |
| tlg2023.tlg006 | Iamblichus | De Mysteriis |
| phi1020.phi001 | Statius | Thebaid |
| phi1020.phi003 | Statius | Achilleid |

### TEI structure

The Perseus TEI XML (`.perseus-eng80.xml`) follows CTS conventions:
- `<div type="translation">` at top level with CTS URN
- `<div type="textpart" subtype="book" n="1">` for books
- `<milestone unit="section" n="1.3"/>` linking to source CTS refs
- `<p n="3">` for each English section

This evolved through three iterations: v1 (section-div structure — failed because
Perseus expects book-level divs), v2 (Greek-chapter divs — failed because English
structure must drive), v3 (English-paragraph structure with Greek milestones —
current, working).

---

## Alignment Algorithms

### Segmental Dynamic Programming (`align_core.segmental_dp_align`)

For sequential texts (most works). Used by: Diodorus, Statius, Marcus Aurelius,
Iamblichus, Dionysius, and all future prose/verse works.

#### Algorithm

State: `DP[i][j]` = best total score for aligning source sections `0..i-1` to
English sections `0..j-1`.

Transitions: for each state `(i, j)`, try all group sizes:
- `g` in `{1, 2, ..., max_source}` source sections consumed
- `e` in `{1, 2}` English sections consumed
- `DP[i+g][j+e] = max(DP[i+g][j+e], DP[i][j] + score)`

Scoring function:
```
score = 0.8 × cosine_sim(mean_embed_source, mean_embed_english)
      + 0.2 × exp(-0.5 × ((source_chars/english_chars)/expected_ratio - 1)²)
```

Optimizations:
- **Banding:** `j` constrained to ±max(20, 15% × n_english) of the expected diagonal
- **Prefix sums:** O(1) mean embedding and character length computation per group
- **Auto-scaling `max_source`:** `max(5, int(section_ratio × 2))` per book, so books
  with high Greek/English ratios (e.g. Diodorus Book 13 at 3.8:1) get wider grouping

Runtime: ~15 min for Diodorus (embedding ~12 min, DP ~3 min on M4 MPS).

#### Completeness guarantee

After DP alignment, the pipeline scans for English sections not referenced by any
group and inserts them as `match_type: "unmatched_english"` records with
`similarity: 0.0`. This was added to fix a bug where 57 of 3,216 Diodorus English
paragraphs were silently dropped (1.8%). The DP groups multiple source sections
onto English paragraphs, but when `group_size_en=2`, only the first English
paragraph was recorded. Now both are recorded.

### Pairwise Embedding Matching (`align_core.pairwise_match`)

For non-sequential texts (Aesop's Fables). Computes full cosine similarity matrix
`sim[i][j]` for all source×target pairs, then matches:

- `many_to_one=True`: each source gets its absolute best target, no exclusion.
  Multiple sources can match the same target. Correct for variant texts (Aesop
  has 96 variant groups like fable 4/4b/4c).
- `many_to_one=False`: greedy 1-to-1 assignment by descending similarity.
- Minimum similarity threshold (default 0.3); below this, sources marked `"unmatched"`.

After matching, unmatched English sections are added as `"unmatched_target"` records.

### Entity Anchoring

Cross-lingual named entity matching validates alignment quality:
1. Greek proper nouns extracted by regex (`\b[Α-Ω][α-ω]{2,}\b`)
2. Transliterated to Latin script (α→a, θ→th, φ→ph, χ→kh, ψ→ps, etc.)
3. Fuzzy-matched against English names using rapidfuzz `partial_ratio > 75%`
4. Entity score = matched names / total Greek names (0.5 neutral if no names found)
5. Combined score: `0.7 × embedding_similarity + 0.3 × entity_overlap`

For Aesop, animal names are matched instead (ἀλώπηξ→fox, λέων→lion, etc. — ~40
entries in the dictionary).

### Confidence bands

| Band | Score range | Meaning |
|------|------------|---------|
| High | ≥ 0.6 | Strong match — text corresponds well |
| Medium | 0.3–0.6 | Approximate match — right area but translation diverges |
| Low | < 0.3 | Weak match — embedding found some similarity but may be wrong section |

---

## Embedding Models

Both models share the same architecture and training methodology, differing only
in training data (Greek vs Latin corpora). All training was done on Apple M4 with
MPS backend, fp32 precision (bf16 tested but provides no speedup on MPS).

### Common architecture

- **Base model:** `xlm-roberta-base` (278M parameters, 12 layers, 768-dim hidden)
- **Sentence embedding head:** Transformer output → MeanPooling → Dense(768→256, Tanh)
- **Training:** two-phase
  1. **MLM continued pre-training:** masked language modeling (15% masking) on
     monolingual ancient text. Teaches the model to predict missing words in the
     target language, adapting XLM-R's multilingual representations to ancient
     vocabulary and syntax.
  2. **Contrastive fine-tuning:** MultipleNegativesRankingLoss with in-batch
     negatives. Batch size 16 yields 240 negative pairs per step. Teaches the
     model to place translations near each other in embedding space.
- **Evaluation:** TranslationEvaluator — for each source sentence in the eval set,
  retrieve the nearest English sentence by cosine similarity; measure top-k accuracy.

### Ancient Greek (`models/ancient-greek-embedding/`)

Scripts: `scripts/embedding/s01-s07` + `run_embedding_pipeline.sh`

#### Training data

| Dataset | Source | Size | Notes |
|---------|--------|------|-------|
| Monolingual corpus | Perseus (8 authors) + First1KGreek (311 authors) | 1,186,792 unique sentences, 288 MB | Sentence-split on `.` `;` `·` (ano teleia). Deduplicated. Filtered non-Greek by Unicode range. |
| Parallel pairs | Perseus bilingual works (196 works) | 21,263 pairs | Extracted at section level by matching CTS refs between `grc` and `eng` editions. Filtered 20-2000 chars. |
| Training split | 90/10 random | 19,136 train / 2,127 eval | |

Major parallel pair contributors: Plutarch (~11k pairs), Herodotus (4,329),
Thucydides (3,587), Polybius (~1.5k), Demosthenes (~1.5k).

#### Tokenizer analysis

XLM-R tokenizer fragmentation on Ancient Greek: **3.48x** (tokens per word).
This is above the 2.5x concern threshold — Greek words are heavily fragmented
into subword tokens because XLM-R was not trained on Ancient Greek. Attempted
tokenizer extension via `add_tokens()` but SentencePiece's internal model
ignores added tokens during tokenization (both ByteLevelBPE and corpus-frequency
approaches produce 0 improvement). The MLM pre-training phase compensates by
teaching the model to work with fragmented Greek tokens in context.

#### Phase 1: MLM continued pre-training

| Parameter | Value |
|-----------|-------|
| Base model | `xlm-roberta-base` |
| Corpus | 100k sentences sampled from 1.19M |
| Epochs | 1 |
| Batch size | 8 (gradient accumulation 4, effective batch 32) |
| Max sequence length | 128 tokens |
| Learning rate | 5e-5 with 10% linear warmup |
| Precision | fp32 |
| Total steps | 3,125 |
| Training loss | 9.54 → 5.31 |
| Wall time | ~4.5 hours |
| Output | `models/xlm-r-greek-mlm/` (1.0 GB) |

Sanity check (fill-mask): "Τοῖς τὰς κοινὰς \<mask\> πραγματευσαμένοις" →
πράξεις (29.5%), δυνάμεις (21.1%), πόλεις (11.6%) — plausible Greek words.

Tuning notes: original config (500k sentences, 3 epochs, batch 4, grad_accum 8,
max_length 256) estimated 87 hours. Iteratively reduced to 100k sentences, 1 epoch,
batch 8, max_length 128 for practical runtime.

#### Phase 2: Contrastive fine-tuning

| Parameter | Value |
|-----------|-------|
| Base model | `models/xlm-r-greek-mlm/` (from phase 1) |
| Architecture | Transformer → MeanPooling → Dense(768→256, Tanh) |
| Loss function | MultipleNegativesRankingLoss (in-batch negatives) |
| Training pairs | 19,136 Greek-English parallel pairs |
| Epochs | 5 |
| Batch size | 16 |
| Learning rate | 5e-5 with 10% warmup |
| Evaluation | TranslationEvaluator every 500 steps, saves best model |
| Total steps | 5,980 |
| Final training loss | 0.098 |
| Accuracy progression | Step 1000: 77.9% → Step 2500: 91.5% → Step 5500: **95.1%** |
| Wall time | ~5.5 hours |
| Output | `models/ancient-greek-embedding/` (~1 GB) |

#### Evaluation results (2,127 held-out pairs)

| Metric | Custom Model | MiniLM Baseline | Improvement |
|--------|:---:|:---:|:---:|
| Top-1 retrieval | **95.1%** | 0.4% | 238x |
| Top-5 retrieval | **98.8%** | 0.9% | 110x |
| Top-10 retrieval | **99.3%** | 2.1% | 47x |
| MRR | **0.968** | 0.012 | 81x |
| Mean parallel similarity | 0.786 | — | — |
| Mean random similarity | 0.000 | — | — |
| Separation | **0.786** | 0.034 | 23x |

All quality gates passed with large margins. No fallback strategy needed.

**Total training time:** ~10.5 hours (4.5h MLM + 5.5h contrastive + 0.5h other).

### Latin (`models/latin-embedding/`)

Scripts: `scripts/embedding_latin/s01-s07` + `run_latin_embedding_pipeline.sh`

Two versions were trained; v2 is the current production model.

#### Training data

| Dataset | v1 (17 sparse-checkout authors) | v2 (all 60 authors) |
|---------|:---:|:---:|
| Monolingual sentences | 206,579 | 349,266 (+69%) |
| Parallel pairs | 4,263 (from 101 works) | 12,207 (from 134 works) (+186%) |
| Training split | 3,836 train / 427 eval | 10,986 train / 1,221 eval |

Major parallel pair contributors: Cicero orations (2,297), Suetonius (481),
Caesar (399), Livy (292), Sallust (117), Horace (99).

v2 added: Columella, Augustine, Quintilian, Gellius, Plautus, Terence, and
~43 additional author directories from canonical-latinLit.

Key challenge in pair extraction: many Latin works have structurally different
editions. Caesar has book.chapter.section (3 levels) in Latin but book.chapter
(2 levels) in English — resolved with multi-level matching. Verse works
(Virgil, Lucretius, Ovid) have incompatible line/card numbering — minimal pairs.
Cicero Letters have radically different reference formats — 0 pairs.

#### Tokenizer analysis

XLM-R tokenizer fragmentation on Latin: **1.62x** (much better than Greek's
3.48x). Per-author: Caesar 1.64x, Virgil 1.50x, Cicero 2.00x, Livy 1.43x.
XLM-R handles Latin well because modern Romance languages in its training data
share Latin vocabulary roots. No tokenizer extension needed.

#### Phase 1: MLM continued pre-training

| Parameter | v1 | v2 |
|-----------|:---:|:---:|
| Corpus sample | 100k sentences | 200k sentences |
| Batch size | 4 (grad accum 8, effective 32) | 4 (grad accum 8) |
| Steps | 3,125 | 6,250 |
| Training loss | 33.5 → 26.5 | similar range |
| Wall time | 3h 17m | ~6.5h |

Batch size reduced from 8 to 4 due to MPS OOM at 8.83 GiB allocation.
Workaround: `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0`.

Sanity check: "Gallia est omnis \<mask\> in partes tres" → "divisa" (90.9%).

#### Phase 2: Contrastive fine-tuning

| Parameter | v1 | v2 |
|-----------|:---:|:---:|
| Training pairs | 3,836 | 10,986 |
| Epochs | 5 | 10 |
| Batch size | 16 | 32 |
| Total steps | 1,200 | ~3,440 (early stopped at ~2,100) |
| Final loss | 0.089 | similar |
| Wall time | 68 min | ~5h |

v2 training was early-stopped at ~60% (step ~2,100 of 3,440) when evaluation
accuracy plateaued. Best model automatically saved by TranslationEvaluator.

#### Evaluation results

| Metric | v1 | v2 | MiniLM Baseline |
|--------|:---:|:---:|:---:|
| Top-1 retrieval | 84.8% | **92.6%** (+7.8pp) | 4.0% |
| Top-5 retrieval | 90.2% | **95.7%** (+5.5pp) | 16.4% |
| Top-10 retrieval | 93.2% | **96.3%** (+3.1pp) | 23.4% |
| MRR | 0.873 | **0.940** (+0.067) | 0.109 |
| Separation | 0.725 | — | 0.089 |

v2 narrowed the gap with the Greek model from ~10pp to ~2.5pp on Top-1.

**Total training time (v2):** ~12 hours on M4 MPS.

### Reproducibility

To retrain either model from scratch:

```bash
source .venv/bin/activate

# Greek (~10.5 hrs on M4 MPS)
caffeinate -i bash scripts/embedding/run_embedding_pipeline.sh

# Latin (~12 hrs on M4 MPS)
caffeinate -i bash scripts/embedding_latin/run_latin_embedding_pipeline.sh
```

Requirements: Python 3.11+, PyTorch with MPS (or CUDA) support,
`sentence-transformers`, `transformers`, `datasets`, `accelerate`,
`sentencepiece`. See `requirements.txt` and `requirements-freeze.txt`.

Both pipelines include quality gates at each decision point. If a gate fails,
the pipeline halts with instructions. Fallback hierarchy:

1. **Tune hyperparameters** (+4-8 hrs): more epochs, lower LR (2e-5), bigger batch
2. **Add more data** (+1-2 hrs prep + retrain): expand Perseus sparse checkout,
   add First1KGreek for Latin if available
3. **Architecture change** (+4-8 hrs): MSE distillation from English teacher,
   different pooling (CLS vs mean), or `bert-base-multilingual`
4. **FastText fallback** (+30 min): static word embeddings via gensim — much
   faster, lower quality
5. **Accept baseline:** continue using `paraphrase-multilingual-MiniLM-L12-v2`

### Disk budget

| Component | Greek | Latin |
|-----------|:-----:|:-----:|
| Monolingual corpus | 288 MB | 23-50 MB |
| Parallel pairs | 5-30 MB | 5-30 MB |
| HuggingFace cache (xlm-roberta-base) | ~1.1 GB | (shared) |
| MLM checkpoint | ~1.0 GB | ~1.1 GB |
| Final embedding model | ~1.0 GB | ~1.1 GB |
| **Total** | **~3.5 GB** | **~2.3 GB** |

---

## Integrity Checks

Every build verifies (`scripts/verify_alignment_integrity.py`):

1. **Completeness:** every source section CTS ref from `greek_sections.json`
   appears in the alignment output
2. **Completeness:** every English section CTS ref from `english_sections.json`
   appears in the alignment output
3. **Text integrity:** SHA-256 hash of all source texts, reconstructed by looking
   up each alignment ref in the source data, matches the hash of the original
   extraction. If any text was lost, changed, or reordered, the hash differs.
4. **Failure behavior:** if any check fails, the build halts with exit code 1.
   Output files are left in `build/` for inspection. Nothing is published to `final/`.

---

## Data Sources

| Source | Contents | License | Path |
|--------|----------|---------|------|
| Perseus canonical-greekLit | 100 ancient Greek authors, TEI XML | CC BY-SA 4.0 | `data-sources/perseus/canonical-greekLit/` |
| Perseus canonical-latinLit | Latin authors, TEI XML | CC BY-SA 4.0 | `data-sources/perseus/canonical-latinLit/` |
| First1KGreek | 311 Greek authors, TEI XML | CC BY-SA 4.0 | `data-sources/greek_corpus/First1KGreek/` |
| Project Gutenberg | English translations + full catalog | Public domain | `data-sources/gutenberg/` |
| Booth 1700 (OTA A36034) | Diodorus English, TEI XML | CC0 | `data-sources/booth/` |
| Mozley 1928 (Wikisource) | Statius English, HTML | CC BY-SA 4.0 | `data-sources/statius_mozley/` |

The Gutenberg full catalog (`pg_catalog.csv`, 89k entries) is used to
cross-reference English translation availability against Perseus and First1KGreek
Greek-only works. See `plans/gutenberg_ancient_greek_texts.md` for the complete
analysis.

See `LICENSE.txt` for complete per-source attribution.

---

## Historical Notes

### Design decisions

- **English-driven TEI structure:** The output TEI uses English paragraph structure
  with Greek milestone markers, not Greek section structure with English content.
  Earlier approaches (v1: section-div, v2: Greek-chapter divs) failed because
  Perseus infrastructure expects the translation to follow its own natural structure.

- **Auto-scaling max_source:** Originally fixed at 5. Diodorus Books 13 and 20
  (section ratio 3.8:1) had many groups hitting the ceiling, causing poor alignment.
  Auto-scaling to `max(5, ratio×2)` improved scores by ~3%.

- **Pairwise matching for Aesop:** Initially tried sequential DP, but fables are
  self-contained units in arbitrary order. The 1-to-1 greedy constraint was also
  wrong: Aesop has 96 variant groups (4/4b/4c) that should all match the same
  English fable. Switching to `many_to_one=True` pairwise matching increased
  matched fables from 311/522 (60%) to 522/522 (100%).

- **Pipeline refactoring:** Originally each work had its own directory with 5-8
  scripts (~400 lines of duplicated code per work). Refactored to a generic pipeline
  with per-work extraction scripts only. Adding a new work now requires 3 files
  instead of 8.

### Plans directory

The `plans/` directory contains historical design documents, investigations, and
decision logs created during development. These are preserved for reference but
superseded by this document for current project state. Key files:

| File | Contents |
|------|----------|
| `alignment_tracker.md` | Work inventory with scores and feasibility ratings |
| `gutenberg_ancient_greek_texts.md` | Full Gutenberg vs Perseus/F1K cross-reference (687 lines) |
| `pd_translation_availability.md` | Public domain translation research (446 lines) |
| `eebo_tcp_tei_xml_investigation.md` | EEBO-TCP Latin translation sources (384 lines) |
| `greek_embedding_plan.md` | Step-by-step embedding training log (271 lines) |
| `latin_embedding_plan.md` | Latin embedding training log (269 lines) |
| `segmental_dp_alignment_plan.md` | DP algorithm specification and per-book results |
| `statius_alignment_plan.md` | Verse alignment challenges and solutions |
| `pipeline_refactor.md` | Refactoring rationale and migration plan |

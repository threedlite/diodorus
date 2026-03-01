# Diodorus: Greek-English Alignment Pipeline

Aligns Diodorus Siculus's *Bibliotheca Historica* between G. Booth's 1700 English translation (OTA A36034) and the Perseus Digital Library Greek TEI texts (tlg0060.tlg001).

## Project Structure

```
scripts/
  embedding/          # Steps s01-s07: train Ancient Greek embedding model (~10.5 hrs)
    run_embedding_pipeline.sh
  alignment/          # Steps 01-07: align Greek sections to English paragraphs (~20 min)
    run_alignment.sh
plans/                # Design documents and decision logs
  greek_embedding_plan.md
  segmental_dp_alignment_plan.md
data-sources/         # Input data (gitignored, see Data Sources below)
  booth/              # Booth 1700 TEI XML (A36034.xml)
  perseus/            # Perseus canonical-greekLit sparse checkout
  greek_corpus/       # First1KGreek + extracted monolingual corpus
  parallel/           # Greek-English parallel pairs (auto-generated)
models/               # Trained models (gitignored)
  xlm-r-greek-mlm/   # Continued pre-training checkpoint (~1 GB)
  ancient-greek-embedding/  # Final embedding model (~1 GB)
output/               # Generated outputs (gitignored)
```

## Prerequisites

- Python 3.11+
- ~5 GB disk for models and data
- Apple Silicon Mac with MPS recommended (CPU works but slower)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

For exact reproducibility use `requirements-freeze.txt` instead.

## Data Sources

All data goes in `data-sources/` (gitignored). Acquire before running:

### Booth English Translation (required)
- **Source:** Oxford Text Archive, A36034
- **File:** `data-sources/booth/A36034.xml` (TEI XML)
- **URL:** https://ota.bodleian.ox.ac.uk/repository/xmlui/handle/20.500.12024/A36034

### Perseus Greek Texts (required)
```bash
mkdir -p data-sources/perseus
cd data-sources/perseus
git clone --filter=blob:none --sparse https://github.com/PerseusDL/canonical-greekLit.git
cd canonical-greekLit
git sparse-checkout set data/tlg0060
# For embedding training, also add:
git sparse-checkout add data/tlg0003 data/tlg0007 data/tlg0012 \
  data/tlg0016 data/tlg0059 data/tlg0085 data/tlg0086
```

### First1KGreek Corpus (for embedding training only)
```bash
cd data-sources/greek_corpus
git clone https://github.com/OpenGreekAndLatin/First1KGreek.git
```

## Running

### Option A: Full Pipeline (embedding training + alignment)

Training the embedding model takes ~10.5 hours on M4 MPS. Run once; the model is reused.

```bash
source .venv/bin/activate

# 1. Train embedding model (~10.5 hrs)
caffeinate -i bash scripts/embedding/run_embedding_pipeline.sh

# 2. Run alignment pipeline (~20 min)
bash scripts/alignment/run_alignment.sh
```

### Option B: Alignment Only (if model already trained)

If `models/ancient-greek-embedding/` exists:

```bash
source .venv/bin/activate
bash scripts/alignment/run_alignment.sh
```

The script falls back to `paraphrase-multilingual-MiniLM-L12-v2` if no custom model exists, but results will be much worse.

## Pipeline Steps

### Embedding Pipeline (`scripts/embedding/`)

| Script | Description | Time |
|---|---|---|
| s01 | Build Greek monolingual corpus from Perseus + First1KGreek | ~5 min |
| s02 | Build Greek-English parallel corpus from Perseus | ~10 min |
| s03 | Check XLM-R tokenizer fragmentation on Greek | <1 min |
| s04 | MLM continued pre-training on Greek corpus | ~4.5 hrs |
| s05 | Prepare parallel pairs for embedding training | <1 min |
| s06 | Fine-tune embedding model (contrastive loss) | ~5.5 hrs |
| s07 | Evaluate model vs MiniLM baseline | ~5 min |

### Alignment Pipeline (`scripts/alignment/`)

| Script | Description | Time |
|---|---|---|
| 01 | Extract Booth TEI -> JSON (15 books, 3,216 paragraphs) | <1 min |
| 02 | Extract Perseus Greek TEI -> JSON (8,123 sections, 3 editions) | <1 min |
| 03 | Normalise early-modern English spelling | <1 min |
| 04 | Match Booth books to Perseus books by heading/number | <1 min |
| 05 | Embed & align via segmental DP (see below) | ~15 min |
| 06 | Validate with cross-lingual named entity matching | ~2 min |
| 07 | Generate TEI XML, TSV, quality report | <1 min |

### Segmental DP Alignment (Step 05)

The core alignment uses Segmental Dynamic Programming rather than simple greedy matching. For each book it:

1. Embeds all Greek sections and English paragraphs with the trained model
2. Runs DP over states `(i, j)` = Greek sections consumed, English paragraphs consumed
3. Tries grouping 1-5 Greek sections onto 1-2 English paragraphs per transition
4. Scores each group: `0.8 * cosine_similarity + 0.2 * length_penalty`
5. Uses banding (j within 15% of diagonal) for efficiency
6. Backtracks to recover optimal alignment path

See `plans/segmental_dp_alignment_plan.md` for full algorithm specification.

## Output Files

After running the full pipeline, `output/` contains:

| File | Description |
|---|---|
| `alignment_booth_perseus.xml` | TEI standoff alignment with confidence scores |
| `alignment_booth_perseus.tsv` | Tabular format: book, refs, similarity, entity, combined scores |
| `alignment_report.md` | Quality summary with confidence distribution |
| `entity_validated_alignments.json` | Full alignment data with all metadata |
| `section_alignments.json` | Raw DP alignment output (before entity validation) |
| `book_alignment.json` | Book-level correspondence table |
| `embedding_eval_report.md` | Embedding model evaluation (custom vs baseline) |

## Quality Metrics

### Embedding Model (eval on 2,127 held-out parallel pairs)

| Metric | Custom Model | MiniLM Baseline |
|---|---|---|
| Top-1 retrieval | 95.1% | 0.4% |
| Top-5 retrieval | 98.8% | 0.9% |
| MRR | 0.968 | 0.012 |

### Alignment (8,123 Greek sections across 15 books)

| Band | Count | Percentage |
|---|---|---|
| High confidence (>= 0.6) | 1,211 | 14.9% |
| Medium confidence (0.3-0.6) | 4,821 | 59.3% |
| Low confidence (< 0.3) | 2,091 | 25.7% |

- Mean combined score: 0.412
- English paragraph coverage: 100% (3,216 / 3,216)

## Plans & Design Documents

- `plans/greek_embedding_plan.md` -- Full embedding training plan with timing, quality gates, decision points
- `plans/segmental_dp_alignment_plan.md` -- DP alignment algorithm specification and results
- `diodorus_alignment_strategy.md` -- Original project strategy
- `supplement_ancient_greek_embedding.md` -- Embedding model research notes

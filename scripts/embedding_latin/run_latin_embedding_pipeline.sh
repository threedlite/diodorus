#!/bin/bash
# run_latin_embedding_pipeline.sh — Master orchestration for Latin embedding model
#
# Chains all steps with logging. Mirrors the Greek embedding pipeline.
#
# Usage:
#   caffeinate -i bash scripts/embedding_latin/run_latin_embedding_pipeline.sh
#
# Total estimated time: ~7-12 hours on M4 Apple Silicon.

set -e

# Resolve project root (two levels up from this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Activate venv
source .venv/bin/activate

# Log directory
LOG_DIR="output/latin_embedding_logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "========================================"
echo "Latin Embedding Pipeline"
echo "Started: $(date)"
echo "Project root: $PROJECT_ROOT"
echo "Logs: $LOG_DIR/"
echo "========================================"

# --- Pre-check: Data Sources ---
echo ""
echo "=== Pre-check: Data Sources ==="
LATIN_DATA="data-sources/perseus/canonical-latinLit/data"
if [ ! -d "$LATIN_DATA" ]; then
    echo "ERROR: canonical-latinLit not found at $LATIN_DATA"
    echo "Cloning now..."
    mkdir -p data-sources/perseus
    cd data-sources/perseus
    git clone --filter=blob:none --sparse https://github.com/PerseusDL/canonical-latinLit.git
    cd canonical-latinLit
    git sparse-checkout set \
        data/phi0448 data/phi0472 data/phi0474 data/phi0550 \
        data/phi0631 data/phi0632 data/phi0690 data/phi0893 \
        data/phi0914 data/phi0917 data/phi0959 data/phi0978 \
        data/phi1017 data/phi1276 data/phi1318 data/phi1348 \
        data/phi1351
    cd "$PROJECT_ROOT"
    echo "canonical-latinLit cloned and sparse checkout configured."
fi

AUTHOR_COUNT=$(ls -d "$LATIN_DATA"/phi* 2>/dev/null | wc -l | tr -d ' ')
echo "Latin authors found: $AUTHOR_COUNT"
if [ "$AUTHOR_COUNT" -lt 2 ]; then
    echo "WARNING: Only $AUTHOR_COUNT author(s) found. Check sparse checkout."
fi

# --- Step 1: Build Latin corpus ---
echo ""
echo "=== S01: Build Latin corpus ==="
python scripts/embedding_latin/s01_build_latin_corpus.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s01.log"

CORPUS="data-sources/latin_corpus/latin_all.txt"
if [ ! -f "$CORPUS" ]; then
    echo "ERROR: Corpus not created. Check logs."
    exit 1
fi
LINES=$(wc -l < "$CORPUS" | tr -d ' ')
echo "Corpus: $LINES sentences"

# --- Step 2: Build parallel corpus ---
echo ""
echo "=== S02: Build Latin-English parallel corpus ==="
python scripts/embedding_latin/s02_build_latin_parallel_corpus.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s02.log"

PARALLEL="data-sources/latin_parallel/lat_eng_pairs.jsonl"
if [ ! -f "$PARALLEL" ]; then
    echo "ERROR: Parallel corpus not created. Check logs."
    exit 1
fi
PAIRS=$(wc -l < "$PARALLEL" | tr -d ' ')
echo "Parallel pairs: $PAIRS"

# Decision point 1: check parallel corpus size
if [ "$PAIRS" -lt 5000 ]; then
    echo ""
    echo "WARNING: Only $PAIRS parallel pairs found (minimum recommended: 5000)."
    echo "Consider expanding sparse checkout: git sparse-checkout disable"
    echo "Continuing anyway..."
    sleep 3
fi

# --- Step 3: Tokenizer check ---
echo ""
echo "=== S03: Check Latin tokenizer ==="
set +e
python scripts/embedding_latin/s03_check_latin_tokenizer.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s03.log"
TOKENIZER_EXIT=$?
set -e

if [ $TOKENIZER_EXIT -eq 1 ]; then
    echo "High fragmentation noted. MLM pre-training will help compensate."
else
    echo "Tokenizer OK for Latin."
fi

# --- Step 4: MLM continued pre-training (LONG) ---
echo ""
echo "=== S04: Continued pre-training (MLM) on Latin ==="
echo "This will take 3-5 hours on M4 Apple Silicon."
echo "Started at: $(date)"
python scripts/embedding_latin/s04_latin_pretraining.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s04.log"
echo "Finished at: $(date)"

# --- Step 5: Prepare embedding data ---
echo ""
echo "=== S05: Prepare Latin embedding training data ==="
python scripts/embedding_latin/s05_prepare_latin_embedding_data.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s05.log"

# --- Step 6: Embedding fine-tuning (LONG) ---
echo ""
echo "=== S06: Train Latin sentence embedding model ==="
echo "This will take 3-6 hours on M4 Apple Silicon."
echo "Started at: $(date)"
python scripts/embedding_latin/s06_train_latin_embedding.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s06.log"
echo "Finished at: $(date)"

# --- Step 7: Evaluation ---
echo ""
echo "=== S07: Evaluate Latin model ==="
python scripts/embedding_latin/s07_evaluate_latin_model.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s07.log"

echo ""
echo "========================================"
echo "Latin pipeline complete: $(date)"
echo "Custom model: models/latin-embedding/"
echo "Eval report:  output/latin_embedding_eval_report.md"
echo "Logs:         $LOG_DIR/"
echo "========================================"
echo ""
echo "Next: review output/latin_embedding_eval_report.md for quality gates."

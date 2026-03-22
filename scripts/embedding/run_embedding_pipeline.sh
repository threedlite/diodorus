#!/bin/bash
# run_embedding_pipeline.sh — Master orchestration for Ancient Greek embedding model
#
# Chains all steps with logging. Includes the fragmentation decision gate.
#
# Usage:
#   caffeinate -i bash scripts/embedding/run_embedding_pipeline.sh
#
# Steps 0-4 run interactively (~40 min). Steps 5-7 are long-running training.
# Practical approach: run steps 0-4, then launch step 5 before bed.
# Next morning run steps 6-8.

set -e

# Resolve project root (two levels up from this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Activate venv
source .venv/bin/activate

# Log directory
LOG_DIR="build/embedding_logs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "========================================"
echo "Ancient Greek Embedding Pipeline"
echo "Started: $(date)"
echo "Project root: $PROJECT_ROOT"
echo "Logs: $LOG_DIR/"
echo "========================================"

# --- Step 1: Data Acquisition (manual prerequisite) ---
echo ""
echo "=== Pre-check: Data Sources ==="
PERSEUS_DATA="data-sources/perseus/canonical-greekLit/data"
if [ ! -d "$PERSEUS_DATA" ]; then
    echo "ERROR: Perseus data not found at $PERSEUS_DATA"
    echo "Run the sparse checkout expansion first:"
    echo "  cd data-sources/perseus/canonical-greekLit"
    echo "  git sparse-checkout set data/tlg0060 data/tlg0012 data/tlg0016 data/tlg0003 data/tlg0059 data/tlg0007 data/tlg0085 data/tlg0086"
    exit 1
fi

AUTHOR_COUNT=$(ls -d "$PERSEUS_DATA"/tlg* 2>/dev/null | wc -l | tr -d ' ')
echo "Perseus authors found: $AUTHOR_COUNT"
if [ "$AUTHOR_COUNT" -lt 2 ]; then
    echo "WARNING: Only $AUTHOR_COUNT author(s) found. Expand sparse checkout for better results."
    echo "  cd data-sources/perseus/canonical-greekLit"
    echo "  git sparse-checkout set data/tlg0060 data/tlg0012 data/tlg0016 data/tlg0003 data/tlg0059 data/tlg0007 data/tlg0085 data/tlg0086"
fi

F1K="data-sources/greek_corpus/First1KGreek"
if [ -d "$F1K" ]; then
    echo "First1KGreek: found"
else
    echo "First1KGreek: not found (optional, will reduce corpus size)"
    echo "  To add: git clone --depth 1 https://github.com/OpenGreekAndLatin/First1KGreek.git $F1K"
fi

# --- Step 2: Build Greek corpus ---
echo ""
echo "=== S01: Build Greek corpus ==="
python scripts/embedding/s01_build_greek_corpus.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s01.log"

CORPUS="data-sources/greek_corpus/ancient_greek_all.txt"
if [ ! -f "$CORPUS" ]; then
    echo "ERROR: Corpus not created. Check logs."
    exit 1
fi
LINES=$(wc -l < "$CORPUS" | tr -d ' ')
echo "Corpus: $LINES sentences"

# --- Step 3: Build parallel corpus ---
echo ""
echo "=== S02: Build parallel corpus ==="
python scripts/embedding/s02_build_parallel_corpus.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s02.log"

PARALLEL="data-sources/parallel/grc_eng_pairs.jsonl"
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
    echo "Options:"
    echo "  A) Expand Perseus: cd data-sources/perseus/canonical-greekLit && git sparse-checkout disable"
    echo "  B) Continue with reduced quality"
    echo ""
    echo "Continuing anyway... (press Ctrl+C to abort and expand data)"
    sleep 3
fi

# --- Step 4: Tokenizer check ---
echo ""
echo "=== S03: Check tokenizer ==="
set +e  # Allow non-zero exit (exit 1 means extension recommended)
python scripts/embedding/s03_check_tokenizer.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s03.log"
TOKENIZER_EXIT=$?
set -e

if [ $TOKENIZER_EXIT -eq 1 ]; then
    echo ""
    echo "=== S03b: Extending tokenizer ==="
    python scripts/embedding/s03b_extend_tokenizer.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s03b.log"
else
    echo "Tokenizer OK — skipping extension."
fi

# --- Step 5: MLM continued pre-training (LONG) ---
echo ""
echo "=== S04: Continued pre-training (MLM) ==="
echo "This will take 3-6 hours on M4 Apple Silicon."
echo "Started at: $(date)"
python scripts/embedding/s04_continued_pretraining.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s04.log"
echo "Finished at: $(date)"

# --- Step 6: Prepare embedding data ---
echo ""
echo "=== S05: Prepare embedding training data ==="
python scripts/embedding/s05_prepare_embedding_data.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s05.log"

# --- Step 7: Embedding fine-tuning (LONG) ---
echo ""
echo "=== S06: Train sentence embedding model ==="
echo "This will take 1-4 hours on M4 Apple Silicon."
echo "Started at: $(date)"
python scripts/embedding/s06_train_embedding_model.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s06.log"
echo "Finished at: $(date)"

# --- Step 8: Evaluation ---
echo ""
echo "=== S07: Evaluate ==="
python scripts/embedding/s07_evaluate_model.py 2>&1 | tee "$LOG_DIR/${TIMESTAMP}_s07.log"

echo ""
echo "========================================"
echo "Pipeline complete: $(date)"
echo "Custom model: models/ancient-greek-embedding/"
echo "Eval report:  build/embedding_eval_report.md"
echo "Logs:         $LOG_DIR/"
echo "========================================"
echo ""
echo "Next: review build/embedding_eval_report.md for quality gates."
echo "If passing, integrate into alignment pipeline (Step 9 in plan)."

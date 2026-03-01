#!/bin/bash
# Autonomous pipeline continuation: monitors s04, then runs s06 + s07
# Logs everything to output/embedding_logs/

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"
source .venv/bin/activate

LOG_DIR="$PROJECT_ROOT/output/embedding_logs"
mkdir -p "$LOG_DIR"
LOGFILE="$LOG_DIR/pipeline_continuation.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOGFILE"
}

S04_PID="${1:?Usage: $0 <s04_pid>}"

log "=== Pipeline continuation started ==="
log "Monitoring s04 (PID $S04_PID) for completion..."

# Wait for s04 to finish
while kill -0 "$S04_PID" 2>/dev/null; do
    # Check for checkpoints as progress indicator
    CKPTS=$(ls -d "$PROJECT_ROOT/models/xlm-r-greek-mlm/checkpoint-"* 2>/dev/null | wc -l | tr -d ' ')
    FILES=$(ls "$PROJECT_ROOT/models/xlm-r-greek-mlm/" 2>/dev/null | wc -l | tr -d ' ')
    MEM=$(ps -o rss= -p "$S04_PID" 2>/dev/null | awk '{printf "%.0f", $1/1024}')
    CPU=$(ps -o %cpu= -p "$S04_PID" 2>/dev/null | tr -d ' ')
    log "s04 still running — checkpoints: $CKPTS, files: $FILES, mem: ${MEM}MB, cpu: ${CPU}%"
    sleep 300  # Check every 5 minutes
done

# s04 finished — check exit code
wait "$S04_PID" 2>/dev/null
S04_EXIT=$?
log "s04 finished with exit code: $S04_EXIT"

# Check if model was saved
if [ ! -f "$PROJECT_ROOT/models/xlm-r-greek-mlm/model.safetensors" ] && \
   [ ! -f "$PROJECT_ROOT/models/xlm-r-greek-mlm/pytorch_model.bin" ]; then
    log "ERROR: s04 did not produce a model file. Checking for checkpoints..."
    LATEST_CKPT=$(ls -d "$PROJECT_ROOT/models/xlm-r-greek-mlm/checkpoint-"* 2>/dev/null | sort -t- -k2 -n | tail -1)
    if [ -n "$LATEST_CKPT" ]; then
        log "Found checkpoint: $LATEST_CKPT — copying as final model"
        cp -r "$LATEST_CKPT"/* "$PROJECT_ROOT/models/xlm-r-greek-mlm/"
    else
        log "FATAL: No model and no checkpoints. Pipeline cannot continue."
        exit 1
    fi
fi

log "s04 model verified at models/xlm-r-greek-mlm/"
ls -lh "$PROJECT_ROOT/models/xlm-r-greek-mlm/" >> "$LOGFILE" 2>&1

# ============================================================
# Step 7: Embedding Fine-tuning (s06)
# ============================================================
log "=== Starting s06_train_embedding_model.py ==="
PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0 python scripts/embedding/s06_train_embedding_model.py 2>&1 | tee -a "$LOG_DIR/s06_embedding_training.log"
S06_EXIT=${PIPESTATUS[0]}
log "s06 finished with exit code: $S06_EXIT"

if [ "$S06_EXIT" -ne 0 ]; then
    log "ERROR: s06 failed. Check $LOG_DIR/s06_embedding_training.log"
    exit 1
fi

# Verify embedding model exists
if [ ! -d "$PROJECT_ROOT/models/ancient-greek-embedding" ]; then
    log "ERROR: s06 did not produce models/ancient-greek-embedding/"
    exit 1
fi
log "s06 embedding model verified at models/ancient-greek-embedding/"
ls -lh "$PROJECT_ROOT/models/ancient-greek-embedding/" >> "$LOGFILE" 2>&1

# ============================================================
# Step 8: Evaluation (s07)
# ============================================================
log "=== Starting s07_evaluate_model.py ==="
python scripts/embedding/s07_evaluate_model.py 2>&1 | tee -a "$LOG_DIR/s07_evaluation.log"
S07_EXIT=${PIPESTATUS[0]}
log "s07 finished with exit code: $S07_EXIT"

if [ "$S07_EXIT" -ne 0 ]; then
    log "WARNING: s07 evaluation failed (non-fatal). Check $LOG_DIR/s07_evaluation.log"
fi

# ============================================================
# Summary
# ============================================================
log "=== Pipeline continuation complete ==="
log "Results:"
log "  s04 MLM model:     models/xlm-r-greek-mlm/"
log "  s06 Embedding:     models/ancient-greek-embedding/"
if [ -f "$PROJECT_ROOT/output/embedding_eval_report.md" ]; then
    log "  s07 Eval report:   output/embedding_eval_report.md"
    log ""
    log "--- Evaluation Report ---"
    cat "$PROJECT_ROOT/output/embedding_eval_report.md" >> "$LOGFILE"
fi
log "=== DONE ==="

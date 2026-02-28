# Plan: Ancient Greek Sentence Embedding Model

## Context

The Diodorus alignment project matches Booth's 1700 English translation with Perseus Greek TEI texts. The current approach uses `paraphrase-multilingual-MiniLM-L12-v2`, a generic multilingual model that was **not trained on Ancient Greek**. A purpose-built embedding model should roughly double retrieval accuracy (15-30% → 40-65% top-1).

This plan follows `supplement_ancient_greek_embedding.md` but adapts it to the actual project state: paths use `data-sources/`, transformers 5.2.0 has API changes, and scripts go in `scripts/embedding/`.

---

## Step 0: Environment Setup (~5 min) — DONE 2026-02-28

### 0.1 Install missing packages — DONE
```bash
source .venv/bin/activate
pip install datasets accelerate sentencepiece
```
Installed: datasets 4.6.1, accelerate 1.12.0, sentencepiece 0.2.1

### 0.2 Create directories — DONE
```
scripts/embedding/     — scripts (committed to git)
models/                — trained models (gitignored)
output/embedding_logs/ — logs and reports (gitignored)
data-sources/greek_corpus/  — monolingual corpus (gitignored)
data-sources/parallel/      — parallel pairs (gitignored)
```

All 9 scripts created and syntax-verified.

---

## Step 1: Data Acquisition (~5-10 min, network-bound) — DONE 2026-02-28

**Steps 1.1 and 1.2 can run in parallel.**

### 1.1 Expand Perseus sparse checkout — DONE
All 8 author directories present: tlg0003, tlg0007, tlg0012, tlg0016, tlg0059, tlg0060, tlg0085, tlg0086.
Actual disk: 101 MB for `data/`.

### 1.2 Clone First1KGreek — DONE
Cloned to `data-sources/greek_corpus/First1KGreek/`.
Actual disk: 988 MB.

---

## Step 2: Build Greek Monolingual Corpus — `s01_build_greek_corpus.py` (~2-10 min)

**Depends on:** Step 1 complete

- Extracts all Ancient Greek text from Perseus (all 8 authors) + First1KGreek
- Sentence-splits on `.` `;` `·` (ano teleia)
- Deduplicates, filters non-Greek and very short lines
- **Input:** `data-sources/perseus/canonical-greekLit/data/`, `data-sources/greek_corpus/First1KGreek/data/`
- **Output:** `data-sources/greek_corpus/ancient_greek_all.txt`
- **Expected:** 200k-500k sentences, 20-60 MB
- **Verify:** `wc -l` > 200k, `head -5` shows polytonic Greek
- **ACTUAL (2026-02-28):** 1,186,792 unique sentences, 287.8 MB (exceeded estimates thanks to First1KGreek)

---

## Step 3: Build Parallel Corpus — `s02_build_parallel_corpus.py` (~5-15 min) — DONE 2026-02-28

**Depends on:** Step 1.1 complete

- Scans all Perseus works for matching `grc` and `eng` editions
- Extracts section-level text keyed by CTS reference (book.chapter.section)
- Pairs Greek and English sections with matching references
- Filters: 20-2000 chars per section
- **Input:** `data-sources/perseus/canonical-greekLit/data/`
- **Output:** `data-sources/parallel/grc_eng_pairs.jsonl`
- **Expected:** 10k-30k pairs (Plutarch and Polybius contribute heavily)
- **ACTUAL:** 21,263 pairs from 196 works (Thucydides 3587, Herodotus 4329, Plutarch ~11k, Polybius ~1.5k, Demosthenes ~1.5k, Lysias 37)

**Bug fix applied:** Original `extract_sections` walked up to the edition/translation div whose `n` was a full URN (`urn:cts:greekLit:...`), making Greek and English refs always differ. Fixed to stop at `type="edition"` / `type="translation"` divs.

### DECISION POINT 1: Parallel corpus size — PASSED
21,263 pairs well above the 5,000 minimum.

---

## Step 4: Tokenizer Check — `s03_check_tokenizer.py` (<1 min) — DONE 2026-02-28

**Depends on:** Nothing

- Tests `xlm-roberta-base` tokenization on sample Ancient Greek text
- Measures fragmentation ratio (tokens per word)
- **ACTUAL:** Average fragmentation 3.48x (above 2.5 threshold)

### DECISION POINT 2: Fragmentation ratio — EXTENSION NOT EFFECTIVE
- Fragmentation is 3.48x (above 2.5 threshold), so s03b was attempted
- **Finding:** `add_tokens()` cannot extend SentencePiece subword tokenization — tokens are added to the vocabulary but SentencePiece's internal model doesn't use them during tokenization. Both ByteLevelBPE and corpus-frequency approaches produce 0 improvement.
- **Decision:** Proceed with base xlm-roberta-base tokenizer. The MLM continued pre-training (Step 5) is what actually teaches the model Greek — even fragmented tokens carry context.

### Step 4b: Extend Tokenizer — SKIPPED (ineffective for SentencePiece)

---

## Step 5: MLM Continued Pre-training — `s04_continued_pretraining.py` (**3-6 hrs on M4**)

**Depends on:** Step 2 (corpus)
**This is the longest step — run overnight with `caffeinate -i`**

- Continues training xlm-roberta-base on Ancient Greek corpus (1.19M sentences, 288 MB)
- Masked Language Modeling objective, 15% masking
- Hyperparameters: batch 8, grad accum 4 (effective 32), 3 epochs, lr 5e-5, warmup 10%
- **Input:** `data-sources/greek_corpus/ancient_greek_all.txt` + xlm-roberta-base
- **Output:** `models/xlm-r-greek-mlm/` (~1-1.5 GB)

**API fix for transformers 5.2.0:** Remove deprecated `overwrite_output_dir`, `no_cuda`, `use_mps_device` from TrainingArguments. Add `bf16=True` for M4 speedup.

**Verify:**
- Training loss decreases over epochs
- Final loss < 3.0
- Sanity: fill-mask pipeline produces plausible Greek words

**STATUS: READY TO RUN** — `caffeinate -i .venv/bin/python scripts/embedding/s04_continued_pretraining.py`

---

## Step 6: Prepare Embedding Data — `s05_prepare_embedding_data.py` (<1 min) — DONE 2026-02-28

**ACTUAL:** 19,136 train pairs, 2,127 eval pairs

**Depends on:** Step 3 (parallel corpus)

- Splits parallel pairs 90% train / 10% eval
- Reformats as sentence-transformers InputExample format
- **Input:** `data-sources/parallel/grc_eng_pairs.jsonl`
- **Output:** `data-sources/parallel/train_pairs.jsonl`, `data-sources/parallel/eval_pairs.jsonl`

---

## Step 7: Embedding Fine-tuning — `s06_train_embedding_model.py` (**1-4 hrs on M4**)

**Depends on:** Step 5 (MLM model) + Step 6 (training data)

- Builds SentenceTransformer: Transformer → MeanPooling → Dense(768→256, Tanh)
- Trains with MultipleNegativesRankingLoss (contrastive, in-batch negatives)
- 5 epochs, batch 16, eval every 500 steps, saves best model
- **Input:** `models/xlm-r-greek-mlm/` + `data-sources/parallel/train_pairs.jsonl`
- **Output:** `models/ancient-greek-embedding/` (~300 MB)
- **Verify:** TranslationEvaluator scores improve during training; model encodes both Greek and English

---

## Step 8: Evaluation — `s07_evaluate_model.py` (~5-15 min)

**Depends on:** Step 7

Compares custom model vs MiniLM baseline:

| Metric | Minimum acceptable | Target |
|---|---|---|
| Top-1 retrieval | 30% | 50%+ |
| Top-5 retrieval | 50% | 75%+ |
| MRR | 0.35 | 0.50+ |
| Parallel-random separation | 0.15 | 0.30+ |

- **Input:** `models/ancient-greek-embedding/` + baseline + `data-sources/parallel/eval_pairs.jsonl`
- **Output:** `output/embedding_eval_report.md`

### DECISION POINT 3: Quality gates
If metrics are below minimum acceptable, see Fallback Strategy below.

---

## Step 9: Integration (~5 min)

**Depends on:** Step 8 passes quality gates

Update the alignment pipeline's model loading (in `05_embed_and_align.py` when created):
```python
CUSTOM_MODEL = Path("models/ancient-greek-embedding")
if CUSTOM_MODEL.exists():
    model = SentenceTransformer(str(CUSTOM_MODEL))
else:
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
```
Cosine similarity is dimension-agnostic (256 vs 384 doesn't matter).

---

## Master Run Script: `scripts/embedding/run_embedding_pipeline.sh`

Chains all steps with logging to `output/embedding_logs/`. Includes the fragmentation decision gate. Invoke with:
```bash
caffeinate -i bash scripts/embedding/run_embedding_pipeline.sh
```

Steps s01 and s02 could run in parallel (different input data) but run sequentially for simplicity.

---

## Timing Summary

| Step | Time (M4) | Cumulative |
|---|---|---|
| 0: Setup | 5 min | 5 min |
| 1: Data acquisition | 5-10 min | 15 min |
| 2: Greek corpus (s01) | 2-10 min | 25 min |
| 3: Parallel corpus (s02) | 5-15 min | 40 min |
| 4: Tokenizer check (s03) | <1 min | 40 min |
| 5: MLM pre-training (s04) | **3-6 hrs** | ~4-7 hrs |
| 6: Prep embedding data (s05) | <1 min | ~4-7 hrs |
| 7: Embedding training (s06) | **1-4 hrs** | ~5-11 hrs |
| 8: Evaluation (s07) | 5-15 min | ~5-11 hrs |
| 9: Integration | 5 min | ~5-11 hrs |

**Practical approach:** Run steps 0-4 interactively (~40 min). Launch step 5 before bed. Next morning run steps 6-9.

---

## Disk Budget (~4-5 GB total)

| Item | Size |
|---|---|
| Expanded Perseus (7 extra authors) | ~200-300 MB |
| First1KGreek clone | ~500 MB |
| Greek corpus txt | 20-60 MB |
| Parallel pairs | 5-30 MB |
| XLM-R base (HF cache) | ~1.1 GB |
| MLM checkpoints | ~1.5 GB |
| Final embedding model | ~300 MB |

---

## Fallback Strategy (if quality gates fail)

1. **Tune hyperparameters** (+4-8 hrs): More epochs (MLM→5, embedding→10), lower LR (2e-5), bigger batch
2. **More data** (+1-2 hrs prep + retrain): `git sparse-checkout disable` for all Perseus authors
3. **Architecture change** (+4-8 hrs): MSE distillation from English teacher model, or use smaller bert-base-multilingual
4. **FastText fallback** (+30 min): Train static word embeddings with gensim (s08); much faster, lower quality
5. **Accept baseline:** Continue using MiniLM — it works "passably"

---

## Scripts to Create (9 files)

All in `scripts/embedding/`:
1. `s01_build_greek_corpus.py` — adapted from supplement lines 86-186
2. `s02_build_parallel_corpus.py` — adapted from supplement lines 198-348
3. `s03_check_tokenizer.py` — adapted from supplement lines 386-413
4. `s03b_extend_tokenizer.py` — adapted from supplement lines 420-457 (conditional)
5. `s04_continued_pretraining.py` — adapted from supplement lines 462-582 (**needs transformers 5.2.0 API fixes**)
6. `s05_prepare_embedding_data.py` — adapted from supplement lines 592-636
7. `s06_train_embedding_model.py` — adapted from supplement lines 641-755
8. `s07_evaluate_model.py` — adapted from supplement lines 762-889
9. `run_embedding_pipeline.sh` — master orchestration script

Key adaptations across all scripts:
- All `data/` paths → `data-sources/`
- All `models/` paths stay as-is
- TrainingArguments: remove `overwrite_output_dir`, `no_cuda`, `use_mps_device`; add `bf16=True`

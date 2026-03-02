# Plan: Latin Sentence Embedding Model

## Context

The Greek embedding pipeline achieved 95.1% top-1 retrieval accuracy (238x over
baseline) using: (1) MLM pre-training on a monolingual corpus, (2) contrastive
fine-tuning on Greek-English parallel pairs from Perseus.

This plan replicates the approach for Latin, enabling alignment of public domain
English translations to Latin source texts in Perseus. The 46-volume Latin gap
(Y original text, N English translation) is the target.

Scripts go in `scripts/embedding_latin/`. Models go in `models/`.

---

## Step 0: Data Acquisition (~5-10 min, network-bound) — DONE 2026-03-01

### 0.1 Clone canonical-latinLit (sparse checkout)
```bash
mkdir -p data-sources/perseus
cd data-sources/perseus
git clone --filter=blob:none --sparse https://github.com/PerseusDL/canonical-latinLit.git
cd canonical-latinLit
# Add all 17 Y/Y PHI IDs for parallel corpus:
git sparse-checkout set \
  data/phi0448 data/phi0472 data/phi0474 data/phi0550 \
  data/phi0631 data/phi0632 data/phi0690 data/phi0893 \
  data/phi0914 data/phi0917 data/phi0959 data/phi0978 \
  data/phi1017 data/phi1276 data/phi1318 data/phi1348 \
  data/phi1351
```

**PHI IDs included** (17 authors/collections, all with Y/Y Perseus status):
- phi0448 Caesar (Gallic War, Civil Wars)
- phi0472 Catullus/Tibullus
- phi0474 Cicero (orations, philosophical works, letters)
- phi0550 Lucretius
- phi0631 Sallust
- phi0632 Rhetorica ad Herennium
- phi0690 Virgil (Eclogues, Georgics, Aeneid)
- phi0893 Horace (Odes, Satires, Epistles)
- phi0914 Livy (many books)
- phi0917 Lucan
- phi0959 Ovid (Metamorphoses, Heroides, etc.)
- phi0978 Pliny the Elder (Natural History)
- phi1017 Seneca (Moral Epistles)
- phi1276 Juvenal/Persius
- phi1318 Pliny the Younger (Letters)
- phi1348 Suetonius
- phi1351 Tacitus

**Actual result:** 16 of 17 PHI IDs present (phi0632 not a separate directory in Perseus).

---

## Step 1: Build Latin Monolingual Corpus — `s01_build_latin_corpus.py` (~2-5 min) — DONE 2026-03-01

**Depends on:** Step 0

- Extracts all Latin text from canonical-latinLit (all lat editions)
- Sentence-splits on `.` `?` `!` (Latin punctuation simpler than Greek)
- Deduplicates, filters non-Latin and very short lines
- **Input:** `data-sources/perseus/canonical-latinLit/data/`
- **Output:** `data-sources/latin_corpus/latin_all.txt`
- **Expected:** 300K-800K sentences
- **ACTUAL:** 206,579 unique sentences, 23.0 MB (lower than Greek's 1.19M — sparse checkout only, no First1KGreek equivalent for Latin)

**Bug fix:** Added `etree.XMLParser(load_dtd=False, no_network=True, recover=True)` to handle Perseus XML files with external DTD references.

---

## Step 2: Build Latin-English Parallel Corpus — `s02_build_latin_parallel_corpus.py` (~5-15 min) — DONE 2026-03-01

**Depends on:** Step 0

- Scans canonical-latinLit for works with both `lat` and `eng` editions
- **Multi-level extraction:** Extracts text at every textpart depth (section, chapter, book)
- Matches at finest level producing common refs; falls back to coarser levels
- Handles both new TEI format (`type="textpart"`) and old format (`type="chapter"`)
- Normalizes refs (e.g., "pr" → "0") for cross-edition matching
- Filters: 20-3000 chars per section
- **Input:** `data-sources/perseus/canonical-latinLit/data/`
- **Output:** `data-sources/latin_parallel/lat_eng_pairs.jsonl`
- **ACTUAL:** 4,263 pairs from 101 works with both editions

**Key challenge:** Many Latin works have structurally different editions:
- Caesar: Latin has book.chapter.section (3 levels), English has book.chapter (2 levels) — fixed with multi-level matching (399 pairs)
- Livy: 20K Latin sections, different numbering scheme in English — 292 pairs at depth 3
- Verse works (Virgil, Lucretius, Lucan, Ovid): line/card numbering incompatible — minimal pairs
- Cicero Letters: radically different reference format — 0 pairs
- Tacitus: old-format TEI without edition wrapper — fixed with body fallback (29 pairs)

**Major contributors:** Cicero orations (2,297 pairs), Caesar (399), Livy (292), Suetonius (481), Horace (99), Sallust (117)

### DECISION POINT 1: Parallel corpus size — ACCEPTED
4,263 pairs below the 5,000 recommendation but above minimum viable. MultipleNegativesRankingLoss is data-efficient (batch 16 = 240 in-batch negatives per step). Tokenizer fragmentation is low (1.62x vs Greek's 3.48x), giving the model a better starting point. Proceeding.

---

## Step 3: Tokenizer Check — `s03_check_latin_tokenizer.py` (<1 min) — DONE 2026-03-01

**Depends on:** Nothing

- Tests xlm-roberta-base tokenization on sample Latin text
- **ACTUAL:** Average fragmentation 1.62x (well below 2.5 threshold)
  - Caesar: 1.64x, Virgil: 1.50x, Cicero: 2.00x, Livy: 1.43x
- XLM-R handles Latin much better than Greek (20,076 Latin-letter tokens vs Greek's limited coverage)

### DECISION POINT 2: Fragmentation ratio — PASSED
1.62x is excellent. No tokenizer extension needed.

---

## Step 4: MLM Continued Pre-training — `s04_latin_pretraining.py` (~3-5 hrs on M4) — DONE 2026-03-02

**Depends on:** Step 1 (corpus) + Step 3 (informational)

- Continues training xlm-roberta-base on Latin corpus
- Masked Language Modeling, 15% masking
- Hyperparameters (adjusted for MPS memory):
  - batch 4, grad accum 8 (effective 32) — reduced from batch 8 due to MPS OOM
  - 1 epoch over 100k sampled sentences
  - max_length 128, lr 5e-5, warmup 10%, fp32
- **Input:** `data-sources/latin_corpus/latin_all.txt`
- **Output:** `models/xlm-r-latin-mlm/` (1.06 GB)
- **ACTUAL:** 3,125 steps in 3h 17m (3.78s/step). Loss: 33.5 → 26.5 (final batch), avg 28.6
- **Sanity check:** "Gallia est omnis `<mask>` in partes tres" → "divisa" (90.9% confidence)

**Fix:** Initial batch_size=8 caused MPS OOM (8.83 GiB allocated). Reduced to 4 with
`PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0`. Used `caffeinate -i` to prevent sleep.

---

## Step 5: Prepare Embedding Data — `s05_prepare_latin_embedding_data.py` (<1 min) — DONE 2026-03-01

**Depends on:** Step 2

- **ACTUAL:** 3,836 training pairs, 427 eval pairs
- **Input:** `data-sources/latin_parallel/lat_eng_pairs.jsonl`
- **Output:** `data-sources/latin_parallel/train_pairs.jsonl`, `eval_pairs.jsonl`

---

## Step 6: Embedding Fine-tuning — `s06_train_latin_embedding.py` (~3-6 hrs on M4) — DONE 2026-03-02

**Depends on:** Step 4 (MLM model) + Step 5 (training data)

- Builds SentenceTransformer: Transformer -> MeanPooling -> Dense(768->256, Tanh)
- Trains with MultipleNegativesRankingLoss
- 5 epochs, batch 16, eval every 500 steps, 1,200 total steps
- **Input:** `models/xlm-r-latin-mlm/` + training pairs
- **Output:** `models/latin-embedding/` (1.1 GB)
- **ACTUAL:** 68 min total. Loss: 0.614 (step 500) → 0.089 (step 1000), avg 0.300
- **Eval during training:** 82.6% mean accuracy at step 500, 84.7% at step 1000

---

## Step 7: Evaluation — `s07_evaluate_latin_model.py` (~5-15 min) — DONE 2026-03-02

**Depends on:** Step 6

Compares custom Latin model vs MiniLM baseline.

### Quality Gates (minimum acceptable) — ALL PASSED

| Gate | Minimum | Actual | Pass? |
|---|---|---|---|
| Top-1 retrieval | 30% | **84.8%** | PASS |
| Top-5 retrieval | 50% | **90.2%** | PASS |
| MRR | 35% | **87.3%** | PASS |
| Separation | 15% | **72.5%** | PASS |

### Full Results

| Metric | Custom Latin | MiniLM Baseline | Improvement |
|---|---|---|---|
| Top-1 accuracy | **84.8%** | 4.0% | **21.2x** |
| Top-5 accuracy | **90.2%** | 16.4% | 5.5x |
| Top-10 accuracy | **93.2%** | 23.4% | 4.0x |
| MRR | **0.873** | 0.109 | 8.0x |
| Parallel similarity | 0.742 | 0.279 | — |
| Random similarity | 0.017 | 0.189 | — |
| Separation | **0.725** | 0.089 | 8.1x |

### Optimistic Targets (based on Greek results)
- Top-1 retrieval >= 80% — **ACHIEVED (84.8%)**
- MRR >= 0.90 — **Close (0.873)**, very strong result

**Output:** `output/latin_embedding_eval_report.md`

---

## Timing — Estimated vs Actual

| Step | Estimated | Actual | Notes |
|---|---|---|---|
| 0: Data acquisition | 5-10 min | ~5 min | Network-bound sparse clone |
| 1: Latin corpus (s01) | 2-5 min | ~3 min | CPU-bound text extraction |
| 2: Parallel corpus (s02) | 5-15 min | ~10 min | CPU-bound XML parsing |
| 3: Tokenizer check (s03) | <1 min | <1 min | |
| 4: MLM pre-training (s04) | 3-5 hrs | **3h 17m** | M4 MPS, fp32, batch 4 |
| 5: Prep embedding data (s05) | <1 min | <1 min | |
| 6: Embedding training (s06) | 3-6 hrs | **68 min** | Much faster than estimated |
| 7: Evaluation (s07) | 5-15 min | ~5 min | |
| **Total** | **~7-12 hrs** | **~4.5 hrs** | Faster due to smaller pair count |

---

## Disk Budget (~3-4 GB additional)

| Item | Size |
|---|---|
| canonical-latinLit sparse checkout | ~200-400 MB |
| Latin corpus txt | ~50-150 MB |
| Latin parallel pairs | ~5-30 MB |
| MLM checkpoints | ~1.5 GB |
| Final embedding model | ~1 GB |

---

## Scripts to Create (8 files)

All in `scripts/embedding_latin/`:
1. `s01_build_latin_corpus.py`
2. `s02_build_latin_parallel_corpus.py`
3. `s03_check_latin_tokenizer.py`
4. `s04_latin_pretraining.py`
5. `s05_prepare_latin_embedding_data.py`
6. `s06_train_latin_embedding.py`
7. `s07_evaluate_latin_model.py`
8. `run_latin_embedding_pipeline.sh`

---

## Fallback Strategy (if quality gates fail)

Same hierarchy as Greek:
1. Tune hyperparameters: more epochs, lower LR
2. More data: disable sparse checkout for all of canonical-latinLit
3. Architecture change: try different pooling or loss
4. Accept baseline: MiniLM may actually work better for Latin than Greek
   (since Latin is closer to modern Romance languages in XLM-R's training)

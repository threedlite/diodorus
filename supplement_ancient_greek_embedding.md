# Supplement: Training an Ancient Greek Sentence Embedding Model

**For use with the Booth–Perseus Diodorus Alignment Pipeline**
*Mac laptop, free open-source software only, no cloud services.*

---

## 0. Why a Custom Ancient Greek Embedding?

The v2 alignment pipeline uses `paraphrase-multilingual-MiniLM-L12-v2`, which handles 50+ languages but was **not trained on Ancient Greek**. It works passably because Ancient Greek shares some lexical and structural overlap with Modern Greek, but it has real limitations: polytonic diacritics are noise to it, classical vocabulary is often out-of-distribution, and word order differences between Attic/Koine prose and any modern language confuse the positional encodings.

A purpose-built Ancient Greek embedding model would improve alignment quality substantially. This document describes how to build one on a Mac laptop with no paid services.

---

## 1. Strategy Overview

We will **not** train a model from scratch — that would require GPU clusters and millions of sentence pairs. Instead, we use a three-stage approach:

1. **Continued pre-training** of an existing multilingual masked language model on a large Ancient Greek corpus (unsupervised, teaches the model Ancient Greek vocabulary and syntax)
2. **Distillation / fine-tuning** into a sentence embedding model using synthetic parallel data (Ancient Greek ↔ English sentence pairs generated from existing aligned corpora)
3. **Evaluation** against known parallel texts to measure quality

All three stages run on a Mac laptop CPU (or MPS on Apple Silicon for ~3× speedup).

---

## 2. Constraints & Feasibility

| Resource | Requirement | Mac Laptop Reality |
|---|---|---|
| Training data | 5–50 MB of Ancient Greek text | ✅ Perseus + First1KGreek = ~80 MB |
| Parallel data | 5,000–50,000 sentence pairs | ✅ Achievable from Perseus aligned translations |
| Base model | Small transformer (< 500M params) | ✅ MiniLM-L12 = 33M params |
| Training time | Hours, not days | ✅ 4–12 hrs on M-series, 12–36 hrs Intel |
| RAM | 8–16 GB | ✅ Standard Mac config |
| Disk | ~5 GB for data + models + checkpoints | ✅ |
| GPU | Not required (MPS optional) | ✅ |

---

## 3. Environment Setup

Extends the v2 pipeline environment:

```bash
cd ~/diodorus-alignment
source .venv/bin/activate

pip install \
  transformers \
  datasets \
  accelerate \
  tokenizers \
  torch \
  sentencepiece \
  evaluate \
  wandb-core-lite  # optional, for local-only training logs

# If on Apple Silicon, PyTorch MPS backend is included automatically
# Verify:
python -c "import torch; print('MPS available:', torch.backends.mps.is_available())"
```

**Note on PyTorch:** `pip install torch` on macOS automatically includes the MPS (Metal Performance Shaders) backend for Apple Silicon. No CUDA needed.

---

## 4. Acquire Training Data

### 4a. Ancient Greek Monolingual Corpus (for continued pre-training)

```bash
mkdir -p data/greek_corpus

# 1. Perseus canonical-greekLit (already cloned in v2 pipeline)
#    Extract all Greek text from all authors, not just Diodorus

# 2. First1KGreek — a major open corpus of Greek texts
git clone --depth 1 https://github.com/OpenGreekAndLatin/First1KGreek.git \
  data/greek_corpus/First1KGreek
```

### 4b. Script: `s01_build_greek_corpus.py`

```python
#!/usr/bin/env python3
"""
Build a plain-text Ancient Greek corpus from Perseus and First1KGreek.
Target: one sentence per line, UTF-8, polytonic Greek.
"""

import re
from pathlib import Path
from lxml import etree

OUTPUT = Path("data/greek_corpus/ancient_greek_all.txt")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

def extract_text_from_tei(xml_path):
    """Extract all text content from a TEI XML file."""
    try:
        tree = etree.parse(str(xml_path))
    except etree.XMLSyntaxError:
        return ""
    
    root = tree.getroot()
    
    # Find body, namespace-agnostic
    body = root.find(".//{*}body")
    if body is None:
        return ""
    
    # Get all text, skip notes and apparatus
    text = []
    for el in body.iter():
        tag = etree.QName(el.tag).localname if isinstance(el.tag, str) else ""
        if tag in ("note", "app", "bibl", "ref", "fw", "gap", "figure"):
            continue
        if el.text:
            text.append(el.text)
        if el.tail:
            text.append(el.tail)
    
    return " ".join(text)

def is_greek(text):
    """Check if text is predominantly Greek characters."""
    greek = sum(1 for c in text if "\u0370" <= c <= "\u03FF" or "\u1F00" <= c <= "\u1FFF")
    return greek > len(text) * 0.3

def sentence_split_greek(text):
    """Split Greek text into sentences on . ; · (ano teleia) and ·"""
    # Greek uses · (middle dot / ano teleia) as a semicolon
    # and ; as a question mark
    sents = re.split(r"(?<=[.·;])\s+", text)
    return [s.strip() for s in sents if len(s.strip()) > 10]

# Collect from all sources
all_sentences = []

# Source 1: Perseus canonical-greekLit
perseus_dir = Path("data/perseus/canonical-greekLit/data")
if perseus_dir.exists():
    for xml_file in sorted(perseus_dir.rglob("*.xml")):
        if "__cts__" in xml_file.name:
            continue
        if "-grc" not in xml_file.name and "-grc" not in xml_file.stem:
            continue  # Only Greek editions
        text = extract_text_from_tei(xml_file)
        if is_greek(text):
            sents = sentence_split_greek(text)
            all_sentences.extend(sents)
    print(f"Perseus: {len(all_sentences)} sentences so far")

# Source 2: First1KGreek
f1k_dir = Path("data/greek_corpus/First1KGreek/data")
if f1k_dir.exists():
    count_before = len(all_sentences)
    for xml_file in sorted(f1k_dir.rglob("*.xml")):
        if "__cts__" in xml_file.name:
            continue
        text = extract_text_from_tei(xml_file)
        if is_greek(text):
            sents = sentence_split_greek(text)
            all_sentences.extend(sents)
    print(f"First1KGreek: {len(all_sentences) - count_before} new sentences")

# Deduplicate and clean
seen = set()
clean_sents = []
for s in all_sentences:
    s = re.sub(r"\s+", " ", s).strip()
    if s not in seen and len(s) > 15 and is_greek(s):
        seen.add(s)
        clean_sents.append(s)

# Write out
with open(OUTPUT, "w", encoding="utf-8") as f:
    for s in clean_sents:
        f.write(s + "\n")

print(f"\nTotal unique Greek sentences: {len(clean_sents)}")
print(f"Corpus size: {OUTPUT.stat().st_size / 1024 / 1024:.1f} MB")
print(f"Saved to {OUTPUT}")
```

**Expected yield:** 200,000–500,000 sentences, 20–60 MB of text.

### 4c. Parallel Corpus (for embedding fine-tuning)

We need Ancient Greek ↔ English sentence pairs. Sources:

```bash
mkdir -p data/parallel
```

#### Script: `s02_build_parallel_corpus.py`

```python
#!/usr/bin/env python3
"""
Build a Greek-English parallel corpus from Perseus, which provides
aligned Greek editions and English translations of the same works.

Strategy:
  1. Find works that have both a grc and an eng edition in Perseus
  2. Extract text at the section level (CTS book.chapter.section)
  3. Pair Greek sections with their English translations
  4. Split into sentences and create training pairs

This is noisy (section-level, not sentence-level) but sufficient for
fine-tuning embeddings via contrastive learning.
"""

import json
import re
from pathlib import Path
from lxml import etree
from collections import defaultdict

PERSEUS_DIR = Path("data/perseus/canonical-greekLit/data")
OUTPUT = Path("data/parallel/grc_eng_pairs.jsonl")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

def extract_sections(xml_path):
    """Extract text keyed by CTS reference (book.chapter.section or similar)."""
    try:
        tree = etree.parse(str(xml_path))
    except etree.XMLSyntaxError:
        return {}
    
    root = tree.getroot()
    sections = {}
    
    # Find all leaf-level textpart divs
    for div in root.iter():
        tag = etree.QName(div.tag).localname if isinstance(div.tag, str) else ""
        if tag != "div":
            continue
        
        subtype = div.get("subtype", "")
        div_type = div.get("type", "")
        n = div.get("n", "")
        
        if subtype in ("section", "verse", "paragraph", "chapter") or \
           div_type == "textpart":
            # Check if this is a leaf node (no child textparts)
            child_divs = [c for c in div if 
                          etree.QName(c.tag).localname == "div" if isinstance(c.tag, str)]
            has_child_textparts = any(
                c.get("type") == "textpart" or c.get("subtype") in 
                ("section", "verse", "paragraph", "chapter")
                for c in child_divs
            )
            
            if not has_child_textparts and n:
                # Build reference by walking up
                ref_parts = [n]
                parent = div.getparent()
                while parent is not None:
                    p_tag = etree.QName(parent.tag).localname if isinstance(parent.tag, str) else ""
                    if p_tag == "div" and parent.get("n"):
                        ref_parts.insert(0, parent.get("n"))
                    parent = parent.getparent()
                
                ref = ".".join(ref_parts)
                text = re.sub(r"\s+", " ", "".join(div.itertext())).strip()
                if text:
                    sections[ref] = text
    
    return sections

# Scan for all text files, grouped by work (textgroup.work)
works = defaultdict(dict)  # work_id -> {"grc": {ref: text}, "eng": {ref: text}}

if PERSEUS_DIR.exists():
    for xml_file in sorted(PERSEUS_DIR.rglob("*.xml")):
        if "__cts__" in xml_file.name:
            continue
        
        stem = xml_file.stem  # e.g. tlg0012.tlg001.perseus-grc5
        parts = stem.split(".")
        if len(parts) < 3:
            continue
        
        work_id = f"{parts[0]}.{parts[1]}"
        version = parts[2]  # e.g. perseus-grc5 or perseus-eng1
        
        if "grc" in version:
            lang = "grc"
        elif "eng" in version:
            lang = "eng"
        else:
            continue
        
        sections = extract_sections(xml_file)
        if sections:
            # Merge with any existing sections for this lang
            if lang not in works[work_id]:
                works[work_id][lang] = {}
            works[work_id][lang].update(sections)

# Find works with both Greek and English
parallel_works = {wid: data for wid, data in works.items() 
                  if "grc" in data and "eng" in data}

print(f"Found {len(parallel_works)} works with both Greek and English editions")

# Create pairs by matching CTS references
pairs = []
for work_id, data in sorted(parallel_works.items()):
    grc = data["grc"]
    eng = data["eng"]
    
    common_refs = set(grc.keys()) & set(eng.keys())
    for ref in sorted(common_refs):
        g_text = grc[ref]
        e_text = eng[ref]
        
        # Skip very short or very long sections
        if len(g_text) < 20 or len(e_text) < 20:
            continue
        if len(g_text) > 2000 or len(e_text) > 2000:
            continue
        
        pairs.append({
            "work": work_id,
            "ref": ref,
            "grc": g_text,
            "eng": e_text
        })

# Write JSONL
with open(OUTPUT, "w", encoding="utf-8") as f:
    for p in pairs:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")

print(f"Total parallel pairs: {len(pairs)}")
print(f"Saved to {OUTPUT}")

# Show sample
if pairs:
    p = pairs[0]
    print(f"\nSample pair ({p['work']} {p['ref']}):")
    print(f"  GRC: {p['grc'][:100]}...")
    print(f"  ENG: {p['eng'][:100]}...")
```

**Expected yield:** 5,000–30,000 section-level pairs depending on how many works have both Greek and English editions in the local Perseus clone. The pipeline only cloned `tlg0060` (Diodorus) so we need to expand:

```bash
# Expand Perseus clone to include all works (for parallel data richness)
cd data/perseus/canonical-greekLit
git sparse-checkout disable  # Get everything
cd ~/diodorus-alignment

# OR if disk is tight, add specific well-translated authors:
cd data/perseus/canonical-greekLit
git sparse-checkout set \
  data/tlg0060 \
  data/tlg0012 \
  data/tlg0016 \
  data/tlg0003 \
  data/tlg0059 \
  data/tlg0007 \
  data/tlg0085 \
  data/tlg0086
cd ~/diodorus-alignment
# tlg0012=Homer, tlg0016=Herodotus, tlg0003=Thucydides,
# tlg0059=Polybius, tlg0007=Plutarch, tlg0085/86=Lysias/Demosthenes
```

---

## 5. Stage 1 — Continued Pre-training (Masked Language Modelling)

This stage teaches the base transformer model Ancient Greek vocabulary and syntax. We take `xlm-roberta-base` (270M params) or `bert-base-multilingual-cased` (110M params) and continue training its MLM objective on our Greek corpus.

**Why XLM-R?** It already has some Modern Greek in its training data and uses SentencePiece tokenisation, which handles polytonic Greek characters better than WordPiece.

### 5a. Prepare tokeniser extension

```python
#!/usr/bin/env python3
"""s03_check_tokeniser.py — Verify and optionally extend the tokeniser."""

from transformers import AutoTokenizer

MODEL_NAME = "xlm-roberta-base"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

# Test on Ancient Greek
test = "Τοῖς τὰς κοινὰς ἱστορίας πραγματευσαμένοις δίκαιον ἀπονέμειν"
tokens = tokenizer.tokenize(test)
print(f"Tokens ({len(tokens)}): {tokens}")

# Check how many Greek-specific tokens exist
vocab = tokenizer.get_vocab()
greek_tokens = [t for t in vocab if any("\u0370" <= c <= "\u03FF" for c in t)]
polytonic = [t for t in vocab if any("\u1F00" <= c <= "\u1FFF" for c in t)]
print(f"\nGreek tokens in vocab: {len(greek_tokens)}")
print(f"Polytonic tokens: {len(polytonic)}")
print(f"Total vocab size: {len(vocab)}")

# If tokenisation is very fragmented (>2x word count), consider adding tokens
words = test.split()
fragmentation = len(tokens) / len(words)
print(f"\nFragmentation ratio: {fragmentation:.1f}x (1.0 = perfect, >2.5 = problematic)")
if fragmentation > 2.5:
    print("⚠️  High fragmentation — consider extending the tokeniser (see Stage 1b)")
else:
    print("✅  Tokenisation acceptable — proceed without extension")
```

### 5b. Optional: Extend tokeniser with Greek subwords

Only needed if fragmentation ratio > 2.5:

```python
#!/usr/bin/env python3
"""s03b_extend_tokeniser.py — Add frequent Greek subwords to the tokeniser."""

from pathlib import Path
from tokenizers import ByteLevelBPETokenizer
from transformers import AutoTokenizer, AutoModelForMaskedLM

MODEL_NAME = "xlm-roberta-base"
CORPUS = Path("data/greek_corpus/ancient_greek_all.txt")
EXTENDED_DIR = Path("models/xlm-r-greek-extended")

# Train a small BPE on the Greek corpus to find common subwords
bpe = ByteLevelBPETokenizer()
bpe.train(
    files=[str(CORPUS)],
    vocab_size=2000,
    min_frequency=5,
    special_tokens=[]
)

# Get the new tokens
new_tokens = list(bpe.get_vocab().keys())

# Load the original tokeniser and add new tokens
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
num_added = tokenizer.add_tokens(new_tokens)
print(f"Added {num_added} new tokens to tokeniser")

# Resize model embeddings
model = AutoModelForMaskedLM.from_pretrained(MODEL_NAME)
model.resize_token_embeddings(len(tokenizer))

# Save
EXTENDED_DIR.mkdir(parents=True, exist_ok=True)
tokenizer.save_pretrained(EXTENDED_DIR)
model.save_pretrained(EXTENDED_DIR)
print(f"Saved extended model+tokeniser to {EXTENDED_DIR}")
```

### 5c. Run continued pre-training

```python
#!/usr/bin/env python3
"""
s04_continued_pretraining.py — MLM training on Ancient Greek corpus.

This adapts the base multilingual model to Ancient Greek.
Expected time: 4-8 hours on Apple Silicon, 12-24 hours on Intel Mac.
"""

import torch
from pathlib import Path
from transformers import (
    AutoTokenizer,
    AutoModelForMaskedLM,
    DataCollatorForLanguageModeling,
    TrainingArguments,
    Trainer,
)
from datasets import load_dataset

# Use extended model if it exists, otherwise base
EXTENDED_DIR = Path("models/xlm-r-greek-extended")
if EXTENDED_DIR.exists():
    MODEL_PATH = str(EXTENDED_DIR)
    print("Using extended tokeniser model")
else:
    MODEL_PATH = "xlm-roberta-base"
    print("Using base xlm-roberta model")

OUTPUT_DIR = Path("models/xlm-r-greek-mlm")
CORPUS = Path("data/greek_corpus/ancient_greek_all.txt")

# Detect device
if torch.backends.mps.is_available():
    device = "mps"
    print("Using Apple Silicon MPS backend")
elif torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"
    print("Using CPU (this will be slow but will work)")

# Load tokeniser and model
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForMaskedLM.from_pretrained(MODEL_PATH)

# Load corpus as a HuggingFace dataset
dataset = load_dataset("text", data_files={"train": str(CORPUS)})

# Tokenise
def tokenize_fn(examples):
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=256,  # Keep short for memory
        padding=False,
        return_special_tokens_mask=True,
    )

tokenized = dataset["train"].map(
    tokenize_fn,
    batched=True,
    remove_columns=["text"],
    num_proc=4,
)

# MLM data collator (15% masking)
data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=True,
    mlm_probability=0.15,
)

# Training arguments — tuned for laptop
training_args = TrainingArguments(
    output_dir=str(OUTPUT_DIR),
    overwrite_output_dir=True,
    
    # Batch sizing for 8-16 GB RAM
    per_device_train_batch_size=8,
    gradient_accumulation_steps=4,  # Effective batch = 32
    
    # Training duration
    num_train_epochs=3,
    
    # Learning rate
    learning_rate=5e-5,
    warmup_ratio=0.1,
    weight_decay=0.01,
    
    # Logging
    logging_steps=100,
    save_steps=2000,
    save_total_limit=2,
    
    # Performance
    fp16=False,  # Not supported on MPS
    dataloader_num_workers=2,
    
    # Device
    no_cuda=True if device == "cpu" else False,
    use_mps_device=True if device == "mps" else False,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized,
    data_collator=data_collator,
)

print(f"\nStarting MLM training on {len(tokenized)} examples...")
print(f"Device: {device}")
print(f"Estimated time: {'4-8 hrs' if device == 'mps' else '12-24 hrs'}")

trainer.train()
trainer.save_model(str(OUTPUT_DIR))
tokenizer.save_pretrained(str(OUTPUT_DIR))

print(f"\nMLM model saved to {OUTPUT_DIR}")
```

---

## 6. Stage 2 — Sentence Embedding Fine-tuning

Now we turn the MLM model into a **sentence embedding** model. We use contrastive learning: given a Greek sentence and its English translation, their embeddings should be close; random pairs should be far apart.

### 6a. Prepare training data

```python
#!/usr/bin/env python3
"""
s05_prepare_embedding_data.py — Format parallel pairs for
sentence-transformers contrastive training.
"""

import json
import random
from pathlib import Path

PAIRS_FILE = Path("data/parallel/grc_eng_pairs.jsonl")
TRAIN_OUT = Path("data/parallel/train_pairs.jsonl")
EVAL_OUT = Path("data/parallel/eval_pairs.jsonl")

pairs = []
with open(PAIRS_FILE) as f:
    for line in f:
        pairs.append(json.loads(line))

random.seed(42)
random.shuffle(pairs)

# 90/10 split
split = int(len(pairs) * 0.9)
train = pairs[:split]
val = pairs[split:]

def write_pairs(data, path):
    """Write in sentence-transformers InputExample-compatible format."""
    with open(path, "w", encoding="utf-8") as f:
        for p in data:
            # Positive pair
            f.write(json.dumps({
                "sentence1": p["grc"],
                "sentence2": p["eng"],
                "label": 1.0
            }, ensure_ascii=False) + "\n")

write_pairs(train, TRAIN_OUT)
write_pairs(val, EVAL_OUT)

print(f"Training pairs: {len(train)}")
print(f"Evaluation pairs: {len(val)}")
```

### 6b. Fine-tune with contrastive loss

```python
#!/usr/bin/env python3
"""
s06_train_embedding_model.py — Fine-tune into a sentence embedding model
using MultipleNegativesRankingLoss (contrastive learning).

This is the most effective single-GPU/CPU approach for learning
cross-lingual sentence embeddings from parallel data.

Expected time: 2-6 hours on Apple Silicon, 6-18 hours on Intel.
"""

import json
import torch
from pathlib import Path
from sentence_transformers import (
    SentenceTransformer,
    InputExample,
    losses,
    evaluation,
)
from torch.utils.data import DataLoader

MLM_MODEL = Path("models/xlm-r-greek-mlm")
TRAIN_FILE = Path("data/parallel/train_pairs.jsonl")
EVAL_FILE = Path("data/parallel/eval_pairs.jsonl")
OUTPUT_DIR = Path("models/ancient-greek-embedding")

# Check if our MLM model exists; if not, fall back to base
if MLM_MODEL.exists():
    base_model = str(MLM_MODEL)
    print(f"Using Greek-adapted MLM model from {MLM_MODEL}")
else:
    base_model = "xlm-roberta-base"
    print("MLM model not found — using base xlm-roberta (results will be weaker)")

# Build sentence-transformers model with mean pooling
from sentence_transformers import models

word_embedding = models.Transformer(base_model, max_seq_length=256)
pooling = models.Pooling(
    word_embedding.get_word_embedding_dimension(),
    pooling_mode_mean_tokens=True,
    pooling_mode_cls_token=False,
    pooling_mode_max_tokens=False,
)
dense = models.Dense(
    in_features=pooling.get_sentence_embedding_dimension(),
    out_features=256,  # Compact embedding dimension
    activation_function=torch.nn.Tanh(),
)

model = SentenceTransformer(modules=[word_embedding, pooling, dense])

# Load training data
def load_examples(path):
    examples = []
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            examples.append(InputExample(
                texts=[d["sentence1"], d["sentence2"]],
                label=d["label"]
            ))
    return examples

train_examples = load_examples(TRAIN_FILE)
eval_examples = load_examples(EVAL_FILE)

print(f"Training examples: {len(train_examples)}")
print(f"Evaluation examples: {len(eval_examples)}")

# DataLoader
train_dataloader = DataLoader(
    train_examples,
    shuffle=True,
    batch_size=16,  # Laptop-friendly
)

# Loss: MultipleNegativesRankingLoss
# Uses in-batch negatives — very data-efficient
train_loss = losses.MultipleNegativesRankingLoss(model)

# Evaluator: translation retrieval accuracy
eval_sentences1 = [e.texts[0] for e in eval_examples]
eval_sentences2 = [e.texts[1] for e in eval_examples]

evaluator = evaluation.TranslationEvaluator(
    source_sentences=eval_sentences1,
    target_sentences=eval_sentences2,
    name="grc-eng-retrieval",
    show_progress_bar=True,
    batch_size=32,
)

# Training
num_epochs = 5
warmup_steps = int(len(train_dataloader) * num_epochs * 0.1)

print(f"\nStarting embedding fine-tuning...")
print(f"Epochs: {num_epochs}, Warmup steps: {warmup_steps}")

model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    evaluator=evaluator,
    epochs=num_epochs,
    warmup_steps=warmup_steps,
    output_path=str(OUTPUT_DIR),
    evaluation_steps=500,
    save_best_model=True,
    show_progress_bar=True,
    use_amp=False,  # AMP not reliably supported on MPS
)

print(f"\n✅ Model saved to {OUTPUT_DIR}")
```

---

## 7. Stage 3 — Evaluation

### 7a. Script: `s07_evaluate_model.py`

```python
#!/usr/bin/env python3
"""
Evaluate the custom Ancient Greek embedding model against baselines.

Tests:
  1. Translation retrieval accuracy (Greek → English)
  2. Cosine similarity distribution for parallel vs. random pairs
  3. Comparison against the generic multilingual MiniLM
"""

import json
import random
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from scipy.spatial.distance import cdist

CUSTOM_MODEL = Path("models/ancient-greek-embedding")
BASELINE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EVAL_FILE = Path("data/parallel/eval_pairs.jsonl")
REPORT = Path("output/embedding_eval_report.md")

# Load eval data
pairs = []
with open(EVAL_FILE) as f:
    for line in f:
        pairs.append(json.loads(line))

greek_sents = [p["sentence1"] for p in pairs]
eng_sents = [p["sentence2"] for p in pairs]

n = len(pairs)
print(f"Evaluation set: {n} pairs")

results = {}

for model_name, model_path in [
    ("Custom Ancient Greek", str(CUSTOM_MODEL)),
    ("Multilingual MiniLM (baseline)", BASELINE_MODEL),
]:
    if not Path(model_path).exists() and model_path == str(CUSTOM_MODEL):
        print(f"Skipping {model_name} — model not found at {model_path}")
        continue
    
    print(f"\n=== Evaluating: {model_name} ===")
    model = SentenceTransformer(model_path)
    
    # Encode
    grc_embs = model.encode(greek_sents, show_progress_bar=True, batch_size=32)
    eng_embs = model.encode(eng_sents, show_progress_bar=True, batch_size=32)
    
    # 1. Translation retrieval: for each Greek sentence, rank all English sentences
    #    and check if the correct one is in top-1, top-5, top-10
    sim = 1 - cdist(grc_embs, eng_embs, metric="cosine")
    
    top1 = 0
    top5 = 0
    top10 = 0
    mrr_sum = 0
    for i in range(n):
        ranking = np.argsort(-sim[i])
        rank = np.where(ranking == i)[0][0] + 1  # 1-indexed
        if rank <= 1:
            top1 += 1
        if rank <= 5:
            top5 += 1
        if rank <= 10:
            top10 += 1
        mrr_sum += 1.0 / rank
    
    acc1 = top1 / n
    acc5 = top5 / n
    acc10 = top10 / n
    mrr = mrr_sum / n
    
    # 2. Cosine similarity distributions
    parallel_sims = [float(sim[i, i]) for i in range(n)]
    
    # Random pairs
    random.seed(42)
    random_sims = []
    for i in range(min(n, 1000)):
        j = random.choice([x for x in range(n) if x != i])
        random_sims.append(float(sim[i, j]))
    
    results[model_name] = {
        "retrieval_accuracy_top1": round(acc1, 4),
        "retrieval_accuracy_top5": round(acc5, 4),
        "retrieval_accuracy_top10": round(acc10, 4),
        "mrr": round(mrr, 4),
        "parallel_sim_mean": round(np.mean(parallel_sims), 4),
        "parallel_sim_std": round(np.std(parallel_sims), 4),
        "random_sim_mean": round(np.mean(random_sims), 4),
        "random_sim_std": round(np.std(random_sims), 4),
        "separation": round(np.mean(parallel_sims) - np.mean(random_sims), 4),
    }
    
    r = results[model_name]
    print(f"  Top-1 accuracy: {r['retrieval_accuracy_top1']:.1%}")
    print(f"  Top-5 accuracy: {r['retrieval_accuracy_top5']:.1%}")
    print(f"  MRR: {r['mrr']:.3f}")
    print(f"  Parallel sim: {r['parallel_sim_mean']:.3f} ± {r['parallel_sim_std']:.3f}")
    print(f"  Random sim:   {r['random_sim_mean']:.3f} ± {r['random_sim_std']:.3f}")
    print(f"  Separation:   {r['separation']:.3f}")

# Write report
REPORT.parent.mkdir(parents=True, exist_ok=True)
lines = [
    "# Ancient Greek Embedding Model — Evaluation Report\n",
    f"Evaluation set: {n} Greek-English parallel sections\n",
]
for name, r in results.items():
    lines.append(f"\n## {name}\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    for k, v in r.items():
        label = k.replace("_", " ").title()
        if "accuracy" in k or k == "mrr":
            lines.append(f"| {label} | {v:.1%} |")
        else:
            lines.append(f"| {label} | {v:.4f} |")

with open(REPORT, "w") as f:
    f.write("\n".join(lines))

print(f"\nReport saved to {REPORT}")
```

### 7b. Expected results

With a reasonable parallel corpus (10K+ pairs) and 3 epochs of MLM + 5 epochs of embedding training:

| Metric | Baseline MiniLM | Custom Model (expected) |
|---|---|---|
| Top-1 retrieval | 15–30% | 40–65% |
| Top-5 retrieval | 30–50% | 65–85% |
| MRR | 0.20–0.35 | 0.45–0.70 |
| Parallel–random separation | 0.10–0.20 | 0.25–0.45 |

The custom model should roughly double retrieval accuracy for Ancient Greek.

---

## 8. Integration with the Alignment Pipeline

Replace the model in `05_embed_and_align.py`:

```python
# In 05_embed_and_align.py, change this line:
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# To:
from pathlib import Path
CUSTOM_MODEL = Path("models/ancient-greek-embedding")
if CUSTOM_MODEL.exists():
    model = SentenceTransformer(str(CUSTOM_MODEL))
    print("Using custom Ancient Greek embedding model")
else:
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    print("Falling back to generic multilingual model")
```

No other changes needed — the embedding dimension may differ (256 vs. 384) but the cosine similarity computation is dimension-agnostic.

---

## 9. Alternative / Supplementary Approaches

If the parallel corpus is too small (< 5,000 pairs), or if you want to try other methods:

### 9a. CLTK + FastText static embeddings

Faster to train, lower quality, but good as a lightweight fallback:

```python
#!/usr/bin/env python3
"""
s08_fasttext_fallback.py — Train FastText embeddings on Ancient Greek
and align via cross-lingual word embedding mapping.

Requires: pip install gensim
"""

from pathlib import Path
from gensim.models import FastText

CORPUS = Path("data/greek_corpus/ancient_greek_all.txt")
OUTPUT = Path("models/fasttext-grc.bin")

# Read corpus as list of tokenised sentences
sentences = []
with open(CORPUS) as f:
    for line in f:
        sentences.append(line.strip().split())

print(f"Training FastText on {len(sentences)} sentences...")

model = FastText(
    sentences=sentences,
    vector_size=100,
    window=5,
    min_count=3,
    workers=4,
    epochs=10,
    sg=1,  # Skip-gram
)

model.save(str(OUTPUT))
print(f"Saved to {OUTPUT}")

# Quick test
test_word = "ἱστορία"
if test_word in model.wv:
    similar = model.wv.most_similar(test_word, topn=5)
    print(f"\nMost similar to '{test_word}':")
    for word, score in similar:
        print(f"  {word}: {score:.3f}")
```

### 9b. Use Sentence-BERT distillation from a teacher model

If you have a strong English embedding model and the parallel data, you can distill cross-lingual knowledge without the MLM step:

```python
# Concept (not full script):
from sentence_transformers import SentenceTransformer, losses

teacher = SentenceTransformer("all-MiniLM-L6-v2")  # English-only teacher
student = SentenceTransformer("xlm-roberta-base")   # Multilingual student

# MSE loss: student(greek) should be close to teacher(english_translation)
train_loss = losses.MSELoss(model=student)

# This is faster than MNR loss but requires a good teacher
```

### 9c. Leverage CLTK's existing Ancient Greek NLP

```python
# CLTK provides lemmatisation, POS tagging, and word embeddings
# These can supplement the neural approach

from cltk import NLP
nlp = NLP(language="grc")

doc = nlp.analyze("Τοῖς τὰς κοινὰς ἱστορίας πραγματευσαμένοις")
for word in doc.words:
    print(f"{word.string:20} lemma={word.lemma:15} pos={word.upos}")
```

---

## 10. Master Run Script

```bash
#!/bin/bash
# run_embedding_training.sh
set -e
cd ~/diodorus-alignment
source .venv/bin/activate

echo "=== S01: Build Greek corpus ==="
python s01_build_greek_corpus.py

echo "=== S02: Build parallel corpus ==="
python s02_build_parallel_corpus.py

echo "=== S03: Check tokeniser ==="
python s03_check_tokeniser.py

echo "=== S04: Continued pre-training (MLM) ==="
echo "⏱️  This will take 4-24 hours depending on hardware"
python s04_continued_pretraining.py

echo "=== S05: Prepare embedding training data ==="
python s05_prepare_embedding_data.py

echo "=== S06: Train sentence embedding model ==="
echo "⏱️  This will take 2-18 hours depending on hardware"
python s06_train_embedding_model.py

echo "=== S07: Evaluate ==="
python s07_evaluate_model.py

echo ""
echo "✅  Done. Custom model in models/ancient-greek-embedding/"
echo "    Eval report in output/embedding_eval_report.md"
echo "    Now re-run the alignment pipeline to use the new model."
```

---

## 11. Time & Resource Budget

| Stage | Apple Silicon (M1/M2/M3) | Intel Mac | Notes |
|---|---|---|---|
| Data download & prep | 10–30 min | 10–30 min | Network-bound |
| Corpus extraction (S01–S02) | 2–10 min | 5–15 min | XML parsing |
| Tokeniser check (S03) | < 1 min | < 1 min | |
| MLM continued pre-training (S04) | **4–8 hrs** | **12–24 hrs** | Biggest cost |
| Embedding data prep (S05) | < 1 min | < 1 min | |
| Embedding fine-tuning (S06) | **2–6 hrs** | **6–18 hrs** | Second biggest |
| Evaluation (S07) | 5–15 min | 10–30 min | |
| **Total** | **7–15 hrs** | **19–43 hrs** | Run overnight |

**Disk:** ~5 GB total (corpus + models + checkpoints)
**RAM peak:** ~6–10 GB during training

### Practical advice

- **Run overnight.** Start MLM training before bed; start embedding training the next morning.
- **Use `caffeinate`.** Prevent the Mac from sleeping:
  ```bash
  caffeinate -i ./run_embedding_training.sh
  ```
- **Monitor with Activity Monitor** or `htop` (Homebrew). Check that Python is using MPS (GPU column in Activity Monitor) on Apple Silicon.
- **Checkpointing is automatic.** If training crashes, it resumes from the last checkpoint.

---

## 12. All Additional Software

| Tool | Licence | Role |
|---|---|---|
| transformers (HuggingFace) | Apache 2.0 | Model loading, training loop |
| datasets (HuggingFace) | Apache 2.0 | Data loading |
| accelerate (HuggingFace) | Apache 2.0 | Device management |
| tokenizers | Apache 2.0 | BPE tokeniser training |
| torch (PyTorch) | BSD | Neural network backend |
| sentencepiece | Apache 2.0 | Subword tokenisation |
| gensim | LGPL 2.1 | FastText fallback |
| cltk | MIT | Ancient Greek NLP utilities |
| evaluate | Apache 2.0 | Metrics computation |
| First1KGreek corpus | CC BY-SA | Training data |
| Perseus canonical-greekLit | CC BY-SA 3.0 | Training + eval data |

All free, all open source, all pip-installable.

---

## 13. File Inventory After Completion

```
~/diodorus-alignment/
├── data/
│   ├── greek_corpus/
│   │   ├── First1KGreek/              # Cloned repo (~500 MB)
│   │   └── ancient_greek_all.txt      # Extracted corpus (20-60 MB)
│   └── parallel/
│       ├── grc_eng_pairs.jsonl        # Raw parallel pairs
│       ├── train_pairs.jsonl          # Training split
│       └── eval_pairs.jsonl           # Evaluation split
├── models/
│   ├── xlm-r-greek-extended/          # (optional) Extended tokeniser
│   ├── xlm-r-greek-mlm/              # After Stage 1 (~1 GB)
│   ├── ancient-greek-embedding/       # Final model (~300 MB)
│   └── fasttext-grc.bin              # (optional) FastText fallback
├── output/
│   └── embedding_eval_report.md       # Evaluation results
├── s01_build_greek_corpus.py
├── s02_build_parallel_corpus.py
├── s03_check_tokeniser.py
├── s03b_extend_tokeniser.py           # (optional)
├── s04_continued_pretraining.py
├── s05_prepare_embedding_data.py
├── s06_train_embedding_model.py
├── s07_evaluate_model.py
├── s08_fasttext_fallback.py           # (optional)
└── run_embedding_training.sh
```

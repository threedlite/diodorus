#!/usr/bin/env python3
"""
s04_latin_pretraining.py — MLM training on Latin corpus.

Continues training xlm-roberta-base on Latin text using Masked Language Modeling.
This adapts the base multilingual model to classical Latin vocabulary and syntax.

Expected time: 3-5 hours on Apple Silicon M4.

Input:
  - data-sources/latin_corpus/latin_all.txt

Output:
  - models/xlm-r-latin-mlm/ (~1-1.5 GB)
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = "xlm-roberta-base"
OUTPUT_DIR = PROJECT_ROOT / "models" / "xlm-r-latin-mlm"
CORPUS = PROJECT_ROOT / "data-sources" / "latin_corpus" / "latin_all.txt"

if not CORPUS.exists():
    print(f"Error: corpus not found at {CORPUS}")
    print("Run s01_build_latin_corpus.py first.")
    raise SystemExit(1)

# Detect device
if torch.backends.mps.is_available():
    device_info = "Apple Silicon MPS"
elif torch.cuda.is_available():
    device_info = "CUDA GPU"
else:
    device_info = "CPU (this will be slow but will work)"
print(f"Device: {device_info}")

# Load tokenizer and model
print(f"Loading model from {MODEL_PATH}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForMaskedLM.from_pretrained(MODEL_PATH)

# Cap at 200k sentences (v2: more data from full corpus for better coverage)
MAX_SENTENCES = 200_000
print(f"Loading corpus from {CORPUS}...")
dataset = load_dataset("text", data_files={"train": str(CORPUS)})
corpus_size = len(dataset["train"])
if corpus_size > MAX_SENTENCES:
    print(f"Corpus has {corpus_size} sentences; sampling {MAX_SENTENCES} for training")
    dataset["train"] = dataset["train"].shuffle(seed=42).select(range(MAX_SENTENCES))
else:
    print(f"Corpus has {corpus_size} sentences; using all")


# Tokenize
def tokenize_fn(examples):
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=128,
        padding=False,
        return_special_tokens_mask=True,
    )


print("Tokenizing corpus...")
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

# Training arguments — same as Greek pipeline (proven to work on M4 MPS)
training_args = TrainingArguments(
    output_dir=str(OUTPUT_DIR),

    per_device_train_batch_size=4,
    gradient_accumulation_steps=8,  # Effective batch = 32

    num_train_epochs=1,

    learning_rate=5e-5,
    warmup_ratio=0.1,
    weight_decay=0.01,

    logging_steps=50,
    save_steps=1000,
    save_total_limit=2,

    bf16=False,
    dataloader_num_workers=0,

    report_to="none",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized,
    data_collator=data_collator,
)

print(f"\nStarting MLM training on {len(tokenized)} examples...")
print(f"Effective batch size: {4 * 8} = 32")
print(f"Epochs: 1")

trainer.train()
trainer.save_model(str(OUTPUT_DIR))
tokenizer.save_pretrained(str(OUTPUT_DIR))

print(f"\nMLM model saved to {OUTPUT_DIR}")

# Sanity check: fill-mask pipeline
print("\nSanity check — fill-mask on Latin text:")
try:
    from transformers import pipeline
    fill_mask = pipeline("fill-mask", model=str(OUTPUT_DIR), tokenizer=str(OUTPUT_DIR))
    result = fill_mask("Gallia est omnis <mask> in partes tres")
    for r in result[:3]:
        print(f"  {r['token_str']:20} score={r['score']:.4f}")
except Exception as e:
    print(f"  Fill-mask test failed (non-critical): {e}")

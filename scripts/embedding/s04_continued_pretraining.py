#!/usr/bin/env python3
"""
s04_continued_pretraining.py — MLM training on Ancient Greek corpus.

Continues training xlm-roberta-base (or extended version from s03b) on
Ancient Greek text using Masked Language Modeling.

This adapts the base multilingual model to Ancient Greek vocabulary and syntax.
Expected time: 3-6 hours on Apple Silicon M4, longer on Intel.

Input:
  - data-sources/greek_corpus/ancient_greek_all.txt
  - (optional) models/xlm-r-greek-extended/

Output:
  - models/xlm-r-greek-mlm/ (~1-1.5 GB)

API notes for transformers 5.2.0:
  - overwrite_output_dir removed (always overwrites)
  - no_cuda removed (use accelerate device placement)
  - use_mps_device removed (auto-detected)
  - bf16=True works on M4 Apple Silicon
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

# Use extended model if it exists, otherwise base
EXTENDED_DIR = PROJECT_ROOT / "models" / "xlm-r-greek-extended"
if EXTENDED_DIR.exists():
    MODEL_PATH = str(EXTENDED_DIR)
    print("Using extended tokenizer model")
else:
    MODEL_PATH = "xlm-roberta-base"
    print("Using base xlm-roberta model")

OUTPUT_DIR = PROJECT_ROOT / "models" / "xlm-r-greek-mlm"
CORPUS = PROJECT_ROOT / "data-sources" / "greek_corpus" / "ancient_greek_all.txt"

if not CORPUS.exists():
    print(f"Error: corpus not found at {CORPUS}")
    print("Run s01_build_greek_corpus.py first.")
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

# Load corpus as a HuggingFace dataset
print(f"Loading corpus from {CORPUS}...")
dataset = load_dataset("text", data_files={"train": str(CORPUS)})


# Tokenize
def tokenize_fn(examples):
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=256,
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

# Training arguments — tuned for laptop, transformers 5.2.0 compatible
# Removed: overwrite_output_dir, no_cuda, use_mps_device (all deprecated/removed)
# Added: bf16=True for M4 speedup
training_args = TrainingArguments(
    output_dir=str(OUTPUT_DIR),

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

    # Performance — bf16 works on M4 Apple Silicon
    bf16=True,
    dataloader_num_workers=2,

    # Reporting
    report_to="none",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized,
    data_collator=data_collator,
)

print(f"\nStarting MLM training on {len(tokenized)} examples...")
print(f"Effective batch size: {8 * 4} = 32")
print(f"Epochs: 3")

trainer.train()
trainer.save_model(str(OUTPUT_DIR))
tokenizer.save_pretrained(str(OUTPUT_DIR))

print(f"\nMLM model saved to {OUTPUT_DIR}")

# Sanity check: fill-mask pipeline
print("\nSanity check — fill-mask on Greek text:")
try:
    from transformers import pipeline
    fill_mask = pipeline("fill-mask", model=str(OUTPUT_DIR), tokenizer=str(OUTPUT_DIR))
    result = fill_mask("Τοῖς τὰς κοινὰς <mask> πραγματευσαμένοις")
    for r in result[:3]:
        print(f"  {r['token_str']:20} score={r['score']:.4f}")
except Exception as e:
    print(f"  Fill-mask test failed (non-critical): {e}")

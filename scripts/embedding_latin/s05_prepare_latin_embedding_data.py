#!/usr/bin/env python3
"""
s05_prepare_latin_embedding_data.py — Format parallel pairs for
sentence-transformers contrastive training.

Splits the parallel corpus 90% train / 10% eval and reformats
as sentence-transformers InputExample-compatible JSONL.

Input:
  - data-sources/latin_parallel/lat_eng_pairs.jsonl

Output:
  - data-sources/latin_parallel/train_pairs.jsonl
  - data-sources/latin_parallel/eval_pairs.jsonl
"""

import json
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PAIRS_FILE = PROJECT_ROOT / "data-sources" / "latin_parallel" / "lat_eng_pairs.jsonl"
TRAIN_OUT = PROJECT_ROOT / "data-sources" / "latin_parallel" / "train_pairs.jsonl"
EVAL_OUT = PROJECT_ROOT / "data-sources" / "latin_parallel" / "eval_pairs.jsonl"

if not PAIRS_FILE.exists():
    print(f"Error: parallel pairs not found at {PAIRS_FILE}")
    print("Run s02_build_latin_parallel_corpus.py first.")
    raise SystemExit(1)

pairs = []
with open(PAIRS_FILE) as f:
    for line in f:
        pairs.append(json.loads(line))

print(f"Loaded {len(pairs)} parallel pairs")

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
            f.write(json.dumps({
                "sentence1": p["lat"],
                "sentence2": p["eng"],
                "label": 1.0
            }, ensure_ascii=False) + "\n")


write_pairs(train, TRAIN_OUT)
write_pairs(val, EVAL_OUT)

print(f"Training pairs: {len(train)} -> {TRAIN_OUT}")
print(f"Evaluation pairs: {len(val)} -> {EVAL_OUT}")

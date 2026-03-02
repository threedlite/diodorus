#!/usr/bin/env python3
"""
s06_train_latin_embedding.py — Fine-tune into a sentence embedding model
using MultipleNegativesRankingLoss (contrastive learning).

Builds: Transformer -> MeanPooling -> Dense(768->256, Tanh)
Loss: MultipleNegativesRankingLoss (in-batch negatives, very data-efficient)
Evaluation: TranslationEvaluator (Latin->English retrieval accuracy)

Expected time: 3-6 hours on Apple Silicon M4.

Input:
  - models/xlm-r-latin-mlm/ (or falls back to xlm-roberta-base)
  - data-sources/latin_parallel/train_pairs.jsonl
  - data-sources/latin_parallel/eval_pairs.jsonl

Output:
  - models/latin-embedding/ (~300 MB - 1 GB)
"""

import json
import torch
from pathlib import Path
from sentence_transformers import (
    SentenceTransformer,
    InputExample,
    losses,
    evaluation,
    models,
)
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MLM_MODEL = PROJECT_ROOT / "models" / "xlm-r-latin-mlm"
TRAIN_FILE = PROJECT_ROOT / "data-sources" / "latin_parallel" / "train_pairs.jsonl"
EVAL_FILE = PROJECT_ROOT / "data-sources" / "latin_parallel" / "eval_pairs.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "models" / "latin-embedding"

# Check prerequisites
for required, name in [(TRAIN_FILE, "training data"), (EVAL_FILE, "eval data")]:
    if not required.exists():
        print(f"Error: {name} not found at {required}")
        print("Run s05_prepare_latin_embedding_data.py first.")
        raise SystemExit(1)

# Check if our MLM model exists; if not, fall back to base
if MLM_MODEL.exists():
    base_model = str(MLM_MODEL)
    print(f"Using Latin-adapted MLM model from {MLM_MODEL}")
else:
    base_model = "xlm-roberta-base"
    print("MLM model not found -- using base xlm-roberta (results will be weaker)")

# Build sentence-transformers model with mean pooling + dense layer
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
    batch_size=32,  # v2: more in-batch negatives for contrastive learning
)

# Loss: MultipleNegativesRankingLoss (contrastive, in-batch negatives)
train_loss = losses.MultipleNegativesRankingLoss(model)

# Evaluator: translation retrieval accuracy
eval_sentences1 = [e.texts[0] for e in eval_examples]
eval_sentences2 = [e.texts[1] for e in eval_examples]

evaluator = evaluation.TranslationEvaluator(
    source_sentences=eval_sentences1,
    target_sentences=eval_sentences2,
    name="lat-eng-retrieval",
    show_progress_bar=True,
    batch_size=32,
)

# Training
num_epochs = 10  # v2: model still improving at epoch 5, needs more passes
warmup_steps = int(len(train_dataloader) * num_epochs * 0.1)

print(f"\nStarting embedding fine-tuning...")
print(f"Epochs: {num_epochs}")
print(f"Batch size: 32")
print(f"Warmup steps: {warmup_steps}")
print(f"Output: {OUTPUT_DIR}")

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

print(f"\nModel saved to {OUTPUT_DIR}")

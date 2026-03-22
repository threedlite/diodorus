#!/usr/bin/env python3
"""
s07_evaluate_model.py — Evaluate the custom Ancient Greek embedding model
against the baseline multilingual MiniLM.

Tests:
  1. Translation retrieval accuracy (Greek -> English), top-1/5/10
  2. Mean Reciprocal Rank (MRR)
  3. Cosine similarity distribution for parallel vs. random pairs
  4. Comparison against the generic multilingual MiniLM baseline

Input:
  - models/ancient-greek-embedding/
  - data-sources/parallel/eval_pairs.jsonl

Output:
  - output/embedding_eval_report.md

Quality gates (minimum acceptable):
  - Top-1 retrieval >= 30%
  - Top-5 retrieval >= 50%
  - MRR >= 0.35
  - Parallel-random separation >= 0.15
"""

import json
import random
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from scipy.spatial.distance import cdist

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CUSTOM_MODEL = PROJECT_ROOT / "models" / "ancient-greek-embedding"
BASELINE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EVAL_FILE = PROJECT_ROOT / "data-sources" / "parallel" / "eval_pairs.jsonl"
REPORT = PROJECT_ROOT / "build" / "embedding_eval_report.md"

if not EVAL_FILE.exists():
    print(f"Error: eval data not found at {EVAL_FILE}")
    print("Run s05_prepare_embedding_data.py first.")
    raise SystemExit(1)

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
        print(f"Skipping {model_name} -- model not found at {model_path}")
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
    print(f"  Top-10 accuracy: {r['retrieval_accuracy_top10']:.1%}")
    print(f"  MRR: {r['mrr']:.3f}")
    print(f"  Parallel sim: {r['parallel_sim_mean']:.3f} +/- {r['parallel_sim_std']:.3f}")
    print(f"  Random sim:   {r['random_sim_mean']:.3f} +/- {r['random_sim_std']:.3f}")
    print(f"  Separation:   {r['separation']:.3f}")

# Write report
REPORT.parent.mkdir(parents=True, exist_ok=True)
lines = [
    "# Ancient Greek Embedding Model -- Evaluation Report\n",
    f"Evaluation set: {n} Greek-English parallel sections\n",
]
for name, r in results.items():
    lines.append(f"\n## {name}\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    for k, v in r.items():
        label = k.replace("_", " ").title()
        if "accuracy" in k or k == "mrr":
            lines.append(f"| {label} | {v:.1%} |")
        else:
            lines.append(f"| {label} | {v:.4f} |")

# Quality gate check
if "Custom Ancient Greek" in results:
    r = results["Custom Ancient Greek"]
    lines.append("\n## Quality Gates\n")
    lines.append("| Gate | Minimum | Actual | Pass? |")
    lines.append("|---|---|---|---|")
    gates = [
        ("Top-1 retrieval", 0.30, r["retrieval_accuracy_top1"]),
        ("Top-5 retrieval", 0.50, r["retrieval_accuracy_top5"]),
        ("MRR", 0.35, r["mrr"]),
        ("Separation", 0.15, r["separation"]),
    ]
    all_pass = True
    for gate_name, minimum, actual in gates:
        passed = actual >= minimum
        if not passed:
            all_pass = False
        lines.append(f"| {gate_name} | {minimum:.0%} | {actual:.1%} | {'PASS' if passed else 'FAIL'} |")

    if all_pass:
        lines.append("\nAll quality gates passed. Model is ready for integration.")
    else:
        lines.append("\nSome quality gates failed. See fallback strategy in plans/greek_embedding_plan.md.")

with open(REPORT, "w") as f:
    f.write("\n".join(lines) + "\n")

print(f"\nReport saved to {REPORT}")

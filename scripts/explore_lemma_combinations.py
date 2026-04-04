#!/usr/bin/env python3
"""
Explore nonlinear combinations of character similarity and translation cosine
to find natural separation between inflected forms and unrelated pairs.

Reads the pair exploration CSV and tests several combination strategies.

Usage:
    python scripts/explore_lemma_combinations.py
"""

import csv
import math
import random
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def harmonic_mean(a, b):
    if a + b == 0:
        return 0.0
    return 2 * a * b / (a + b)


def geometric_mean(a, b):
    if a <= 0 or b <= 0:
        return 0.0
    return math.sqrt(a * b)


def product(a, b):
    return a * b


def min_score(a, b):
    return min(a, b)


def weighted_harmonic(a, b, w=0.7):
    """Weighted harmonic mean — w controls emphasis on char similarity."""
    if a == 0 or b == 0:
        return 0.0
    return (1 + 1) / (w / a + (1 - w) / b)


def main():
    csv_path = PROJECT_ROOT / "build" / "lemma_pair_exploration.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found. Run explore_lemma_pairs.py first.",
              file=sys.stderr)
        sys.exit(1)

    print("Loading pair data...")
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "word1": r["word1"],
                "word2": r["word2"],
                "tc": float(r["translation_cosine"]),
                "tj": float(r["trigram_jaccard"]),
                "lcs": float(r["lc_substring"]),
                "edr": float(r["edit_dist_ratio"]),
                "lcseq": float(r["lc_subsequence"]),
            })
    print(f"Loaded {len(rows)} pairs")

    # Use lc_substring as the best character metric from previous analysis
    char_metric = "lcs"

    combinations = [
        ("product", lambda r: product(r[char_metric], r["tc"])),
        ("geometric_mean", lambda r: geometric_mean(r[char_metric], r["tc"])),
        ("harmonic_mean", lambda r: harmonic_mean(r[char_metric], r["tc"])),
        ("min", lambda r: min_score(r[char_metric], r["tc"])),
        ("weighted_harm_0.7", lambda r: weighted_harmonic(r[char_metric], r["tc"], 0.7)),
        ("weighted_harm_0.3", lambda r: weighted_harmonic(r[char_metric], r["tc"], 0.3)),
        # Also try with edit_dist_ratio
        ("product_edr", lambda r: product(r["edr"], r["tc"])),
        ("harmonic_edr", lambda r: harmonic_mean(r["edr"], r["tc"])),
    ]

    # Compute combined scores
    for r in rows:
        for name, func in combinations:
            r[name] = func(r)

    # For each combination, build histogram and look for gaps
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(4, 2, figsize=(14, 20))
    axes = axes.flatten()

    print(f"\n{'Combination':<22} {'Non-zero':>8} {'P25':>6} {'P50':>6} {'P75':>6} {'P90':>6} {'P95':>6}")
    for idx, (name, _) in enumerate(combinations):
        scores = [r[name] for r in rows]
        nonzero = [s for s in scores if s > 0]

        if nonzero:
            pcts = np.percentile(nonzero, [25, 50, 75, 90, 95])
            print(f"{name:<22} {len(nonzero):>8} {pcts[0]:>6.3f} {pcts[1]:>6.3f} "
                  f"{pcts[2]:>6.3f} {pcts[3]:>6.3f} {pcts[4]:>6.3f}")
        else:
            print(f"{name:<22} {0:>8}")

        ax = axes[idx]
        ax.hist(nonzero, bins=100, color="steelblue", edgecolor="none", alpha=0.7)
        ax.set_title(name)
        ax.set_xlabel("Combined score")
        ax.set_ylabel("Count")
        ax.set_xlim(0, 1)

    fig.suptitle("Distribution of Combined Scores (non-zero only)", fontsize=14)
    fig.tight_layout()
    plot_path = PROJECT_ROOT / "build" / "lemma_combined_histograms.png"
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    print(f"\nSaved: {plot_path}")

    # Now look at top-scoring pairs for the most promising combination
    # to see if they're actually inflections
    print("\n--- Top pairs by harmonic mean (lc_substring + translation_cosine) ---")
    rows_sorted = sorted(rows, key=lambda r: -r["harmonic_mean"])
    for r in rows_sorted[:30]:
        print(f"  {r['word1']:<20} — {r['word2']:<20}  "
              f"harm={r['harmonic_mean']:.3f}  char={r['lcs']:.3f}  trans={r['tc']:.3f}")

    print("\n--- Top pairs by geometric mean ---")
    rows_sorted = sorted(rows, key=lambda r: -r["geometric_mean"])
    for r in rows_sorted[:30]:
        print(f"  {r['word1']:<20} — {r['word2']:<20}  "
              f"geom={r['geometric_mean']:.3f}  char={r['lcs']:.3f}  trans={r['tc']:.3f}")

    # Score distribution scatter: combined score vs rank
    # Look for an "elbow" — a natural breakpoint
    fig2, axes2 = plt.subplots(2, 2, figsize=(14, 12))
    axes2 = axes2.flatten()
    for idx, name in enumerate(["product", "geometric_mean", "harmonic_mean", "min"]):
        ax = axes2[idx]
        scores = sorted([r[name] for r in rows if r[name] > 0], reverse=True)
        ax.plot(range(len(scores)), scores, linewidth=0.5, color="steelblue")
        ax.set_title(f"{name} — sorted scores")
        ax.set_xlabel("Rank")
        ax.set_ylabel("Score")
        ax.set_ylim(0, 1)

    fig2.suptitle("Sorted Combined Scores — Looking for Elbows", fontsize=14)
    fig2.tight_layout()
    elbow_path = PROJECT_ROOT / "build" / "lemma_combined_elbows.png"
    fig2.savefig(elbow_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {elbow_path}")


if __name__ == "__main__":
    main()

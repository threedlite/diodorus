#!/usr/bin/env python3
"""
Explore whether inflected Greek forms naturally separate from unrelated words
using different character similarity metrics vs translation vector cosine.

Compares three character metrics:
1. Trigram Jaccard (baseline)
2. Longest common substring ratio
3. Edit distance ratio (1 - levenshtein / max_len)
4. Longest common subsequence ratio

Outputs scatter plots and a CSV for inspection.

Usage:
    python scripts/explore_lemma_pairs.py
"""

import csv
import pickle
import random
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --- Character similarity metrics ---

def char_trigrams(word):
    """Return the set of character trigrams in a word."""
    if len(word) < 3:
        return {word}
    return {word[i:i+3] for i in range(len(word) - 2)}


def trigram_jaccard(w1, w2):
    """Character trigram Jaccard similarity."""
    t1 = char_trigrams(w1)
    t2 = char_trigrams(w2)
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


def longest_common_substring_ratio(w1, w2):
    """Length of longest common contiguous substring / length of shorter word."""
    n, m = len(w1), len(w2)
    if n == 0 or m == 0:
        return 0.0
    # DP table for LCS (substring, not subsequence)
    prev = [0] * (m + 1)
    best = 0
    for i in range(1, n + 1):
        curr = [0] * (m + 1)
        for j in range(1, m + 1):
            if w1[i-1] == w2[j-1]:
                curr[j] = prev[j-1] + 1
                if curr[j] > best:
                    best = curr[j]
        prev = curr
    return best / min(n, m)


def levenshtein(w1, w2):
    """Levenshtein edit distance."""
    n, m = len(w1), len(w2)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if w1[i-1] == w2[j-1] else 1
            curr[j] = min(curr[j-1] + 1, prev[j] + 1, prev[j-1] + cost)
        prev = curr
    return prev[m]


def edit_distance_ratio(w1, w2):
    """1 - (levenshtein / max(len1, len2))."""
    maxlen = max(len(w1), len(w2))
    if maxlen == 0:
        return 1.0
    return 1.0 - levenshtein(w1, w2) / maxlen


def longest_common_subsequence_ratio(w1, w2):
    """Length of longest common subsequence / length of shorter word."""
    n, m = len(w1), len(w2)
    if n == 0 or m == 0:
        return 0.0
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        curr = [0] * (m + 1)
        for j in range(1, m + 1):
            if w1[i-1] == w2[j-1]:
                curr[j] = prev[j-1] + 1
            else:
                curr[j] = max(curr[j-1], prev[j])
        prev = curr
    return prev[m] / min(n, m)


# --- Translation similarity ---

def translation_cosine(vec1, vec2):
    """Cosine similarity between two translation weight dicts."""
    all_keys = set(vec1.keys()) | set(vec2.keys())
    if not all_keys:
        return 0.0
    a = np.array([vec1.get(k, 0) for k in all_keys])
    b = np.array([vec2.get(k, 0) for k in all_keys])
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


# --- Sampling ---

def find_candidate_pairs(src2en, words, n_high_char=5000, n_random=5000):
    """Sample pairs biased toward high character overlap (where the action is)."""
    pairs = set()

    by_prefix = {}
    for w in words:
        for plen in (4, 5):
            if len(w) >= plen:
                pfx = w[:plen]
                by_prefix.setdefault(pfx, []).append(w)

    prefix_pairs = []
    for pfx, group in by_prefix.items():
        if len(group) < 2 or len(group) > 50:
            continue
        for i in range(len(group)):
            for j in range(i + 1, min(i + 5, len(group))):
                prefix_pairs.append((group[i], group[j]))

    random.shuffle(prefix_pairs)
    for p in prefix_pairs[:n_high_char]:
        pairs.add(p)

    word_list = list(words)
    attempts = 0
    while len(pairs) < n_high_char + n_random and attempts < n_random * 3:
        w1 = random.choice(word_list)
        w2 = random.choice(word_list)
        if w1 < w2:
            pairs.add((w1, w2))
        attempts += 1

    return list(pairs)


def main():
    pkl_path = PROJECT_ROOT / "build" / "global_lexical_table.pkl"
    if not pkl_path.exists():
        print(f"Error: {pkl_path} not found.", file=sys.stderr)
        sys.exit(1)

    print("Loading lexical table...")
    with open(pkl_path, "rb") as f:
        data = pickle.load(f)

    src2en = data["src2en"]

    words = [w for w, trans in src2en.items() if len(trans) >= 2 and len(w) >= 3]
    print(f"Words with ≥2 translations: {len(words)}")

    print("Sampling pairs...")
    random.seed(42)
    pairs = find_candidate_pairs(src2en, words)
    print(f"Pairs to evaluate: {len(pairs)}")

    metrics = [
        ("trigram_jaccard", trigram_jaccard),
        ("lc_substring", longest_common_substring_ratio),
        ("edit_dist_ratio", edit_distance_ratio),
        ("lc_subsequence", longest_common_subsequence_ratio),
    ]

    print("Computing similarities...")
    results = []
    for i, (w1, w2) in enumerate(pairs):
        tc = translation_cosine(src2en[w1], src2en[w2])
        row = {"word1": w1, "word2": w2, "translation_cosine": round(tc, 4)}
        for name, func in metrics:
            row[name] = round(func(w1, w2), 4)
        results.append(row)
        if (i + 1) % 2000 == 0:
            print(f"  {i+1}/{len(pairs)}...")

    # Write CSV
    csv_path = PROJECT_ROOT / "build" / "lemma_pair_exploration.csv"
    fieldnames = ["word1", "word2", "translation_cosine"] + [m[0] for m in metrics]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"Saved: {csv_path}")

    # Generate scatter plots — one per character metric
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    axes = axes.flatten()

    for idx, (name, _) in enumerate(metrics):
        ax = axes[idx]
        x_vals = [r[name] for r in results]
        y_vals = [r["translation_cosine"] for r in results]
        ax.scatter(x_vals, y_vals, alpha=0.08, s=4, c="steelblue")
        ax.set_xlabel(name)
        ax.set_ylabel("Translation Cosine")
        ax.set_title(name)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)

    fig.suptitle(f"Greek Word Pair Similarity — 4 Character Metrics ({len(results):,} pairs)",
                 fontsize=14)
    fig.tight_layout()

    plot_path = PROJECT_ROOT / "build" / "lemma_pair_scatter_4metrics.png"
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {plot_path}")

    # Quadrant analysis for each metric
    print(f"\nQuadrant analysis (threshold 0.3 on each axis):")
    print(f"{'Metric':<20} {'High+High':>10} {'High+Low':>10} {'Low+High':>10} {'Low+Low':>10}")
    for name, _ in metrics:
        hh = sum(1 for r in results if r[name] > 0.3 and r["translation_cosine"] > 0.3)
        hl = sum(1 for r in results if r[name] > 0.3 and r["translation_cosine"] <= 0.3)
        lh = sum(1 for r in results if r[name] <= 0.3 and r["translation_cosine"] > 0.3)
        ll = sum(1 for r in results if r[name] <= 0.3 and r["translation_cosine"] <= 0.3)
        print(f"{name:<20} {hh:>10} {hl:>10} {lh:>10} {ll:>10}")

    # Show examples from the "low char but high trans" quadrant for each metric
    # (these are the inflections that the metric MISSES)
    print("\n--- Pairs with high translation cosine (>0.3) missed by each metric (score ≤ 0.3) ---")
    for name, _ in metrics:
        missed = [r for r in results if r[name] <= 0.3 and r["translation_cosine"] > 0.3]
        print(f"\n  {name}: {len(missed)} missed")
        sample = random.sample(missed, min(8, len(missed)))
        for r in sample:
            top1 = max(src2en[r["word1"]], key=src2en[r["word1"]].get)
            top2 = max(src2en[r["word2"]], key=src2en[r["word2"]].get)
            print(f"    {r['word1']} ({top1}) — {r['word2']} ({top2})  "
                  f"{name}={r[name]:.2f} trans={r['translation_cosine']:.2f}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Build synthetic lemma groups from the lexical table using:
  - Longest common substring ratio (character similarity)
  - Translation vector cosine similarity
  - Product of the two as the combined score

Groups inflected Greek forms into lemma clusters without external
morphological models. Uses connected components on pairs above
a data-derived threshold.

Usage:
    python scripts/build_synthetic_lemmas.py
"""

import csv
import math
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from pyuca import Collator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def longest_common_substring_len(w1, w2):
    """Length of the longest common contiguous substring."""
    n, m = len(w1), len(w2)
    if n == 0 or m == 0:
        return 0
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
    return best


def lcs_ratio(w1, w2):
    """Longest common substring ratio: LCS length / min(len1, len2)."""
    minlen = min(len(w1), len(w2))
    if minlen == 0:
        return 0.0
    return longest_common_substring_len(w1, w2) / minlen


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


def find_elbow(scores):
    """Find elbow point in sorted descending scores using max curvature.

    Returns the threshold value at the elbow.
    """
    if len(scores) < 10:
        return 0.15  # fallback

    n = len(scores)
    # Normalize x to [0,1] so curvature isn't dominated by axis scale
    x = np.linspace(0, 1, n)
    y = np.array(scores)

    # Smooth with a moving average to reduce noise
    window = max(n // 50, 5)
    y_smooth = np.convolve(y, np.ones(window)/window, mode='valid')
    x_smooth = x[:len(y_smooth)]

    # Second derivative (curvature proxy)
    if len(y_smooth) < 5:
        return 0.15
    d2 = np.diff(y_smooth, 2)

    # Elbow = point of maximum second derivative (most negative curvature
    # means steepest dropoff). Look in the first 80% to avoid tail noise.
    search_range = int(len(d2) * 0.8)
    if search_range < 1:
        return 0.15
    elbow_idx = np.argmin(d2[:search_range])

    # Map back to score value
    elbow_score = float(y_smooth[elbow_idx])
    return elbow_score


def build_pairwise_clusters(edges, pair_scores, max_cluster_size=20):
    """Build clusters requiring pairwise similarity for all members.

    A node joins a cluster only if it has a qualifying score with every
    existing member. This prevents chain-merging where A-B and B-C link
    unrelated A and C.

    Args:
        edges: list of (word1, word2) pairs above threshold
        pair_scores: dict mapping (word1, word2) → score (both orderings)
        max_cluster_size: cap on cluster size

    Returns dict mapping node → component_id.
    """
    # Build adjacency with scores
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)

    # Sort nodes by degree descending — high-degree nodes seed clusters first
    nodes = sorted(adj.keys(), key=lambda n: len(adj[n]), reverse=True)

    components = {}
    clusters = []  # list of sets

    for node in nodes:
        if node in components:
            continue

        # Try to join an existing cluster
        best_cluster = None
        for i, cluster in enumerate(clusters):
            if len(cluster) >= max_cluster_size:
                continue
            # Check pairwise: node must have a score with every member
            all_linked = True
            for member in cluster:
                key = (min(node, member), max(node, member))
                if key not in pair_scores:
                    all_linked = False
                    break
            if all_linked:
                best_cluster = i
                break

        if best_cluster is not None:
            clusters[best_cluster].add(node)
            components[node] = best_cluster
        else:
            # Start a new cluster
            comp_id = len(clusters)
            clusters.append({node})
            components[node] = comp_id

    # Second pass: try to merge unclustered neighbors into existing clusters
    for node in nodes:
        if node in components:
            continue
        components[node] = len(clusters)
        clusters.append({node})

    return components


def main():
    pkl_path = PROJECT_ROOT / "build" / "global_lexical_table.pkl"
    if not pkl_path.exists():
        print(f"Error: {pkl_path} not found.", file=sys.stderr)
        sys.exit(1)

    print("Loading lexical table...")
    with open(pkl_path, "rb") as f:
        data = pickle.load(f)

    src2en = data["src2en"]
    src_idf = data.get("src_idf", {})
    cooccur = data.get("cooccur", {})

    words = [w for w in src2en if len(w) >= 3]
    print(f"Words: {len(words)}")

    # Step 1: Build candidate pairs — words sharing ≥4 chars in LCS
    print("Building candidate pairs (LCS ≥ 4 chars)...")
    # Index by character 4-grams for efficient candidate finding
    ngram_index = defaultdict(list)
    for w in words:
        seen = set()
        for i in range(len(w) - 3):
            ng = w[i:i+4]
            if ng not in seen:
                seen.add(ng)
                ngram_index[ng].append(w)

    # Generate candidate pairs from shared 4-grams
    candidate_pairs = set()
    for ng, members in ngram_index.items():
        if len(members) > 100:
            continue  # skip very common n-grams to keep it tractable
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                candidate_pairs.add((members[i], members[j]) if members[i] < members[j]
                                    else (members[j], members[i]))

    print(f"Candidate pairs from shared 4-grams: {len(candidate_pairs):,}")

    # Step 2: Score all candidate pairs
    print("Scoring pairs...")
    scored_pairs = []
    batch = 0
    for w1, w2 in candidate_pairs:
        lcs = lcs_ratio(w1, w2)
        if lcs < 0.5:  # early filter — need substantial stem overlap
            continue
        tc = translation_cosine(src2en[w1], src2en[w2])
        score = lcs * tc
        if score > 0:
            scored_pairs.append((w1, w2, score, lcs, tc))
        batch += 1
        if batch % 100000 == 0:
            print(f"  {batch:,}/{len(candidate_pairs):,}...")

    scored_pairs.sort(key=lambda x: -x[2])
    print(f"Pairs with positive product score: {len(scored_pairs):,}")

    # Step 3: Find threshold from elbow
    scores_sorted = [s[2] for s in scored_pairs]
    threshold = find_elbow(scores_sorted)
    # Clamp threshold to reasonable range
    threshold = max(0.10, min(threshold, 0.30))
    n_above = sum(1 for s in scores_sorted if s >= threshold)
    print(f"Elbow threshold: {threshold:.3f} ({n_above:,} pairs above)")

    # Step 4: Build clusters with pairwise requirement
    edges = [(w1, w2) for w1, w2, score, _, _ in scored_pairs if score >= threshold]
    print(f"Edges for clustering: {len(edges):,}")

    # Build lookup for pairwise scores (both orderings via canonical key)
    pair_scores = {}
    for w1, w2, score, _, _ in scored_pairs:
        if score >= threshold:
            key = (min(w1, w2), max(w1, w2))
            pair_scores[key] = score

    comp_map = build_pairwise_clusters(edges, pair_scores, max_cluster_size=20)

    # Group by component
    clusters = defaultdict(list)
    for word, comp_id in comp_map.items():
        clusters[comp_id].append(word)

    print(f"Lemma groups: {len(clusters):,}")

    # Step 5: Pick representative for each cluster (most frequent form)
    # Frequency = total cooccurrence count across all English translations
    def word_frequency(w):
        return sum(cooccur.get((w, ew), 0) for ew in src2en.get(w, {}))

    # Build word → best score into its group (for confidence column)
    word_best_score = {}
    for w1, w2, score, lcs, tc in scored_pairs:
        if score >= threshold:
            if w1 not in word_best_score or score > word_best_score[w1]:
                word_best_score[w1] = score
            if w2 not in word_best_score or score > word_best_score[w2]:
                word_best_score[w2] = score

    lemma_map = {}  # word → representative
    lemma_confidence = {}  # word → best score
    for comp_id, members in clusters.items():
        rep = max(members, key=word_frequency)
        for m in members:
            lemma_map[m] = rep
            lemma_confidence[m] = word_best_score.get(m, 0.0)
        # Representative's confidence is the max score of any link it has
        lemma_confidence[rep] = max(word_best_score.get(m, 0.0) for m in members)

    # Words not in any cluster map to themselves
    for w in words:
        if w not in lemma_map:
            lemma_map[w] = w
            lemma_confidence[w] = 0.0

    # Step 6: Write synthetic_lemmas.csv
    collator = Collator()
    lemma_index = []
    for comp_id, members in clusters.items():
        rep = max(members, key=word_frequency)
        members_sorted = sorted(members, key=collator.sort_key)
        top_en = max(src2en.get(rep, {}), key=src2en.get(rep, {}).get, default="")
        top_weight = src2en.get(rep, {}).get(top_en, 0)
        lemma_index.append({
            "lemma": rep,
            "forms": "|".join(members_sorted),
            "form_count": len(members),
            "top_english": top_en,
            "top_weight": round(top_weight, 4),
        })
    lemma_index.sort(key=lambda r: collator.sort_key(r["lemma"]))

    lemma_path = PROJECT_ROOT / "build" / "synthetic_lemmas.csv"
    with open(lemma_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["lemma", "forms", "form_count",
                                                "top_english", "top_weight"])
        writer.writeheader()
        writer.writerows(lemma_index)
    print(f"Saved: {lemma_path}")

    # Step 7: Save lemma_map and confidence to pickle for use by export_concordance
    lemma_pkl_path = PROJECT_ROOT / "build" / "synthetic_lemmas.pkl"
    with open(lemma_pkl_path, "wb") as f:
        pickle.dump({"lemma_map": lemma_map, "lemma_confidence": lemma_confidence}, f)
    print(f"Saved: {lemma_pkl_path}")

    # Stats
    grouped = sum(1 for w in words if lemma_map.get(w, w) != w)
    multi_clusters = [c for c in clusters.values() if len(c) >= 2]
    sizes = [len(c) for c in multi_clusters]
    print(f"\nSummary:")
    print(f"  Words grouped: {grouped:,} / {len(words):,}")
    print(f"  Multi-form lemma groups: {len(multi_clusters):,}")
    if sizes:
        print(f"  Cluster sizes: min={min(sizes)}, median={int(np.median(sizes))}, "
              f"max={max(sizes)}, mean={np.mean(sizes):.1f}")

    # Show sample groups
    print(f"\nSample lemma groups (top 20 by cluster size):")
    top_clusters = sorted(multi_clusters, key=len, reverse=True)[:20]
    for members in top_clusters:
        rep = max(members, key=word_frequency)
        top_en = max(src2en.get(rep, {}), key=src2en.get(rep, {}).get, default="")
        forms = ", ".join(sorted(members, key=collator.sort_key))
        print(f"  {rep} ({top_en}): {forms}")


if __name__ == "__main__":
    main()

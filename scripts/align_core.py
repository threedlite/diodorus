#!/usr/bin/env python3
"""
Core alignment algorithms shared across all author pipelines.

Two strategies:
  1. segmental_dp_align  — for sequential texts (Diodorus, Marcus Aurelius, Procopius, etc.)
  2. pairwise_match      — for non-sequential units (Aesop fables, epigrams, fragments, etc.)

Both produce the same output format: list of (source_indices, target_indices, score) groups.
"""

import math
import numpy as np


def _speaker_lcs_similarity(seq_a, seq_b):
    """LCS-based similarity between two speaker sequences.

    Returns a float in [0, 1] measuring how well the ordered speaker turns
    match. Uses the Longest Common Subsequence normalized by total length.
    """
    if not seq_a or not seq_b:
        return 0.0
    m, n = len(seq_a), len(seq_b)
    dp_lcs = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq_a[i - 1] == seq_b[j - 1]:
                dp_lcs[i][j] = dp_lcs[i - 1][j - 1] + 1
            else:
                dp_lcs[i][j] = max(dp_lcs[i - 1][j], dp_lcs[i][j - 1])
    lcs = dp_lcs[m][n]
    return (2 * lcs) / (m + n)


def segmental_dp_align(source_embs, target_embs, source_lens, target_lens,
                       expected_ratio, max_source=5, max_target=2,
                       source_speakers=None, target_speakers=None,
                       entity_matrix=None):
    """
    Segmental Dynamic Programming alignment for sequential texts.

    Assumes source and target are in roughly the same order (e.g., both follow
    book/chapter sequence). Groups 1-max_source source sections onto
    1-max_target target paragraphs.

    Scoring adapts automatically to group size: cosine similarity is weighted
    by 1/sqrt(g*e) because averaging more embeddings dilutes the signal.
    When speaker sequences are provided, speaker-sequence LCS similarity is
    blended in as an additional signal channel.

    Args:
        source_embs: np.array (n_src, dim) - source (e.g. Greek) embeddings
        target_embs: np.array (n_tgt, dim) - target (e.g. English) embeddings
        source_lens: list[int] - character lengths of source sections
        target_lens: list[int] - character lengths of target sections
        expected_ratio: float - expected source chars / target chars ratio
        max_source: int - max source sections per group (default 5)
        max_target: int - max target sections per group (default 2)
        source_speakers: list[list[str]] or None - ordered speaker names per
            source section (e.g. from TEI <speaker> tags). None for prose.
        target_speakers: list[str] or None - single speaker name per target
            section (e.g. from CAPS labels in English drama). None for prose.
        entity_matrix: np.array (n_src, n_tgt) or None - precomputed entity
            name overlap scores. entity_matrix[i][j] is the fraction of Greek
            names in source section i that fuzzy-match names in target section j.
            None if not available.

    Returns:
        list of (src_start, src_end, tgt_start, tgt_end, score) tuples
        where ranges are half-open [start, end)
    """
    n_src = len(source_embs)
    n_tgt = len(target_embs)
    dim = source_embs.shape[1]

    bandwidth = max(20, int(n_tgt * 0.15))

    # Prefix sums for efficient mean embedding computation
    prefix_src = np.zeros((n_src + 1, dim), dtype=np.float64)
    for i in range(n_src):
        prefix_src[i + 1] = prefix_src[i] + source_embs[i]

    prefix_tgt = np.zeros((n_tgt + 1, dim), dtype=np.float64)
    for i in range(n_tgt):
        prefix_tgt[i + 1] = prefix_tgt[i] + target_embs[i]

    prefix_src_len = np.zeros(n_src + 1, dtype=np.float64)
    for i in range(n_src):
        prefix_src_len[i + 1] = prefix_src_len[i] + source_lens[i]

    prefix_tgt_len = np.zeros(n_tgt + 1, dtype=np.float64)
    for i in range(n_tgt):
        prefix_tgt_len[i + 1] = prefix_tgt_len[i] + target_lens[i]

    NEG_INF = -1e18
    dp = np.full((n_src + 1, n_tgt + 1), NEG_INF, dtype=np.float64)
    dp[0][0] = 0.0
    parent = [[None] * (n_tgt + 1) for _ in range(n_src + 1)]

    for i in range(n_src + 1):
        j_expected = i * (n_tgt / n_src) if n_src > 0 else 0
        j_lo = max(0, int(j_expected - bandwidth))
        j_hi = min(n_tgt, int(j_expected + bandwidth))

        for j in range(j_lo, j_hi + 1):
            if dp[i][j] == NEG_INF:
                continue

            for g in range(1, max_source + 1):
                if i + g > n_src:
                    break
                for e in range(1, max_target + 1):
                    if j + e > n_tgt:
                        break

                    tgt_j_expected = (i + g) * (n_tgt / n_src) if n_src > 0 else 0
                    if abs((j + e) - tgt_j_expected) > bandwidth:
                        continue

                    mean_src = (prefix_src[i + g] - prefix_src[i]) / g
                    mean_tgt = (prefix_tgt[j + e] - prefix_tgt[j]) / e

                    norm_src = np.linalg.norm(mean_src)
                    norm_tgt = np.linalg.norm(mean_tgt)
                    if norm_src < 1e-10 or norm_tgt < 1e-10:
                        cos_sim = 0.0
                    else:
                        cos_sim = float(np.dot(mean_src, mean_tgt) / (norm_src * norm_tgt))

                    src_chars = prefix_src_len[i + g] - prefix_src_len[i]
                    tgt_chars = prefix_tgt_len[j + e] - prefix_tgt_len[j]
                    if tgt_chars > 0 and expected_ratio > 0:
                        ratio = (src_chars / tgt_chars) / expected_ratio
                        length_pen = math.exp(-0.5 * (ratio - 1.0) ** 2)
                    else:
                        length_pen = 0.5

                    # Adaptive weighting: cosine signal degrades as 1/sqrt(group_size)
                    # because averaging many embeddings dilutes specificity.
                    # Floor at 0.5: even diluted cosine from averaging many sections
                    # carries signal and shouldn't be dominated by length ratio.
                    cos_weight = max(0.5, 1.0 / math.sqrt(g * e))
                    len_weight = 1.0 - cos_weight

                    # Speaker sequence scoring (when available)
                    spk_score = None
                    if source_speakers is not None and target_speakers is not None:
                        # Build combined source speaker sequence for this group
                        src_seq = []
                        prev = None
                        for si in range(i, i + g):
                            for sp in source_speakers[si]:
                                if sp != prev:
                                    src_seq.append(sp)
                                    prev = sp
                        # Build target speaker sequence
                        tgt_seq = []
                        prev = None
                        for tj in range(j, j + e):
                            sp = target_speakers[tj]
                            if sp and sp != prev:
                                tgt_seq.append(sp)
                                prev = sp
                        if src_seq and tgt_seq:
                            spk_score = _speaker_lcs_similarity(src_seq, tgt_seq)

                    # Entity overlap scoring (when available)
                    ent_score = None
                    if entity_matrix is not None:
                        # Average entity overlap: for each source section in the
                        # group, take its best overlap with any target section.
                        # Average over source sections. This penalizes groups
                        # where some source sections have zero overlap (wrong
                        # grouping) even if others match well.
                        ent_sum = 0.0
                        ent_count = 0
                        for si in range(i, i + g):
                            best_for_si = 0.0
                            for tj in range(j, j + e):
                                if entity_matrix[si][tj] > best_for_si:
                                    best_for_si = entity_matrix[si][tj]
                            ent_sum += best_for_si
                            ent_count += 1
                        avg_ent = ent_sum / ent_count if ent_count > 0 else 0.0
                        if avg_ent > 0:
                            ent_score = avg_ent

                    # Combine all scoring channels additively.
                    # Each channel is on a [0, 1] scale and contributes
                    # independently — no relative weighting needed.
                    score = cos_weight * cos_sim + len_weight * length_pen
                    if spk_score is not None:
                        score += spk_score
                    if ent_score is not None:
                        score += ent_score

                    new_score = dp[i][j] + score

                    if new_score > dp[i + g][j + e]:
                        dp[i + g][j + e] = new_score
                        parent[i + g][j + e] = (i, j, g, e)

    # Backtrack
    if dp[n_src][n_tgt] == NEG_INF:
        best_score = NEG_INF
        ci, cj = n_src, n_tgt
        for i in range(max(0, n_src - max_source), n_src + 1):
            for j in range(max(0, n_tgt - max_target), n_tgt + 1):
                if dp[i][j] > best_score:
                    best_score = dp[i][j]
                    ci, cj = i, j
    else:
        ci, cj = n_src, n_tgt

    groups = []
    while ci > 0 and cj > 0 and parent[ci][cj] is not None:
        prev_i, prev_j, g, e = parent[ci][cj]
        mean_src = (prefix_src[ci] - prefix_src[prev_i]) / g
        mean_tgt = (prefix_tgt[cj] - prefix_tgt[prev_j]) / e
        norm_src = np.linalg.norm(mean_src)
        norm_tgt = np.linalg.norm(mean_tgt)
        if norm_src < 1e-10 or norm_tgt < 1e-10:
            cos_sim = 0.0
        else:
            cos_sim = float(np.dot(mean_src, mean_tgt) / (norm_src * norm_tgt))
        groups.append((prev_i, ci, prev_j, cj, cos_sim))
        ci, cj = prev_i, prev_j

    groups.reverse()
    return groups


def pairwise_match(source_embs, target_embs, min_similarity=0.3,
                   many_to_one=False):
    """
    Pairwise embedding matching for non-sequential texts.

    Finds the best target match for each source unit using cosine similarity.
    No ordering assumption — any source can match any target.

    Args:
        source_embs: np.array (n_src, dim) - source (e.g. Greek) embeddings
        target_embs: np.array (n_tgt, dim) - target (e.g. English) embeddings
        min_similarity: float - minimum cosine similarity to count as a match
        many_to_one: bool - if True, multiple sources can match the same target
                     (correct for variant texts like Aesop 4 / 4b / 4c).
                     If False, greedy 1-to-1 assignment (each target used once).

    Returns:
        matches: list of dicts, one per source unit:
            {
                "source_idx": int,
                "target_idx": int or None,    # None if unmatched
                "similarity": float,
                "runner_up_similarity": float,
                "match_type": "pairwise_top1" | "unmatched",
            }
        sim_matrix: np.array (n_src, n_tgt) - full cosine similarity matrix
    """
    n_src = len(source_embs)
    n_tgt = len(target_embs)

    # Normalize embeddings for cosine similarity via dot product
    src_norm = source_embs / (np.linalg.norm(source_embs, axis=1, keepdims=True) + 1e-10)
    tgt_norm = target_embs / (np.linalg.norm(target_embs, axis=1, keepdims=True) + 1e-10)

    # Full similarity matrix: (n_src, n_tgt)
    sim_matrix = src_norm @ tgt_norm.T

    if many_to_one:
        # Each source gets its absolute best target, no exclusion
        matches = []
        for i in range(n_src):
            sorted_indices = np.argsort(sim_matrix[i])[::-1]
            best_j = int(sorted_indices[0])
            best_sim = float(sim_matrix[i, best_j])
            runner_up = float(sim_matrix[i, sorted_indices[1]]) if n_tgt > 1 else 0.0

            if best_sim >= min_similarity:
                matches.append({
                    "source_idx": i,
                    "target_idx": best_j,
                    "similarity": best_sim,
                    "runner_up_similarity": runner_up,
                    "match_type": "pairwise_top1",
                })
            else:
                matches.append({
                    "source_idx": i,
                    "target_idx": None,
                    "similarity": best_sim,
                    "runner_up_similarity": runner_up,
                    "match_type": "unmatched",
                })
    else:
        # Greedy 1-to-1 matching: assign each source to its best available target
        pairs = []
        for i in range(n_src):
            for j in range(n_tgt):
                pairs.append((sim_matrix[i, j], i, j))
        pairs.sort(reverse=True)

        src_assigned = {}
        tgt_taken = set()

        for sim, src_i, tgt_j in pairs:
            if src_i in src_assigned:
                continue
            if tgt_j in tgt_taken:
                continue
            if sim < min_similarity:
                break
            src_assigned[src_i] = (tgt_j, float(sim))
            tgt_taken.add(tgt_j)

        matches = []
        for i in range(n_src):
            sorted_sims = np.sort(sim_matrix[i])[::-1]
            runner_up = float(sorted_sims[1]) if len(sorted_sims) > 1 else 0.0

            if i in src_assigned:
                tgt_idx, sim = src_assigned[i]
                matches.append({
                    "source_idx": i,
                    "target_idx": tgt_idx,
                    "similarity": sim,
                    "runner_up_similarity": runner_up,
                    "match_type": "pairwise_top1",
                })
            else:
                best_sim = float(sorted_sims[0]) if len(sorted_sims) > 0 else 0.0
                matches.append({
                    "source_idx": i,
                    "target_idx": None,
                    "similarity": best_sim,
                    "runner_up_similarity": runner_up,
                    "match_type": "unmatched",
                })

    return matches, sim_matrix


def cosine_similarity_single(a, b):
    """Cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

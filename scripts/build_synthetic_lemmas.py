#!/usr/bin/env python3
"""
Build synthetic lemma groups using unsupervised stemming.

Pipeline:
  1. Bootstrap clusters via LCS + translation cosine (pairwise validated)
  2. Discover suffixes and prefixes from bootstrap clusters
  3. Stem all words (strip longest suffix, normalize diacritics)
  4. Group by stem, validate with translation cosine
  5. Prefix-stripping pass for augmented verbs
  6. Distributional merge pass for remaining stragglers

No hardcoded Greek morphology — everything discovered from data.

Usage:
    python scripts/build_synthetic_lemmas.py
"""

import csv
import math
import pickle
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from pyuca import Collator

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MIN_STEM_LEN = 4  # minimum stem length after stripping


def strip_diacritics(word):
    """Strip diacritics from Greek word, returning base letters only."""
    nfd = unicodedata.normalize("NFD", word)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _lcs_with_position(w1, w2):
    """LCS length and start positions in both words."""
    n, m = len(w1), len(w2)
    if n == 0 or m == 0:
        return 0, 0, 0
    prev = [0] * (m + 1)
    best = 0
    best_i = 0
    best_j = 0
    for i in range(1, n + 1):
        curr = [0] * (m + 1)
        for j in range(1, m + 1):
            if w1[i-1] == w2[j-1]:
                curr[j] = prev[j-1] + 1
                if curr[j] > best:
                    best = curr[j]
                    best_i = i - best
                    best_j = j - best
        prev = curr
    return best, best_i, best_j


def lcs_ratio(w1, w2):
    """Longest common substring ratio on base letters."""
    b1 = strip_diacritics(w1)
    b2 = strip_diacritics(w2)
    minlen = min(len(b1), len(b2))
    if minlen == 0:
        return 0.0
    lcs_len, _, _ = _lcs_with_position(b1, b2)
    return lcs_len / minlen


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
    """Find elbow point in sorted descending scores."""
    if len(scores) < 10:
        return 0.15
    n = len(scores)
    y = np.array(scores)
    window = max(n // 50, 5)
    y_smooth = np.convolve(y, np.ones(window)/window, mode='valid')
    if len(y_smooth) < 5:
        return 0.15
    d2 = np.diff(y_smooth, 2)
    search_range = max(1, int(len(d2) * 0.8))
    elbow_idx = np.argmin(d2[:search_range])
    return float(y_smooth[elbow_idx])


def build_pairwise_clusters(edges, pair_scores, max_cluster_size=20):
    """Build clusters requiring pairwise similarity for all members."""
    adj = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)

    nodes = sorted(adj.keys(), key=lambda n: len(adj[n]), reverse=True)
    components = {}
    clusters = []
    representatives = {}

    for node in nodes:
        if node in components:
            continue
        best_cluster = None
        for i, cluster in enumerate(clusters):
            if len(cluster) >= max_cluster_size:
                continue
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
            comp_id = len(clusters)
            clusters.append({node})
            components[node] = comp_id
            representatives[comp_id] = node

    for node in nodes:
        if node in components:
            continue
        comp_id = len(clusters)
        components[node] = comp_id
        clusters.append({node})
        representatives[comp_id] = node

    return components, clusters, representatives


# ─── Suffix/prefix discovery ─────────────────────────────────────────────

def discover_affixes(cluster_list, position="suffix"):
    """Discover common affixes from bootstrap clusters.

    For each multi-member cluster, find shared stem and extract what
    differs. position="suffix" extracts endings, "prefix" extracts beginnings.
    """
    affix_counts = Counter()
    for members in cluster_list:
        if len(members) < 2:
            continue
        members_base = [strip_diacritics(w) for w in members]
        # Find shared stem length (minimum pairwise LCS)
        stem_len = min(len(w) for w in members_base)
        for i in range(len(members_base)):
            for j in range(i + 1, len(members_base)):
                l, p1, p2 = _lcs_with_position(members_base[i], members_base[j])
                stem_len = min(stem_len, l)

        for wb in members_base:
            diff_len = len(wb) - stem_len
            if diff_len < 1 or diff_len > 6:
                continue
            if position == "suffix":
                affix = wb[-diff_len:]
                if len(affix) < 1:
                    continue
            else:  # prefix
                affix = wb[:diff_len]
                if len(affix) < 2:  # prefixes must be ≥2 chars
                    continue
            if True:
                affix_counts[affix] += 1

    if not affix_counts:
        return frozenset(), affix_counts

    # Top 5% by frequency
    counts = sorted(affix_counts.values(), reverse=True)
    cutoff_idx = max(1, len(counts) // 20)
    freq_cutoff = counts[cutoff_idx]
    common = frozenset(a for a, c in affix_counts.items() if c >= freq_cutoff)
    return common, affix_counts


# ─── Stemming ─────────────────────────────────────────────────────────────

def build_suffix_list(common_suffixes, suffix_counts):
    """Build sorted suffix list (longest first) for greedy stripping.

    Excludes single-character suffixes — they're real grammatical endings
    (movable-nu, nominative-sigma) but too aggressive for stemming.
    """
    return sorted((s for s in common_suffixes if len(s) >= 2),
                  key=lambda s: (-len(s), -suffix_counts.get(s, 0)))


def stem_word(word_base, suffix_list):
    """Strip longest matching suffix from base-letter word.

    Returns (stem, suffix) or (word, "") if no suffix matches.
    """
    for suffix in suffix_list:
        if word_base.endswith(suffix):
            stem = word_base[:-len(suffix)]
            if len(stem) >= MIN_STEM_LEN:
                return stem, suffix
    return word_base, ""


def stem_word_with_prefix(word_base, suffix_list, prefix_list):
    """Try stripping prefix + suffix to get a stem.

    Used as rescue for words that don't stem cleanly with suffix alone.
    Returns (stem, prefix, suffix) or (word, "", "") if nothing works.
    """
    # First try suffix only
    stem, suffix = stem_word(word_base, suffix_list)
    if suffix:
        return stem, "", suffix

    # Try prefix stripping then suffix stripping
    for prefix in prefix_list:
        if word_base.startswith(prefix):
            remainder = word_base[len(prefix):]
            stem2, suffix2 = stem_word(remainder, suffix_list)
            if suffix2 and len(stem2) >= MIN_STEM_LEN:
                return stem2, prefix, suffix2
            # Also try just prefix stripping (no suffix)
            if len(remainder) >= MIN_STEM_LEN:
                return remainder, prefix, ""

    return word_base, "", ""


# ─── Main ─────────────────────────────────────────────────────────────────

def main():
    pkl_path = PROJECT_ROOT / "build" / "global_lexical_table.pkl"
    if not pkl_path.exists():
        print(f"Error: {pkl_path} not found.", file=sys.stderr)
        sys.exit(1)

    print("Loading lexical table...")
    with open(pkl_path, "rb") as f:
        data = pickle.load(f)

    src2en = data["src2en"]
    cooccur = data.get("cooccur", {})

    # Load distributional context vectors if available
    ctx_path = PROJECT_ROOT / "build" / "greek_contexts.pkl"
    dist_embeddings = None
    dist_word2idx = None
    if ctx_path.exists():
        print("Loading distributional context vectors...")
        with open(ctx_path, "rb") as f:
            ctx = pickle.load(f)
        dist_embeddings = ctx["embeddings"]
        dist_word2idx = ctx["word2idx"]
        print(f"  {len(dist_word2idx)} words, {dist_embeddings.shape[1]} dimensions")

    words = [w for w in src2en if len(w) >= 3]
    words_set = set(words)
    print(f"Words: {len(words)}")

    def word_frequency(w):
        return sum(cooccur.get((w, ew), 0) for ew in src2en.get(w, {}))

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 1: Bootstrap clusters via LCS + translation cosine
    # ═══════════════════════════════════════════════════════════════════════

    print("\n--- Phase 1: Bootstrap LCS clusters ---")
    print("Building candidate pairs...")
    ngram_index = defaultdict(list)
    for w in words:
        wb = strip_diacritics(w)
        seen = set()
        for i in range(len(wb) - 3):
            ng = wb[i:i+4]
            if ng not in seen:
                seen.add(ng)
                ngram_index[ng].append(w)

    # No member limit — process all groups
    candidate_pairs = set()
    skipped_large = 0
    for ng, members in ngram_index.items():
        if len(members) > 500:
            skipped_large += 1
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                candidate_pairs.add((members[i], members[j]) if members[i] < members[j]
                                    else (members[j], members[i]))
    print(f"Candidate pairs: {len(candidate_pairs):,} (skipped {skipped_large} very large groups)")

    print("Scoring pairs...")
    scored_pairs = []
    for idx, (w1, w2) in enumerate(candidate_pairs):
        b1 = strip_diacritics(w1)
        b2 = strip_diacritics(w2)
        lcs = _lcs_with_position(b1, b2)
        lcs_len, pos1, pos2 = lcs
        ratio = lcs_len / min(len(b1), len(b2)) if min(len(b1), len(b2)) > 0 else 0
        if ratio < 0.5 or lcs_len < 4:
            continue
        # Reject pure suffix matches
        if pos1 + lcs_len == len(b1) and pos2 + lcs_len == len(b2):
            continue
        tc = translation_cosine(src2en[w1], src2en[w2])
        # Weight toward character similarity when LCS is very high
        if ratio >= 0.8:
            score = (ratio ** 0.7) * (tc ** 0.3) if tc > 0 else 0
        else:
            score = ratio * tc
        if score > 0:
            scored_pairs.append((w1, w2, score, ratio, tc))
        if (idx + 1) % 200000 == 0:
            print(f"  {idx+1:,}/{len(candidate_pairs):,}...")

    scored_pairs.sort(key=lambda x: -x[2])
    print(f"Pairs with positive score: {len(scored_pairs):,}")

    threshold = find_elbow([s[2] for s in scored_pairs])
    threshold = max(0.10, min(threshold, 0.30))
    n_above = sum(1 for s in scored_pairs if s[2] >= threshold)
    print(f"Threshold: {threshold:.3f} ({n_above:,} pairs above)")

    lcs_edges = [(w1, w2) for w1, w2, score, _, _ in scored_pairs if score >= threshold]
    pair_scores = {}
    for w1, w2, score, _, _ in scored_pairs:
        if score >= threshold:
            pair_scores[(min(w1, w2), max(w1, w2))] = score

    comp_map, cluster_list, cluster_reps = build_pairwise_clusters(
        lcs_edges, pair_scores, max_cluster_size=20)

    for comp_id in range(len(cluster_list)):
        if len(cluster_list[comp_id]) >= 2:
            cluster_reps[comp_id] = max(cluster_list[comp_id], key=word_frequency)

    multi = [c for c in cluster_list if len(c) >= 2]
    print(f"Bootstrap: {len(multi):,} groups, "
          f"{sum(len(c) for c in multi):,} words grouped")

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2: Discover suffixes and prefixes
    # ═══════════════════════════════════════════════════════════════════════

    print("\n--- Phase 2: Discover affixes ---")
    common_suffixes, suffix_counts = discover_affixes(cluster_list, "suffix")
    suffix_list = build_suffix_list(common_suffixes, suffix_counts)
    print(f"Suffixes: {len(common_suffixes)}")
    if common_suffixes:
        top = sorted(common_suffixes, key=lambda s: -suffix_counts[s])[:15]
        print(f"  Top 15: {', '.join(f'{s}({suffix_counts[s]})' for s in top)}")

    common_prefixes, prefix_counts = discover_affixes(cluster_list, "prefix")
    prefix_list = sorted(common_prefixes,
                         key=lambda p: (-len(p), -prefix_counts.get(p, 0)))
    print(f"Prefixes: {len(common_prefixes)}")
    if common_prefixes:
        top = sorted(common_prefixes, key=lambda p: -prefix_counts[p])[:15]
        print(f"  Top 15: {', '.join(f'{p}({prefix_counts[p]})' for p in top)}")

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 3: Stem all words and group by stem
    # ═══════════════════════════════════════════════════════════════════════

    print("\n--- Phase 3: Stemming pass ---")
    stem_groups = defaultdict(list)  # stem → [words]
    word_stem = {}  # word → stem

    for w in words:
        wb = strip_diacritics(w)
        stem, prefix, suffix = stem_word_with_prefix(wb, suffix_list, prefix_list)
        word_stem[w] = stem
        stem_groups[stem].append(w)

    multi_stems = {s: ws for s, ws in stem_groups.items() if len(ws) >= 2}
    print(f"Unique stems: {len(stem_groups):,}")
    print(f"Multi-word stems: {len(multi_stems):,} "
          f"({sum(len(ws) for ws in multi_stems.values()):,} words)")

    # Validate stem groups with translation cosine — split divergent members
    print("Validating stem groups...")
    SPLIT_THRESHOLD = 0.15  # minimum cosine to centroid to stay in group

    final_groups = []  # list of (stem, [words])
    split_count = 0

    for stem, members in multi_stems.items():
        if len(members) <= 1:
            continue

        if len(members) == 2:
            # Simple pair: just check cosine
            w1, w2 = members
            tc = translation_cosine(src2en.get(w1, {}), src2en.get(w2, {}))
            if tc >= SPLIT_THRESHOLD:
                final_groups.append((stem, members))
            else:
                split_count += 1
            continue

        # For larger groups: compute centroid, remove members far from centroid
        # Centroid = average translation vector
        all_keys = set()
        for w in members:
            all_keys.update(src2en.get(w, {}).keys())
        if not all_keys:
            final_groups.append((stem, members))
            continue

        # Build matrix
        vecs = []
        for w in members:
            v = src2en.get(w, {})
            vecs.append(np.array([v.get(k, 0) for k in all_keys]))
        mat = np.array(vecs)
        centroid = mat.mean(axis=0)
        centroid_norm = np.linalg.norm(centroid)
        if centroid_norm == 0:
            final_groups.append((stem, members))
            continue
        centroid = centroid / centroid_norm

        # Keep members with cosine > threshold to centroid
        kept = []
        for i, w in enumerate(members):
            v = mat[i]
            norm = np.linalg.norm(v)
            if norm == 0:
                kept.append(w)  # keep words with no translation vector
                continue
            cos = float(np.dot(v / norm, centroid))
            if cos >= SPLIT_THRESHOLD:
                kept.append(w)

        if len(kept) >= 2:
            final_groups.append((stem, kept))
            if len(kept) < len(members):
                split_count += len(members) - len(kept)
        else:
            split_count += len(members)

    print(f"Validated stem groups: {len(final_groups):,}")
    print(f"Words split out: {split_count:,}")

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 4: Merge bootstrap clusters + stem groups
    # ═══════════════════════════════════════════════════════════════════════

    print("\n--- Phase 4: Merge all sources ---")

    # Start with bootstrap clusters
    lemma_map = {}
    lemma_confidence = {}

    # First, assign bootstrap cluster members
    for comp_id, members in enumerate(cluster_list):
        if len(members) < 2:
            continue
        rep = cluster_reps.get(comp_id)
        if rep is None:
            rep = max(members, key=word_frequency)
        for m in members:
            lemma_map[m] = rep
            key = (min(m, rep), max(m, rep))
            lemma_confidence[m] = pair_scores.get(key, 0.0)

    bootstrap_grouped = len(lemma_map)

    # Then, add stem group members that aren't already grouped
    stem_added = 0
    for stem, members in final_groups:
        # Find which members are already grouped and which aren't
        ungrouped = [w for w in members if w not in lemma_map]
        grouped = [w for w in members if w in lemma_map]

        if not ungrouped:
            continue

        # If some members are already in a bootstrap cluster, add ungrouped
        # to that cluster (use the most frequent grouped member's representative)
        if grouped:
            # Find the most common representative among grouped members
            rep_counts = Counter(lemma_map[w] for w in grouped)
            target_rep = rep_counts.most_common(1)[0][0]
            for w in ungrouped:
                lemma_map[w] = target_rep
                # Confidence based on translation cosine with representative
                tc = translation_cosine(src2en.get(w, {}), src2en.get(target_rep, {}))
                lemma_confidence[w] = tc
                stem_added += 1
        else:
            # No existing cluster — create new group from stem
            rep = max(members, key=word_frequency)
            for w in members:
                lemma_map[w] = rep
                if w != rep:
                    tc = translation_cosine(src2en.get(w, {}), src2en.get(rep, {}))
                    lemma_confidence[w] = tc
                    stem_added += 1
                else:
                    lemma_confidence[w] = 1.0

    print(f"Bootstrap grouped: {bootstrap_grouped:,}")
    print(f"Stem pass added: {stem_added:,}")

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 5: Distributional merge for remaining stragglers
    # ═══════════════════════════════════════════════════════════════════════

    dist_merged = 0
    if dist_embeddings is not None:
        print("\n--- Phase 5: Distributional merge ---")
        DIST_THRESHOLD = 0.55
        TRANS_MIN = 0.10
        LCS_MIN_CHARS = 3

        # Build reverse index
        dist_idx2word = {}
        for w in words:
            if w in dist_word2idx:
                dist_idx2word[dist_word2idx[w]] = w

        # Collect representatives of multi-member groups
        rep_to_members = defaultdict(set)
        for w, rep in lemma_map.items():
            rep_to_members[rep].add(w)

        rep_set = {}
        for rep, members in rep_to_members.items():
            if len(members) >= 2 and rep in dist_word2idx:
                rep_set[rep] = True

        print(f"  Representatives with dist vectors: {len(rep_set):,}")

        ungrouped = [w for w in words
                     if w in dist_word2idx and
                     (w not in lemma_map or lemma_map[w] == w) and
                     w not in rep_set]
        print(f"  Ungrouped words with dist vectors: {len(ungrouped):,}")

        rep_words = list(rep_set.keys())
        rep_indices = [dist_word2idx[w] for w in rep_words]
        rep_matrix = dist_embeddings[rep_indices]

        for wi, w1 in enumerate(ungrouped):
            if wi % 10000 == 0 and wi > 0:
                print(f"  {wi:,}/{len(ungrouped):,}...")

            v1 = dist_embeddings[dist_word2idx[w1]]
            sims = rep_matrix @ v1

            best_idx = np.argmax(sims)
            best_sim = float(sims[best_idx])
            if best_sim < DIST_THRESHOLD:
                continue

            best_rep = rep_words[best_idx]

            # LCS check on base letters
            b1 = strip_diacritics(w1)
            b2 = strip_diacritics(best_rep)
            lcs_len, lcs_pos1, lcs_pos2 = _lcs_with_position(b1, b2)
            if lcs_len < LCS_MIN_CHARS:
                continue
            shared = b1[lcs_pos1:lcs_pos1 + lcs_len]
            # Reject suffix-only matches
            if (lcs_pos1 + lcs_len == len(b1) and
                    lcs_pos2 + lcs_len == len(b2)):
                continue
            if shared in common_suffixes:
                continue

            # Translation cosine check
            if w1 in src2en and best_rep in src2en:
                tc = translation_cosine(src2en[w1], src2en[best_rep])
                if tc < TRANS_MIN:
                    continue
                score = best_sim * tc
            else:
                if best_sim < 0.70:
                    continue
                score = best_sim

            lemma_map[w1] = best_rep
            lemma_confidence[w1] = score
            dist_merged += 1

        print(f"  Singletons merged: {dist_merged:,}")

        # Phase 5b: Merge small clusters into larger ones via distributional
        # similarity between representatives
        print("  Merging small clusters into larger ones...")
        rep_to_members2 = defaultdict(set)
        for w, rep in lemma_map.items():
            rep_to_members2[rep].add(w)

        # Find small clusters (2-5 members) whose rep has a dist vector
        small_reps = {}  # rep → set of members
        large_reps = {}  # rep → set of members (target clusters)
        for rep, members in rep_to_members2.items():
            if rep not in dist_word2idx:
                continue
            if len(members) <= 5:
                small_reps[rep] = members
            elif len(members) >= 3:
                large_reps[rep] = members

        large_rep_words = list(large_reps.keys())
        if large_rep_words:
            large_rep_indices = [dist_word2idx[w] for w in large_rep_words]
            large_rep_matrix = dist_embeddings[large_rep_indices]

            cluster_merges = 0
            for small_rep, small_members in small_reps.items():
                v1 = dist_embeddings[dist_word2idx[small_rep]]
                sims = large_rep_matrix @ v1

                best_idx = np.argmax(sims)
                best_sim = float(sims[best_idx])
                if best_sim < 0.60:  # higher threshold for cluster merges
                    continue

                target_rep = large_rep_words[best_idx]
                if len(large_reps[target_rep]) + len(small_members) > 25:
                    continue

                # LCS check on base letters
                b1 = strip_diacritics(small_rep)
                b2 = strip_diacritics(target_rep)
                lcs_len, lcs_pos1, lcs_pos2 = _lcs_with_position(b1, b2)
                if lcs_len < LCS_MIN_CHARS:
                    continue
                shared = b1[lcs_pos1:lcs_pos1 + lcs_len]
                if (lcs_pos1 + lcs_len == len(b1) and
                        lcs_pos2 + lcs_len == len(b2)):
                    continue
                if shared in common_suffixes:
                    continue

                # Translation cosine between reps
                tc = translation_cosine(src2en.get(small_rep, {}),
                                        src2en.get(target_rep, {}))
                if tc < TRANS_MIN:
                    continue

                # Merge small cluster into large one
                for w in small_members:
                    lemma_map[w] = target_rep
                    lemma_confidence[w] = best_sim * tc
                large_reps[target_rep] |= small_members
                cluster_merges += 1

            print(f"  Cluster merges: {cluster_merges:,}")

        print(f"  Total distributional: {dist_merged + cluster_merges:,}")

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 6: Finalize and output
    # ═══════════════════════════════════════════════════════════════════════

    print("\n--- Phase 6: Output ---")

    # Ensure all words have a mapping
    for w in words:
        if w not in lemma_map:
            lemma_map[w] = w
            lemma_confidence[w] = 0.0

    # Build final cluster dict
    clusters = defaultdict(list)
    for w in words:
        clusters[lemma_map[w]].append(w)

    # Write synthetic_lemmas.csv
    collator = Collator()
    lemma_index = []
    for rep, members in clusters.items():
        if len(members) < 2:
            continue
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

    # Save pickle
    lemma_pkl_path = PROJECT_ROOT / "build" / "synthetic_lemmas.pkl"
    with open(lemma_pkl_path, "wb") as f:
        pickle.dump({"lemma_map": lemma_map, "lemma_confidence": lemma_confidence}, f)
    print(f"Saved: {lemma_pkl_path}")

    # Stats
    multi_clusters = [c for c in clusters.values() if len(c) >= 2]
    grouped = sum(1 for w in words if lemma_map.get(w, w) != w)
    sizes = [len(c) for c in multi_clusters]
    print(f"\nSummary:")
    print(f"  Words grouped: {grouped:,} / {len(words):,}")
    print(f"  Multi-form lemma groups: {len(multi_clusters):,}")
    if sizes:
        print(f"  Cluster sizes: min={min(sizes)}, median={int(np.median(sizes))}, "
              f"max={max(sizes)}, mean={np.mean(sizes):.1f}")

    # Sample groups
    print(f"\nSample lemma groups (top 20 by cluster size):")
    top_clusters = sorted(multi_clusters, key=len, reverse=True)[:20]
    for members in top_clusters:
        rep = lemma_map[members[0]]
        top_en = max(src2en.get(rep, {}), key=src2en.get(rep, {}).get, default="")
        forms = ", ".join(sorted(members, key=collator.sort_key))
        print(f"  {rep} ({top_en}): {forms}")


if __name__ == "__main__":
    main()

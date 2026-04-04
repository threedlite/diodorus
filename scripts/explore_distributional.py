#!/usr/bin/env python3
"""
Explore distributional similarity (metric 3) and discriminative filter (metric 4)
on known pairs to validate before integrating into lemma builder.

Tests:
- Augmented verb pairs (should be linked: ἠγάπησεν ↔ ἀγαπῶν)
- Synonym pairs (should NOT be linked: ἀγάπη ↔ φιλία)
- Known inflections (should be linked: θάνατος ↔ θανάτου)

Usage:
    python scripts/explore_distributional.py
"""

import pickle
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def distributional_cosine(w1, w2, embeddings, word2idx):
    """Cosine similarity of distributional context vectors."""
    if w1 not in word2idx or w2 not in word2idx:
        return None
    v1 = embeddings[word2idx[w1]]
    v2 = embeddings[word2idx[w2]]
    dot = np.dot(v1, v2)
    return float(dot)  # already unit normalized


def discriminative_score(w1, w2, embeddings, word2idx, idx2word, word_freq):
    """Compute inflection likelihood from discriminating context words.

    Finds context words that differ most between w1 and w2, then checks
    if those discriminators are high-frequency (function words → inflection)
    or low-frequency (content words → synonym).

    Returns:
        inflection_ratio: mean_freq(discriminators) / corpus_median_freq
        Higher = more likely inflectional, lower = more likely synonyms.
    """
    if w1 not in word2idx or w2 not in word2idx:
        return None, []

    v1 = embeddings[word2idx[w1]]
    v2 = embeddings[word2idx[w2]]

    # Find words most similar to w1 but not w2 (and vice versa)
    sims1 = embeddings @ v1
    sims2 = embeddings @ v2

    # Discriminating words: large difference in similarity
    diff = np.abs(sims1 - sims2)

    # Get top discriminators (excluding the words themselves)
    exclude = {word2idx.get(w1, -1), word2idx.get(w2, -1)}
    top_idx = np.argsort(-diff)
    discriminators = []
    for idx in top_idx:
        idx = int(idx)
        if idx in exclude:
            continue
        discriminators.append(idx)
        if len(discriminators) >= 20:
            break

    # Measure average frequency of discriminators
    disc_freqs = [word_freq.get(idx2word[i], 0) for i in discriminators]
    if not disc_freqs:
        return None, []

    # Compute corpus median frequency for normalization
    all_freqs = list(word_freq.values())
    corpus_median = float(np.median(all_freqs))
    if corpus_median == 0:
        corpus_median = 1

    mean_disc_freq = np.mean(disc_freqs)
    ratio = mean_disc_freq / corpus_median

    disc_words = [(idx2word[i], word_freq.get(idx2word[i], 0), float(diff[i]))
                  for i in discriminators[:10]]

    return float(ratio), disc_words


def main():
    ctx_path = PROJECT_ROOT / "build" / "greek_contexts.pkl"
    if not ctx_path.exists():
        print(f"Error: {ctx_path} not found. Run build_greek_contexts.py first.",
              file=sys.stderr)
        sys.exit(1)

    print("Loading context vectors...")
    with open(ctx_path, "rb") as f:
        ctx = pickle.load(f)

    embeddings = ctx["embeddings"]
    word2idx = ctx["word2idx"]
    idx2word = ctx["idx2word"]
    word_freq = ctx["word_freq"]

    # Also load lexical table for translation cosine comparison
    lex_path = PROJECT_ROOT / "build" / "global_lexical_table.pkl"
    src2en = {}
    if lex_path.exists():
        with open(lex_path, "rb") as f:
            lex = pickle.load(f)
        src2en = lex.get("src2en", {})

    def trans_cosine(w1, w2):
        if w1 not in src2en or w2 not in src2en:
            return None
        v1, v2 = src2en[w1], src2en[w2]
        keys = set(v1.keys()) | set(v2.keys())
        if not keys:
            return 0.0
        a = np.array([v1.get(k, 0) for k in keys])
        b = np.array([v2.get(k, 0) for k in keys])
        d = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / d) if d > 0 else 0.0

    # Test pairs
    test_groups = {
        "AUGMENTED VERBS (should link)": [
            ("ἀγαπῶν", "ἠγάπησεν"),
            ("ἀγαπᾷ", "ἠγάπα"),
            ("ἀγάπην", "ἠγάπησεν"),
            ("ἔλυσε", "λύσας"),
            ("ἔγραψε", "γράψας"),
            ("εἶπε", "λέγων"),
            ("ἔπεμψε", "πέμψας"),
            ("ἐβασίλευσε", "βασιλεύων"),
            ("ἐστράτευσε", "στρατεύσας"),
            ("ἐπολέμησε", "πολεμῶν"),
        ],
        "SYNONYMS (should NOT link)": [
            ("ἀγάπη", "φιλία"),
            ("θάνατος", "τελευτή"),
            ("πόλεμος", "μάχη"),
            ("βασιλεύς", "τύραννος"),
            ("πόλις", "ἄστυ"),
            ("ναῦς", "πλοῖον"),
            ("στρατιώτης", "ὁπλίτης"),
            ("ἵππος", "ἅρμα"),
            ("γυνή", "γαμετή"),
            ("οἰκία", "δόμος"),
        ],
        "KNOWN INFLECTIONS (should link)": [
            ("θάνατος", "θανάτου"),
            ("πόλεμος", "πολέμου"),
            ("βασιλεύς", "βασιλέως"),
            ("στρατηγός", "στρατηγοῦ"),
            ("πόλις", "πόλεως"),
            ("φίλος", "φίλου"),
            ("φίλοι", "φίλους"),
            ("ἀγάπη", "ἀγάπην"),
            ("ἀγάπη", "ἀγάπης"),
            ("φιλία", "φιλίαν"),
        ],
    }

    print(f"\n{'='*90}")
    print(f"{'Pair':<35} {'Distrib':>8} {'DiscRatio':>10} {'TransCos':>9} {'LCS':>5}")
    print(f"{'='*90}")

    for group_name, pairs in test_groups.items():
        print(f"\n--- {group_name} ---")
        for w1, w2 in pairs:
            dc = distributional_cosine(w1, w2, embeddings, word2idx)
            dr, disc_words = discriminative_score(w1, w2, embeddings, word2idx,
                                                  idx2word, word_freq)
            tc = trans_cosine(w1, w2)

            # LCS ratio
            n, m = len(w1), len(w2)
            if n > 0 and m > 0:
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
                lcs = best / min(n, m)
            else:
                lcs = 0

            dc_str = f"{dc:.3f}" if dc is not None else "N/A"
            dr_str = f"{dr:.2f}" if dr is not None else "N/A"
            tc_str = f"{tc:.3f}" if tc is not None else "N/A"

            print(f"  {w1} ↔ {w2:<18} {dc_str:>8} {dr_str:>10} {tc_str:>9} {lcs:>5.2f}")

            # Show top discriminating words for augmented verb pairs
            if disc_words and "AUGMENTED" in group_name:
                dw_str = ", ".join(f"{w}(f={freq})" for w, freq, _ in disc_words[:5])
                print(f"    discriminators: {dw_str}")

    # Summary statistics
    print(f"\n{'='*90}")
    print("Summary: mean scores by group")
    print(f"{'='*90}")
    for group_name, pairs in test_groups.items():
        dcs, drs, tcs = [], [], []
        for w1, w2 in pairs:
            dc = distributional_cosine(w1, w2, embeddings, word2idx)
            dr, _ = discriminative_score(w1, w2, embeddings, word2idx,
                                         idx2word, word_freq)
            tc = trans_cosine(w1, w2)
            if dc is not None: dcs.append(dc)
            if dr is not None: drs.append(dr)
            if tc is not None: tcs.append(tc)

        dc_mean = f"{np.mean(dcs):.3f}" if dcs else "N/A"
        dr_mean = f"{np.mean(drs):.2f}" if drs else "N/A"
        tc_mean = f"{np.mean(tcs):.3f}" if tcs else "N/A"
        print(f"  {group_name}")
        print(f"    Distributional: {dc_mean}  DiscRatio: {dr_mean}  TransCosine: {tc_mean}")


if __name__ == "__main__":
    main()

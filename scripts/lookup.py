#!/usr/bin/env python3
"""
Look up Greek words for an English concept, showing lemma groups and senses.

Uses the concordance data (translation vectors + synthetic lemmas) to answer:
"What are the Greek words for X, and what are their different senses?"

Usage:
    python scripts/lookup.py love
    python scripts/lookup.py death
    python scripts/lookup.py "send"
    python scripts/lookup.py war --top 20
"""

import argparse
import csv
import pickle
import sys
from collections import defaultdict
from pathlib import Path

from pyuca import Collator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_data():
    """Load concordance data and lemma mappings."""
    pkl_path = PROJECT_ROOT / "build" / "global_lexical_table.pkl"
    if not pkl_path.exists():
        print(f"Error: {pkl_path} not found.", file=sys.stderr)
        sys.exit(1)

    with open(pkl_path, "rb") as f:
        data = pickle.load(f)

    src2en = data["src2en"]
    cooccur = data.get("cooccur", {})

    lemma_pkl = PROJECT_ROOT / "build" / "synthetic_lemmas.pkl"
    lemma_map = {}
    if lemma_pkl.exists():
        with open(lemma_pkl, "rb") as f:
            lem = pickle.load(f)
        lemma_map = lem.get("lemma_map", {})

    # Load unfiltered English→Greek reverse index for looking up common
    # English words (death, war, city) that were stopword-filtered from src2en
    reverse_path = PROJECT_ROOT / "build" / "en2gr_index.pkl"
    en2gr = {}
    gr_marginals = {}  # greek_word → total co-occurrence count across all English
    total_mass = 0
    if reverse_path.exists():
        with open(reverse_path, "rb") as f:
            en2gr = pickle.load(f)
        # Precompute Greek word marginals for PMI scoring
        for ew, gr_counts in en2gr.items():
            for gw, count in gr_counts.items():
                gr_marginals[gw] = gr_marginals.get(gw, 0) + count
                total_mass += count

    return src2en, cooccur, lemma_map, en2gr, gr_marginals, total_mass


def find_greek_for_english(english_word, src2en, cooccur, lemma_map, en2gr,
                           gr_marginals, total_mass, top_n=15):
    """Find Greek words that translate to the given English word.

    Returns a list of lemma groups, each with:
    - representative form
    - all forms in the group that map to this English word
    - the weight/rank of the English word in each form's translations
    - the other English senses of this lemma group
    """
    english_lower = english_word.lower()

    # Find all Greek words where this English word appears in translations
    matches = []  # (greek_word, weight, rank, freq)
    for greek_word, translations in src2en.items():
        ranked = sorted(translations.items(), key=lambda x: -x[1])
        for rank, (eng, weight) in enumerate(ranked, 1):
            if eng == english_lower:
                freq = sum(cooccur.get((greek_word, ew), 0)
                           for ew in translations)
                matches.append((greek_word, weight, rank, freq))
                break

    # If no matches in pruned translations, fall back to reverse index
    # (covers words like "death", "war", "city" that were stopword-filtered
    # from src2en but exist in raw co-occurrence counts)
    if not matches and english_lower in en2gr:
        gr_counts = en2gr[english_lower]  # {greek_word: count}

        import math
        en_total = sum(gr_counts.values())
        pmi_scored = []
        for gw, count in gr_counts.items():
            if gw not in src2en:
                continue
            gr_total = gr_marginals.get(gw, 0)
            if gr_total == 0:
                continue
            pmi = math.log(max(count * total_mass / (gr_total * en_total), 1e-10))
            if pmi > 0:
                weight = count * pmi
                pmi_scored.append((gw, weight, count))

        pmi_scored.sort(key=lambda x: -x[1])
        for gw, weight, count in pmi_scored[:50]:
            freq = sum(cooccur.get((gw, ew), 0) for ew in src2en.get(gw, {}))
            matches.append((gw, weight, 0, freq))

    if not matches:
        return []

    # Group by lemma
    lemma_groups = defaultdict(list)
    for greek_word, weight, rank, freq in matches:
        rep = lemma_map.get(greek_word, greek_word)
        lemma_groups[rep].append((greek_word, weight, rank, freq))

    # For each lemma group, compute aggregate score and collect all senses
    results = []
    for rep, forms in lemma_groups.items():
        # Aggregate: sum of weights × frequencies across forms
        total_weight = sum(w for _, w, _, _ in forms)
        total_freq = sum(f for _, _, _, f in forms)
        best_weight = max(w for _, w, _, _ in forms)
        best_rank = min(r for _, _, r, _ in forms)

        # Collect all English senses for this lemma group
        all_forms_in_group = [w for w, r in lemma_map.items() if r == rep]
        if not all_forms_in_group:
            all_forms_in_group = [rep]

        # Merge translation vectors across all forms in the group
        merged_translations = defaultdict(float)
        merged_cooccur = defaultdict(int)
        for form in all_forms_in_group:
            if form in src2en:
                for eng, w in src2en[form].items():
                    merged_translations[eng] += w
                    merged_cooccur[eng] += cooccur.get((form, eng), 0)

        # Normalize
        total = sum(merged_translations.values())
        if total > 0:
            merged_translations = {e: w / total
                                   for e, w in merged_translations.items()}

        # Top senses (excluding the query word)
        other_senses = sorted(
            ((eng, w, merged_cooccur[eng])
             for eng, w in merged_translations.items()
             if eng != english_lower),
            key=lambda x: -x[1]
        )[:8]

        # Query word's merged weight
        query_merged_weight = merged_translations.get(english_lower, 0)

        results.append({
            "representative": rep,
            "forms_matching": sorted(forms, key=lambda x: -x[1]),
            "n_forms_total": len(all_forms_in_group),
            "best_weight": best_weight,
            "best_rank": best_rank,
            "total_freq": total_freq,
            "query_merged_weight": query_merged_weight,
            "other_senses": other_senses,
        })

    # Sort by: best_rank ascending, then best_weight descending
    results.sort(key=lambda r: (r["best_rank"], -r["best_weight"]))

    return results[:top_n]


def main():
    parser = argparse.ArgumentParser(
        description="Look up Greek words for an English concept")
    parser.add_argument("word", help="English word to look up")
    parser.add_argument("--top", type=int, default=15,
                        help="Maximum number of lemma groups to show (default: 15)")
    args = parser.parse_args()

    src2en, cooccur, lemma_map, en2gr, gr_marginals, total_mass = load_data()

    results = find_greek_for_english(args.word, src2en, cooccur, lemma_map,
                                     en2gr, gr_marginals, total_mass,
                                     top_n=args.top)

    if not results:
        print(f"No Greek words found for \"{args.word}\"")
        sys.exit(0)

    print(f"\nGreek words for \"{args.word}\" ({len(results)} lemma groups):\n")

    for i, r in enumerate(results, 1):
        rep = r["representative"]
        n_total = r["n_forms_total"]
        qw = r["query_merged_weight"]

        # Header
        print(f"  {i}. {rep}  ({n_total} forms, "
              f"\"{args.word}\" = {qw:.1%} of merged senses)")

        # Matching forms
        for greek, weight, rank, freq in r["forms_matching"][:5]:
            tag = ""
            if greek != rep:
                tag = f" → {rep}"
            rank_str = f"rank {rank}" if rank > 0 else "cooccur"
            print(f"     {greek}{tag}  "
                  f"{rank_str}, weight {weight:.2f}, "
                  f"freq {freq}")

        if len(r["forms_matching"]) > 5:
            print(f"     ... and {len(r['forms_matching']) - 5} more forms")

        # Other senses
        if r["other_senses"]:
            senses = ", ".join(
                f"{eng} ({w:.1%})" for eng, w, _ in r["other_senses"][:6]
            )
            print(f"     Other senses: {senses}")

        print()


if __name__ == "__main__":
    main()

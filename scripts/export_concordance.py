#!/usr/bin/env python3
"""
Export the synthetic Greek→English lexical table as a human-readable CSV concordance.

Reads build/global_lexical_table.pkl and writes build/greek_english_concordance.csv.

Usage:
    python scripts/export_concordance.py
    python scripts/export_concordance.py --min-weight 0.05 --max-rank 5
    python scripts/export_concordance.py --top-only
"""

import argparse
import csv
import pickle
import sys
from datetime import date
from pathlib import Path

from pyuca import Collator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description="Export Greek-English concordance CSV")
    parser.add_argument("--min-weight", type=float, default=0.01,
                        help="Drop translations below this weight (default: 0.01)")
    parser.add_argument("--min-cooccur", type=int, default=3,
                        help="Drop pairs seen fewer than N times (default: 3)")
    parser.add_argument("--max-rank", type=int, default=10,
                        help="Keep only top-K translations per word (default: 10)")
    parser.add_argument("--top-only", action="store_true",
                        help="Emit only rank-1 translation per word")
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV path (default: build/greek_english_concordance.csv)")
    args = parser.parse_args()

    pkl_path = PROJECT_ROOT / "build" / "global_lexical_table.pkl"
    if not pkl_path.exists():
        print(f"Error: {pkl_path} not found. Run scripts/build_lexicon.py first.",
              file=sys.stderr)
        sys.exit(1)

    with open(pkl_path, "rb") as f:
        data = pickle.load(f)

    src2en = data["src2en"]
    src_idf = data.get("src_idf", {})
    cooccur = data.get("cooccur", {})
    has_cooccur = bool(cooccur)

    if not has_cooccur:
        print("Note: pickle lacks cooccur counts (old format). "
              "Rebuild with build_lexicon.py to include them.", file=sys.stderr)

    # Load synthetic lemmas if available
    lemma_pkl_path = PROJECT_ROOT / "build" / "synthetic_lemmas.pkl"
    lemma_map = {}
    lemma_confidence = {}
    if lemma_pkl_path.exists():
        with open(lemma_pkl_path, "rb") as f:
            lemma_data = pickle.load(f)
        lemma_map = lemma_data.get("lemma_map", {})
        lemma_confidence = lemma_data.get("lemma_confidence", {})
    has_lemmas = bool(lemma_map)

    # Build rows
    collator = Collator()
    rows = []
    for greek_word in sorted(src2en.keys(), key=collator.sort_key):
        translations = src2en[greek_word]
        idf = src_idf.get(greek_word, 0.0)

        # Sort by weight descending
        ranked = sorted(translations.items(), key=lambda x: -x[1])

        for rank, (eng_word, weight) in enumerate(ranked, 1):
            if rank > args.max_rank:
                break
            if args.top_only and rank > 1:
                break
            if weight < args.min_weight:
                continue

            count = cooccur.get((greek_word, eng_word), 0) if has_cooccur else ""
            if has_cooccur and count < args.min_cooccur:
                continue

            row = {
                "greek": greek_word,
                "english": eng_word,
                "weight": round(weight, 4),
                "rank": rank,
                "cooccur_count": count,
                "greek_idf": round(idf, 4),
            }
            if has_lemmas:
                lemma = lemma_map.get(greek_word, greek_word)
                conf = lemma_confidence.get(greek_word, 0.0)
                row["synthetic_lemma"] = lemma
                row["synthetic_lemma_confidence"] = round(conf, 4) if conf > 0 else ""
            rows.append(row)

    # Write CSV
    out_path = Path(args.output) if args.output else PROJECT_ROOT / "greek_english_concordance.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_headwords = len(src2en)
    n_total_pairs = sum(len(v) for v in src2en.values())

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        # Metadata header
        f.write(f"# Greek-English Concordance — auto-generated from global_lexical_table.pkl\n")
        f.write(f"# Generated: {date.today().isoformat()}\n")
        f.write(f"# Greek headwords: {n_headwords}\n")
        f.write(f"# Total translation pairs (before filters): {n_total_pairs}\n")
        f.write(f"# Rows after filters: {len(rows)}\n")
        f.write(f"# Filters: min_weight={args.min_weight}, min_cooccur={args.min_cooccur}, "
                f"max_rank={args.max_rank}, top_only={args.top_only}\n")
        f.write(f"# WARNING: Forms are uninflected surface forms, not lemmas\n")

        fieldnames = ["greek", "english", "weight", "rank", "cooccur_count", "greek_idf"]
        if has_lemmas:
            fieldnames += ["synthetic_lemma", "synthetic_lemma_confidence"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Print source summary table
    source_stats = data.get("source_stats", [])
    if source_stats:
        total_works = sum(s["works"] for s in source_stats)
        total_pairs = sum(s["pairs"] for s in source_stats)
        name_w = max(len(s["source"]) for s in source_stats + [{"source": "Total"}])
        hdr = f"  {'Source':<{name_w}}   Works    Pairs"
        sep = f"  {'-' * name_w}   -----   ------"
        print(hdr)
        print(sep)
        for s in source_stats:
            print(f"  {s['source']:<{name_w}}   {s['works']:>5}   {s['pairs']:>6,}")
        print(sep)
        print(f"  {'Total':<{name_w}}   {total_works:>5}   {total_pairs:>6,}")
        print()

    print(f"Concordance: {len(rows)} rows from {n_headwords} Greek headwords")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()

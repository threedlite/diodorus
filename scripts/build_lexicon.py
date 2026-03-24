#!/usr/bin/env python3
"""
Build the global Greek→English lexical dictionary from all aligned works.

Collects aligned text pairs from every work's entity_validated_alignments.json,
then builds a PMI-weighted translation table and caches it.

Output: build/global_lexical_table.pkl

Usage:
    python scripts/build_lexicon.py
"""

import json
import operator
import pickle
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "pipeline"))

from lexical_overlap import build_lexical_table


def collect_aligned_pairs(min_score=0.2):
    """Collect (greek_text, english_text) pairs from all works."""
    works_dir = PROJECT_ROOT / "scripts" / "works"
    pairs = []

    for config_path in sorted(works_dir.glob("*/config.json")):
        with open(config_path) as f:
            cfg = json.load(f)

        align_path = PROJECT_ROOT / cfg["output_dir"] / "entity_validated_alignments.json"
        gr_path = PROJECT_ROOT / cfg["output_dir"] / "greek_sections.json"
        en_path = PROJECT_ROOT / cfg["output_dir"] / "english_sections.json"

        if not all(p.exists() for p in [align_path, gr_path, en_path]):
            continue

        with open(gr_path) as f:
            gr_data = json.load(f)
        with open(en_path) as f:
            en_data = json.load(f)

        gr_secs = gr_data["sections"] if isinstance(gr_data, dict) else gr_data
        en_secs = en_data["sections"] if isinstance(en_data, dict) else en_data

        gr_by_ref = {s.get("cts_ref", ""): s for s in gr_secs}
        en_by_ref = {}
        for s in en_secs:
            key = s.get("cts_ref", s.get("fable_index", s.get("section", "")))
            en_by_ref[str(key)] = s

        with open(align_path) as f:
            aligns = json.load(f)

        work_count = 0
        for a in aligns:
            if a.get("combined_score", 0) < min_score:
                continue
            gr_ref = a.get("greek_cts_ref", "")
            en_ref = str(a.get("english_cts_ref", a.get("english_section", "")))
            gr_text = gr_by_ref.get(gr_ref, {}).get("text", "")
            en_text = en_by_ref.get(en_ref, {}).get("text", "")
            if gr_text and en_text:
                pairs.append((gr_text, en_text))
                work_count += 1

        if work_count:
            print(f"  {cfg['name']}: {work_count} pairs")

    return pairs


def quality_check(src2en):
    """Check known Greek→English translations."""
    known = {
        "θάνατος": "death", "πόλεμος": "war", "βασιλεύς": "king",
        "στρατηγός": "general", "φιλοσοφία": "philosophy", "ἀρετή": "virtue",
        "δικαιοσύνη": "justice", "ψυχή": "soul", "πόλις": "city",
        "ἄνθρωπος": "man", "θεός": "god", "νόμος": "law",
        "ἀλήθεια": "truth", "δύναμις": "power", "χρόνος": "time",
        "γυνή": "woman", "πατήρ": "father", "μήτηρ": "mother",
        "σῶμα": "body", "ναῦς": "ship", "ἵππος": "horse",
    }
    found = correct = 0
    for gw, expected in known.items():
        if gw in src2en:
            found += 1
            top = sorted(src2en[gw].items(),
                         key=operator.itemgetter(1), reverse=True)[:5]
            has = any(expected in ew for ew, _ in top)
            if has:
                correct += 1
            mark = "✓" if has else "✗"
            en_str = ", ".join(f"{ew}({tw:.2f})" for ew, tw in top)
            print(f"  {mark} {gw} → {en_str}")
        else:
            print(f"  ? {gw} NOT FOUND")

    print(f"\n  Found: {found}/{len(known)}, Correct in top-5: {correct}/{found}")


def main():
    print("Building global lexical dictionary...\n")

    pairs = collect_aligned_pairs(min_score=0.2)
    print(f"\nTotal aligned pairs: {len(pairs)}")

    src2en, src_idf, en_idf = build_lexical_table(
        pairs,
        min_cooccur=3,
        max_translations=10,
        min_weight=0.005,
        idf_cap_percentile=90,
        use_stemming=False,
    )

    n_pairs = sum(len(v) for v in src2en.values())
    avg = n_pairs / max(len(src2en), 1)
    print(f"Dictionary: {len(src2en)} entries, {n_pairs} translation pairs")
    print(f"Avg translations per word: {avg:.1f}")

    print("\nKnown word check:")
    quality_check(src2en)

    out_path = PROJECT_ROOT / "build" / "global_lexical_table.pkl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump({"src2en": src2en, "src_idf": src_idf, "en_idf": en_idf}, f)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Build the global Greek→English lexical dictionary from:
1. All parallel Greek-English works in Perseus (500+ works, ~30K section pairs)
2. Our 35 aligned works (~22K section pairs)

Uses PMI (pointwise mutual information) to learn which Greek words
translate to which English words based on co-occurrence in aligned text.

Output: build/global_lexical_table.pkl

Usage:
    python scripts/build_lexicon.py
"""

import json
import operator
import pickle
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "pipeline"))

from lexical_overlap import build_lexical_table

TEI_NS = "{http://www.tei-c.org/ns/1.0}"


def collect_perseus_pairs():
    """Collect (greek_text, english_text) pairs from all of Perseus.

    Extracts text at the chapter/section level from paired Greek-English
    TEI XML files and matches them by CTS reference structure.
    """
    from lxml import etree

    perseus_dir = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data"
    if not perseus_dir.exists():
        return []

    def extract_by_chapter(xml_path):
        try:
            tree = etree.parse(str(xml_path))
        except Exception:
            return {}
        root = tree.getroot()
        chapters = {}
        for div in root.iter(f"{TEI_NS}div"):
            subtype = div.get("subtype", "")
            n = div.get("n", "")
            if not n:
                continue
            parent = div.getparent()
            book_n = ""
            while parent is not None:
                if isinstance(parent.tag, str) and parent.tag.endswith("div"):
                    if parent.get("subtype", "") == "book" and parent.get("n", ""):
                        book_n = parent.get("n", "")
                        break
                parent = parent.getparent()
            if subtype in ("chapter", "section", "card"):
                text = " ".join(div.itertext()).strip()[:2000]
                if len(text) > 30:
                    key = f"{book_n}.{n}" if book_n else n
                    chapters[key] = text
        return chapters

    pairs = []
    works = 0
    for author_dir in sorted(perseus_dir.iterdir()):
        if not author_dir.is_dir():
            continue
        for work_dir in sorted(author_dir.iterdir()):
            if not work_dir.is_dir():
                continue
            grc = [f for f in work_dir.glob("*grc*.xml") if f.name != "__cts__.xml"]
            eng = [f for f in work_dir.glob("*eng*.xml") if f.name != "__cts__.xml"]
            if not grc or not eng:
                continue
            gr = extract_by_chapter(grc[0])
            en = extract_by_chapter(eng[0])
            common = set(gr.keys()) & set(en.keys())
            if len(common) >= 3:
                works += 1
                for key in common:
                    pairs.append((gr[key], en[key]))

    print(f"  Perseus: {works} works, {len(pairs)} pairs")
    return pairs


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

    # Collect from Perseus (500+ parallel works)
    perseus_pairs = collect_perseus_pairs()

    # Collect from our aligned works
    our_pairs = collect_aligned_pairs(min_score=0.2)

    pairs = perseus_pairs + our_pairs
    print(f"\nTotal pairs: {len(pairs)} ({len(perseus_pairs)} Perseus + {len(our_pairs)} ours)")

    src2en, src_idf, en_idf = build_lexical_table(
        pairs,
        min_cooccur=3,
        max_translations=10,
        min_weight=0.005,
        idf_cap_percentile=90,
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

    # Compute corpus-derived stopwords from word frequencies.
    # Words appearing in >30% of sections are too common to be distinctive.
    import re
    from lexical_overlap import GR_WORD_RE, EN_WORD_RE

    gr_df = Counter()
    en_df = Counter()
    n_pairs_count = len(pairs)
    for gr_text, en_text in pairs:
        for w in set(w.lower() for w in GR_WORD_RE.findall(gr_text) if len(w) > 2):
            gr_df[w] += 1
        for w in set(w.lower() for w in EN_WORD_RE.findall(en_text) if len(w) > 2):
            en_df[w] += 1

    threshold = 0.10  # words in >10% of sections
    gr_stops = {w for w, df in gr_df.items() if df > n_pairs_count * threshold}
    en_stops = {w for w, df in en_df.items() if df > n_pairs_count * threshold}

    stopwords_path = PROJECT_ROOT / "build" / "stopwords.pkl"
    with open(stopwords_path, "wb") as f:
        pickle.dump({"greek": gr_stops, "english": en_stops}, f)
    print(f"Stopwords: {len(gr_stops)} Greek, {len(en_stops)} English "
          f"(>{threshold:.0%} of {n_pairs_count} sections)")
    print(f"Saved: {stopwords_path}")


if __name__ == "__main__":
    main()

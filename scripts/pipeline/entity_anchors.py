#!/usr/bin/env python3
"""
Generic entity anchor validation.

Uses Greek transliteration + fuzzy matching against English names.
For fable-mode works, also uses animal name matching.

Inputs:
  <output_dir>/section_alignments.json
  <output_dir>/greek_sections.json
  <output_dir>/english_sections.json

Outputs:
  <output_dir>/entity_validated_alignments.json
"""

import json
import re
import sys
from pathlib import Path
from unidecode import unidecode
from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

GREEK_SIMPLE = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z",
    "η": "e", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n",
    "ξ": "x", "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s",
    "τ": "t", "υ": "y", "φ": "ph", "χ": "kh", "ψ": "ps", "ω": "o",
    "θ": "th",
    "ά": "a", "έ": "e", "ή": "e", "ί": "i", "ό": "o", "ύ": "y",
    "ώ": "o", "ϊ": "i", "ϋ": "y", "ΐ": "i", "ΰ": "y",
}


def greek_to_latin(text):
    t = text.lower()
    for greek, latin in GREEK_SIMPLE.items():
        t = t.replace(greek, latin)
    t = re.sub(r"[^\w\s]", "", t)
    return unidecode(t).lower()


def extract_greek_names(text):
    words = re.findall(r"\b[\u0391-\u03A9][\u03b1-\u03c9\u03ac-\u03ce]{2,}\b", text)
    return [(w, greek_to_latin(w)) for w in words]


def extract_english_names(text):
    stopwords = {"The", "But", "And", "For", "With", "From", "This", "That",
                 "What", "When", "Where", "How", "Who", "Not", "All", "Every",
                 "Such", "Let", "Are", "His", "Her", "Its", "Has", "Have",
                 "May", "Can", "Will", "Shall", "Should", "Would", "Could",
                 "Now", "Then", "There", "Here", "Thus", "Yet", "Still",
                 "First", "Second", "Third", "Much", "Many", "Other"}
    words = re.findall(r"\b[A-Z][a-z]{2,}\b", text)
    return [w.lower() for w in words if w not in stopwords]


def load_config(work_name):
    config_path = PROJECT_ROOT / "scripts" / "works" / work_name / "config.json"
    with open(config_path) as f:
        return json.load(f)


def main(work_name):
    config = load_config(work_name)
    out_dir = PROJECT_ROOT / config["output_dir"]

    align_path = out_dir / "section_alignments.json"
    greek_path = out_dir / "greek_sections.json"
    english_path = out_dir / "english_sections.json"

    # Handle legacy names
    if not greek_path.exists():
        alt = out_dir / "greek_fables.json"
        if alt.exists():
            greek_path = alt
    if not english_path.exists():
        alt = out_dir / "english_fables.json"
        if alt.exists():
            english_path = alt

    for p in [align_path, greek_path, english_path]:
        if not p.exists():
            print(f"Error: {p} not found")
            raise SystemExit(1)

    with open(align_path) as f:
        alignments = json.load(f)
    with open(greek_path) as f:
        greek_data = json.load(f)
    with open(english_path) as f:
        english_data = json.load(f)

    if isinstance(greek_data, list):
        greek_data = {"sections": greek_data}
    if isinstance(english_data, list):
        english_data = {"sections": english_data}

    # Build indexes
    greek_by_ref = {s["cts_ref"]: s for s in greek_data["sections"]}
    # English may use cts_ref, fable_index, or section
    english_by_ref = {}
    for s in english_data["sections"]:
        key = s.get("cts_ref", s.get("fable_index", s.get("section", "")))
        english_by_ref[str(key)] = s

    # Build lexical table from all aligned pairs for multi-signal scoring
    from lexical_overlap import (build_lexical_table,
                                 lexical_overlap_score)
    import pickle

    # Load global cross-work lexical dictionary if available
    global_lex_path = PROJECT_ROOT / "build" / "global_lexical_table.pkl"
    if global_lex_path.exists():
        with open(global_lex_path, "rb") as f:
            global_lex = pickle.load(f)
        src2en = global_lex["src2en"]
        src_idf = global_lex["src_idf"]
        print(f"  Global lexical table: {len(src2en)} words")
    else:
        # Fall back to per-work table
        aligned_pairs = []
        for a in alignments:
            if a.get("greek_cts_ref") is None or a.get("english_cts_ref") is None:
                continue
            gr_text = greek_by_ref.get(a["greek_cts_ref"], {}).get("text", "")
            en_key = str(a.get("english_cts_ref", a.get("english_section", "")))
            en_text = english_by_ref.get(en_key, {}).get("text", "")
            if gr_text and en_text:
                aligned_pairs.append((gr_text, en_text))

        src2en, src_idf, _ = build_lexical_table(aligned_pairs) if aligned_pairs else ({}, {}, {})
        if src2en:
            print(f"  Per-work lexical table: {len(src2en)} words")

    # Compute expected char ratio for length penalty
    total_gr = sum(len(greek_by_ref.get(a.get("greek_cts_ref", ""), {}).get("text", ""))
                   for a in alignments if a.get("greek_cts_ref"))
    total_en = sum(len(english_by_ref.get(str(a.get("english_cts_ref", "")), {}).get("text", ""))
                   for a in alignments if a.get("english_cts_ref"))
    expected_ratio = total_gr / total_en if total_en > 0 else 1.0

    # Count how many Greek sections point to each English section.
    # Non-1:1 mappings should be penalized — they indicate the alignment
    # couldn't find a unique match.
    from collections import Counter
    en_ref_counts = Counter()
    for a in alignments:
        en_ref = a.get("english_cts_ref")
        if en_ref is not None:
            en_ref_counts[str(en_ref)] += 1

    print("Validating alignments with entity anchors + lexical overlap...")

    import math
    for a in alignments:
        if a.get("match_type") == "unmatched_english" or a.get("greek_cts_ref") is None:
            a["entity_overlap_score"] = 0.0
            a["entity_match_count"] = 0
            a["lexical_score"] = 0.0
            a["length_ratio_score"] = 0.0
            a["combined_score"] = 0.0
            continue

        gr_text = greek_by_ref.get(a["greek_cts_ref"], {}).get("text", "")
        en_key = a.get("english_cts_ref", a.get("english_section", ""))
        en_text = english_by_ref.get(str(en_key), {}).get("text", "")

        # 1. Entity overlap
        gr_names = extract_greek_names(gr_text)
        en_names = extract_english_names(en_text)

        matches = 0
        total = max(len(gr_names), 1)
        for _, gn_lat in gr_names:
            for en in en_names:
                if fuzz.partial_ratio(gn_lat, en) > 75:
                    matches += 1
                    break

        entity_score = matches / total if gr_names else 0.0
        a["entity_overlap_score"] = round(entity_score, 3)
        a["entity_match_count"] = matches

        # 2. Lexical overlap (TF-IDF weighted)
        lex_score = lexical_overlap_score(gr_text, en_text, src2en, src_idf)
        a["lexical_score"] = round(lex_score, 3)

        # 3. Length ratio penalty
        gr_chars = len(gr_text)
        en_chars = len(en_text)
        if en_chars > 0 and expected_ratio > 0:
            ratio = (gr_chars / en_chars) / expected_ratio
            length_pen = math.exp(-0.5 * (ratio - 1.0) ** 2)
        else:
            length_pen = 0.5
        a["length_ratio_score"] = round(length_pen, 3)

        # 4. Combined score — normalize each signal to 0-1 range,
        # then weighted average.
        cos_sim = min(a.get("similarity", 0), 1.0)  # clamp CTS 1.0 overrides

        # Normalize lexical score: P5=0.004, P95=0.218 → stretch to 0-1
        lex_norm = min(1.0, max(0.0, lex_score / 0.25))

        # Weights: embedding 0.4, lexical 0.3, length 0.2, entity 0.1
        # Entity weight scales with evidence
        if gr_names and entity_score > 0:
            ent_w = min(0.15, 0.05 * len(gr_names))
        else:
            ent_w = 0.0
        remaining = 1.0 - ent_w

        score = (remaining * (0.4 * cos_sim + 0.3 * lex_norm + 0.3 * length_pen)
                 + ent_w * entity_score)

        # Penalize non-1:1 mappings: if N Greek sections share the same
        # English section, each one's score is reduced. A 2:1 mapping gets
        # ~70% of the score, 3:1 gets ~58%, etc. Refined splits (where
        # English was actually divided) are not penalized.
        en_ref = str(a.get("english_cts_ref", ""))
        sharing = en_ref_counts.get(en_ref, 1)
        if sharing > 1 and a.get("match_type") != "dp_refined":
            score *= 1.0 / math.sqrt(sharing)
            a["sharing_penalty"] = sharing

        a["combined_score"] = round(min(1.0, score), 4)

    low_conf = sum(1 for a in alignments if a.get("combined_score", 0) < 0.3)
    print(f"  Total: {len(alignments)}, Low confidence: {low_conf}")

    output_path = out_dir / "entity_validated_alignments.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(alignments, f, ensure_ascii=False, indent=2)

    print(f"Saved: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/pipeline/entity_anchors.py <work_name>")
        sys.exit(1)
    main(sys.argv[1])

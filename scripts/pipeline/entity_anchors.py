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

    print("Validating alignments with entity anchors...")

    for a in alignments:
        if a.get("match_type") == "unmatched_english" or a.get("greek_cts_ref") is None:
            a["entity_overlap_score"] = 0.0
            a["entity_match_count"] = 0
            a["combined_score"] = 0.0
            continue

        gr_text = greek_by_ref.get(a["greek_cts_ref"], {}).get("text", "")
        en_key = a.get("english_cts_ref", a.get("english_section", ""))
        en_text = english_by_ref.get(str(en_key), {}).get("text", "")

        gr_names = extract_greek_names(gr_text)
        en_names = extract_english_names(en_text)

        matches = 0
        total = max(len(gr_names), 1)
        for _, gn_lat in gr_names:
            for en in en_names:
                if fuzz.partial_ratio(gn_lat, en) > 75:
                    matches += 1
                    break

        entity_score = matches / total if gr_names else 0.5

        a["entity_overlap_score"] = round(entity_score, 3)
        a["entity_match_count"] = matches
        a["combined_score"] = round(0.7 * a["similarity"] + 0.3 * entity_score, 4)

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

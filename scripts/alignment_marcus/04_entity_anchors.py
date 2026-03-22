#!/usr/bin/env python3
"""
Validate Marcus Aurelius alignments with entity anchoring.

Marcus is philosophical prose with few proper names, so entity validation
will be weak. We still run it for consistency, using Greek transliteration
matching against any names that do appear.

Input:  output/marcus/section_alignments.json
Output: output/marcus/entity_validated_alignments.json
"""

import json
import re
from pathlib import Path
from unidecode import unidecode
from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GREEK = PROJECT_ROOT / "build" / "marcus" / "greek_sections.json"
ENGLISH = PROJECT_ROOT / "build" / "marcus" / "english_sections.json"
ALIGNMENTS = PROJECT_ROOT / "build" / "marcus" / "section_alignments.json"
OUTPUT = PROJECT_ROOT / "build" / "marcus" / "entity_validated_alignments.json"

# Greek-to-Latin transliteration
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
    # Simple capitalized word extraction (no spaCy needed for this small corpus)
    words = re.findall(r"\b[A-Z][a-z]{2,}\b", text)
    # Filter common English words that happen to be capitalized
    stopwords = {"The", "But", "And", "For", "With", "From", "This", "That",
                 "What", "When", "Where", "How", "Who", "Not", "All", "Every",
                 "Such", "Let", "Are", "His", "Her", "Its", "Has", "Have",
                 "May", "Can", "Will", "Shall", "Should", "Would", "Could",
                 "Now", "Then", "There", "Here", "Thus", "Yet", "Still",
                 "First", "Second", "Third", "Much", "Many", "Other"}
    return [w.lower() for w in words if w not in stopwords]


for f in [ALIGNMENTS, GREEK, ENGLISH]:
    if not f.exists():
        print(f"Error: {f} not found")
        raise SystemExit(1)

with open(ALIGNMENTS) as f:
    alignments = json.load(f)
with open(GREEK) as f:
    greek_data = json.load(f)
with open(ENGLISH) as f:
    english_data = json.load(f)

# Build indexes
greek_by_ref = {s["cts_ref"]: s for s in greek_data["sections"]}
english_by_ref = {s["cts_ref"]: s for s in english_data["sections"]}

print("Validating alignments with entity anchors...")

for a in alignments:
    if a.get("match_type") == "unmatched_english" or a.get("greek_cts_ref") is None:
        a["entity_overlap_score"] = 0.0
        a["entity_match_count"] = 0
        a["combined_score"] = 0.0
        continue

    gr_text = greek_by_ref.get(a["greek_cts_ref"], {}).get("text", "")
    en_text = english_by_ref.get(a.get("english_cts_ref", ""), {}).get("text", "")

    gr_names = extract_greek_names(gr_text)
    en_names = extract_english_names(en_text)

    matches = 0
    total = max(len(gr_names), 1)
    for gn_orig, gn_lat in gr_names:
        for en in en_names:
            if fuzz.partial_ratio(gn_lat, en) > 75:
                matches += 1
                break

    entity_score = matches / total if gr_names else 0.5

    a["entity_overlap_score"] = round(entity_score, 3)
    a["entity_match_count"] = matches
    a["combined_score"] = round(0.7 * a["similarity"] + 0.3 * entity_score, 4)

matched = [a for a in alignments if a.get("match_type") != "unmatched_english"]
low_conf = [a for a in alignments if a.get("combined_score", 0) < 0.3]
print(f"  Total: {len(alignments)}, Low confidence: {len(low_conf)}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(alignments, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

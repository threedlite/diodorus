#!/usr/bin/env python3
"""
Extract named entities from both texts and use name co-occurrence
to validate / correct section alignments.

Greek NER: regex-based extraction of capitalised Greek words + known names.
English NER: spaCy en_core_web_sm.
Cross-lingual matching: transliteration-based fuzzy matching.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

import spacy
from unidecode import unidecode
from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BOOTH = PROJECT_ROOT / "build" / "booth_normalised.json"
PERSEUS = PROJECT_ROOT / "build" / "perseus_extracted.json"
ALIGNMENTS = PROJECT_ROOT / "build" / "section_alignments.json"
OUTPUT = PROJECT_ROOT / "build" / "entity_validated_alignments.json"

for f, name in [
    (BOOTH, "booth_normalised.json"),
    (PERSEUS, "perseus_extracted.json"),
    (ALIGNMENTS, "section_alignments.json"),
]:
    if not f.exists():
        print(f"Error: {f} not found. Run previous scripts first.")
        raise SystemExit(1)

nlp = spacy.load("en_core_web_sm")

# Greek-to-Latin transliteration (basic)
# str.maketrans only supports 1-to-1 char mapping, so multi-char mappings
# (th, kh, ps) are handled via str.replace after the initial pass.
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
    """Rough transliteration of Greek to Latin characters."""
    t = text.lower()
    for greek, latin in GREEK_SIMPLE.items():
        t = t.replace(greek, latin)
    t = re.sub(r"[^\w\s]", "", t)
    return unidecode(t).lower()


def extract_greek_names(text):
    """Extract likely proper nouns from Greek text (capitalised words)."""
    words = re.findall(r"\b[\u0391-\u03A9][\u03b1-\u03c9\u03ac-\u03ce]{2,}\b", text)
    return [(w, greek_to_latin(w)) for w in words]


def extract_english_names(text):
    """Extract named entities using spaCy."""
    doc = nlp(text[:10000])
    names = []
    for ent in doc.ents:
        if ent.label_ in ("PERSON", "GPE", "LOC", "NORP"):
            names.append(ent.text.lower())
    return names


with open(BOOTH) as f:
    booth = json.load(f)
with open(PERSEUS) as f:
    perseus = json.load(f)
with open(ALIGNMENTS) as f:
    alignments = json.load(f)

# Build entity indices for each Greek section
print("Extracting Greek named entities...")
greek_entities = {}
for s in perseus["sections"]:
    names = extract_greek_names(s["text"])
    greek_entities[s["cts_ref"]] = [lat for _, lat in names]

# Build entity index for Booth paragraphs (keyed by book/div2/p)
print("Extracting English named entities...")
en_entities = {}
for bk in booth["books"]:
    for ch in bk["chapters"]:
        for p in ch["paragraphs"]:
            key = f"{bk['div1_n']}/{ch['div2_index']}/{p['p_index']}"
            text = p.get("text_normalised", p["text"])
            en_entities[key] = extract_english_names(text)

# Validate each alignment by entity overlap
print("Validating alignments with entity anchors...")
for a in alignments:
    # Skip unmatched English paragraphs (no Greek to compare)
    if a.get("match_type") == "unmatched_english" or a.get("greek_cts_ref") is None:
        a["entity_overlap_score"] = 0.0
        a["entity_match_count"] = 0
        a["combined_score"] = 0.0
        continue

    gr_ref = a["greek_cts_ref"]
    en_key = f"{a['book']}/{a['booth_div2_index']}/{a['booth_p_index']}"

    gr_names = greek_entities.get(gr_ref, [])
    en_names = en_entities.get(en_key, [])

    # Fuzzy match Greek transliterated names against English names
    matches = 0
    total = max(len(gr_names), 1)
    for gn in gr_names:
        for en in en_names:
            if fuzz.partial_ratio(gn, en) > 75:
                matches += 1
                break

    entity_score = matches / total if gr_names else 0.5  # neutral if no entities

    a["entity_overlap_score"] = round(entity_score, 3)
    a["entity_match_count"] = matches
    a["combined_score"] = round(0.7 * a["similarity"] + 0.3 * entity_score, 4)

# Flag low-confidence alignments
low_conf = [a for a in alignments if a["combined_score"] < 0.3]
print(f"\nLow-confidence alignments (<0.3): {len(low_conf)} / {len(alignments)}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(alignments, f, ensure_ascii=False, indent=2)

print(f"Saved validated alignments to {OUTPUT}")

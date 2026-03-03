#!/usr/bin/env python3
"""
Extract named entities from both Latin and English texts and use name
co-occurrence to validate / correct section alignments.

Latin NER: regex extraction of capitalised Latin words (proper nouns).
English NER: spaCy en_core_web_sm.
Cross-lingual matching: direct string + simple Latin→English name mapping.

Simplified vs Diodorus: Latin names pass nearly directly to English
(Achilles → Achilles, Thebae → Thebes) — no Greek transliteration needed.

Inputs:
  output/statius/mozley_normalised.json
  output/statius/latin_passages.json
  output/statius/section_alignments.json

Output:
  output/statius/entity_validated_alignments.json
"""

import json
import re
from pathlib import Path
from collections import defaultdict

import spacy
from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MOZLEY = PROJECT_ROOT / "output" / "statius" / "mozley_normalised.json"
PASSAGES = PROJECT_ROOT / "output" / "statius" / "latin_passages.json"
ALIGNMENTS = PROJECT_ROOT / "output" / "statius" / "section_alignments.json"
OUTPUT = PROJECT_ROOT / "output" / "statius" / "entity_validated_alignments.json"

for f, name in [
    (MOZLEY, "mozley_normalised.json"),
    (PASSAGES, "latin_passages.json"),
    (ALIGNMENTS, "section_alignments.json"),
]:
    if not f.exists():
        print(f"Error: {f} not found. Run previous scripts first.")
        raise SystemExit(1)

nlp = spacy.load("en_core_web_sm")

# Common Latin→English name mappings for Statius
LATIN_TO_ENGLISH = {
    "thebae": "thebes",
    "thebas": "thebes",
    "achilles": "achilles",
    "achillem": "achilles",
    "achilli": "achilles",
    "thetis": "thetis",
    "thetidis": "thetis",
    "iovis": "jove",
    "iuppiter": "jupiter",
    "iove": "jove",
    "mars": "mars",
    "martem": "mars",
    "martis": "mars",
    "apollo": "apollo",
    "apollinis": "apollo",
    "minerva": "minerva",
    "minervae": "minerva",
    "venus": "venus",
    "veneris": "venus",
    "hercules": "hercules",
    "herculis": "hercules",
    "bacchus": "bacchus",
    "bacchi": "bacchus",
    "iuno": "juno",
    "iunonis": "juno",
    "iunonem": "juno",
    "diana": "diana",
    "dianae": "diana",
    "neptunus": "neptune",
    "neptuni": "neptune",
    "pluton": "pluto",
    "plutonis": "pluto",
    "vulcanus": "vulcan",
    "vulcani": "vulcan",
    "mercurius": "mercury",
    "mercurii": "mercury",
    "oedipus": "oedipus",
    "oedipi": "oedipus",
    "oedipodae": "oedipus",
    "polynices": "polynices",
    "polynicis": "polynices",
    "polynicem": "polynices",
    "eteocles": "eteocles",
    "eteoclis": "eteocles",
    "tydeus": "tydeus",
    "tydei": "tydeus",
    "tydea": "tydeus",
    "adrastus": "adrastus",
    "adrasti": "adrastus",
    "adrastum": "adrastus",
    "argia": "argia",
    "argiae": "argia",
    "creon": "creon",
    "creontis": "creon",
    "antigone": "antigone",
    "antigonae": "antigone",
    "capaneus": "capaneus",
    "capanei": "capaneus",
    "amphiaraus": "amphiaraus",
    "amphiarai": "amphiaraus",
    "hippomedon": "hippomedon",
    "hippomedontis": "hippomedon",
    "parthenopaeus": "parthenopaeus",
    "parthenop": "parthenopaeus",
}


def normalise_latin_name(name):
    """Normalise a Latin proper noun for matching."""
    lower = name.lower()
    # Check dictionary first
    if lower in LATIN_TO_ENGLISH:
        return LATIN_TO_ENGLISH[lower]
    # Simple Latin ending removal: -us, -um, -is, -ae, -em, -i, -orum
    for suffix in ["-orum", "-arum", "-ibus", "-aque", "-us", "-um",
                   "-is", "-ae", "-em", "-am", "-os", "-as", "-es", "-i"]:
        if lower.endswith(suffix[1:]) and len(lower) > len(suffix):
            stem = lower[: -len(suffix) + 1]
            if len(stem) >= 3:
                return stem
    return lower


def extract_latin_names(text):
    """Extract likely proper nouns from Latin text (capitalised words)."""
    # Latin proper nouns: words starting with uppercase, at least 3 chars
    words = re.findall(r'\b[A-Z][a-z]{2,}\b', text)
    return [(w, normalise_latin_name(w)) for w in words]


def extract_english_names(text):
    """Extract named entities using spaCy."""
    doc = nlp(text[:10000])
    names = []
    for ent in doc.ents:
        if ent.label_ in ("PERSON", "GPE", "LOC", "NORP"):
            names.append(ent.text.lower())
    return names


with open(MOZLEY) as f:
    mozley = json.load(f)
with open(PASSAGES) as f:
    passages_data = json.load(f)
with open(ALIGNMENTS) as f:
    alignments = json.load(f)

# Build entity index for Latin passages
print("Extracting Latin named entities...")
latin_entities = {}
for p in passages_data["passages"]:
    key = f"{p['work']}/{p['book']}/{p['first_line']}-{p['last_line']}"
    names = extract_latin_names(p["text"])
    latin_entities[key] = [norm for _, norm in names]

# Build entity index for English paragraphs
print("Extracting English named entities...")
en_entities = {}
for work_key, work_data in mozley["works"].items():
    work_name = work_key.capitalize()
    for book in work_data["books"]:
        for idx, para in enumerate(book["paragraphs"]):
            key = f"{work_name}/{book['book']}/{idx}"
            text = para.get("text_normalised", para["text"])
            en_entities[key] = extract_english_names(text)

# Validate each alignment by entity overlap
print("Validating alignments with entity anchors...")
for a in alignments:
    lat_key = f"{a['work']}/{a['book']}/{a['latin_first_line']}-{a['latin_last_line']}"
    en_key = f"{a['work']}/{a['book']}/{a['english_p_index']}"

    lat_names = latin_entities.get(lat_key, [])
    en_names = en_entities.get(en_key, [])

    # Fuzzy match Latin normalised names against English names
    matches = 0
    total = max(len(lat_names), 1)
    for ln in lat_names:
        for en in en_names:
            if fuzz.partial_ratio(ln, en) > 75:
                matches += 1
                break

    entity_score = matches / total if lat_names else 0.5  # neutral if no entities

    a["entity_overlap_score"] = round(entity_score, 3)
    a["entity_match_count"] = matches
    a["combined_score"] = round(0.7 * a["similarity"] + 0.3 * entity_score, 4)

# Flag low-confidence alignments
low_conf = [a for a in alignments if a["combined_score"] < 0.3]
print(f"\nLow-confidence alignments (<0.3): {len(low_conf)} / {len(alignments)}")

# Score distribution
scores = [a["combined_score"] for a in alignments]
if scores:
    print(f"Score distribution: min={min(scores):.3f}, max={max(scores):.3f}, "
          f"mean={sum(scores)/len(scores):.3f}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(alignments, f, ensure_ascii=False, indent=2)

print(f"Saved validated alignments to {OUTPUT}")

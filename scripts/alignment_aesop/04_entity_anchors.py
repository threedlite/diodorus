#!/usr/bin/env python3
"""
Validate Aesop fable alignments using animal/character name matching.

Instead of spaCy NER (overkill for fables), uses a Greek-English animal
name dictionary for cross-lingual entity matching.

Input:  output/aesop/section_alignments.json
Output: output/aesop/entity_validated_alignments.json
"""

import json
import re
from pathlib import Path
from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALIGNMENTS = PROJECT_ROOT / "build" / "aesop" / "section_alignments.json"
GREEK_FABLES = PROJECT_ROOT / "build" / "aesop" / "greek_fables.json"
ENGLISH_FABLES = PROJECT_ROOT / "build" / "aesop" / "english_fables.json"
OUTPUT = PROJECT_ROOT / "build" / "aesop" / "entity_validated_alignments.json"

# Greek animal/character names -> English equivalents
ANIMAL_DICT = {
    "ἀλώπηξ": "fox", "ἀλωπεκ": "fox",
    "λέων": "lion", "λέοντ": "lion", "λεαιν": "lion",
    "λύκ": "wolf",
    "λαγ": "hare",
    "ὄν": "ass", "ὀνο": "ass",  # also matches donkey
    "κύων": "dog", "κυν": "dog",
    "αἴλουρ": "cat",
    "μῦς": "mouse", "μυ": "mouse",
    "βάτραχ": "frog",
    "ὄρνι": "bird", "ὄρνεο": "bird",
    "ἀλεκτρυ": "cock", "ἀλεκτρ": "cock",
    "κόραξ": "crow", "κορακ": "crow",
    "ἀετ": "eagle",
    "γέρανο": "crane",
    "χελιδ": "swallow",
    "χελών": "tortoise", "χελωνη": "tortoise",
    "ἵππο": "horse", "ἱππ": "horse",
    "βοῦ": "ox", "ταῦρ": "bull",
    "πρόβατ": "sheep", "ἀρνί": "lamb",
    "αἴξ": "goat", "αἰγ": "goat",
    "ὗ": "pig", "χοῖρ": "pig",
    "ἔλαφ": "deer", "stag": "stag",
    "ἄρκτ": "bear",
    "ὄφι": "serpent", "δράκ": "dragon",
    "σκορπί": "scorpion",
    "μέλισσ": "bee",
    "μύρμη": "ant",
    "τέττιξ": "grasshopper", "τεττιγ": "grasshopper",
    "ἰχθ": "fish",
    "γαλ": "weasel",
    "νυκτερίδ": "bat",
    "πίθηκ": "monkey", "ape": "ape",
    "κάμηλ": "camel",
    "ἐλέφα": "elephant",
    "ἔριφ": "kid",
    "ὄνειρ": "dream",
    # Mythological / human characters common in fables
    "Ζεύ": "jupiter", "Δί": "jupiter",
    "Ἑρμ": "mercury", "hermes": "hermes",
    "Ἀφροδίτ": "venus",
    "Ἡρακλ": "hercules",
    "Προμηθε": "prometheus",
}

# Also match English animal words in the English text
ENGLISH_ANIMALS = set(ANIMAL_DICT.values())
# Add common synonyms
ENGLISH_ANIMALS.update([
    "donkey", "rooster", "hen", "chicken", "raven", "dove", "pigeon",
    "wolf", "wolves", "lion", "lions", "fox", "foxes", "lamb", "lambs",
    "stork", "heron", "hawk", "kite", "owl", "parrot", "peacock",
    "snail", "crab", "dolphin", "whale", "fly", "flies", "mosquito",
    "spider", "worm", "caterpillar", "butterfly",
])


def find_greek_animals(text):
    """Find animal references in Greek text using prefix matching."""
    text_lower = text.lower()
    found = set()
    for greek_prefix, english in ANIMAL_DICT.items():
        if greek_prefix.lower() in text_lower:
            found.add(english)
    return found


def find_english_animals(text):
    """Find animal references in English text."""
    text_lower = text.lower()
    found = set()
    for animal in ENGLISH_ANIMALS:
        if animal in text_lower:
            found.add(animal)
    return found


for f in [ALIGNMENTS, GREEK_FABLES, ENGLISH_FABLES]:
    if not f.exists():
        print(f"Error: {f} not found. Run previous steps first.")
        raise SystemExit(1)

with open(ALIGNMENTS) as f:
    alignments = json.load(f)
with open(GREEK_FABLES) as f:
    greek_fables = json.load(f)
with open(ENGLISH_FABLES) as f:
    english_fables = json.load(f)

# Build Greek fable index by fabula_n
greek_by_n = {gf["fabula_n"]: gf for gf in greek_fables}

# Build English fable index
english_by_idx = {ef["fable_index"]: ef for ef in english_fables}

print("Validating alignments with animal-name matching...")

for a in alignments:
    greek_text = greek_by_n.get(a["greek_cts_ref"], {}).get("text", "")
    gr_animals = find_greek_animals(greek_text)

    en_animals = set()
    if a.get("english_fable_index") is not None:
        en_text = english_by_idx.get(a["english_fable_index"], {}).get("text", "")
        en_title = a.get("english_title", "")
        en_animals = find_english_animals(en_text + " " + en_title)

    # Compute overlap
    if gr_animals and en_animals:
        overlap = gr_animals & en_animals
        entity_score = len(overlap) / max(len(gr_animals), 1)
    elif a["match_type"] == "unmatched":
        entity_score = 0.0
    else:
        entity_score = 0.5  # neutral if no animals detected

    a["entity_overlap_score"] = round(entity_score, 3)
    a["entity_match_count"] = len(gr_animals & en_animals) if gr_animals and en_animals else 0
    a["combined_score"] = round(0.7 * a["similarity"] + 0.3 * entity_score, 4)

# Summary
matched = [a for a in alignments if a["match_type"] == "pairwise_top1"]
unmatched = [a for a in alignments if a["match_type"] == "unmatched"]
high = sum(1 for a in alignments if a["combined_score"] >= 0.6)
low = sum(1 for a in alignments if a["combined_score"] < 0.3)

print(f"\nResults:")
print(f"  Total: {len(alignments)}")
print(f"  Matched: {len(matched)}, Unmatched: {len(unmatched)}")
print(f"  High confidence (>=0.6): {high}")
print(f"  Low confidence (<0.3): {low}")
if matched:
    scores = [a["combined_score"] for a in matched]
    print(f"  Matched combined scores: min={min(scores):.3f}, "
          f"max={max(scores):.3f}, mean={sum(scores)/len(scores):.3f}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(alignments, f, ensure_ascii=False, indent=2)

print(f"\nSaved: {OUTPUT}")

#!/usr/bin/env python3
"""
Normalise Booth's early-modern English for better NLP processing.
Uses a lightweight regex + dictionary approach (no VARD2 dependency).
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT = PROJECT_ROOT / "build" / "booth_extracted.json"
OUTPUT = PROJECT_ROOT / "build" / "booth_normalised.json"

if not INPUT.exists():
    print(f"Error: {INPUT} not found. Run 01_extract_booth.py first.")
    raise SystemExit(1)

# Common early-modern English spelling substitutions
SPELLING_MAP = {
    r"\bdoth\b": "does",
    r"\bhath\b": "has",
    r"\bthou\b": "you",
    r"\bthee\b": "you",
    r"\bthy\b": "your",
    r"\bthine\b": "yours",
    r"\bwhereof\b": "of which",
    r"\bthereof\b": "of that",
    r"\bhereof\b": "of this",
    r"\bhereafter\b": "after this",
    r"\bwherefore\b": "therefore",
    r"\bwhilst\b": "while",
    r"\bamongst\b": "among",
    r"\btill\b": "until",
    r"\b(\w+)eth\b": r"\1es",  # loveth -> loves (rough)
    r"\b(\w+)est\b": r"\1",  # goest -> go (rough)
}

# Letter-level patterns common in EEBO texts
LETTER_SUBS = [
    (r"(?<=[a-z])ck(?=[a-z])", "c"),  # Occasional archaic ck
    (r"\bI\b(?=\s+[a-z])", "I"),  # Keep capital I
    (r"\u2223", ""),  # EEBO line-break marker
    (r"\u3008.*?\u3009", ""),  # EEBO gap markers
]


def normalise(text):
    """Apply spelling normalisation to a text string."""
    t = text
    for pat, rep in LETTER_SUBS:
        t = re.sub(pat, rep, t)
    for pat, rep in SPELLING_MAP.items():
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

for book in data["books"]:
    for ch in book["chapters"]:
        for p in ch["paragraphs"]:
            p["text_normalised"] = normalise(p["text"])

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Normalised text saved to {OUTPUT}")

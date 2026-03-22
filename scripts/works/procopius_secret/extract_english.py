#!/usr/bin/env python3
"""
Extract English sections from the Secret History translation (Gutenberg #12916).

Anonymous 1896 translation. Chapters are marked "CHAPTER I", "CHAPTER II", etc.
Flat chapter structure (no book level), 30 chapters matching the Greek.

Input:  data-sources/gutenberg/procopius/secret_history_12916.txt
Output: build/procopius_secret/english_sections.json
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT = PROJECT_ROOT / "data-sources" / "gutenberg" / "procopius" / "secret_history_12916.txt"
OUTPUT = PROJECT_ROOT / "build" / "procopius_secret" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

if not INPUT.exists():
    print(f"Error: {INPUT} not found")
    raise SystemExit(1)

text = INPUT.read_text(encoding="utf-8-sig")
text = text.replace("\r\n", "\n").replace("\r", "\n")

# Strip Gutenberg header/footer
gut_start = text.find("*** START OF THE PROJECT GUTENBERG EBOOK")
if gut_start != -1:
    gut_start = text.find("\n", gut_start) + 1
else:
    gut_start = 0
gut_end = text.find("*** END OF THE PROJECT GUTENBERG EBOOK")
if gut_end == -1:
    gut_end = len(text)
text = text[gut_start:gut_end]

# Roman numeral mapping
ROMAN = {}
for i, r in enumerate(["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
                        "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX",
                        "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII",
                        "XXVIII", "XXIX", "XXX"], 1):
    ROMAN[r] = i

# Find chapter markers: "CHAPTER I", "CHAPTER II", etc.
chapter_pattern = re.compile(r'^CHAPTER\s+([IVXL]+)\s*$', re.MULTILINE)
matches = list(chapter_pattern.finditer(text))

print(f"Found {len(matches)} chapter markers")

all_sections = []

for i, m in enumerate(matches):
    roman = m.group(1)
    if roman not in ROMAN:
        print(f"  Warning: unrecognized Roman numeral '{roman}', skipping")
        continue
    chapter_num = ROMAN[roman]

    start = m.end()
    if i + 1 < len(matches):
        end = matches[i + 1].start()
    else:
        end = len(text)

    ch_text = text[start:end].strip()

    # Remove footnote references [1], [2], etc.
    ch_text = re.sub(r'\[\d+\]', '', ch_text)
    # Remove [Footnote N: ...] blocks
    ch_text = re.sub(r'\[Footnote \d+:.*?\]', '', ch_text, flags=re.DOTALL)

    # Split chapter into paragraphs (double newline)
    paragraphs = re.split(r'\n\s*\n', ch_text)
    para_idx = 0
    for para in paragraphs:
        para = " ".join(para.split())
        if len(para) < 30:
            continue
        all_sections.append({
            "book": str(chapter_num),
            "chapter": str(chapter_num),
            "section": str(para_idx),
            "cts_ref": f"{chapter_num}.{para_idx}",
            "text": para,
            "char_count": len(para),
        })
        para_idx += 1

# Sort by chapter number
all_sections.sort(key=lambda s: int(s["chapter"]))

print(f"\nExtracted {len(all_sections)} English sections (one per chapter)")
for s in all_sections:
    print(f"  Chapter {s['chapter']}: {s['char_count']} chars")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

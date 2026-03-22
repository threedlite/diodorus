#!/usr/bin/env python3
"""
Extract English translation from Dansey's Arrian on Coursing (Gutenberg #78013).

Only ~6% of the file is actual Arrian translation. The translation section
runs from "ARRIAN ON COURSING" through 35 chapters marked with
[Sidenote: +Chap. N.+] markers. The rest is Dansey's scholarly apparatus.

Input:  data-sources/gutenberg/arrian_cynegeticus/pg78013.txt
Output: build/arrian_cynegeticus/english_sections.json
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT = PROJECT_ROOT / "data-sources" / "gutenberg" / "arrian_cynegeticus" / "pg78013.txt"
OUTPUT = PROJECT_ROOT / "build" / "arrian_cynegeticus" / "english_sections.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

text = INPUT.read_text(encoding="utf-8-sig")
text = text.replace("\r\n", "\n")

# Find chapter markers: [Sidenote: +Chap. I.+ ...]
chapter_pattern = re.compile(
    r'\[Sidenote:\s*\+Chap\.\s*([IVXL]+\.?)\+\s*([^\]]*)\]',
    re.IGNORECASE
)

ROMAN = {}
for i, r in enumerate(["I","II","III","IV","V","VI","VII","VIII","IX","X",
                        "XI","XII","XIII","XIV","XV","XVI","XVII","XVIII","XIX","XX",
                        "XXI","XXII","XXIII","XXIV","XXV","XXVI","XXVII","XXVIII",
                        "XXIX","XXX","XXXI","XXXII","XXXIII","XXXIV","XXXV"], 1):
    ROMAN[r] = i

matches = list(chapter_pattern.finditer(text))
print(f"Found {len(matches)} chapter markers")

all_sections = []
for i, m in enumerate(matches):
    roman = m.group(1).rstrip(".").upper()
    ch_num = ROMAN.get(roman, 0)
    if ch_num == 0:
        continue

    ch_start = m.end()
    ch_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

    # Limit to ~200 lines after last chapter to avoid appendix
    if i == len(matches) - 1:
        lines_after = text[ch_start:].split("\n")
        ch_text = "\n".join(lines_after[:100])
    else:
        ch_text = text[ch_start:ch_end]

    # Strip sidenotes, footnote markers, and Dansey's annotations
    ch_text = re.sub(r'\[Sidenote:[^\]]*\]', '', ch_text)
    ch_text = re.sub(r'\[\d+\]', '', ch_text)
    ch_text = re.sub(r'\[Illustration[^\]]*\]', '', ch_text)

    # Clean up
    ch_text = " ".join(ch_text.split())

    if len(ch_text) < 20:
        continue

    all_sections.append({
        "book": str(ch_num),
        "section": "1",
        "cts_ref": f"{ch_num}.1",
        "text": ch_text,
        "char_count": len(ch_text),
    })

all_sections.sort(key=lambda s: int(s["book"]))
print(f"Extracted {len(all_sections)} English chapters")
for s in all_sections[:3]:
    print(f"  Ch {s['book']}: {s['char_count']} chars")
print(f"  ...")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

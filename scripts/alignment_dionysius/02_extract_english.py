#!/usr/bin/env python3
"""
Extract English chapters from Roberts' translation of De Compositione Verborum.

Gutenberg #50212 is a bilingual edition. We extract only the English text,
splitting on "CHAPTER I", "CHAPTER II", etc.

Input:  data-sources/gutenberg/dionysius/de_compositione_50212.txt
Output: output/dionysius/english_sections.json
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT = PROJECT_ROOT / "data-sources" / "gutenberg" / "dionysius" / "de_compositione_50212.txt"
OUTPUT = PROJECT_ROOT / "build" / "dionysius" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

text = INPUT.read_text(encoding="utf-8-sig")
text = text.replace("\r\n", "\n")

ROMAN = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
    "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
    "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17,
    "XVIII": 18, "XIX": 19, "XX": 20, "XXI": 21, "XXII": 22,
    "XXIII": 23, "XXIV": 24, "XXV": 25, "XXVI": 26,
}

# Find chapter markers
chapter_pattern = re.compile(r"^CHAPTER\s+([IVXL]+)\s*$", re.MULTILINE)
matches = list(chapter_pattern.finditer(text))
print(f"Found {len(matches)} chapter markers")

sections = []
for i, m in enumerate(matches):
    roman_num = m.group(1)
    chapter_num = ROMAN.get(roman_num)
    if chapter_num is None:
        continue

    start = m.end()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

    for stop in ["*** END OF", "ADDITIONAL NOTES", "FOOTNOTES", "INDEX"]:
        idx = text.find(stop, start, end)
        if idx != -1:
            end = idx

    body = text[start:end].strip()

    # The bilingual text has Greek and English interleaved.
    # English lines tend to be normal prose; Greek lines contain Greek chars.
    # Split into lines and keep only lines that are predominantly Latin-script.
    en_lines = []
    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Count Greek vs Latin characters
        greek_chars = sum(1 for c in line if '\u0370' <= c <= '\u03FF' or '\u1F00' <= c <= '\u1FFF')
        latin_chars = sum(1 for c in line if 'A' <= c <= 'z')
        total = greek_chars + latin_chars
        if total > 0 and greek_chars / total < 0.3:
            en_lines.append(line)

    body = " ".join(en_lines)
    body = " ".join(body.split())

    # Remove footnote markers like [1], [2], etc.
    body = re.sub(r"\[\d+\]", "", body)

    if body and len(body) > 20:
        sections.append({
            "book": "1",
            "section": str(chapter_num),
            "cts_ref": str(chapter_num),
            "text": body,
            "char_count": len(body),
        })

sections.sort(key=lambda s: int(s["section"]))
print(f"Extracted {len(sections)} English chapters")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

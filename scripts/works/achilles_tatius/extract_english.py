#!/usr/bin/env python3
"""
Extract English sections from Smith's Achilles Tatius (Gutenberg #55406).

The Gutenberg file contains all three novels (Heliodorus, Longus, Achilles
Tatius). The AT section starts after "ACHILLES TATIUS." heading and has
8 books with no chapter subdivisions — just continuous prose paragraphs.

Inline endnote markers [1], [2] etc. need stripping.

Input:  data-sources/gutenberg/achilles_tatius/pg55406.txt
Output: build/achilles_tatius/english_sections.json
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT = PROJECT_ROOT / "data-sources" / "gutenberg" / "achilles_tatius" / "pg55406.txt"
OUTPUT = PROJECT_ROOT / "build" / "achilles_tatius" / "english_sections.json"

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from pipeline.strip_notes import strip_notes

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

text = INPUT.read_text(encoding="utf-8-sig")
text = text.replace("\r\n", "\n")

# Strip Gutenberg header/footer
start = text.find("*** START OF THE PROJECT GUTENBERG EBOOK")
end = text.find("*** END OF THE PROJECT GUTENBERG EBOOK")
if start != -1:
    text = text[text.find("\n", start) + 1:]
if end != -1:
    text = text[:end]

# Find Achilles Tatius section — starts after the Longus section
# Look for "ACHILLES TATIUS." heading that comes AFTER the Longus section
# (there's one at the start of the volume for the TOC and one for the actual text)
at_positions = [m.start() for m in re.finditer(r'\nACHILLES TATIUS\.\s*\n', text)]

# The last occurrence is the actual AT text section (after Longus)
if len(at_positions) >= 2:
    at_start = at_positions[-1]
elif at_positions:
    at_start = at_positions[0]
else:
    print("Error: could not find Achilles Tatius section")
    raise SystemExit(1)

at_text = text[at_start:]
print(f"Achilles Tatius section starts at position {at_start}")

# Find book boundaries
book_pattern = re.compile(r'^BOOK\s+([IVXL]+)\.\s*$', re.MULTILINE)
book_matches = list(book_pattern.finditer(at_text))
print(f"Found {len(book_matches)} books")

ROMAN = {}
for i, r in enumerate(["I","II","III","IV","V","VI","VII","VIII","IX","X"], 1):
    ROMAN[r] = i

all_sections = []

for bi, bm in enumerate(book_matches):
    book_num = ROMAN.get(bm.group(1), 0)
    book_start = bm.end()
    book_end = book_matches[bi + 1].start() if bi + 1 < len(book_matches) else len(at_text)
    book_text = at_text[book_start:book_end].strip()

    # Remove footnotes section at end of book if present
    for marker in ["\nFOOTNOTES\n", "\nFOOTNOTES:\n", "\nNOTES\n", "\nNOTES:\n"]:
        idx = book_text.rfind(marker)
        if idx != -1 and idx > len(book_text) * 0.7:
            book_text = book_text[:idx]

    # Split into paragraphs
    paragraphs = re.split(r'\n\s*\n', book_text)
    pi = 0
    for para in paragraphs:
        para = " ".join(para.split())
        if len(para) < 30:
            continue

        # Strip endnote markers
        clean = re.sub(r'\[\d+\]', '', para)
        clean = " ".join(clean.split())

        pi += 1
        all_sections.append({
            "book": str(book_num),
            "section": str(pi),
            "cts_ref": f"{book_num}.{pi}",
            "text": para,
            "text_for_embedding": clean,
            "notes": [],
            "char_count": len(para),
        })

all_sections.sort(key=lambda s: (int(s["book"]), int(s["section"])))

print(f"\nExtracted {len(all_sections)} English sections")
for book in sorted(set(s["book"] for s in all_sections), key=int):
    n = sum(1 for s in all_sections if s["book"] == book)
    print(f"  Book {book}: {n} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

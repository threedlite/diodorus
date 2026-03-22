#!/usr/bin/env python3
"""
Extract English chapters from Dewing's Procopius Wars (Gutenberg #16764, #16765, #20298).

V1: Books I-II (Persian War)
V2: Books III-IV (Vandalic War)
V3: Books V-VI (Gothic War)
Books VII-VIII have no English translation on Gutenberg.

Input:  data-sources/gutenberg/procopius/wars_v*.txt
Output: build/procopius_wars/english_sections.json
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GUTENBERG_DIR = PROJECT_ROOT / "data-sources" / "gutenberg" / "procopius"
OUTPUT = PROJECT_ROOT / "build" / "procopius_wars" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

VOLUMES = [
    ("wars_v1_16764.txt", [1, 2]),
    ("wars_v2_16765.txt", [3, 4]),
    ("wars_v3_20298.txt", [5, 6]),
]

ROMAN = {}
for i, r in enumerate(["I","II","III","IV","V","VI","VII","VIII","IX","X",
                        "XI","XII","XIII","XIV","XV","XVI","XVII","XVIII","XIX","XX",
                        "XXI","XXII","XXIII","XXIV","XXV","XXVI","XXVII","XXVIII",
                        "XXIX","XXX","XXXI","XXXII","XXXIII","XXXIV","XXXV"], 1):
    ROMAN[r] = i


def strip_gutenberg(text):
    start = text.find("*** START OF THE PROJECT GUTENBERG EBOOK")
    end = text.find("*** END OF THE PROJECT GUTENBERG EBOOK")
    if start != -1:
        text = text[text.find("\n", start) + 1:]
    if end != -1:
        text = text[:end]
    return text


all_sections = []

for filename, book_nums in VOLUMES:
    filepath = GUTENBERG_DIR / filename
    if not filepath.exists():
        print(f"Warning: {filepath} not found, skipping")
        continue

    text = filepath.read_text(encoding="utf-8-sig")
    text = text.replace("\r\n", "\n")
    text = strip_gutenberg(text)

    first_book = book_nums[0]
    second_book = book_nums[1] if len(book_nums) > 1 else None

    # Find book boundaries using multiple marker formats:
    #   "HISTORY OF THE WARS: BOOK II"  (V1, V3)
    #   "BOOK IV"                        (V2)
    # Both appear as standalone lines or with subtitle underneath

    # Find ALL book markers in the text (after the TOC)
    # TOC entries have page numbers or colons with descriptions — skip those
    toc_end = text.find("\n\n\n\n")  # TOC ends with multiple blank lines
    if toc_end == -1:
        toc_end = 0

    book_positions = []  # (book_num, text_position)

    # Pattern 1: "HISTORY OF THE WARS: BOOK N" or just "BOOK N" on its own line
    for m in re.finditer(r'(?:HISTORY OF THE WARS:\s*)?BOOK\s+([IVXL]+)\b', text):
        if m.start() < toc_end:
            continue
        roman = m.group(1)
        if roman not in ROMAN:
            continue
        book_num = ROMAN[roman]
        if book_num not in book_nums:
            continue
        # Check this isn't a TOC entry or footnote cross-reference
        line_end = text.find("\n", m.end())
        rest = text[m.end():line_end] if line_end != -1 else ""
        if re.search(r'[ivxl]+\.\s*\d+', rest.lower()):
            continue  # footnote cross-reference like "Book VI. xxx. 30."
        if ".--" in rest or "_(CONTINUE" in rest or re.search(r'\d+$', rest.strip()):
            continue  # TOC entry like "BOOK I.--THE PERSIAN WAR  1"
        book_positions.append((book_num, m.end()))

    # Deduplicate — keep the FIRST occurrence of each book number
    seen = set()
    unique_positions = []
    for bn, pos in book_positions:
        if bn not in seen:
            seen.add(bn)
            unique_positions.append((bn, pos))
    book_positions = unique_positions

    if not book_positions:
        print(f"  Warning: no book markers found in {filename}")
        continue

    book_positions.sort(key=lambda x: x[1])

    for i, (book_num, start) in enumerate(book_positions):
        end = book_positions[i + 1][1] if i + 1 < len(book_positions) else len(text)
        book_text = text[start:end]

        # Remove footnotes at end
        for marker in ["\nFOOTNOTES\n", "\nNOTES\n"]:
            idx = book_text.rfind(marker)
            if idx != -1 and idx > len(book_text) * 0.7:
                book_text = book_text[:idx]

        # Split on chapter markers: standalone Roman numerals on their own line
        chapter_pattern = re.compile(r'^\s*([IVXL]+)\s*$', re.MULTILINE)
        matches = list(chapter_pattern.finditer(book_text))

        # Filter to valid sequential Roman numerals.
        # Handle OCR errors where a chapter number goes backwards (e.g.
        # XVIII, XI, XX — the "XI" is really "XIX").  When a number is
        # lower than the previous, use previous + 1 instead.
        chapters = []
        for m in matches:
            r = m.group(1).strip()
            if r in ROMAN:
                num = ROMAN[r]
                if chapters and num <= chapters[-1][0]:
                    corrected = chapters[-1][0] + 1
                    print(f"    Warning: chapter {r} ({num}) follows {chapters[-1][0]}, "
                          f"correcting to {corrected}")
                    num = corrected
                chapters.append((num, m.end()))

        print(f"  Book {book_num}: {len(chapters)} chapters")

        for ci, (ch_num, ch_start) in enumerate(chapters):
            ch_end = chapters[ci + 1][1] if ci + 1 < len(chapters) else len(book_text)
            ch_text = book_text[ch_start:ch_end].strip()

            # Clean
            ch_text = re.sub(r'\[\d+\]', '', ch_text)

            # Split into paragraphs
            paragraphs = re.split(r'\n\s*\n', ch_text)
            for pi, para in enumerate(paragraphs):
                para = " ".join(para.split())
                if len(para) < 30:
                    continue
                all_sections.append({
                    "book": str(book_num),
                    "section": f"{ch_num}.{pi}",
                    "cts_ref": f"{book_num}.{ch_num}.{pi}",
                    "text": para,
                    "char_count": len(para),
                })

all_sections.sort(key=lambda s: (
    int(s["book"]),
    int(s["section"].split(".")[0]),
    int(s["section"].split(".")[-1])
))

print(f"\nExtracted {len(all_sections)} English sections")
for b in sorted(set(s["book"] for s in all_sections), key=int):
    n = sum(1 for s in all_sections if s["book"] == b)
    print(f"  Book {b}: {n} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

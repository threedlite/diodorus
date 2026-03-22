#!/usr/bin/env python3
"""
Extract English paragraphs from Legge's Philosophumena (Gutenberg #65478, #67116).

V1 has Books I, (II-III lost), IV, V.
V2 has Books VI, VII, VIII, IX, X.

Input:  data-sources/gutenberg/hippolytus/
Output: build/hippolytus/english_sections.json
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT_V1 = PROJECT_ROOT / "data-sources" / "gutenberg" / "hippolytus" / "philosophumena_v1_65478.txt"
INPUT_V2 = PROJECT_ROOT / "data-sources" / "gutenberg" / "hippolytus" / "philosophumena_v2_67116.txt"
OUTPUT = PROJECT_ROOT / "build" / "hippolytus" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
         "VII": 7, "VIII": 8, "IX": 9, "X": 10}


def strip_gutenberg(text):
    start = text.find("*** START OF THE PROJECT GUTENBERG EBOOK")
    end = text.find("*** END OF THE PROJECT GUTENBERG EBOOK")
    if start != -1:
        text = text[text.find("\n", start) + 1:]
    if end != -1:
        text = text[:end]
    return text


def find_books(text):
    """Find book boundaries. Handles various BOOK markers in the text."""
    # Match "BOOK I", "BOOK IV", "BOOK VI" etc on their own line
    # May have [1] footnotes, [Sidenote:] prefixes, or leading whitespace
    pattern = re.compile(
        r'^\s*(?:\[Sidenote:[^\]]*\]\s*)?BOOK\s+(I{1,3}|IV|V|VI{0,3}|IX|X)(?:\[?\d*\]?)?\s*$',
        re.MULTILINE
    )

    books = []
    for m in pattern.finditer(text):
        roman = m.group(1)
        if roman in ROMAN:
            book_num = ROMAN[roman]
            books.append((book_num, m.end()))

    # Also check for "BOOKS II AND III" (lost books)
    lost = re.search(r'BOOKS?\s+II\s+AND\s+III', text)
    if lost:
        books.append((2, lost.end()))

    books.sort(key=lambda x: x[1])
    return books


all_sections = []

for input_file in [INPUT_V1, INPUT_V2]:
    if not input_file.exists():
        print(f"Error: {input_file} not found")
        raise SystemExit(1)

    text = input_file.read_text(encoding="utf-8-sig")
    text = text.replace("\r\n", "\n")
    text = strip_gutenberg(text)

    books = find_books(text)
    print(f"{input_file.name}: found books {[b[0] for b in books]}")

    for i, (book_num, start) in enumerate(books):
        end = books[i + 1][1] if i + 1 < len(books) else len(text)

        # For "BOOKS II AND III" (lost), just note them as empty
        if book_num == 2:
            # Find where this note ends (next BOOK marker)
            book_text = text[start:end].strip()
            # Books 2-3 are lost — create minimal placeholder sections
            for lost_book in [2, 3]:
                all_sections.append({
                    "book": str(lost_book),
                    "section": "0",
                    "cts_ref": f"{lost_book}.0",
                    "text": f"[Books {lost_book} is lost]",
                    "char_count": 20,
                })
            continue

        book_text = text[start:end]

        # Remove footnote markers and sidenotes
        book_text = re.sub(r'\[Sidenote:[^\]]*\]', '', book_text)
        book_text = re.sub(r'\[\d+\]', '', book_text)

        # Remove the FOOTNOTES section at the end
        for marker in ["FOOTNOTES", "BOOKS FOR STUDENTS", "END OF BOOK"]:
            idx = book_text.find(marker)
            if idx != -1:
                book_text = book_text[:idx]

        # Split into paragraphs on double newlines
        paragraphs = re.split(r'\n\s*\n', book_text)

        para_idx = 0
        for para in paragraphs:
            para = para.strip()
            para = " ".join(para.split())
            if len(para) < 30:
                continue
            # Skip chapter headings that are just "CHAPTER I" etc
            if re.match(r'^(CHAPTER|SECT|PART)\s+[IVXL]+\.?$', para):
                continue
            all_sections.append({
                "book": str(book_num),
                "section": str(para_idx),
                "cts_ref": f"{book_num}.{para_idx}",
                "text": para,
                "char_count": len(para),
            })
            para_idx += 1

        print(f"  Book {book_num}: {para_idx} paragraphs")

all_sections.sort(key=lambda s: (int(s["book"]), int(s["section"])))

print(f"\nExtracted {len(all_sections)} English sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

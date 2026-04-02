#!/usr/bin/env python3
"""
Extract English sections from Chinnock's Arrian Anabasis (Gutenberg #46976).

7 books, ~206 chapters (including preface). Clean text with inline endnote
markers [14] etc. that need stripping. Chapters have descriptive ALL-CAPS
subtitles that should be kept as headings.

Input:  data-sources/gutenberg/arrian_anabasis/pg46976.txt
Output: build/arrian_anabasis/english_sections.json
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT = PROJECT_ROOT / "data-sources" / "gutenberg" / "arrian_anabasis" / "pg46976.txt"
OUTPUT = PROJECT_ROOT / "build" / "arrian_anabasis" / "english_sections.json"

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

# Extract Arrian's preface (before BOOK I.) as a section
book1_pos = text.find("\nBOOK I.\n")
preface_section = None
if book1_pos != -1:
    preamble = text[:book1_pos]
    pref_marker = preamble.find("ARRIAN'S PREFACE")
    if pref_marker == -1:
        pref_marker = preamble.find("ARRIAN\u2019S PREFACE")
    if pref_marker != -1:
        # Extract text after the "ARRIAN'S PREFACE." heading
        pref_text = preamble[pref_marker:]
        # Skip the heading line itself
        pref_text = pref_text[pref_text.find("\n") + 1:].strip()
        pref_clean, pref_notes = strip_notes(pref_text)
        pref_clean = " ".join(pref_clean.split())
        pref_full = " ".join(pref_text.split())
        if len(pref_clean) > 50:
            preface_section = {
                "book": "1",
                "section": "pr",
                "cts_ref": "1.pr",
                "text": pref_full,
                "text_for_embedding": pref_clean,
                "notes": pref_notes,
                "char_count": len(pref_full),
            }
    text = text[book1_pos:]

# Remove footnotes section at end
footnotes_pos = text.find("\nFOOTNOTES:\n")
if footnotes_pos == -1:
    footnotes_pos = text.find("\nFOOTNOTES\n")
if footnotes_pos != -1:
    text = text[:footnotes_pos]

# Remove "THE END" marker
text = re.sub(r'\nTHE END OF THE HISTORY.*?\n', '\n', text)

ROMAN = {}
for i, r in enumerate(["I","II","III","IV","V","VI","VII","VIII","IX","X",
                        "XI","XII","XIII","XIV","XV","XVI","XVII","XVIII","XIX","XX",
                        "XXI","XXII","XXIII","XXIV","XXV","XXVI","XXVII","XXVIII",
                        "XXIX","XXX"], 1):
    ROMAN[r] = i

# Find book boundaries
book_pattern = re.compile(r'^BOOK\s+([IVXL]+)\.\s*$', re.MULTILINE)
book_matches = list(book_pattern.finditer(text))
print(f"Found {len(book_matches)} books")

# Find chapter boundaries
chapter_pattern = re.compile(r'^CHAPTER\s+([IVXL]+)\.\s*$', re.MULTILINE)

all_sections = []

for bi, bm in enumerate(book_matches):
    book_roman = bm.group(1)
    book_num = ROMAN.get(book_roman, 0)

    book_start = bm.end()
    book_end = book_matches[bi + 1].start() if bi + 1 < len(book_matches) else len(text)
    book_text = text[book_start:book_end]

    # Find chapters within this book
    ch_matches = list(chapter_pattern.finditer(book_text))

    # Check for preface before first chapter
    if ch_matches:
        preface_text = book_text[:ch_matches[0].start()].strip()
        # Look for "ARRIAN'S PREFACE" or similar
        if "PREFACE" in preface_text.upper() or (book_num == 1 and len(preface_text) > 200):
            clean_text = re.sub(r'\[\d+\]', '', preface_text)
            clean_text = " ".join(clean_text.split())
            if len(clean_text) > 50:
                all_sections.append({
                    "book": str(book_num),
                    "section": "pr",
                    "cts_ref": f"{book_num}.pr",
                    "text": " ".join(preface_text.split()),
                    "text_for_embedding": clean_text,
                    "notes": [],
                    "char_count": len(clean_text),
                })

    for ci, cm in enumerate(ch_matches):
        ch_roman = cm.group(1)
        ch_num = ROMAN.get(ch_roman, 0)

        ch_start = cm.end()
        ch_end = ch_matches[ci + 1].start() if ci + 1 < len(ch_matches) else len(book_text)
        ch_text = book_text[ch_start:ch_end].strip()

        # Extract heading (ALL-CAPS line after chapter marker)
        heading = None
        lines = ch_text.split("\n")
        content_start = 0
        for li, line in enumerate(lines):
            stripped = line.strip()
            if stripped and stripped == stripped.upper() and len(stripped) > 5:
                heading = stripped.rstrip(".")
                content_start = li + 1
            elif stripped:
                break

        body = "\n".join(lines[content_start:]).strip()

        # Strip endnote markers
        clean, notes = strip_notes(body)
        clean = " ".join(clean.split())
        full = " ".join(body.split())

        if not clean or len(clean) < 30:
            continue

        entry = {
            "book": str(book_num),
            "section": str(ch_num),
            "cts_ref": f"{book_num}.{ch_num}",
            "text": full,
            "text_for_embedding": clean,
            "notes": notes,
            "char_count": len(full),
        }
        if heading:
            entry["heading_text"] = heading

        all_sections.append(entry)

# Insert Arrian's preface if extracted
if preface_section:
    all_sections.append(preface_section)

# Sort
def sort_key(s):
    book = int(s["book"])
    sec = s["section"]
    if sec == "pr":
        return (book, -1)
    return (book, int(sec))

all_sections.sort(key=sort_key)

print(f"\nExtracted {len(all_sections)} English sections")
for book in sorted(set(s["book"] for s in all_sections), key=int):
    n = sum(1 for s in all_sections if s["book"] == book)
    print(f"  Book {book}: {n} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

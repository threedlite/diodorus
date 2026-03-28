#!/usr/bin/env python3
"""
Extract English sections from George Long's Meditations translation (Gutenberg #15877).

Parses the plain text into book/section structure matching the Greek.
Long numbers sections as "2.", "3.", etc. (section 1 is unnumbered, starts
immediately after the book heading).

Input:  data-sources/gutenberg/marcus_aurelius/meditations_long_15877.txt
Output: output/marcus/english_sections.json
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT = PROJECT_ROOT / "data-sources" / "gutenberg" / "marcus_aurelius" / "meditations_long_15877.txt"
OUTPUT = PROJECT_ROOT / "build" / "marcus" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

if not INPUT.exists():
    print(f"Error: {INPUT} not found")
    raise SystemExit(1)

text = INPUT.read_text(encoding="utf-8-sig")
text = text.replace("\r\n", "\n").replace("\r", "\n")

# Find the actual Meditations text (starts after "THE THOUGHTS" heading near line 2120)
# and ends at "THE END."
gut_start = text.find("*** START OF THE PROJECT GUTENBERG EBOOK")
gut_end = text.find("*** END OF THE PROJECT GUTENBERG EBOOK")
if gut_start != -1:
    text = text[gut_start:gut_end] if gut_end != -1 else text[gut_start:]

# Find book boundaries using Roman numeral headers on their own line
# Books are marked as "I.", "II.", ... "XII." on their own line
book_pattern = re.compile(r"^(I{1,3}|IV|V|VI{0,3}|IX|X|XI{0,2}|XII)\.\s*$", re.MULTILINE)

# Map Roman to Arabic
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
         "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}

book_matches = list(book_pattern.finditer(text))
print(f"Found {len(book_matches)} book markers")

if len(book_matches) != 12:
    # Try to find them more carefully
    print("  Trying alternate pattern...")
    book_matches = list(re.finditer(r"^\n(I{1,3}|IV|V|VI{0,3}|IX|X|XI{0,2}|XII)\.\n", text, re.MULTILINE))
    print(f"  Found {len(book_matches)} book markers")

books = []
for i, m in enumerate(book_matches):
    roman_num = m.group(1)
    book_num = ROMAN.get(roman_num)
    if book_num is None:
        continue

    start = m.end()
    end = book_matches[i + 1].start() if i + 1 < len(book_matches) else len(text)

    # Trim trailing material: index, appendix, "THE END."
    for stop_marker in ["INDEXES.", "INDEX OF TERMS.", "APPENDIX", "THE END."]:
        stop_pos = text.find(stop_marker, start, end)
        if stop_pos != -1 and stop_pos < end:
            end = stop_pos

    book_text = text[start:end].strip()
    books.append((book_num, book_text))
    print(f"  Book {book_num}: {len(book_text)} chars")

# Parse each book into sections
# Section pattern: number followed by period at start of line, or start of paragraph
# Section 1 is the text before the first "2." marker
all_sections = []

for book_num, book_text in books:
    # Split on section numbers: "2.", "3.", etc. at start of line or after blank lines
    # The pattern is: blank line(s) then a number followed by period
    section_pattern = re.compile(r"\n\s*\n\s*(\d+)\.\s+")

    parts = section_pattern.split(book_text)
    # parts[0] = section 1 text (before first numbered section)
    # parts[1] = "2", parts[2] = section 2 text
    # parts[3] = "3", parts[4] = section 3 text, etc.

    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from pipeline.strip_notes import strip_notes

    def process_section(raw_text, book_num, sec_num):
        """Process a raw section: strip notes, normalize, return section dict."""
        # strip_notes needs raw text with indentation preserved
        clean, notes = strip_notes(raw_text)
        full = " ".join(raw_text.split())   # original with footnotes, normalized
        clean = " ".join(clean.split())      # without footnotes, for embedding
        if not clean:
            return None
        return {
            "book": str(book_num),
            "section": str(sec_num),
            "cts_ref": f"{book_num}.{sec_num}",
            "text": full,
            "text_for_embedding": clean,
            "notes": notes,
            "char_count": len(full),
        }

    # Section 1
    sec = process_section(parts[0].strip(), book_num, "1")
    if sec:
        all_sections.append(sec)

    # Remaining sections
    for j in range(1, len(parts) - 1, 2):
        sec_num = parts[j]
        sec = process_section(parts[j + 1].strip(), book_num, sec_num)
        if sec:
            all_sections.append(sec)

# Merge English sections where the Greek source combines them into one.
# Perseus 12.17.1 contains both sections 17 and 18 (the Greek numeral ιη′
# marks the boundary inline). Merge English 12.18 into 12.17 so CTS matches.
MERGE_INTO = {
    ("12", "18"): ("12", "17"),  # 12.18 → append to 12.17
}
for (src_book, src_sec), (dst_book, dst_sec) in MERGE_INTO.items():
    src = [s for s in all_sections if s["book"] == src_book and s["section"] == src_sec]
    dst = [s for s in all_sections if s["book"] == dst_book and s["section"] == dst_sec]
    if src and dst:
        dst[0]["text"] += " " + src[0]["text"]
        dst[0]["text_for_embedding"] += " " + src[0]["text_for_embedding"]
        dst[0]["char_count"] = len(dst[0]["text"])
        dst[0]["notes"].extend(src[0].get("notes", []))
        all_sections.remove(src[0])
        print(f"  Merged {src_book}.{src_sec} into {dst_book}.{dst_sec}")

# Sort
all_sections.sort(key=lambda s: (int(s["book"]), int(s["section"])))

print(f"\nExtracted {len(all_sections)} English sections")
for book in sorted(set(s["book"] for s in all_sections), key=int):
    book_secs = [s for s in all_sections if s["book"] == book]
    print(f"  Book {book}: {len(book_secs)} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

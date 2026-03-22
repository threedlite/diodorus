#!/usr/bin/env python3
"""
Extract English prose from eng_trans-dev Apollonius Argonautica (Coleridge 1889).

CTS-split file with chapter divisions within 4 books.

Input:  data-sources/english_trans-dev/data/tlg0001/tlg001/
Output: build/apollonius/english_sections.json
"""

import json
import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data-sources" / "english_trans-dev" / "data" / "tlg0001" / "tlg001"
OUTPUT = PROJECT_ROOT / "build" / "apollonius" / "english_sections.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_files = [f for f in sorted(INPUT_DIR.glob("*.xml")) if f.name != "_cts_.xml"]
xml_path = xml_files[0]
print(f"Parsing: {xml_path.name}")

tree = etree.parse(str(xml_path))
root = tree.getroot()
TEI_NS = "http://www.tei-c.org/ns/1.0"

ROMAN = {r: i for i, r in enumerate(["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII"], 1)}


def extract_p_text(p_elem):
    parts = []
    if p_elem.text: parts.append(p_elem.text)
    for child in p_elem:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag in ("note", "figure", "pb", "foreign"): pass
        elif tag == "lb": parts.append(" ")
        else: parts.append("".join(child.itertext()))
        if child.tail: parts.append(child.tail)
    text = "".join(parts).replace("­", "")
    return re.sub(r'\s+', ' ', text).strip()


body = root.find(f".//{{{TEI_NS}}}body")

# Find chapter divs and extract paragraphs
# The CTS file has chapters numbered like 8, 9, 10, 11 where
# chapters map to books (8=Book I, 9=Book II, etc.)
all_sections = []

# Look for book markers or chapter structure
# Try to find book-level divs first
book_divs = []
for div in body.iter(f"{{{TEI_NS}}}div"):
    if div.get("subtype") == "chapter" and div.get("type") == "textpart":
        titles = []
        for t in div.findall(f".//{{{TEI_NS}}}title"):
            titles.append((t.text or "").strip().upper())
        book_divs.append((div, titles))

# Determine book boundaries from titles
current_book = "1"
for div, titles in book_divs:
    # Check for BOOK markers
    for t in titles:
        m = re.match(r'BOOK\s+([IVXL]+)', t)
        if m and m.group(1) in ROMAN:
            current_book = str(ROMAN[m.group(1)])

    # Skip preface/commentary divs
    div_type = div.get("type", "")
    if div_type == "commentary":
        continue

    paragraphs = list(div.findall(f"{{{TEI_NS}}}p"))
    for pi, p in enumerate(paragraphs):
        text = extract_p_text(p)
        if len(text) >= 20:
            all_sections.append({
                "book": current_book,
                "section": str(len([s for s in all_sections if s["book"] == current_book]) + 1),
                "cts_ref": f"{current_book}.{len([s for s in all_sections if s['book'] == current_book]) + 1}",
                "text": text,
                "char_count": len(text),
            })

# Fix section numbering
for book in sorted(set(s["book"] for s in all_sections), key=int):
    book_secs = [s for s in all_sections if s["book"] == book]
    for i, s in enumerate(book_secs):
        s["section"] = str(i + 1)
        s["cts_ref"] = f"{book}.{i + 1}"

print(f"Extracted {len(all_sections)} English sections")
for book in sorted(set(s["book"] for s in all_sections), key=int):
    n = sum(1 for s in all_sections if s["book"] == book)
    print(f"  Book {book}: {n} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

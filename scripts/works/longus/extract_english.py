#!/usr/bin/env python3
"""
Extract English sections from Smith's Longus translation (eng_trans-dev 1901).

The English is in a multi-novel TEI XML volume. We extract only the Longus
section, split into books by BOOK markers, with each <p> element becoming
a section.

Book structure:
  - Preface (div type="commentary" subtype="preface")
  - Main text (div type="textpart" subtype="chapter"):
    Book 1: starts immediately
    Book 2-4: marked by <title type="sub">BOOK II/III/IV</title>

Input:  data-sources/english_trans-dev/volumes/heliodorus_longus_achillesTatius_1901/
Output: build/longus/english_sections.json
"""

import json
import re
import sys
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data-sources" / "english_trans-dev" / "volumes" / "heliodorus_longus_achillesTatius_1901"
OUTPUT = PROJECT_ROOT / "build" / "longus" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_files = sorted(INPUT_DIR.glob("*.xml"))
if not xml_files:
    print(f"Error: no XML files in {INPUT_DIR}")
    raise SystemExit(1)

xml_path = xml_files[0]
print(f"Parsing: {xml_path.name}")

tree = etree.parse(str(xml_path))
root = tree.getroot()

TEI_NS = "http://www.tei-c.org/ns/1.0"


def extract_text(elem):
    """Extract text from an element, skipping footnotes and figures."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag == "note":
            pass  # skip footnotes
        elif tag == "figure":
            pass  # skip illustrations
        elif tag == "lb":
            parts.append(" ")  # line break → space
        elif tag == "pb":
            pass  # skip page breaks
        elif tag == "foreign":
            pass  # skip Greek quotations
        else:
            parts.append("".join(child.itertext()))
        if child.tail:
            parts.append(child.tail)
    text = "".join(parts)
    # Clean OCR artifacts
    text = text.replace("­\n", "")  # soft hyphen + newline
    text = text.replace("­ ", "")   # soft hyphen + space
    text = text.replace("­", "")    # standalone soft hyphen
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# Find all top-level divs
body = root.find(f".//{{{TEI_NS}}}body")
if body is None:
    print("Error: no <body> found")
    raise SystemExit(1)

edition_div = body.find(f"{{{TEI_NS}}}div")
if edition_div is None:
    print("Error: no edition div found")
    raise SystemExit(1)

# Find Longus sections by looking for the title marker
longus_divs = []
in_longus = False
for div in edition_div:
    tag = etree.QName(div.tag).localname if isinstance(div.tag, str) else ""
    if tag != "div":
        continue

    # Check for Longus title
    heads = div.findall(f".//{{{TEI_NS}}}title")
    for h in heads:
        title_text = (h.text or "").strip()
        if "DAPHNIS AND CHLOE" in title_text.upper() and "PASTORAL" in title_text.upper():
            in_longus = True
            break
        if "ACHILLES TATIUS" in title_text.upper() and in_longus:
            in_longus = False
            break

    if in_longus:
        longus_divs.append(div)

print(f"Found {len(longus_divs)} Longus divs")

# Process Longus divs — combine preface + main text
# Skip epigraph divs (e.g. Shakespeare quote) that appear before the preface.
# The preface div has type="commentary" subtype="preface"; anything before it
# is decorative front matter, not part of the translation.
preface_idx = next((i for i, d in enumerate(longus_divs)
                     if d.get("type") == "commentary" or d.get("subtype") == "preface"), 0)
longus_divs = longus_divs[preface_idx:]

all_p_elements = []
for div in longus_divs:
    div_type = div.get("type", "")
    div_subtype = div.get("subtype", "")

    # Collect all <p> and book markers in order
    for child in div.iter():
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag == "p":
            all_p_elements.append(("p", child))
        elif tag == "title":
            title_text = (child.text or "").strip().upper()
            if re.match(r'BOOK\s+[IVXL]+', title_text) or "BOOK IT" in title_text:
                all_p_elements.append(("book_marker", title_text))

# Split paragraphs into books
books = {}
current_book = "1"  # Book 1 starts without explicit marker

for item_type, item in all_p_elements:
    if item_type == "book_marker":
        title = item
        # Parse book number from marker
        # Handle OCR variants: "BOOK IT." = "BOOK II"
        # Match longest first to avoid "III" matching "II"
        if "BOOK IV" in title:
            current_book = "4"
        elif "BOOK III" in title:
            current_book = "3"
        elif "BOOK IT" in title or re.search(r'BOOK\s+II[^I]', title + " "):
            current_book = "2"
        print(f"  Book marker: '{title}' → Book {current_book}")
    elif item_type == "p":
        text = extract_text(item)
        if len(text) >= 20:
            books.setdefault(current_book, []).append(text)

# Build sections
all_sections = []
for book_num in sorted(books.keys(), key=int):
    paragraphs = books[book_num]
    for pi, para in enumerate(paragraphs):
        all_sections.append({
            "book": book_num,
            "section": str(pi + 1),
            "cts_ref": f"{book_num}.{pi + 1}",
            "text": para,
            "char_count": len(para),
        })

print(f"\nExtracted {len(all_sections)} English sections")
for book in sorted(set(s["book"] for s in all_sections), key=int):
    n = sum(1 for s in all_sections if s["book"] == book)
    print(f"  Book {book}: {n} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

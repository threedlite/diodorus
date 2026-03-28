#!/usr/bin/env python3
"""
Extract English sections from Smith's Heliodorus Aethiopica (eng_trans-dev 1901).

The volume structure is: summaries (Heliodorus, Longus, AT) then full texts.
The Heliodorus narrative starts at the div titled "THE ADVENTURES OF THEAGENES
AND CHARICLEA" and runs until the Longus div ("THE LOVES OF DAPHNIS AND CHLOE").

10 books, Book I has no explicit marker, Books II-X have BOOK markers.

Input:  data-sources/english_trans-dev/volumes/heliodorus_longus_achillesTatius_1901/
Output: build/heliodorus/english_sections.json
"""

import json
import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data-sources" / "english_trans-dev" / "volumes" / "heliodorus_longus_achillesTatius_1901"
OUTPUT = PROJECT_ROOT / "build" / "heliodorus" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_files = sorted(INPUT_DIR.glob("*.xml"))
xml_path = xml_files[0]
print(f"Parsing: {xml_path.name}")

tree = etree.parse(str(xml_path))
root = tree.getroot()
TEI_NS = "http://www.tei-c.org/ns/1.0"

ROMAN = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8,"IX":9,"X":10}


def extract_text(elem):
    """Extract text from a <p>, skipping footnotes, figures, foreign text."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag in ("note", "figure", "pb", "foreign"):
            pass
        elif tag == "lb":
            parts.append(" ")
        else:
            parts.append("".join(child.itertext()))
        if child.tail:
            parts.append(child.tail)
    text = "".join(parts)
    text = text.replace("­", "")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


body = root.find(f".//{{{TEI_NS}}}body")
edition_div = body.find(f"{{{TEI_NS}}}div")

# Find the Heliodorus narrative div: has title "ADVENTURES OF THEAGENES"
# Then collect all divs until we hit the Longus div
heliodorus_divs = []
found_heliodorus = False

for div in edition_div:
    tag = etree.QName(div.tag).localname if isinstance(div.tag, str) else ""
    if tag != "div":
        continue

    titles = div.findall(f".//{{{TEI_NS}}}title")
    title_texts = [(t.text or "").strip().upper() for t in titles]

    # Start: "THE ADVENTURES OF THEAGENES AND CHARICLEA" (narrative div)
    # Must start with "THE" to distinguish from the summary div
    # ("ETHIOPICS: OR, ADVENTURES OF...")
    if any(t.startswith("THE ADVENTURES") and "THEAGENES" in t for t in title_texts):
        found_heliodorus = True

    # Stop: Longus section
    if found_heliodorus and any("DAPHNIS" in t and "CHLOE" in t for t in title_texts):
        break

    if found_heliodorus:
        heliodorus_divs.append(div)

print(f"Found {len(heliodorus_divs)} Heliodorus divs")

# Process divs — collect <p> elements and book markers
all_p_elements = []

for div in heliodorus_divs:
    for child in div.iter():
        child_tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if child_tag == "p":
            all_p_elements.append(("p", child))
        elif child_tag == "title" and child.get("type") == "sub":
            title_text = (child.text or "").strip().upper()
            m = re.match(r'BOOK\s+([IVXL]+)', title_text)
            if m and m.group(1) in ROMAN:
                all_p_elements.append(("book_marker", str(ROMAN[m.group(1)])))

# Split by book markers
books = {}
current_book = "1"

for item_type, item in all_p_elements:
    if item_type == "book_marker":
        current_book = item
        print(f"  Book marker: {current_book}")
    elif item_type == "p":
        text = extract_text(item)
        if len(text) >= 20:
            books.setdefault(current_book, []).append(text)

# Merge English paragraphs to match Greek section count per book.
# The English has 1.5-4x more paragraphs than Greek sections. CTS matches
# by section number, so English 1.34 has no Greek counterpart if Greek only
# goes to 1.33. Merging consecutive paragraphs proportionally by character
# count ensures 1:1 correspondence.
import math

greek_path = PROJECT_ROOT / "build" / "heliodorus" / "greek_sections.json"
gr_counts = {}
if greek_path.exists():
    with open(greek_path) as f:
        gr_data = json.load(f)
    from collections import Counter
    gr_counts = Counter(s.get("book", "") for s in gr_data["sections"])
    print(f"  Greek section counts: {dict(sorted(gr_counts.items(), key=lambda x: int(x[0])))}")

all_sections = []
for book_num in sorted(books.keys(), key=int):
    paragraphs = books[book_num]
    target_n = gr_counts.get(book_num, len(paragraphs))

    if len(paragraphs) > target_n and target_n > 0:
        # Merge: distribute paragraphs into exactly target_n groups.
        # Assign ceil(n_paras/target_n) paragraphs per group, adjusting
        # the last groups to absorb any remainder.
        n = len(paragraphs)
        per_group = max(1, n // target_n)
        merged = []
        idx = 0
        for g in range(target_n):
            # How many paragraphs for this group?
            remaining_groups = target_n - g
            remaining_paras = n - idx
            count = max(1, remaining_paras // remaining_groups)
            group_text = " ".join(paragraphs[idx:idx + count])
            merged.append(group_text)
            idx += count
        # Any leftover paragraphs go into the last group
        if idx < n:
            merged[-1] += " " + " ".join(paragraphs[idx:])
        paragraphs = merged
        print(f"  Book {book_num}: merged {len(books[book_num])} → {len(paragraphs)} paragraphs (target {target_n})")

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

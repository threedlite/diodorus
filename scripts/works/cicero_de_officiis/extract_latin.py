#!/usr/bin/env python3
"""
Extract Latin sections from Perseus Cicero De Officiis TEI XML.

Structure: 3 books, 371 sections total (book.section).
The TEI has book divs containing section divs; chapter milestones exist
but are not div boundaries (so sections cleanly nest under books).

Input:  data-sources/perseus/canonical-latinLit/data/phi0474/phi055/
Output: build/cicero_de_officiis/greek_sections.json (named "greek" for pipeline compat)
"""

from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-latinLit" / "data" / "phi0474" / "phi055"
OUTPUT = PROJECT_ROOT / "build" / "cicero_de_officiis" / "greek_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Pick the Latin edition file (perseus-lat1)
xml_files = sorted(f for f in PERSEUS_DIR.iterdir()
                   if f.suffix == ".xml" and "lat" in f.name and f.name != "__cts__.xml")
if not xml_files:
    print(f"Error: no Latin XML in {PERSEUS_DIR}")
    raise SystemExit(1)

xml_path = xml_files[0]
edition = xml_path.stem  # e.g. "phi0474.phi055.perseus-lat1"

print(f"Parsing: {xml_path.name}")
tree = etree.parse(str(xml_path))
root = tree.getroot()

sections = []
for elem in root.iter():
    tag = str(elem.tag).split("}")[-1]
    if tag != "div" or elem.get("subtype") != "section":
        continue

    # Walk up to the enclosing book div
    book_n = None
    parent = elem.getparent()
    while parent is not None:
        pt = str(parent.tag).split("}")[-1]
        if pt == "div" and parent.get("subtype") == "book":
            book_n = parent.get("n", "")
            break
        parent = parent.getparent()

    section_n = elem.get("n", "")
    text = " ".join(elem.itertext()).strip()
    text = " ".join(text.split())

    if text and book_n and section_n:
        cts_ref = f"{book_n}.{section_n}"
        sections.append({
            "book": book_n,
            "section": section_n,
            "cts_ref": cts_ref,
            "edition": edition,
            "text": text,
            "char_count": len(text),
        })


def cts_sort_key(s):
    parts = s["cts_ref"].split(".")
    return tuple(int(p) for p in parts if p.isdigit())


sections.sort(key=cts_sort_key)

print(f"Extracted {len(sections)} sections across {len(set(s['book'] for s in sections))} books")
for book in sorted(set(s["book"] for s in sections), key=int):
    book_secs = [s for s in sections if s["book"] == book]
    print(f"  Book {book}: {len(book_secs)} sections (max n={max(int(s['section']) for s in book_secs)})")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

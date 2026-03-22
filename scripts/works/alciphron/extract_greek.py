#!/usr/bin/env python3
"""
Extract Greek letters from First1KGreek Alciphron Epistulae.

4 books, 122 letters (sections). Each letter is a "section" within a book.

Input:  data-sources/greek_corpus/First1KGreek/data/tlg0640/tlg001/
Output: build/alciphron/greek_sections.json
"""

import json
from lxml import etree
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
F1K_DIR = PROJECT_ROOT / "data-sources" / "greek_corpus" / "First1KGreek" / "data" / "tlg0640" / "tlg001"
OUTPUT = PROJECT_ROOT / "build" / "alciphron" / "greek_sections.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_files = [f for f in sorted(F1K_DIR.glob("*.xml")) if f.name != "__cts__.xml"]
xml_path = xml_files[0]
edition = xml_path.stem

print(f"Parsing: {xml_path.name}")
tree = etree.parse(str(xml_path))
root = tree.getroot()

sections = []
for elem in root.iter():
    tag = str(elem.tag).split("}")[-1]
    if tag != "div": continue
    if elem.get("subtype") != "section": continue

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

    if text and book_n:
        sections.append({
            "book": book_n,
            "section": section_n,
            "cts_ref": f"{book_n}.{section_n}",
            "edition": edition,
            "text": text,
            "char_count": len(text),
        })

sections.sort(key=lambda s: (int(s["book"]), int(s["section"])))

print(f"Extracted {len(sections)} letters across {len(set(s['book'] for s in sections))} books")
for book in sorted(set(s["book"] for s in sections), key=int):
    n = sum(1 for s in sections if s["book"] == book)
    print(f"  Book {book}: {n} letters")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

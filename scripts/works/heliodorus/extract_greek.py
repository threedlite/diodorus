#!/usr/bin/env python3
"""
Extract Greek chapters from First1KGreek Heliodorus Aethiopica TEI XML.

Structure: 10 books, 273 chapters. No sub-sections — each chapter contains
one or more <p> elements. We concatenate all <p> text per chapter into one
section.

Input:  data-sources/greek_corpus/First1KGreek/data/tlg0658/tlg001/
Output: build/heliodorus/greek_sections.json
"""

from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
F1K_DIR = PROJECT_ROOT / "data-sources" / "greek_corpus" / "First1KGreek" / "data" / "tlg0658" / "tlg001"
OUTPUT = PROJECT_ROOT / "build" / "heliodorus" / "greek_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_files = sorted(F1K_DIR.glob("*.xml"))
xml_files = [f for f in xml_files if f.name != "__cts__.xml"]
xml_path = xml_files[0]
edition = xml_path.stem

print(f"Parsing: {xml_path.name}")
tree = etree.parse(str(xml_path))
root = tree.getroot()

sections = []
for elem in root.iter():
    tag = str(elem.tag).split("}")[-1]
    if tag != "div":
        continue
    if elem.get("subtype") != "chapter":
        continue

    book_n = None
    parent = elem.getparent()
    while parent is not None:
        pt = str(parent.tag).split("}")[-1]
        if pt == "div" and parent.get("subtype") == "book":
            book_n = parent.get("n", "")
            break
        parent = parent.getparent()

    chapter_n = elem.get("n", "")
    text = " ".join(elem.itertext()).strip()
    text = " ".join(text.split())

    if text and book_n:
        cts_ref = f"{book_n}.{chapter_n}"
        sections.append({
            "book": book_n,
            "section": chapter_n,
            "cts_ref": cts_ref,
            "edition": edition,
            "text": text,
            "char_count": len(text),
        })

def cts_sort_key(s):
    parts = s["cts_ref"].split(".")
    return tuple(int(p) for p in parts if p.isdigit())

sections.sort(key=cts_sort_key)

print(f"Extracted {len(sections)} chapters across {len(set(s['book'] for s in sections))} books")
for book in sorted(set(s["book"] for s in sections), key=int):
    n = sum(1 for s in sections if s["book"] == book)
    print(f"  Book {book}: {n} chapters")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

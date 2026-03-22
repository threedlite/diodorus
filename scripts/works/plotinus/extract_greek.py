#!/usr/bin/env python3
"""
Extract Greek sections from First1KGreek Plotinus TEI XML.

Enneads: 6 books (Enneads), 54 chapters (tractates), 653 sections.
Uses 1st1K-grc1 edition. Structure: book.chapter.section.

Input:  data-sources/greek_corpus/First1KGreek/data/tlg2000/tlg001/
Output: build/plotinus/greek_sections.json
"""

from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
F1K_DIR = PROJECT_ROOT / "data-sources" / "greek_corpus" / "First1KGreek" / "data" / "tlg2000" / "tlg001"
OUTPUT = PROJECT_ROOT / "build" / "plotinus" / "greek_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Find the Greek XML — prefer 1st1K-grc1
xml_files = sorted(f for f in F1K_DIR.iterdir()
                   if f.suffix == ".xml" and f.name != "__cts__.xml")
if not xml_files:
    print(f"Error: no XML files in {F1K_DIR}")
    raise SystemExit(1)

xml_path = xml_files[0]
for f in xml_files:
    if "1st1K-grc1" in f.name:
        xml_path = f
        break

edition = xml_path.stem
print(f"Parsing: {xml_path.name}")

tree = etree.parse(str(xml_path))
root = tree.getroot()

sections = []

for elem in root.iter():
    tag = str(elem.tag).split("}")[-1]
    if tag != "div":
        continue
    if elem.get("subtype") != "section":
        continue

    # Walk up to find chapter (tractate) and book (Ennead) numbers
    book_n = None
    chapter_n = None
    parent = elem.getparent()
    while parent is not None:
        pt = str(parent.tag).split("}")[-1]
        if pt == "div":
            ps = parent.get("subtype", "")
            if ps == "chapter" and chapter_n is None:
                chapter_n = parent.get("n", "")
            elif ps == "book" and book_n is None:
                book_n = parent.get("n", "")
        parent = parent.getparent()

    section_n = elem.get("n", "")
    text = " ".join(elem.itertext()).strip()
    text = " ".join(text.split())

    if text and book_n:
        if chapter_n:
            cts_ref = f"{book_n}.{chapter_n}.{section_n}"
        else:
            cts_ref = f"{book_n}.{section_n}"

        sections.append({
            "book": book_n,
            "chapter": chapter_n or "",
            "section": section_n,
            "cts_ref": cts_ref,
            "edition": edition,
            "text": text,
            "char_count": len(text),
        })


# Sort by CTS ref components
def cts_sort_key(s):
    parts = s["cts_ref"].split(".")
    return tuple(int(p) for p in parts if p.isdigit())


sections.sort(key=cts_sort_key)

print(f"Extracted {len(sections)} sections across {len(set(s['book'] for s in sections))} books")
for book in sorted(set(s["book"] for s in sections), key=int):
    book_secs = [s for s in sections if s["book"] == book]
    chapters = set(s["chapter"] for s in book_secs)
    print(f"  Book {book}: {len(book_secs)} sections across {len(chapters)} chapters")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

#!/usr/bin/env python3
"""
Extract Greek sections from Perseus Longus Daphnis and Chloe TEI XML.

Greek structure: 4 books, ~145 chapters, each with numbered sections.
Book 1 has a preface (chapter "praef") followed by chapters 1-32.
CTS ref format: book.chapter.section

Input:  data-sources/perseus/canonical-greekLit/data/tlg0561/tlg001/
Output: build/longus/greek_sections.json
"""

from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0561" / "tlg001"
OUTPUT = PROJECT_ROOT / "build" / "longus" / "greek_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_files = sorted(PERSEUS_DIR.glob("*.xml"))
xml_files = [f for f in xml_files if f.name != "__cts__.xml"]
if not xml_files:
    print(f"Error: no XML files in {PERSEUS_DIR}")
    raise SystemExit(1)

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
    if elem.get("subtype") != "section":
        continue

    # Walk up to find chapter and book
    chapter_n = None
    book_n = None
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

    if text and book_n and chapter_n:
        cts_ref = f"{book_n}.{chapter_n}.{section_n}"
        sections.append({
            "book": book_n,
            "chapter": chapter_n,
            "section": section_n,
            "cts_ref": cts_ref,
            "edition": edition,
            "text": text,
            "char_count": len(text),
        })

# Sort by CTS ref
def cts_sort_key(s):
    parts = s["cts_ref"].split(".")
    result = []
    for p in parts:
        if p == "praef":
            result.append(-1)  # preface comes first
        elif p.isdigit():
            result.append(int(p))
        else:
            result.append(0)
    return tuple(result)

sections.sort(key=cts_sort_key)

print(f"Extracted {len(sections)} sections across {len(set(s['book'] for s in sections))} books")
for book in sorted(set(s["book"] for s in sections), key=int):
    book_secs = [s for s in sections if s["book"] == book]
    chapters = sorted(set(s["chapter"] for s in book_secs),
                      key=lambda x: -1 if x == "praef" else int(x))
    print(f"  Book {book}: {len(book_secs)} sections across {len(chapters)} chapters")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

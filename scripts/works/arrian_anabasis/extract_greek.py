#!/usr/bin/env python3
"""
Extract Greek sections from Perseus Arrian Anabasis TEI XML.

Structure: 7 books, ~206 chapters (including "pr" preface), ~1406 sections.
CTS ref: book.chapter.section. Preface chapter uses "pr" for chapter number.

Input:  data-sources/perseus/canonical-greekLit/data/tlg0074/tlg001/
Output: build/arrian_anabasis/greek_sections.json
"""

from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0074" / "tlg001"
OUTPUT = PROJECT_ROOT / "build" / "arrian_anabasis" / "greek_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_files = sorted(PERSEUS_DIR.glob("*.xml"))
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
    if elem.get("subtype") != "section":
        continue

    chapter_n = book_n = None
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

def cts_sort_key(s):
    parts = s["cts_ref"].split(".")
    result = []
    for p in parts:
        if p == "pr":
            result.append(-1)
        elif p.isdigit():
            result.append(int(p))
        else:
            result.append(0)
    return tuple(result)

sections.sort(key=cts_sort_key)

print(f"Extracted {len(sections)} sections across {len(set(s['book'] for s in sections))} books")
for book in sorted(set(s["book"] for s in sections), key=int):
    n = sum(1 for s in sections if s["book"] == book)
    print(f"  Book {book}: {n} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

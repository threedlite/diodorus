#!/usr/bin/env python3
"""
Extract Greek sections from Perseus Procopius Secret History TEI XML.

Flat chapter.section structure (no book level): 30 chapters, 1019 sections.

Input:  data-sources/perseus/canonical-greekLit/data/tlg4029/tlg002/
Output: build/procopius_secret/greek_sections.json
"""

from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg4029" / "tlg002"
OUTPUT = PROJECT_ROOT / "build" / "procopius_secret" / "greek_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Find the Greek XML
xml_files = sorted(f for f in PERSEUS_DIR.iterdir()
                   if f.suffix == ".xml" and f.name != "__cts__.xml")
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

    subtype = elem.get("subtype", "")

    # Secret History has flat chapter > section (no book level)
    if subtype == "section":
        # Walk up to find chapter
        chapter_n = None
        parent = elem.getparent()
        while parent is not None:
            pt = str(parent.tag).split("}")[-1]
            if pt == "div" and parent.get("subtype") == "chapter":
                chapter_n = parent.get("n", "")
                break
            parent = parent.getparent()

        section_n = elem.get("n", "")
        text = " ".join(elem.itertext()).strip()
        text = " ".join(text.split())

        if text and chapter_n:
            cts_ref = f"{chapter_n}.{section_n}"
            sections.append({
                "book": chapter_n,
                "chapter": chapter_n,
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

print(f"Extracted {len(sections)} sections across {len(set(s['chapter'] for s in sections))} chapters")
for chapter in sorted(set(s["chapter"] for s in sections), key=int):
    ch_secs = [s for s in sections if s["chapter"] == chapter]
    print(f"  Chapter {chapter}: {len(ch_secs)} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

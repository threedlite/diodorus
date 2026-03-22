#!/usr/bin/env python3
"""
Extract Greek sections from Perseus Theophrastus Characters TEI XML.

Greek structure: 31 chapters (0 = Proem, 1-30 = character sketches),
each with numbered sections. CTS ref format: chapter.section.

Input:  data-sources/perseus/canonical-greekLit/data/tlg0093/tlg009/
Output: build/theophrastus/greek_sections.json
"""

from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0093" / "tlg009"
OUTPUT = PROJECT_ROOT / "build" / "theophrastus" / "greek_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Find the Greek XML
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

    # Walk up to find chapter number
    chapter_n = None
    parent = elem.getparent()
    while parent is not None:
        pt = str(parent.tag).split("}")[-1]
        if pt == "div":
            ps = parent.get("subtype", "")
            if ps == "chapter" and chapter_n is None:
                chapter_n = parent.get("n", "")
        parent = parent.getparent()

    section_n = elem.get("n", "")
    text = " ".join(elem.itertext()).strip()
    text = " ".join(text.split())

    if text and chapter_n is not None:
        cts_ref = f"{chapter_n}.{section_n}"

        sections.append({
            "book": chapter_n,
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

print(f"Extracted {len(sections)} sections across {len(set(s['book'] for s in sections))} chapters")
for ch in sorted(set(s["book"] for s in sections), key=int):
    ch_secs = [s for s in sections if s["book"] == ch]
    print(f"  Chapter {ch}: {len(ch_secs)} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

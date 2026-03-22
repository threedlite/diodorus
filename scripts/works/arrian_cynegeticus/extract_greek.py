#!/usr/bin/env python3
"""Extract Greek sections from Perseus Arrian Cynegeticus TEI XML."""
from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0074" / "tlg003"
OUTPUT = PROJECT_ROOT / "build" / "arrian_cynegeticus" / "greek_sections.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_files = [f for f in sorted(PERSEUS_DIR.glob("*.xml")) if f.name != "__cts__.xml"]
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

    if text:
        book = chapter_n or "1"
        # Convert "pr" preface to chapter 0 for compatibility
        if book == "pr":
            book = "0"
        sections.append({
            "book": book,
            "section": section_n,
            "cts_ref": f"{book}.{section_n}",
            "edition": edition,
            "text": text,
            "char_count": len(text),
        })

def sort_key(s):
    b = -1 if s["book"] == "pr" else int(s["book"])
    sec = -1 if s["section"] == "pr" else int(s["section"])
    return (b, sec)
sections.sort(key=sort_key)
print(f"Extracted {len(sections)} sections across {len(set(s['book'] for s in sections))} chapters")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

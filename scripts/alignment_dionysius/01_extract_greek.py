#!/usr/bin/env python3
"""
Extract Greek sections from Perseus Dionysius De Compositione Verborum.

Input:  data-sources/perseus/canonical-greekLit/data/tlg0081/tlg012/
Output: output/dionysius/greek_sections.json
"""

from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0081" / "tlg012"
OUTPUT = PROJECT_ROOT / "build" / "dionysius" / "greek_sections.json"

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
    if tag == "div" and elem.get("subtype") == "section":
        n = elem.get("n", "")
        text = " ".join(elem.itertext()).strip()
        text = " ".join(text.split())
        if text:
            sections.append({
                "book": "1",
                "section": n,
                "cts_ref": n,
                "edition": edition,
                "text": text,
                "char_count": len(text),
            })

sections.sort(key=lambda s: int(s["section"]))
print(f"Extracted {len(sections)} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

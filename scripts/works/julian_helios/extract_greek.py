#!/usr/bin/env python3
"""Extract Greek sections from Perseus Julian TEI XML."""
from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg2003" / "tlg011"
OUTPUT = PROJECT_ROOT / "build" / "julian_helios" / "greek_sections.json"
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
    n = elem.get("n", "")
    text = " ".join(elem.itertext()).strip()
    text = " ".join(text.split())
    if text and n:
        sections.append({
            "book": "1",
            "section": n,
            "cts_ref": f"1.{n}",
            "edition": edition,
            "text": text,
            "char_count": len(text),
        })

sections.sort(key=lambda s: int(s["section"]))
print(f"Extracted {len(sections)} sections")
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

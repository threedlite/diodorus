#!/usr/bin/env python3
"""
Extract Greek fables from First1KGreek Aesop TEI XML.

Input:  data-sources/greek_corpus/First1KGreek/data/tlg0096/tlg002/
Output: output/aesop/greek_sections.json
"""

from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
F1K_DIR = PROJECT_ROOT / "data-sources" / "greek_corpus" / "First1KGreek" / "data" / "tlg0096" / "tlg002"
OUTPUT = PROJECT_ROOT / "build" / "aesop" / "greek_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Find the primary Greek XML
xml_files = sorted(F1K_DIR.glob("*.xml"))
xml_files = [f for f in xml_files if f.name != "__cts__.xml"]
if not xml_files:
    print(f"Error: no XML files found in {F1K_DIR}")
    raise SystemExit(1)

# Prefer 1st1K edition
xml_path = xml_files[0]
for f in xml_files:
    if "1st1K" in f.name:
        xml_path = f
        break

print(f"Parsing: {xml_path.name}")
tree = etree.parse(str(xml_path))
root = tree.getroot()

edition = xml_path.stem  # e.g. "tlg0096.tlg002.1st1K-grc1"

fables = []
for elem in root.iter():
    tag = str(elem.tag).split("}")[-1]
    if tag == "div" and elem.get("subtype") == "fabula":
        n = elem.get("n", "")
        # Extract head (title) if present
        head = ""
        for child in elem:
            child_tag = str(child.tag).split("}")[-1]
            if child_tag == "head":
                head = " ".join(child.itertext()).strip()
                break
        # Extract all text
        text = " ".join(elem.itertext()).strip()
        # Clean up whitespace
        text = " ".join(text.split())

        fables.append({
            "book": "fables",
            "section": n,
            "cts_ref": n,
            "fabula_n": n,
            "head": head,
            "text": text,
            "char_count": len(text),
            "edition": edition,
        })

print(f"Extracted {len(fables)} fables")
print(f"  Char sizes: min={min(f['char_count'] for f in fables)}, "
      f"max={max(f['char_count'] for f in fables)}, "
      f"mean={sum(f['char_count'] for f in fables) // len(fables)}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": fables}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

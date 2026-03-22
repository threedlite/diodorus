#!/usr/bin/env python3
"""
Extract Greek sections from First1KGreek Iamblichus TEI XML.

Handles both De Vita Pythagorica (tlg001) and De Mysteriis (tlg006).

Input:  data-sources/greek_corpus/First1KGreek/data/tlg2023/
Output: output/iamblichus/greek_sections.json
"""

from lxml import etree
from pathlib import Path
import json
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
F1K_DIR = PROJECT_ROOT / "data-sources" / "greek_corpus" / "First1KGreek" / "data" / "tlg2023"
OUTPUT = PROJECT_ROOT / "build" / "iamblichus" / "greek_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

WORKS = {
    "tlg001": "De Vita Pythagorica",
    "tlg006": "De Mysteriis",
}

all_sections = []

for work_id, work_title in WORKS.items():
    work_dir = F1K_DIR / work_id
    if not work_dir.exists():
        print(f"Warning: {work_dir} not found, skipping")
        continue

    xmls = sorted(f for f in work_dir.iterdir()
                  if f.suffix == ".xml" and f.name != "__cts__.xml")
    if not xmls:
        print(f"Warning: no XML in {work_dir}")
        continue

    # Prefer 1st1K edition
    xml_path = xmls[0]
    for f in xmls:
        if "1st1K" in f.name:
            xml_path = f
            break

    edition = xml_path.stem
    print(f"=== {work_title} ({work_id}) ===")
    print(f"  Parsing: {xml_path.name}")

    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    work_sections = []
    for elem in root.iter():
        tag = str(elem.tag).split("}")[-1]
        if tag != "div" or elem.get("subtype") != "section":
            continue

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

        if text:
            cts_ref = f"{chapter_n}.{section_n}" if chapter_n else section_n
            work_sections.append({
                "work": work_title,
                "work_id": work_id,
                "book": chapter_n or "1",
                "section": section_n,
                "cts_ref": cts_ref,
                "edition": edition,
                "text": text,
                "char_count": len(text),
            })

    # If no sections found, try chapter-level (De Mysteriis may use chapter as leaf)
    if not work_sections:
        for elem in root.iter():
            tag = str(elem.tag).split("}")[-1]
            if tag != "div" or elem.get("subtype") != "chapter":
                continue
            # Check if this is a leaf (no child divs)
            has_child_div = any(str(c.tag).split("}")[-1] == "div" for c in elem)
            if has_child_div:
                continue

            chapter_n = elem.get("n", "")
            text = " ".join(elem.itertext()).strip()
            text = " ".join(text.split())

            if text:
                work_sections.append({
                    "work": work_title,
                    "work_id": work_id,
                    "book": "1",
                    "section": chapter_n,
                    "cts_ref": chapter_n,
                    "edition": edition,
                    "text": text,
                    "char_count": len(text),
                })

    print(f"  Extracted {len(work_sections)} sections")
    all_sections.extend(work_sections)

print(f"\nTotal: {len(all_sections)} sections across {len(WORKS)} works")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

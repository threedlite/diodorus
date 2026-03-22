#!/usr/bin/env python3
"""
Extract Greek verse from Perseus Theocritus Epigrams TEI XML.

Each epigram is very short (5-15 lines), so we extract each as a single
section rather than grouping lines. Each epigram becomes a "book" for
alignment purposes.

Input:  data-sources/perseus/canonical-greekLit/data/tlg0005/tlg002/
Output: build/theocritus_epigrams/greek_sections.json
"""

import json
from lxml import etree
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0005" / "tlg002"
OUTPUT = PROJECT_ROOT / "build" / "theocritus_epigrams" / "greek_sections.json"

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

TEI_NS = "http://www.tei-c.org/ns/1.0"

sections = []
for poem_div in root.iter():
    tag = str(poem_div.tag).split("}")[-1]
    if tag != "div":
        continue
    if poem_div.get("subtype") != "poem":
        continue

    poem_n = poem_div.get("n", "")
    if not poem_n.isdigit():
        continue

    lines = []
    for l_elem in poem_div.iter(f"{{{TEI_NS}}}l"):
        text = " ".join(l_elem.itertext()).strip()
        text = " ".join(text.split())
        if text:
            lines.append(text)

    if lines:
        full_text = " ".join(lines)
        sections.append({
            "book": poem_n,
            "section": "1",
            "cts_ref": f"{poem_n}.1",
            "edition": edition,
            "text": full_text,
            "char_count": len(full_text),
            "line_count": len(lines),
        })
        print(f"  Epigram {poem_n}: {len(lines)} lines, {len(full_text)} chars")

sections.sort(key=lambda s: int(s["book"]))

print(f"\nExtracted {len(sections)} epigrams")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

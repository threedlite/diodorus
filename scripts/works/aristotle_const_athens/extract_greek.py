#!/usr/bin/env python3
"""
Extract Greek sections from Perseus Aristotle Constitution of Athens TEI XML.

Greek structure: 69 sections (matching Kenyon's Parts 1-69), each with
numbered subsections. CTS ref format: section.subsection.
Section 1 has no subsections (single paragraph).

Input:  data-sources/perseus/canonical-greekLit/data/tlg0086/tlg003/
Output: build/aristotle_const_athens/greek_sections.json
"""

from lxml import etree
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0086" / "tlg003"
OUTPUT = PROJECT_ROOT / "build" / "aristotle_const_athens" / "greek_sections.json"

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

    subtype = elem.get("subtype", "")

    if subtype == "subsection":
        # Has parent section
        subsection_n = elem.get("n", "")
        section_n = None
        parent = elem.getparent()
        while parent is not None:
            pt = str(parent.tag).split("}")[-1]
            if pt == "div" and parent.get("subtype") == "section":
                section_n = parent.get("n", "")
                break
            parent = parent.getparent()

        text = " ".join(elem.itertext()).strip()
        text = " ".join(text.split())

        if text and section_n:
            cts_ref = f"{section_n}.{subsection_n}"
            sections.append({
                "book": section_n,
                "section": subsection_n,
                "cts_ref": cts_ref,
                "edition": edition,
                "text": text,
                "char_count": len(text),
            })

    elif subtype == "section":
        # Check if this section has subsection children
        has_subsections = False
        for child in elem:
            ct = str(child.tag).split("}")[-1]
            if ct == "div" and child.get("subtype") == "subsection":
                has_subsections = True
                break

        if not has_subsections:
            # Section with no subsections (e.g. section 1)
            section_n = elem.get("n", "")
            text = " ".join(elem.itertext()).strip()
            text = " ".join(text.split())

            if text:
                cts_ref = f"{section_n}.1"
                sections.append({
                    "book": section_n,
                    "section": "1",
                    "cts_ref": cts_ref,
                    "edition": edition,
                    "text": text,
                    "char_count": len(text),
                })

# Filter out fragments (frag_1, frag_2 etc.) — no English translation exists
sections = [s for s in sections if not s["book"].startswith("frag")]

# Sort by CTS ref
def cts_sort_key(s):
    parts = s["cts_ref"].split(".")
    return tuple(int(p) for p in parts if p.isdigit())

sections.sort(key=cts_sort_key)

# Count sections per part
parts = sorted(set(s["book"] for s in sections), key=int)
print(f"Extracted {len(sections)} subsections across {len(parts)} parts")
for part in parts[:5]:
    n = sum(1 for s in sections if s["book"] == part)
    print(f"  Part {part}: {n} subsections")
print(f"  ...")
for part in parts[-3:]:
    n = sum(1 for s in sections if s["book"] == part)
    print(f"  Part {part}: {n} subsections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

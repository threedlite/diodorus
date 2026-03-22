#!/usr/bin/env python3
"""
Extract English prose translations of Theocritus Idylls from eng_trans-dev TEI XML.

The 1878 volume contains prose translations of 30 idylls, followed by
Bion, Moschus, and then metrical translations (which we ignore).

Each idyll is marked by <title type="sub">IDYLL I.</title> etc.
We extract one section per idyll as a "book" for alignment.

Input:  data-sources/english_trans-dev/volumes/theocritus_1878/
Output: build/theocritus_idylls/english_sections.json
"""

import json
import re
import sys
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data-sources" / "english_trans-dev" / "volumes" / "theocritus_1878"
OUTPUT = PROJECT_ROOT / "build" / "theocritus_idylls" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_files = sorted(INPUT_DIR.glob("*.xml"))
if not xml_files:
    print(f"Error: no XML files in {INPUT_DIR}")
    raise SystemExit(1)

xml_path = xml_files[0]
print(f"Parsing: {xml_path.name}")

tree = etree.parse(str(xml_path))
root = tree.getroot()
TEI_NS = "http://www.tei-c.org/ns/1.0"

ROMAN = {}
for i, r in enumerate(["I","II","III","IV","V","VI","VII","VIII","IX","X",
                        "XI","XII","XIII","XIV","XV","XVI","XVII","XVIII","XIX","XX",
                        "XXI","XXII","XXIII","XXIV","XXV","XXVI","XXVII","XXVIII",
                        "XXIX","XXX"], 1):
    ROMAN[r] = i


def extract_p_text(p_elem):
    """Extract text from a <p>, skipping footnotes, figures, foreign text."""
    parts = []
    if p_elem.text:
        parts.append(p_elem.text)
    for child in p_elem:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag == "note":
            pass  # skip footnotes
        elif tag == "figure":
            pass
        elif tag == "lb":
            parts.append(" ")
        elif tag == "pb":
            pass
        elif tag == "foreign":
            pass  # skip Greek quotations in footnotes
        else:
            parts.append("".join(child.itertext()))
        if child.tail:
            parts.append(child.tail)
    text = "".join(parts)
    text = text.replace("­", "")  # soft hyphens
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# Find the Theocritus prose section
# It's the first <div type="textpart" subtype="chapter"> that contains "THEOCRITUS"
body = root.find(f".//{{{TEI_NS}}}body")
edition_div = body.find(f"{{{TEI_NS}}}div")

# Collect all elements in order, splitting by IDYLL markers
all_sections = []
current_idyll = None
current_paragraphs = []
in_theocritus = False
in_epigrams = False

for div in edition_div:
    tag = etree.QName(div.tag).localname if isinstance(div.tag, str) else ""
    if tag != "div":
        continue

    # Check titles in this div
    titles = div.findall(f".//{{{TEI_NS}}}title")
    title_texts = [(t.text or "").strip().upper() for t in titles]

    # Start of Theocritus section
    if any("THEOCRITUS" in t and "IDYLL" not in t for t in title_texts):
        in_theocritus = True

    # Stop at epigrams or Bion/Moschus
    if any("EPIGRAM" in t for t in title_texts):
        in_epigrams = True
    if any("BION" in t for t in title_texts):
        in_theocritus = False
        in_epigrams = False
    if any("MOSCHUS" in t for t in title_texts):
        in_theocritus = False

    if not in_theocritus or in_epigrams:
        continue

    # Process elements within this div
    for elem in div.iter():
        elem_tag = etree.QName(elem.tag).localname if isinstance(elem.tag, str) else ""

        if elem_tag == "title" and elem.get("type") == "sub":
            title_text = (elem.text or "").strip()
            # Check for IDYLL marker
            m = re.match(r'IDYLL\s+([IVXL]+)', title_text)
            if m:
                # Save previous idyll
                if current_idyll is not None and current_paragraphs:
                    all_sections.append({
                        "book": str(current_idyll),
                        "section": "1",
                        "cts_ref": f"{current_idyll}.1",
                        "text": " ".join(current_paragraphs),
                        "char_count": sum(len(p) for p in current_paragraphs),
                    })

                roman = m.group(1)
                current_idyll = ROMAN.get(roman)
                current_paragraphs = []
                continue

        if elem_tag == "p" and current_idyll is not None:
            # Only process direct children, not nested
            if elem.getparent() == div:
                text = extract_p_text(elem)
                if len(text) >= 10:
                    current_paragraphs.append(text)

# Save last idyll
if current_idyll is not None and current_paragraphs:
    all_sections.append({
        "book": str(current_idyll),
        "section": "1",
        "cts_ref": f"{current_idyll}.1",
        "text": " ".join(current_paragraphs),
        "char_count": sum(len(p) for p in current_paragraphs),
    })

all_sections.sort(key=lambda s: int(s["book"]))

print(f"\nExtracted {len(all_sections)} English idylls")
for s in all_sections:
    print(f"  Idyll {s['book']}: {s['char_count']} chars")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

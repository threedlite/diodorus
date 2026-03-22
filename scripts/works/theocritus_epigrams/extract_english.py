#!/usr/bin/env python3
"""
Extract English prose translations of Theocritus Epigrams from eng_trans-dev TEI XML.

The epigrams section is a single <div> containing 24 numbered epigrams.
Each epigram has both a prose and metrical translation — we take only
the first paragraph (prose) for each number.

Input:  data-sources/english_trans-dev/volumes/theocritus_1878/
Output: build/theocritus_epigrams/english_sections.json
"""

import json
import re
import sys
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data-sources" / "english_trans-dev" / "volumes" / "theocritus_1878"
OUTPUT = PROJECT_ROOT / "build" / "theocritus_epigrams" / "english_sections.json"

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
                        "XXI","XXII","XXIII","XXIV","XXV"], 1):
    ROMAN[r] = i


def extract_p_text(p_elem):
    """Extract text from a <p>, skipping footnotes, figures, foreign text."""
    parts = []
    if p_elem.text:
        parts.append(p_elem.text)
    for child in p_elem:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag == "note":
            pass
        elif tag == "figure":
            pass
        elif tag == "lb":
            parts.append(" ")
        elif tag == "pb":
            pass
        elif tag == "foreign":
            pass
        else:
            parts.append("".join(child.itertext()))
        if child.tail:
            parts.append(child.tail)
    text = "".join(parts)
    text = text.replace("­", "")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# Find the epigrams div by searching for the title
body = root.find(f".//{{{TEI_NS}}}body")
edition_div = body.find(f"{{{TEI_NS}}}div")

epigrams_div = None
for div in edition_div:
    tag = etree.QName(div.tag).localname if isinstance(div.tag, str) else ""
    if tag != "div":
        continue
    titles = div.findall(f".//{{{TEI_NS}}}title")
    for t in titles:
        if "EPIGRAM" in (t.text or "").upper() and "THEOCRITUS" in (t.text or "").upper():
            epigrams_div = div
            break
    if epigrams_div is not None:
        break

if epigrams_div is None:
    print("Error: epigrams section not found")
    raise SystemExit(1)

# Walk through the epigrams div, collecting paragraphs per number
# Only take the FIRST paragraph for each epigram number (prose, not metrical)
all_sections = []
current_epigram = None
seen_epigrams = set()

for elem in epigrams_div:
    elem_tag = etree.QName(elem.tag).localname if isinstance(elem.tag, str) else ""

    if elem_tag == "ab":
        # Check for epigram number marker
        for sub in elem:
            sub_tag = etree.QName(sub.tag).localname if isinstance(sub.tag, str) else ""
            if sub_tag == "title" and sub.get("type") == "sub":
                title_text = (sub.text or "").strip().rstrip(".")
                if title_text in ROMAN:
                    num = ROMAN[title_text]
                    if num not in seen_epigrams:
                        current_epigram = num
                    else:
                        current_epigram = None  # skip duplicate (metrical)

    elif elem_tag == "p" and current_epigram is not None:
        text = extract_p_text(elem)
        if len(text) >= 5:
            all_sections.append({
                "book": str(current_epigram),
                "section": "1",
                "cts_ref": f"{current_epigram}.1",
                "text": text,
                "char_count": len(text),
            })
            seen_epigrams.add(current_epigram)
            current_epigram = None  # one paragraph per epigram

all_sections.sort(key=lambda s: int(s["book"]))

print(f"\nExtracted {len(all_sections)} English epigrams")
for s in all_sections:
    print(f"  Epigram {s['book']}: {s['char_count']} chars")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

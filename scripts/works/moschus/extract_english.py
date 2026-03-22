#!/usr/bin/env python3
"""
Extract English prose translations of Moschus from eng_trans-dev theocritus_1878.

Moschus section starts at "THE IDYLLS OF MOSCHUS THE SYRACUSAN" and ends
at the metrical translations or end of file. 7 idylls numbered I-VII.
Each idyll becomes a book.

Input:  data-sources/english_trans-dev/volumes/theocritus_1878/
Output: build/moschus/english_sections.json
"""

import json
import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data-sources" / "english_trans-dev" / "volumes" / "theocritus_1878"
OUTPUT = PROJECT_ROOT / "build" / "moschus" / "english_sections.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_path = sorted(INPUT_DIR.glob("*.xml"))[0]
tree = etree.parse(str(xml_path))
root = tree.getroot()
TEI_NS = "http://www.tei-c.org/ns/1.0"

ROMAN = {r: i for i, r in enumerate(["I","II","III","IV","V","VI","VII"], 1)}


def extract_p_text(p_elem):
    parts = []
    if p_elem.text: parts.append(p_elem.text)
    for child in p_elem:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag in ("note", "figure", "pb", "foreign"): pass
        elif tag == "lb": parts.append(" ")
        else: parts.append("".join(child.itertext()))
        if child.tail: parts.append(child.tail)
    text = "".join(parts).replace("­", "")
    return re.sub(r'\s+', ' ', text).strip()


body = root.find(f".//{{{TEI_NS}}}body")
edition_div = body.find(f"{{{TEI_NS}}}div")

all_sections = []
current_idyll = None
current_paragraphs = []
in_moschus = False

for div in edition_div:
    tag = etree.QName(div.tag).localname if isinstance(div.tag, str) else ""
    if tag != "div": continue

    titles = div.findall(f".//{{{TEI_NS}}}title")
    title_texts = [(t.text or "").strip().upper() for t in titles]

    if any("MOSCHUS" in t and "SYRACUSAN" in t for t in title_texts):
        in_moschus = True
    # Stop at metrical section or Epitaph of Bion (by Moschus, last idyll)
    if in_moschus and any("BION" in t and "SMYRN" in t for t in title_texts):
        in_moschus = False  # metrical section

    if not in_moschus: continue

    for elem in div.iter():
        elem_tag = etree.QName(elem.tag).localname if isinstance(elem.tag, str) else ""
        if elem_tag == "title" and elem.get("type") == "sub":
            title_text = (elem.text or "").strip()
            m = re.match(r'IDYLL\s+([IVXL]+)', title_text)
            if m and m.group(1) in ROMAN:
                if current_idyll and current_paragraphs:
                    all_sections.append({
                        "book": str(current_idyll),
                        "section": "1",
                        "cts_ref": f"{current_idyll}.1",
                        "text": " ".join(current_paragraphs),
                        "char_count": sum(len(p) for p in current_paragraphs),
                    })
                current_idyll = ROMAN[m.group(1)]
                current_paragraphs = []
        elif elem_tag == "p" and current_idyll and elem.getparent() == div:
            text = extract_p_text(elem)
            if len(text) >= 10:
                current_paragraphs.append(text)

if current_idyll and current_paragraphs:
    all_sections.append({
        "book": str(current_idyll),
        "section": "1",
        "cts_ref": f"{current_idyll}.1",
        "text": " ".join(current_paragraphs),
        "char_count": sum(len(p) for p in current_paragraphs),
    })

all_sections.sort(key=lambda s: int(s["book"]))
print(f"Extracted {len(all_sections)} Moschus English idylls")
for s in all_sections:
    print(f"  Idyll {s['book']}: {s['char_count']} chars")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

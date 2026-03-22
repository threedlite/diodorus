#!/usr/bin/env python3
"""
Extract English translation from eng_trans-dev Alciphron Epistulae.

The English CTS-split file has 7 chapters that reorganize the 122 letters
thematically. We extract paragraphs with chapter as book number.

Input:  data-sources/english_trans-dev/data/tlg0640/tlg001/
Output: build/alciphron/english_sections.json
"""

import json
import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data-sources" / "english_trans-dev" / "data" / "tlg0640" / "tlg001"
OUTPUT = PROJECT_ROOT / "build" / "alciphron" / "english_sections.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

xml_files = [f for f in sorted(INPUT_DIR.glob("*.xml")) if f.name != "_cts_.xml"]
xml_path = xml_files[0]
print(f"Parsing: {xml_path.name}")

tree = etree.parse(str(xml_path))
root = tree.getroot()
TEI_NS = "http://www.tei-c.org/ns/1.0"


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

all_sections = []
chapter_num = 0

for div in body.iter(f"{{{TEI_NS}}}div"):
    if div.get("subtype") != "chapter" or div.get("type") != "textpart":
        continue

    chapter_num += 1
    book = str(chapter_num)

    paragraphs = list(div.findall(f"{{{TEI_NS}}}p"))
    pi = 0
    for p in paragraphs:
        text = extract_p_text(p)
        if len(text) >= 15:
            pi += 1
            all_sections.append({
                "book": book,
                "section": str(pi),
                "cts_ref": f"{book}.{pi}",
                "text": text,
                "char_count": len(text),
            })

print(f"Extracted {len(all_sections)} English sections across {chapter_num} chapters")
for book in sorted(set(s["book"] for s in all_sections), key=int):
    n = sum(1 for s in all_sections if s["book"] == book)
    print(f"  Chapter {book}: {n} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

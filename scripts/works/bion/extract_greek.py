#!/usr/bin/env python3
"""
Extract Greek verse from Perseus Bion — 3 works across separate XML files.
Same approach as Moschus.

Input:  data-sources/perseus/canonical-greekLit/data/tlg0036/tlg00[1-3]/
Output: build/bion/greek_sections.json
"""

import json
import re
from lxml import etree
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_BASE = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0036"
OUTPUT = PROJECT_ROOT / "build" / "bion" / "greek_sections.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

TEI_NS = "http://www.tei-c.org/ns/1.0"
MIN_LINES = 8
MAX_LINES = 15

WORK_IDS = ["tlg001", "tlg002", "tlg003"]


def is_sentence_end(text):
    return bool(re.search(r'[.?!;·]\s*$', text.rstrip()))


def segment_lines(lines):
    passages = []
    current = []
    for line in lines:
        current.append(line)
        if len(current) >= MIN_LINES and is_sentence_end(line["text"]):
            passages.append(current); current = []
        elif len(current) >= MAX_LINES:
            passages.append(current); current = []
    if current:
        if passages and len(current) < MIN_LINES // 2:
            passages[-1].extend(current)
        else:
            passages.append(current)
    return passages


sections = []
for wid in WORK_IDS:
    work_dir = PERSEUS_BASE / wid
    xml_files = [f for f in sorted(work_dir.glob("*.xml")) if f.name != "__cts__.xml"]
    if not xml_files:
        continue
    xml_path = xml_files[0]
    edition = xml_path.stem
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    lines = []
    for l_elem in root.iter(f"{{{TEI_NS}}}l"):
        line_n = l_elem.get("n", "")
        if not line_n or not line_n.isdigit():
            continue
        text = " ".join(l_elem.itertext()).strip()
        text = " ".join(text.split())
        if text:
            lines.append({"line": line_n, "text": text})

    if not lines:
        continue

    passages = segment_lines(lines)
    book_num = str(WORK_IDS.index(wid) + 1)

    for passage in passages:
        first_line = passage[0]["line"]
        text = " ".join(l["text"] for l in passage)
        sections.append({
            "book": book_num,
            "section": first_line,
            "cts_ref": f"{book_num}.{first_line}",
            "edition": edition,
            "work_id": wid,
            "text": text,
            "char_count": len(text),
        })

    print(f"  {wid}: {len(lines)} lines → {len(passages)} passages (book {book_num})")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)
print(f"Extracted {len(sections)} passages across {len(WORK_IDS)} works")
print(f"Saved: {OUTPUT}")

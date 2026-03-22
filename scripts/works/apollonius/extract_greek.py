#!/usr/bin/env python3
"""
Extract Greek verse from Perseus Apollonius Argonautica TEI XML.

4 books, 5834 lines total. Lines grouped into ~10-line passages.

Input:  data-sources/perseus/canonical-greekLit/data/tlg0001/tlg001/
Output: build/apollonius/greek_sections.json
"""

import json
import re
from lxml import etree
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0001" / "tlg001"
OUTPUT = PROJECT_ROOT / "build" / "apollonius" / "greek_sections.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

TEI_NS = "http://www.tei-c.org/ns/1.0"
MIN_LINES = 8
MAX_LINES = 15

xml_files = [f for f in sorted(PERSEUS_DIR.glob("*.xml")) if f.name != "__cts__.xml"]
xml_path = xml_files[0]
edition = xml_path.stem

print(f"Parsing: {xml_path.name}")
tree = etree.parse(str(xml_path))
root = tree.getroot()


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


# Find book divs
sections = []
for book_div in root.iter():
    tag = str(book_div.tag).split("}")[-1]
    if tag != "div": continue
    if book_div.get("subtype") != "book": continue

    book_n = book_div.get("n", "")
    if not book_n.isdigit(): continue

    lines = []
    for l_elem in book_div.iter(f"{{{TEI_NS}}}l"):
        line_n = l_elem.get("n", "")
        if not line_n or not line_n.isdigit(): continue
        text = " ".join(l_elem.itertext()).strip()
        text = " ".join(text.split())
        if text:
            lines.append({"line": line_n, "text": text})

    if not lines: continue

    passages = segment_lines(lines)
    for passage in passages:
        first_line = passage[0]["line"]
        text = " ".join(l["text"] for l in passage)
        sections.append({
            "book": book_n,
            "section": first_line,
            "cts_ref": f"{book_n}.{first_line}",
            "edition": edition,
            "text": text,
            "char_count": len(text),
        })

    print(f"  Book {book_n}: {len(lines)} lines → {len(passages)} passages")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)
print(f"Extracted {len(sections)} passages across {len(set(s['book'] for s in sections))} books")
print(f"Saved: {OUTPUT}")

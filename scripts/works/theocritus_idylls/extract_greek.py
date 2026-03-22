#!/usr/bin/env python3
"""
Extract Greek verse lines from Perseus Theocritus Idylls TEI XML and group
into ~10-line passages for embedding alignment.

Greek structure: 30 poems (idylls), each with numbered verse lines.
Individual lines (~40 chars) are too short for embedding similarity,
so we group them into passages of 8-15 lines, breaking at sentence
boundaries (same approach as Statius).

Each idyll becomes a "book" for alignment purposes.

Input:  data-sources/perseus/canonical-greekLit/data/tlg0005/tlg001/
Output: build/theocritus_idylls/greek_sections.json
"""

import json
import re
from lxml import etree
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0005" / "tlg001"
OUTPUT = PROJECT_ROOT / "build" / "theocritus_idylls" / "greek_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

MIN_LINES = 8
MAX_LINES = 15

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


def is_sentence_end(text):
    """Check if a line ends at a sentence boundary."""
    stripped = text.rstrip()
    return bool(re.search(r'[.?!;·]\s*$', stripped))


def segment_lines(lines):
    """Group verse lines into passages of 8-15 lines."""
    passages = []
    current = []

    for line in lines:
        current.append(line)

        should_break = False
        if len(current) >= MIN_LINES and is_sentence_end(line["text"]):
            should_break = True
        if len(current) >= MAX_LINES:
            should_break = True

        if should_break:
            passages.append(current)
            current = []

    if current:
        # Merge short remainder with previous passage if possible
        if passages and len(current) < MIN_LINES // 2:
            passages[-1].extend(current)
        else:
            passages.append(current)

    return passages


# Extract lines per poem
poems = {}
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
        line_n = l_elem.get("n", "")
        text = " ".join(l_elem.itertext()).strip()
        text = " ".join(text.split())
        if text:
            lines.append({"line": line_n, "text": text})

    if lines:
        poems[int(poem_n)] = lines

print(f"Found {len(poems)} idylls with {sum(len(v) for v in poems.values())} total lines")

# Segment each poem into passages
sections = []
for poem_num in sorted(poems.keys()):
    lines = poems[poem_num]
    passages = segment_lines(lines)

    for pi, passage_lines in enumerate(passages):
        first_line = passage_lines[0]["line"]
        last_line = passage_lines[-1]["line"]
        text = " ".join(l["text"] for l in passage_lines)

        sections.append({
            "book": str(poem_num),
            "section": first_line,
            "cts_ref": f"{poem_num}.{first_line}",
            "edition": edition,
            "text": text,
            "char_count": len(text),
            "line_count": len(passage_lines),
            "first_line": first_line,
            "last_line": last_line,
        })

    print(f"  Idyll {poem_num}: {len(lines)} lines → {len(passages)} passages")

print(f"\nExtracted {len(sections)} passages across {len(poems)} idylls")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

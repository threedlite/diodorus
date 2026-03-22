#!/usr/bin/env python3
"""
Shared extractor for Hickie Aristophanes plays from unsplit volumes.

Each play is a single <div type="textpart" subtype="chapter"> containing
the title and all <p> elements. We find the div matching the play title
and extract its paragraphs.
"""

import json
import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEI_NS = "http://www.tei-c.org/ns/1.0"


def extract_p_text(p_elem):
    parts = []
    if p_elem.text:
        parts.append(p_elem.text)
    for child in p_elem:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag in ("note", "figure", "pb", "foreign"):
            pass
        elif tag == "lb":
            parts.append(" ")
        else:
            parts.append("".join(child.itertext()))
        if child.tail:
            parts.append(child.tail)
    text = "".join(parts)
    text = text.replace("\xad", "")
    return re.sub(r'\s+', ' ', text).strip()


def extract_play(volume_path, play_title, output_path):
    """Extract a single play from a Hickie volume."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tree = etree.parse(str(volume_path))
    root = tree.getroot()
    body = root.find(f".//{{{TEI_NS}}}body")
    edition_div = body.find(f"{{{TEI_NS}}}div")
    if edition_div is None:
        edition_div = body

    # Find the play div by matching title
    play_div = None
    for div in edition_div:
        tag = etree.QName(div.tag).localname if isinstance(div.tag, str) else ""
        if tag != "div":
            continue
        titles = [(t.text or "").strip().upper() for t in div.findall(f".//{{{TEI_NS}}}title")]
        if any(play_title.upper() in t for t in titles):
            play_div = div
            break

    if play_div is None:
        print(f"Error: play '{play_title}' not found in {volume_path.name}")
        # Show available titles for debugging
        for div in edition_div:
            tag = etree.QName(div.tag).localname if isinstance(div.tag, str) else ""
            if tag == "div":
                titles = [(t.text or "").strip() for t in div.findall(f".//{{{TEI_NS}}}title")]
                print(f"  Available: {titles[:2]}")
        with open(output_path, "w") as f:
            json.dump({"sections": []}, f)
        return

    # Extract paragraphs from this div
    all_sections = []
    pi = 0
    for p in play_div.findall(f"{{{TEI_NS}}}p"):
        text = extract_p_text(p)
        if len(text) >= 20:
            pi += 1
            all_sections.append({
                "book": "1",
                "section": str(pi),
                "cts_ref": f"1.{pi}",
                "text": text,
                "char_count": len(text),
            })

    print(f"Extracted {len(all_sections)} English paragraphs for {play_title}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)
    print(f"Saved: {output_path}")

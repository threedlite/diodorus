#!/usr/bin/env python3
"""
Shared extraction functions for Aristophanes plays.

Greek: Perseus TEI XML with dramatic divisions (Prologue, Parodos, etc.)
       and line-level verse (<l n="...">). Lines grouped into ~10-line passages.

English: eng_trans-dev CTS-split TEI XML (Rogers translations) with prose
         paragraphs. Commentary preface and appendix stripped.
"""

import json
import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

TEI_NS = "http://www.tei-c.org/ns/1.0"
MIN_LINES = 8
MAX_LINES = 15


def is_sentence_end(text):
    return bool(re.search(r'[.?!;·]\s*$', text.rstrip()))


def segment_lines(lines):
    """Group verse lines into passages of 8-15 lines."""
    passages = []
    current = []
    for line in lines:
        current.append(line)
        if len(current) >= MIN_LINES and is_sentence_end(line["text"]):
            passages.append(current)
            current = []
        elif len(current) >= MAX_LINES:
            passages.append(current)
            current = []
    if current:
        if passages and len(current) < MIN_LINES // 2:
            passages[-1].extend(current)
        else:
            passages.append(current)
    return passages


def extract_greek(work_id, output_path):
    """Extract Greek verse lines from Perseus Aristophanes TEI XML."""
    perseus_dir = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0019" / work_id
    xml_files = [f for f in sorted(perseus_dir.glob("*.xml")) if f.name != "__cts__.xml"]
    xml_path = xml_files[0]
    edition = xml_path.stem

    print(f"Parsing Greek: {xml_path.name}")
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    # Find all top-level dramatic divisions
    # These are the subtypes like Prologue, Parodos, Agon, etc.
    edition_div = root.find(f".//{{{TEI_NS}}}div[@type='edition']")
    if edition_div is None:
        print("Error: no edition div")
        return

    # Collect lines per dramatic section, using section name as "book"
    sections = []
    section_idx = 0

    for top_div in edition_div:
        tag = etree.QName(top_div.tag).localname if isinstance(top_div.tag, str) else ""
        if tag != "div":
            continue
        subtype = top_div.get("subtype", "")
        if not subtype:
            continue

        # Use single book "1" for alignment — entire play is one unit
        book_name = "1"

        # Collect all lines in this section
        lines = []
        for l_elem in top_div.iter(f"{{{TEI_NS}}}l"):
            line_n = l_elem.get("n", "")
            if not line_n or not line_n.isdigit():
                continue
            text = " ".join(l_elem.itertext()).strip()
            text = " ".join(text.split())
            if text:
                lines.append({"line": line_n, "text": text})

        if not lines:
            continue

        # Group into passages
        passages = segment_lines(lines)
        for passage_lines in passages:
            first_line = passage_lines[0]["line"]
            last_line = passage_lines[-1]["line"]
            text = " ".join(l["text"] for l in passage_lines)

            sections.append({
                "book": book_name,
                "section": first_line,
                "cts_ref": f"{book_name}.{first_line}",
                "edition": edition,
                "text": text,
                "char_count": len(text),
                "dramatic_section": subtype,
                "first_line": first_line,
                "last_line": last_line,
            })

        print(f"  {subtype}: {len(lines)} lines → {len(passages)} passages")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)

    print(f"Extracted {len(sections)} passages")
    print(f"Saved: {output_path}")


def extract_english(work_id, output_path, eng_suffix="ogl-eng2"):
    """Extract English prose from eng_trans-dev Aristophanes TEI XML."""
    eng_dir = PROJECT_ROOT / "data-sources" / "english_trans-dev" / "data" / "tlg0019" / work_id
    xml_files = sorted(eng_dir.glob(f"*{eng_suffix}*"))
    if not xml_files:
        xml_files = [f for f in sorted(eng_dir.glob("*.xml")) if f.name != "_cts_.xml"]
    xml_path = xml_files[0]

    print(f"Parsing English: {xml_path.name}")
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    def extract_p_text(p_elem):
        parts = []
        if p_elem.text:
            parts.append(p_elem.text)
        for child in p_elem:
            child_tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
            if child_tag in ("note", "figure", "pb", "foreign"):
                pass
            elif child_tag == "lb":
                parts.append(" ")
            else:
                parts.append("".join(child.itertext()))
            if child.tail:
                parts.append(child.tail)
        text = "".join(parts)
        text = text.replace("­", "")
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # Find the translation div (skip preface/commentary)
    body = root.find(f".//{{{TEI_NS}}}body")
    trans_div = body.find(f".//{{{TEI_NS}}}div[@type='translation']")
    if trans_div is None:
        # Try finding any div with textpart chapters
        trans_div = body

    # Find the play text div (skip preface AND appendix)
    play_div = None
    for div in trans_div.iter(f"{{{TEI_NS}}}div"):
        subtype = div.get("subtype", "")
        div_type = div.get("type", "")
        if subtype == "chapter" and div_type == "textpart":
            # Check if this is the appendix
            titles = div.findall(f".//{{{TEI_NS}}}title")
            title_texts = [(t.text or "").strip().upper() for t in titles]
            if any("APPENDIX" in t for t in title_texts):
                continue  # skip appendix
            play_div = div
            break

    if play_div is None:
        print("Warning: no play text div found, using full body")
        play_div = body

    # Extract play text <p> elements, filtering commentary.
    # Rogers translations have extensive inline commentary (line notes,
    # scholarly apparatus) mixed with dialogue. Commentary paragraphs
    # typically start with line numbers or scholarly references, while
    # dialogue starts with character names in CAPS or abbreviations.
    #
    # For heavily annotated plays (Wasps), we filter to keep only
    # dialogue paragraphs. For cleaner plays, we keep everything.

    all_ps = list(play_div.iter(f"{{{TEI_NS}}}p"))

    # Detect if this is a heavily commented play (>60% likely commentary)
    dialogue_pattern = re.compile(
        r'^[A-Z]{2,}\.?\s'  # SOSIAS. or XANTHIAS
        r'|^[A-Z][a-z]{1,8}\.\s'  # Sos. or Phil.
        r'|^[A-Z][a-z]{1,8}\s\('  # Sos (Producing...)
    )

    raw_texts = []
    for p in all_ps:
        text = extract_p_text(p)
        if len(text) >= 20:
            raw_texts.append(text)

    dialogue_count = sum(1 for t in raw_texts if dialogue_pattern.match(t))
    commentary_ratio = 1 - (dialogue_count / max(len(raw_texts), 1))

    if commentary_ratio > 0.5 and len(raw_texts) > 200:
        print(f"  Heavy commentary detected ({commentary_ratio:.0%}), filtering to dialogue only")
        paragraphs = [t for t in raw_texts if dialogue_pattern.match(t)]
    else:
        paragraphs = raw_texts

    # Build sections — one section per paragraph, all in one "book"
    # (the pipeline treats each play as a single work)
    all_sections = []
    for pi, para in enumerate(paragraphs):
        all_sections.append({
            "book": "1",
            "section": str(pi + 1),
            "cts_ref": f"1.{pi + 1}",
            "text": para,
            "char_count": len(para),
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

    print(f"Extracted {len(all_sections)} English paragraphs")
    print(f"Saved: {output_path}")

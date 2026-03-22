#!/usr/bin/env python3
"""
Extract Greek sections from Perseus Diodorus Siculus TEI XML.

Input:  data-sources/perseus/canonical-greekLit/data/tlg0060/tlg001/
Output: build/diodorus/greek_sections.json
"""

import json
import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data" / "tlg0060" / "tlg001"
OUTPUT = PROJECT_ROOT / "build" / "diodorus" / "greek_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

if not PERSEUS_DIR.exists():
    print(f"Error: Perseus data not found at {PERSEUS_DIR}")
    raise SystemExit(1)

all_sections = []

for xml_file in sorted(PERSEUS_DIR.glob("*.xml")):
    if "__cts__" in xml_file.name:
        continue

    print(f"Parsing {xml_file.name}...")
    tree = etree.parse(str(xml_file))
    root = tree.getroot()

    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    nsmap = {"tei": ns.strip("{}")} if ns else {}
    edition_id = xml_file.stem

    def find_all(el, local_name):
        return el.findall(
            f".//{{{nsmap['tei']}}}{local_name}" if nsmap else f".//{local_name}"
        )

    def get_text(el):
        return re.sub(r"\s+", " ", "".join(el.itertext())).strip()

    for div in find_all(root, "div"):
        subtype = div.get("subtype", "")
        n = div.get("n", "")

        if subtype == "section":
            chapter_n = ""
            book_n = ""
            parent = div.getparent()
            while parent is not None:
                p_subtype = parent.get("subtype", "")
                if p_subtype == "chapter":
                    chapter_n = parent.get("n", "")
                elif p_subtype == "book":
                    book_n = parent.get("n", "")
                parent = parent.getparent()

            p_els = div.findall(f"{{{nsmap['tei']}}}p" if nsmap else "p")
            text = " ".join(get_text(p) for p in p_els).strip()

            if text:
                cts_ref = f"{book_n}.{chapter_n}.{n}"
                all_sections.append({
                    "edition": edition_id,
                    "book": book_n,
                    "section": f"{chapter_n}.{n}",
                    "cts_ref": cts_ref,
                    "text": text,
                    "char_count": len(text),
                })

        elif subtype == "chapter" and not div.findall(
            f".//{{{nsmap['tei']}}}div[@subtype='section']"
            if nsmap else ".//div[@subtype='section']"
        ):
            book_n = ""
            parent = div.getparent()
            while parent is not None:
                if parent.get("subtype") == "book":
                    book_n = parent.get("n", "")
                    break
                parent = parent.getparent()

            text = get_text(div)
            if text:
                cts_ref = f"{book_n}.{n}"
                all_sections.append({
                    "edition": edition_id,
                    "book": book_n,
                    "section": n,
                    "cts_ref": cts_ref,
                    "text": text,
                    "char_count": len(text),
                })

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

books_found = sorted(set(s["book"] for s in all_sections))
print(f"Extracted {len(all_sections)} sections across books: {books_found}")
print(f"Saved: {OUTPUT}")

#!/usr/bin/env python3
"""Extract structured text from Perseus Greek TEI files for Diodorus."""

import json
import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PERSEUS_DIR = (
    PROJECT_ROOT
    / "data-sources"
    / "perseus"
    / "canonical-greekLit"
    / "data"
    / "tlg0060"
    / "tlg001"
)
OUTPUT = PROJECT_ROOT / "output" / "perseus_extracted.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

if not PERSEUS_DIR.exists():
    print(f"Error: Perseus data not found at {PERSEUS_DIR}")
    raise SystemExit(1)

all_sections = []

for xml_file in sorted(PERSEUS_DIR.glob("*.xml")):
    if "__cts__" in xml_file.name:
        continue  # Skip CTS metadata files

    print(f"Parsing {xml_file.name}...")
    tree = etree.parse(str(xml_file))
    root = tree.getroot()

    # Determine namespace
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    nsmap = {"tei": ns.strip("{}")} if ns else {}

    edition_id = xml_file.stem  # e.g. tlg0060.tlg001.perseus-grc5

    def find_all(el, local_name):
        """Find elements by local name, namespace-agnostic."""
        return el.findall(
            f".//{{{nsmap['tei']}}}{local_name}" if nsmap else f".//{local_name}"
        )

    def get_text(el):
        return re.sub(r"\s+", " ", "".join(el.itertext())).strip()

    # Find all textpart divs — may be nested (book > chapter > section)
    for div in find_all(root, "div"):
        subtype = div.get("subtype", "")
        n = div.get("n", "")

        if subtype == "section":
            # This is a leaf section — get its full CTS path
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
                all_sections.append(
                    {
                        "edition": edition_id,
                        "book": book_n,
                        "chapter": chapter_n,
                        "section": n,
                        "cts_ref": cts_ref,
                        "text": text,
                        "char_count": len(text),
                    }
                )

        elif subtype == "chapter" and not div.findall(
            f".//{{{nsmap['tei']}}}div[@subtype='section']"
            if nsmap
            else ".//div[@subtype='section']"
        ):
            # Chapter with no sub-sections — treat whole chapter as one unit
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
                all_sections.append(
                    {
                        "edition": edition_id,
                        "book": book_n,
                        "chapter": n,
                        "section": "",
                        "cts_ref": cts_ref,
                        "text": text,
                        "char_count": len(text),
                    }
                )

result = {
    "source": "Perseus Digital Library — Diodorus Siculus, Bibliotheca Historica",
    "cts_urn": "urn:cts:greekLit:tlg0060.tlg001",
    "sections": all_sections,
}

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

books_found = sorted(set(s["book"] for s in all_sections))
print(f"Extracted {len(all_sections)} sections across books: {books_found}")
print(f"Saved to {OUTPUT}")

#!/usr/bin/env python3
"""
Extract Latin verse lines from Perseus TEI XML files for Statius.

Parses:
  - data/phi1020/phi001/ (Thebaid) — 12 books, ~9,742 lines
  - data/phi1020/phi003/ (Achilleid) — 2 books, ~1,127 lines

Extracts <l n="..."> elements within <div subtype="book">.

Output:
  output/statius/latin_extracted.json
"""

import json
import re
from pathlib import Path

from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PERSEUS_BASE = (
    PROJECT_ROOT / "data-sources" / "perseus" / "canonical-latinLit" / "data" / "phi1020"
)
OUTPUT = PROJECT_ROOT / "output" / "statius" / "latin_extracted.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

WORKS = [
    {
        "subdir": "phi001",
        "name": "Thebaid",
        "cts_work": "phi1020.phi001",
    },
    {
        "subdir": "phi003",
        "name": "Achilleid",
        "cts_work": "phi1020.phi003",
    },
]


def get_text(el):
    """Extract all text from an element, collapsing whitespace."""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def extract_work(work_info):
    """Extract all verse lines from a single Statius work."""
    work_dir = PERSEUS_BASE / work_info["subdir"]
    if not work_dir.exists():
        print(f"  Error: {work_dir} not found")
        return []

    all_lines = []

    for xml_file in sorted(work_dir.glob("*.xml")):
        if "__cts__" in xml_file.name:
            continue

        print(f"  Parsing {xml_file.name}...")
        tree = etree.parse(str(xml_file))
        root = tree.getroot()

        # Determine namespace
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"
        nsmap = {"tei": ns.strip("{}")} if ns else {}

        edition_id = xml_file.stem  # e.g. phi1020.phi001.perseus-lat2

        def find_all(el, local_name):
            """Find elements by local name, namespace-agnostic."""
            return el.findall(
                f".//{{{nsmap['tei']}}}{local_name}" if nsmap else f".//{local_name}"
            )

        # Find book divs
        for book_div in find_all(root, "div"):
            if book_div.get("subtype") != "book":
                continue
            book_n = book_div.get("n", "")

            # Extract lines from this book
            for line_el in find_all(book_div, "l"):
                line_n = line_el.get("n", "")
                text = get_text(line_el)

                if text and line_n:
                    all_lines.append({
                        "work": work_info["name"],
                        "cts_work": work_info["cts_work"],
                        "edition": edition_id,
                        "book": book_n,
                        "line": line_n,
                        "cts_ref": f"{book_n}.{line_n}",
                        "text": text,
                        "char_count": len(text),
                    })

    return all_lines


def main():
    all_lines = []

    for work in WORKS:
        print(f"\n=== Extracting {work['name']} ===")
        work_dir = PERSEUS_BASE / work["subdir"]
        if not work_dir.exists():
            print(f"  Warning: {work_dir} not found, skipping")
            continue

        lines = extract_work(work)
        all_lines.extend(lines)

        # Summary per book
        books = sorted(set(l["book"] for l in lines))
        for b in books:
            book_lines = [l for l in lines if l["book"] == b]
            print(f"  Book {b}: {len(book_lines)} lines")
        print(f"  Total {work['name']}: {len(lines)} lines")

    result = {
        "source": "Perseus Digital Library — P. Papinius Statius",
        "cts_urn_base": "urn:cts:latinLit:phi1020",
        "lines": all_lines,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nTotal lines extracted: {len(all_lines)}")
    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    main()

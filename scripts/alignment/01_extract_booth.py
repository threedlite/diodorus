#!/usr/bin/env python3
"""Extract structured text from Booth's TEI XML (A36034).

The EEBO-TCP TEI uses:
  <TEI><text>
    <front>...</front>
    <group>
      <text><body><div type="book">
        <div type="part|chapter">
          <p>...</p>
      </div></body></text>
      ...
    </group>
    <back>...</back>
  </text></TEI>

Book numbers are in heading text ("BOOK I.", "BOOK XI."), not n= attributes.
"""

import json
import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT = PROJECT_ROOT / "data-sources" / "booth" / "A36034.xml"
OUTPUT = PROJECT_ROOT / "build" / "booth_extracted.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

if not INPUT.exists():
    print(f"Error: Booth TEI not found at {INPUT}")
    raise SystemExit(1)

tree = etree.parse(str(INPUT))
root = tree.getroot()

NS = "{http://www.tei-c.org/ns/1.0}"


def get_text(el):
    """Recursively extract all text, skipping <note>, <gap>, <figure>, <fw>."""
    parts = []
    if el.text:
        parts.append(el.text)
    for child in el:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag not in ("note", "gap", "figure", "fw"):
            parts.append(get_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(parts)


def clean(text):
    """Normalise whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def roman_to_int(s):
    """Convert Roman numeral string to integer."""
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    s = s.upper().strip()
    total = 0
    for i, c in enumerate(s):
        if c not in vals:
            return None
        v = vals[c]
        if i + 1 < len(s) and vals.get(s[i + 1], 0) > v:
            total -= v
        else:
            total += v
    return total


# The actual books are under <group><text><body><div type="book">
# Find all book-level divs across all <text> elements in <group>
group = root.find(f".//{NS}group")
if group is None:
    # Fallback: try body directly
    bodies = root.findall(f".//{NS}body")
else:
    bodies = group.findall(f".//{NS}text/{NS}body")

books = []
for body in bodies:
    for book_div in body.findall(f"{NS}div"):
        div_type = book_div.get("type", "")
        if div_type != "book":
            continue

        # Extract heading
        head_el = book_div.find(f"{NS}head")
        head_text = clean(get_text(head_el)) if head_el is not None else ""

        # Extract book number from heading text
        book_num = None
        m = re.search(r"BOOK\s+([IVXLC]+)", head_text, re.IGNORECASE)
        if m:
            book_num = roman_to_int(m.group(1))

        # Extract chapters — may be nested under "part" divs or directly
        chapters = []
        chapter_idx = 0

        for sub_div in book_div.findall(f"{NS}div"):
            sub_type = sub_div.get("type", "")

            if sub_type == "chapter":
                # Direct chapter under book
                ch_head_el = sub_div.find(f"{NS}head")
                ch_head = clean(get_text(ch_head_el)) if ch_head_el is not None else ""

                paragraphs = []
                for j, p in enumerate(sub_div.findall(f".//{NS}p")):
                    text = clean(get_text(p))
                    if text:
                        paragraphs.append(
                            {"p_index": j, "text": text, "char_count": len(text)}
                        )

                chapters.append(
                    {
                        "div2_index": chapter_idx,
                        "head": ch_head,
                        "paragraphs": paragraphs,
                    }
                )
                chapter_idx += 1

            elif sub_type == "part":
                # Part contains chapters
                for ch_div in sub_div.findall(f"{NS}div"):
                    if ch_div.get("type", "") != "chapter":
                        continue
                    ch_head_el = ch_div.find(f"{NS}head")
                    ch_head = (
                        clean(get_text(ch_head_el)) if ch_head_el is not None else ""
                    )

                    paragraphs = []
                    for j, p in enumerate(ch_div.findall(f".//{NS}p")):
                        text = clean(get_text(p))
                        if text:
                            paragraphs.append(
                                {"p_index": j, "text": text, "char_count": len(text)}
                            )

                    chapters.append(
                        {
                            "div2_index": chapter_idx,
                            "head": ch_head,
                            "paragraphs": paragraphs,
                        }
                    )
                    chapter_idx += 1

        # If no chapters found, extract paragraphs directly from book div
        if not chapters:
            paragraphs = []
            for j, p in enumerate(book_div.findall(f".//{NS}p")):
                text = clean(get_text(p))
                if text:
                    paragraphs.append(
                        {"p_index": j, "text": text, "char_count": len(text)}
                    )
            if paragraphs:
                chapters.append(
                    {"div2_index": 0, "head": "", "paragraphs": paragraphs}
                )

        books.append(
            {
                "div1_type": "book",
                "div1_n": str(book_num) if book_num else "",
                "head": head_text,
                "chapters": chapters,
            }
        )

result = {"source": "Booth (1700) — OTA A36034", "books": books}

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

total_p = sum(len(ch["paragraphs"]) for bk in books for ch in bk["chapters"])
total_ch = sum(len(bk["chapters"]) for bk in books)
print(f"Extracted {len(books)} books, {total_ch} chapters, {total_p} paragraphs")
for bk in books:
    ps = sum(len(ch["paragraphs"]) for ch in bk["chapters"])
    print(f"  Book {bk['div1_n']:>3}: {len(bk['chapters'])} chapters, {ps} paragraphs")
print(f"Saved to {OUTPUT}")

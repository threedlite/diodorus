#!/usr/bin/env python3
"""
Match Booth div1 elements to Perseus book numbers.
Uses heading text and positional heuristics.
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BOOTH = PROJECT_ROOT / "output" / "booth_normalised.json"
PERSEUS = PROJECT_ROOT / "output" / "perseus_extracted.json"
OUTPUT = PROJECT_ROOT / "output" / "book_alignment.json"

for f, name in [(BOOTH, "booth_normalised.json"), (PERSEUS, "perseus_extracted.json")]:
    if not f.exists():
        print(f"Error: {f} not found. Run previous scripts first.")
        raise SystemExit(1)

with open(BOOTH) as f:
    booth = json.load(f)
with open(PERSEUS) as f:
    perseus = json.load(f)

# Get set of available Greek book numbers
greek_books = sorted(set(s["book"] for s in perseus["sections"]))


def roman_to_int(s):
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


alignments = []
for bk in booth["books"]:
    head = bk["head"]
    n = bk["div1_n"]

    book_num = None
    if n and n.isdigit():
        book_num = int(n)
    elif n:
        book_num = roman_to_int(n)

    if book_num is None:
        m = re.search(r"BOOK\s+([IVXLC]+)", head, re.IGNORECASE)
        if m:
            book_num = roman_to_int(m.group(1))

    has_greek = str(book_num) in greek_books if book_num else False

    alignments.append(
        {
            "booth_div1_type": bk["div1_type"],
            "booth_div1_n": bk["div1_n"],
            "booth_head": head[:100],
            "inferred_book_num": book_num,
            "greek_available": has_greek,
            "booth_paragraph_count": sum(
                len(ch["paragraphs"]) for ch in bk["chapters"]
            ),
            "greek_section_count": len(
                [s for s in perseus["sections"] if s["book"] == str(book_num)]
            )
            if book_num
            else 0,
        }
    )

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(alignments, f, ensure_ascii=False, indent=2)

print(
    f"{'Booth div1':<12} {'Head':<30} {'Book#':<6} {'Greek?':<7} {'EN ps':<7} {'GR ss':<7}"
)
print("-" * 80)
for a in alignments:
    greek_mark = "yes" if a["greek_available"] else "no"
    print(
        f"{a['booth_div1_n']:<12} {a['booth_head'][:28]:<30} "
        f"{str(a['inferred_book_num'] or '?'):<6} "
        f"{greek_mark:<7} "
        f"{a['booth_paragraph_count']:<7} {a['greek_section_count']:<7}"
    )

print(f"\nSaved to {OUTPUT}")

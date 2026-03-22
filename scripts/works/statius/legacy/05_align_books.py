#!/usr/bin/env python3
"""
Match Latin books to Mozley English books.

Straightforward 1:1 mapping:
  - Thebaid: books 1-12
  - Achilleid: books 1-2

Validates both sides exist. Counts passages and paragraphs per book.

Inputs:
  output/statius/latin_passages.json
  output/statius/mozley_normalised.json

Output:
  output/statius/book_alignment.json
"""

import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
PASSAGES = PROJECT_ROOT / "build" / "statius" / "latin_passages.json"
MOZLEY = PROJECT_ROOT / "build" / "statius" / "mozley_normalised.json"
OUTPUT = PROJECT_ROOT / "build" / "statius" / "book_alignment.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

for f, name in [
    (PASSAGES, "latin_passages.json"),
    (MOZLEY, "mozley_normalised.json"),
]:
    if not f.exists():
        print(f"Error: {f} not found. Run previous scripts first.")
        raise SystemExit(1)

with open(PASSAGES) as f:
    passages_data = json.load(f)
with open(MOZLEY) as f:
    mozley_data = json.load(f)

# Index Latin passages by (work, book)
latin_by_book = defaultdict(list)
for p in passages_data["passages"]:
    latin_by_book[(p["work"], p["book"])].append(p)

# Index English paragraphs by (work, book)
english_by_book = {}
for work_key, work_data in mozley_data["works"].items():
    work_name = work_key.capitalize()  # "thebaid" -> "Thebaid"
    for book in work_data["books"]:
        book_num = book["book"]
        english_by_book[(work_name, str(book_num))] = book["paragraphs"]

# Build book alignment
alignments = []

for work_name in ["Thebaid", "Achilleid"]:
    # Get all book numbers from Latin side
    latin_books = sorted(
        set(b for (w, b) in latin_by_book.keys() if w == work_name),
        key=lambda x: int(x),
    )

    for book_n in latin_books:
        latin_passages = latin_by_book.get((work_name, book_n), [])
        english_paras = english_by_book.get((work_name, book_n), [])

        latin_available = len(latin_passages) > 0
        english_available = len(english_paras) > 0

        latin_lines = sum(p["line_count"] for p in latin_passages)
        latin_chars = sum(p["char_count"] for p in latin_passages)
        english_chars = sum(p.get("char_count", len(p.get("text_normalised", p["text"])))
                           for p in english_paras)

        alignment = {
            "work": work_name,
            "book": book_n,
            "latin_available": latin_available,
            "english_available": english_available,
            "latin_passages": len(latin_passages),
            "latin_lines": latin_lines,
            "latin_chars": latin_chars,
            "english_paragraphs": len(english_paras),
            "english_chars": english_chars,
        }
        alignments.append(alignment)

        status = "OK" if latin_available and english_available else "MISSING"
        print(
            f"  {work_name} Book {book_n}: {status} — "
            f"{len(latin_passages)} passages ({latin_lines} lines) / "
            f"{len(english_paras)} paragraphs"
        )

# Summary
total_ok = sum(1 for a in alignments if a["latin_available"] and a["english_available"])
print(f"\nBook alignments: {total_ok} / {len(alignments)} OK")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(alignments, f, ensure_ascii=False, indent=2)

print(f"Saved to {OUTPUT}")

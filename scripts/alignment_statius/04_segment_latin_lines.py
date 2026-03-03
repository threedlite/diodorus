#!/usr/bin/env python3
"""
Group consecutive Latin verse lines into alignment passages.

Individual verse lines (~40 chars) are too short for meaningful embedding
similarity. This step groups them into passages (~8-12 lines, ~400 chars)
as alignment units for the segmental DP.

Segmentation heuristic:
  - Accumulate lines until 8+ lines reached
  - Then break at the next sentence boundary (line ending with . ? !)
  - Maximum 15 lines per passage (hard cap)

Each passage records:
  - first_line, last_line: line number range
  - text: concatenated text of all lines
  - line_count, char_count

Input:
  output/statius/latin_extracted.json

Output:
  output/statius/latin_passages.json
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT = PROJECT_ROOT / "output" / "statius" / "latin_extracted.json"
OUTPUT = PROJECT_ROOT / "output" / "statius" / "latin_passages.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

MIN_LINES = 8
MAX_LINES = 15


def line_sort_key(line_n):
    """Parse line number for sorting. Handles '184a' style variants."""
    m = re.match(r'^(\d+)(.*)', line_n)
    if m:
        return (int(m.group(1)), m.group(2))
    return (0, line_n)


def is_sentence_end(text):
    """Check if a line ends with a sentence-ending punctuation mark."""
    stripped = text.rstrip()
    return bool(re.search(r'[.?!;]\s*$', stripped))


def segment_book_lines(lines):
    """
    Group verse lines from a single book into passages.

    Args:
        lines: list of line dicts (each with 'line', 'text', etc.)

    Returns:
        list of passage dicts
    """
    passages = []
    current_lines = []

    for line in lines:
        current_lines.append(line)

        # Check if we should break here
        should_break = False

        if len(current_lines) >= MIN_LINES:
            # Prefer to break at sentence boundaries
            if is_sentence_end(line["text"]):
                should_break = True

        if len(current_lines) >= MAX_LINES:
            # Hard cap — break regardless
            should_break = True

        if should_break:
            passage_text = " ".join(l["text"] for l in current_lines)
            passages.append({
                "first_line": current_lines[0]["line"],
                "last_line": current_lines[-1]["line"],
                "text": passage_text,
                "line_count": len(current_lines),
                "char_count": len(passage_text),
            })
            current_lines = []

    # Remaining lines (append to last passage or create new)
    if current_lines:
        passage_text = " ".join(l["text"] for l in current_lines)
        if passages and len(current_lines) < MIN_LINES // 2:
            # Too few lines — merge with previous passage
            prev = passages[-1]
            prev["last_line"] = current_lines[-1]["line"]
            prev["text"] += " " + passage_text
            prev["line_count"] += len(current_lines)
            prev["char_count"] = len(prev["text"])
        else:
            passages.append({
                "first_line": current_lines[0]["line"],
                "last_line": current_lines[-1]["line"],
                "text": passage_text,
                "line_count": len(current_lines),
                "char_count": len(passage_text),
            })

    return passages


def main():
    if not INPUT.exists():
        print(f"Error: {INPUT} not found. Run 02_extract_latin_tei.py first.")
        raise SystemExit(1)

    with open(INPUT) as f:
        data = json.load(f)

    all_passages = []

    # Group lines by work and book
    from collections import defaultdict
    by_work_book = defaultdict(list)
    for line in data["lines"]:
        key = (line["work"], line["cts_work"], line["edition"], line["book"])
        by_work_book[key].append(line)

    for (work_name, cts_work, edition, book_n), lines in sorted(by_work_book.items()):
        # Sort lines by line number
        lines.sort(key=lambda l: line_sort_key(l["line"]))

        passages = segment_book_lines(lines)

        for passage in passages:
            passage["work"] = work_name
            passage["cts_work"] = cts_work
            passage["edition"] = edition
            passage["book"] = book_n

        all_passages.extend(passages)

        avg_chars = (
            sum(p["char_count"] for p in passages) / len(passages)
            if passages else 0
        )
        print(
            f"  {work_name} Book {book_n}: {len(lines)} lines -> "
            f"{len(passages)} passages (avg {avg_chars:.0f} chars)"
        )

    result = {
        "source": "Statius Latin verse passages (grouped for alignment)",
        "segmentation": {
            "min_lines": MIN_LINES,
            "max_lines": MAX_LINES,
            "break_at": "sentence boundary (. ? ! ;)",
        },
        "passages": all_passages,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total_passages = len(all_passages)
    total_lines = sum(p["line_count"] for p in all_passages)
    avg_lines = total_lines / total_passages if total_passages else 0
    avg_chars = (
        sum(p["char_count"] for p in all_passages) / total_passages
        if total_passages else 0
    )
    print(f"\nTotal: {total_passages} passages from {total_lines} lines")
    print(f"Average: {avg_lines:.1f} lines/passage, {avg_chars:.0f} chars/passage")
    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    main()

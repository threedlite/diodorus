#!/usr/bin/env python3
"""
Extract and normalise Mozley's English translation of Statius.

Runs the legacy scrape + normalise pipeline, then transforms
the output into standard sections format.

Input:  data-sources/statius_mozley/ (cached HTML from Wikisource)
Output: build/statius/english_sections.json
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LEGACY_DIR = Path(__file__).resolve().parent / "legacy"
OUT_DIR = PROJECT_ROOT / "build" / "statius"

OUT_DIR.mkdir(parents=True, exist_ok=True)

# Run legacy extraction steps
print("Running legacy Mozley scrape...")
subprocess.run([sys.executable, str(LEGACY_DIR / "01_scrape_mozley.py")],
               cwd=str(PROJECT_ROOT), check=True)

print("\nRunning legacy Mozley normalisation...")
subprocess.run([sys.executable, str(LEGACY_DIR / "03_normalise_mozley.py")],
               cwd=str(PROJECT_ROOT), check=True)

# Also need book alignment
print("\nRunning legacy book alignment...")
subprocess.run([sys.executable, str(LEGACY_DIR / "05_align_books.py")],
               cwd=str(PROJECT_ROOT), check=True)

# Transform legacy mozley_normalised.json to standard format
mozley_path = OUT_DIR / "mozley_normalised.json"
if not mozley_path.exists():
    print(f"Error: {mozley_path} not found")
    raise SystemExit(1)

with open(mozley_path) as f:
    mozley_data = json.load(f)

sections = []
for work_key, work_data in mozley_data["works"].items():
    work_name = work_key.capitalize()  # "thebaid" -> "Thebaid"
    for book in work_data["books"]:
        book_n = str(book["book"])
        for idx, para in enumerate(book["paragraphs"]):
            text = para.get("text_normalised", para["text"])
            sections.append({
                "work": work_name,
                "book": book_n,
                "section": str(idx),
                "cts_ref": f"{book_n}.{idx}",
                "text": text,
                "char_count": len(text),
            })

output = OUT_DIR / "english_sections.json"
with open(output, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)

print(f"\nTransformed {len(sections)} English paragraphs to standard format")
print(f"Saved: {output}")

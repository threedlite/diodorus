#!/usr/bin/env python3
"""
Extract Latin passages from Perseus Statius TEI XML.

Runs the legacy extraction + segmentation pipeline, then transforms
the output into standard sections format.

Steps:
  1. Extract Latin verse lines from TEI (02_extract_latin_tei.py logic)
  2. Segment lines into ~10-line passages (04_segment_latin_lines.py logic)
  3. Output standard format

Input:  data-sources/perseus/canonical-latinLit/data/phi1020/
Output: build/statius/greek_sections.json (named "greek" for generic pipeline compat)
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LEGACY_DIR = PROJECT_ROOT / "scripts" / "alignment_statius"
OUT_DIR = PROJECT_ROOT / "build" / "statius"

OUT_DIR.mkdir(parents=True, exist_ok=True)

# Run legacy extraction steps
print("Running legacy Latin extraction...")
subprocess.run([sys.executable, str(LEGACY_DIR / "02_extract_latin_tei.py")],
               cwd=str(PROJECT_ROOT), check=True)

print("\nRunning legacy line segmentation...")
subprocess.run([sys.executable, str(LEGACY_DIR / "04_segment_latin_lines.py")],
               cwd=str(PROJECT_ROOT), check=True)

# Transform legacy latin_passages.json to standard format
passages_path = OUT_DIR / "latin_passages.json"
if not passages_path.exists():
    print(f"Error: {passages_path} not found")
    raise SystemExit(1)

with open(passages_path) as f:
    passages_data = json.load(f)

sections = []
for p in passages_data["passages"]:
    work = p["work"]
    book = str(p["book"])
    first_line = str(p["first_line"])
    last_line = str(p["last_line"])

    sections.append({
        "work": work,
        "book": book,
        "section": first_line,
        "cts_ref": f"{book}.{first_line}",
        "edition": p["edition"],
        "text": p["text"],
        "char_count": p["char_count"],
        "latin_first_line": first_line,
        "latin_last_line": last_line,
    })

output = OUT_DIR / "greek_sections.json"
with open(output, "w", encoding="utf-8") as f:
    json.dump({"sections": sections}, f, ensure_ascii=False, indent=2)

print(f"\nTransformed {len(sections)} Latin passages to standard format")
print(f"Saved: {output}")

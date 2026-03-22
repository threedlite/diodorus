#!/usr/bin/env python3
"""
Align Greek sections to Long English sections using Segmental DP.

Marcus Aurelius has a clean 1:1 structure: 12 books, numbered sections
in both Greek and English. Uses the shared segmental_dp_align from align_core.

Inputs:
  output/marcus/greek_sections.json
  output/marcus/english_sections.json

Outputs:
  output/marcus/section_alignments.json
"""

import json
import sys
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from align_core import segmental_dp_align

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GREEK = PROJECT_ROOT / "build" / "marcus" / "greek_sections.json"
ENGLISH = PROJECT_ROOT / "build" / "marcus" / "english_sections.json"
OUTPUT = PROJECT_ROOT / "build" / "marcus" / "section_alignments.json"

CUSTOM_MODEL = PROJECT_ROOT / "models" / "ancient-greek-embedding"
BASELINE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

for f, name in [(GREEK, "greek_sections.json"), (ENGLISH, "english_sections.json")]:
    if not f.exists():
        print(f"Error: {f} not found. Run previous steps first.")
        raise SystemExit(1)

with open(GREEK) as f:
    greek_data = json.load(f)
with open(ENGLISH) as f:
    english_data = json.load(f)

print("Loading sentence embedding model...")
if CUSTOM_MODEL.exists():
    print(f"  Using custom Ancient Greek model: {CUSTOM_MODEL}")
    model = SentenceTransformer(str(CUSTOM_MODEL))
else:
    print(f"  Falling back to baseline: {BASELINE_MODEL}")
    model = SentenceTransformer(BASELINE_MODEL)

# Align book by book
greek_by_book = {}
for s in greek_data["sections"]:
    greek_by_book.setdefault(s["book"], []).append(s)

english_by_book = {}
for s in english_data["sections"]:
    english_by_book.setdefault(s["book"], []).append(s)

all_books = sorted(set(greek_by_book.keys()) & set(english_by_book.keys()), key=int)
print(f"\nBooks to align: {all_books}")

all_alignments = []

for book in all_books:
    greek_secs = greek_by_book[book]
    english_secs = english_by_book[book]

    print(f"\n=== Book {book}: {len(greek_secs)} Greek, {len(english_secs)} English ===")

    # Embed
    greek_embs = model.encode([s["text"] for s in greek_secs], show_progress_bar=False, batch_size=32)
    english_embs = model.encode([s["text"] for s in english_secs], show_progress_bar=False, batch_size=32)

    greek_lens = [s["char_count"] for s in greek_secs]
    english_lens = [s["char_count"] for s in english_secs]

    expected_ratio = sum(greek_lens) / sum(english_lens) if sum(english_lens) > 0 else 1.0
    print(f"  Char ratio (Greek/English): {expected_ratio:.2f}")

    # DP alignment
    groups = segmental_dp_align(greek_embs, english_embs, greek_lens, english_lens, expected_ratio)
    print(f"  DP produced {len(groups)} alignment groups")

    # Track which English sections are used
    en_used = set()
    for gr_start, gr_end, en_start, en_end, score in groups:
        for ej in range(en_start, en_end):
            en_used.add(ej)

    en_skipped = len(english_secs) - len(en_used)
    print(f"  English sections: {len(en_used)} matched, {en_skipped} unmatched")

    # Build records — ensure every English section appears
    en_to_greek = {}
    for group_id, (gr_start, gr_end, en_start, en_end, score) in enumerate(groups):
        for ej in range(en_start, en_end):
            if ej not in en_to_greek:
                en_to_greek[ej] = []
            for gi in range(gr_start, gr_end):
                gs = greek_secs[gi]
                es = english_secs[ej]
                en_to_greek[ej].append({
                    "book": book,
                    "greek_cts_ref": gs["cts_ref"],
                    "greek_edition": gs["edition"],
                    "english_cts_ref": es["cts_ref"],
                    "english_section": es["section"],
                    "similarity": round(score, 4),
                    "greek_preview": gs["text"][:80],
                    "english_preview": es["text"][:80],
                    "group_id": group_id,
                    "group_size_gr": gr_end - gr_start,
                    "group_size_en": en_end - en_start,
                    "match_type": "dp_aligned",
                })

    for ej in range(len(english_secs)):
        if ej in en_to_greek:
            all_alignments.extend(en_to_greek[ej])
        else:
            es = english_secs[ej]
            all_alignments.append({
                "book": book,
                "greek_cts_ref": None,
                "greek_edition": None,
                "english_cts_ref": es["cts_ref"],
                "english_section": es["section"],
                "similarity": 0.0,
                "greek_preview": "",
                "english_preview": es["text"][:80],
                "group_id": None,
                "group_size_gr": 0,
                "group_size_en": 1,
                "match_type": "unmatched_english",
            })

    if en_skipped > 0:
        print(f"  Added {en_skipped} unmatched English sections")

print(f"\nTotal alignments: {len(all_alignments)}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(all_alignments, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

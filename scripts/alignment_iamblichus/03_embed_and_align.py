#!/usr/bin/env python3
"""
Align Greek sections to Long English sections using Segmental DP.

Iamblichus has a clean 1:1 structure: 12 books, numbered sections
in both Greek and English. Uses the shared segmental_dp_align from align_core.

Inputs:
  output/iamblichus/greek_sections.json
  output/iamblichus/english_sections.json

Outputs:
  output/iamblichus/section_alignments.json
"""

import json
import sys
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from align_core import segmental_dp_align

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GREEK = PROJECT_ROOT / "build" / "iamblichus" / "greek_sections.json"
ENGLISH = PROJECT_ROOT / "build" / "iamblichus" / "english_sections.json"
OUTPUT = PROJECT_ROOT / "build" / "iamblichus" / "section_alignments.json"

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

# Group by (work, book) — Iamblichus has two works with overlapping chapter numbers
greek_by_wb = {}
for s in greek_data["sections"]:
    key = (s.get("work", ""), s["book"])
    greek_by_wb.setdefault(key, []).append(s)

english_by_wb = {}
for s in english_data["sections"]:
    key = (s.get("work", ""), s["book"])
    english_by_wb.setdefault(key, []).append(s)

# For each work, align all chapters together (single DP run per work)
works = sorted(set(s.get("work", "") for s in greek_data["sections"]))
print(f"\nWorks to align: {works}")

all_alignments = []

for work in works:
    # Gather all sections for this work, sorted by chapter/section
    greek_secs = [s for s in greek_data["sections"] if s.get("work", "") == work]
    english_secs = [s for s in english_data["sections"] if s.get("work", "") == work]

    if not greek_secs or not english_secs:
        print(f"\n=== {work}: skipping (no {'Greek' if not greek_secs else 'English'}) ===")
        continue

    book = work  # use work name as the "book" for grouping
    print(f"\n=== {work}: {len(greek_secs)} Greek, {len(english_secs)} English ===")

    # Embed
    greek_embs = model.encode([s["text"] for s in greek_secs], show_progress_bar=False, batch_size=32)
    english_embs = model.encode([s["text"] for s in english_secs], show_progress_bar=False, batch_size=32)

    greek_lens = [s["char_count"] for s in greek_secs]
    english_lens = [s["char_count"] for s in english_secs]

    expected_ratio = sum(greek_lens) / sum(english_lens) if sum(english_lens) > 0 else 1.0

    # Iamblichus: Greek has sections within chapters, English has chapters only.
    # Need to allow wider grouping — up to ratio * 2 Greek sections per English chapter.
    gr_per_en = len(greek_secs) / max(len(english_secs), 1)
    max_source = max(5, int(gr_per_en * 2))
    print(f"  Char ratio (Greek/English): {expected_ratio:.2f}")
    print(f"  Sections ratio: {gr_per_en:.1f} Greek per English, max_source={max_source}")

    # DP alignment
    groups = segmental_dp_align(greek_embs, english_embs, greek_lens, english_lens,
                               expected_ratio, max_source=max_source)
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

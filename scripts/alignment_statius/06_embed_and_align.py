#!/usr/bin/env python3
"""
Align Latin passages to Mozley English paragraphs using Segmental Dynamic
Programming on cross-lingual sentence embeddings.

Algorithm (segmental_dp_align):
  - DP[i][j] = best total score aligning latin[0:i] to english[0:j]
  - Transitions: group g in {1..5} Latin passages onto e in {1..2} English paragraphs
  - Score: 0.8 * cosine_sim(mean_embed_lat, mean_embed_en)
         + 0.2 * exp(-0.5 * ((lat_chars/en_chars)/expected_ratio - 1)^2)
  - Banding: j constrained to +/- max(20, 15% * n_en) of expected diagonal
  - Prefix sums on embeddings and char lengths for O(1) group mean computation

Inputs:
  output/statius/mozley_normalised.json   -- from 03_normalise_mozley.py
  output/statius/latin_passages.json      -- from 04_segment_latin_lines.py
  output/statius/book_alignment.json      -- from 05_align_books.py

Outputs:
  output/statius/section_alignments.json  -- one record per Latin passage with group_id
  output/statius/section_alignments.tsv   -- tabular summary

Model: uses custom Latin embedding (models/latin-embedding/)
       if available, otherwise paraphrase-multilingual-MiniLM-L12-v2.
"""

import json
import re
import sys

import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Import shared alignment algorithms
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from align_core import segmental_dp_align

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MOZLEY = PROJECT_ROOT / "build" / "statius" / "mozley_normalised.json"
PASSAGES = PROJECT_ROOT / "build" / "statius" / "latin_passages.json"
BOOK_ALIGN = PROJECT_ROOT / "build" / "statius" / "book_alignment.json"
OUTPUT = PROJECT_ROOT / "build" / "statius" / "section_alignments.json"
OUTPUT_TSV = PROJECT_ROOT / "build" / "statius" / "section_alignments.tsv"

# --- Model selection: prefer custom Latin model ---
CUSTOM_MODEL = PROJECT_ROOT / "models" / "latin-embedding"
BASELINE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

for f, name in [
    (MOZLEY, "mozley_normalised.json"),
    (PASSAGES, "latin_passages.json"),
    (BOOK_ALIGN, "book_alignment.json"),
]:
    if not f.exists():
        print(f"Error: {f} not found. Run previous scripts first.")
        raise SystemExit(1)

print("Loading sentence embedding model...")
if CUSTOM_MODEL.exists():
    print(f"  Using custom Latin model: {CUSTOM_MODEL}")
    model = SentenceTransformer(str(CUSTOM_MODEL))
else:
    print(f"  Custom model not found at {CUSTOM_MODEL}")
    print(f"  Falling back to baseline: {BASELINE_MODEL}")
    model = SentenceTransformer(BASELINE_MODEL)

with open(MOZLEY) as f:
    mozley = json.load(f)
with open(PASSAGES) as f:
    passages_data = json.load(f)
with open(BOOK_ALIGN) as f:
    book_align = json.load(f)


all_alignments = []

for ba in book_align:
    work_name = ba["work"]
    book_n = ba["book"]

    if not ba["latin_available"] or not ba["english_available"]:
        continue

    print(f"\n=== Aligning {work_name} Book {book_n} ===")

    # Gather Latin passages for this book
    latin_passages = [
        p for p in passages_data["passages"]
        if p["work"] == work_name and p["book"] == book_n
    ]
    if not latin_passages:
        print(f"  No Latin passages found")
        continue

    # Gather English paragraphs for this book
    work_key = work_name.lower()
    work_data = mozley["works"].get(work_key)
    if not work_data:
        print(f"  No English data for {work_name}")
        continue

    en_book = None
    for bk in work_data["books"]:
        if str(bk["book"]) == book_n:
            en_book = bk
            break
    if not en_book:
        print(f"  No English book {book_n} for {work_name}")
        continue

    en_paragraphs = []
    for idx, para in enumerate(en_book["paragraphs"]):
        en_paragraphs.append({
            "p_index": idx,
            "text": para.get("text_normalised", para["text"]),
            "text_original": para["text"],
        })

    if not en_paragraphs:
        print(f"  No English paragraphs")
        continue

    print(
        f"  Latin passages: {len(latin_passages)}, "
        f"English paragraphs: {len(en_paragraphs)}"
    )

    # Embed Latin passages
    latin_texts = [p["text"] for p in latin_passages]
    print("  Embedding Latin passages...")
    latin_embs = model.encode(latin_texts, show_progress_bar=True, batch_size=32)

    # Embed English paragraphs
    en_texts = [p["text"] for p in en_paragraphs]
    print("  Embedding English paragraphs...")
    en_embs = model.encode(en_texts, show_progress_bar=True, batch_size=32)

    # Character lengths for length penalty
    latin_lens = [len(p["text"]) for p in latin_passages]
    en_lens = [len(p["text"]) for p in en_paragraphs]

    # Expected character ratio (Latin / English)
    total_lat_chars = sum(latin_lens)
    total_en_chars = sum(en_lens)
    expected_ratio = total_lat_chars / total_en_chars if total_en_chars > 0 else 1.0
    print(f"  Char ratio (Latin/English): {expected_ratio:.2f}")

    # Segmental DP alignment
    print("  Running segmental DP alignment...")
    groups = segmental_dp_align(
        latin_embs, en_embs, latin_lens, en_lens, expected_ratio
    )
    print(f"  DP produced {len(groups)} alignment groups")

    # English paragraph coverage
    en_used = set()
    for lat_start, lat_end, en_start, en_end, score in groups:
        for ej in range(en_start, en_end):
            en_used.add(ej)
    print(
        f"  English paragraphs used: {len(en_used)} / {len(en_paragraphs)} "
        f"({len(en_used) / len(en_paragraphs) * 100:.1f}%)"
    )

    # Record alignments: one record per Latin passage, with group_id
    for group_id, (lat_start, lat_end, en_start, en_end, score) in enumerate(groups):
        en_preview = " | ".join(
            en_paragraphs[ej]["text"][:80] for ej in range(en_start, en_end)
        )
        for li in range(lat_start, lat_end):
            lp = latin_passages[li]
            ep = en_paragraphs[en_start]
            all_alignments.append({
                "work": work_name,
                "book": book_n,
                "latin_first_line": lp["first_line"],
                "latin_last_line": lp["last_line"],
                "latin_cts_work": lp["cts_work"],
                "latin_edition": lp["edition"],
                "english_p_index": ep["p_index"],
                "similarity": round(score, 4),
                "latin_preview": lp["text"][:80],
                "english_preview": en_preview[:80],
                "group_id": group_id,
                "group_size_lat": lat_end - lat_start,
                "group_size_en": en_end - en_start,
            })

    # Print sample
    print("  Sample alignment groups (first 5):")
    for lat_start, lat_end, en_start, en_end, score in groups[:5]:
        lp = latin_passages[lat_start]
        ep = en_paragraphs[en_start]
        print(
            f"    lat[{lat_start}:{lat_end}] -> en[{en_start}:{en_end}]  "
            f"sim={score:.3f}  LAT: {lp['text'][:40]}..."
        )

# Save JSON
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(all_alignments, f, ensure_ascii=False, indent=2)

# Save TSV
with open(OUTPUT_TSV, "w", encoding="utf-8") as f:
    header = (
        "work\tbook\tlatin_first_line\tlatin_last_line\tlatin_edition\t"
        "english_p_index\tsimilarity\n"
    )
    f.write(header)
    for a in all_alignments:
        f.write(
            f"{a['work']}\t{a['book']}\t{a['latin_first_line']}\t"
            f"{a['latin_last_line']}\t{a['latin_edition']}\t"
            f"{a['english_p_index']}\t{a['similarity']}\n"
        )

print(f"\nTotal alignments: {len(all_alignments)}")
print(f"Saved to {OUTPUT} and {OUTPUT_TSV}")

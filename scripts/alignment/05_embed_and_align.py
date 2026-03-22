#!/usr/bin/env python3
"""
Align Greek sections to Booth English paragraphs using Segmental Dynamic
Programming on cross-lingual sentence embeddings.

Algorithm (segmental_dp_align):
  - DP[i][j] = best total score aligning greek[0:i] to english[0:j]
  - Transitions: group g in {1..5} Greek sections onto e in {1..2} English paragraphs
  - Score: 0.8 * cosine_sim(mean_embed_gr, mean_embed_en)
         + 0.2 * exp(-0.5 * ((gr_chars/en_chars)/expected_ratio - 1)^2)
  - Banding: j constrained to +/- max(20, 15% * n_en) of expected diagonal
  - Prefix sums on embeddings and char lengths for O(1) group mean computation

Inputs:
  output/booth_normalised.json   -- from 03_normalise_booth.py
  output/perseus_extracted.json  -- from 02_extract_perseus.py
  output/book_alignment.json     -- from 04_align_books.py

Outputs:
  output/section_alignments.json -- one record per Greek section with group_id
  output/section_alignments.tsv  -- tabular summary

Model: uses custom Ancient Greek embedding (models/ancient-greek-embedding/)
       if available, otherwise paraphrase-multilingual-MiniLM-L12-v2.

See plans/segmental_dp_alignment_plan.md for full algorithm details.
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
BOOTH = PROJECT_ROOT / "build" / "booth_normalised.json"
PERSEUS = PROJECT_ROOT / "build" / "perseus_extracted.json"
BOOK_ALIGN = PROJECT_ROOT / "build" / "book_alignment.json"
OUTPUT = PROJECT_ROOT / "build" / "section_alignments.json"
OUTPUT_TSV = PROJECT_ROOT / "build" / "section_alignments.tsv"

# --- Model selection: prefer custom Ancient Greek model ---
CUSTOM_MODEL = PROJECT_ROOT / "models" / "ancient-greek-embedding"
BASELINE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

for f, name in [
    (BOOTH, "booth_normalised.json"),
    (PERSEUS, "perseus_extracted.json"),
    (BOOK_ALIGN, "book_alignment.json"),
]:
    if not f.exists():
        print(f"Error: {f} not found. Run previous scripts first.")
        raise SystemExit(1)

print("Loading sentence embedding model...")
if CUSTOM_MODEL.exists():
    print(f"  Using custom Ancient Greek model: {CUSTOM_MODEL}")
    model = SentenceTransformer(str(CUSTOM_MODEL))
else:
    print(f"  Custom model not found at {CUSTOM_MODEL}")
    print(f"  Falling back to baseline: {BASELINE_MODEL}")
    model = SentenceTransformer(BASELINE_MODEL)

with open(BOOTH) as f:
    booth = json.load(f)
with open(PERSEUS) as f:
    perseus = json.load(f)
with open(BOOK_ALIGN) as f:
    book_align = json.load(f)


def split_sentences(text, max_len=500):
    """Simple sentence splitter. Keeps chunks under max_len chars."""
    sents = re.split(r"(?<=[.;:!?])\s+", text)
    merged = []
    buf = ""
    for s in sents:
        if len(buf) + len(s) < max_len:
            buf = (buf + " " + s).strip()
        else:
            if buf:
                merged.append(buf)
            buf = s
    if buf:
        merged.append(buf)
    return merged if merged else [text]


all_alignments = []

for ba in book_align:
    book_num = ba["inferred_book_num"]
    if not ba["greek_available"] or book_num is None:
        continue

    print(f"\n=== Aligning Book {book_num} ===")

    # Gather Greek sections for this book
    greek_secs = [s for s in perseus["sections"] if s["book"] == str(book_num)]
    if not greek_secs:
        print(f"  No Greek sections found for book {book_num}")
        continue

    # Gather English paragraphs for this book
    booth_book = None
    for bk in booth["books"]:
        if ba["booth_div1_n"] == bk["div1_n"]:
            booth_book = bk
            break
    if not booth_book:
        continue

    en_paragraphs = []
    for ch in booth_book["chapters"]:
        for p in ch["paragraphs"]:
            en_paragraphs.append(
                {
                    "div2_index": ch["div2_index"],
                    "p_index": p["p_index"],
                    "text": p.get("text_normalised", p["text"]),
                    "text_original": p["text"],
                }
            )

    if not en_paragraphs:
        print(f"  No English paragraphs for book {book_num}")
        continue

    print(
        f"  Greek sections: {len(greek_secs)}, English paragraphs: {len(en_paragraphs)}"
    )

    # Embed Greek sections
    greek_texts = [s["text"] for s in greek_secs]
    print("  Embedding Greek sections...")
    greek_embs = model.encode(greek_texts, show_progress_bar=True, batch_size=32)

    # Embed English paragraphs
    en_texts = [p["text"] for p in en_paragraphs]
    print("  Embedding English paragraphs...")
    en_embs = model.encode(en_texts, show_progress_bar=True, batch_size=32)

    # Compute character lengths for length penalty
    greek_lens = [len(s["text"]) for s in greek_secs]
    en_lens = [len(p["text"]) for p in en_paragraphs]

    # Expected character ratio (Greek / English) for this book
    total_gr_chars = sum(greek_lens)
    total_en_chars = sum(en_lens)
    expected_ratio = total_gr_chars / total_en_chars if total_en_chars > 0 else 1.0
    print(f"  Char ratio (Greek/English): {expected_ratio:.2f}")

    # Auto-scale max_source based on the section ratio for this book
    # If there are 3.8 Greek sections per English paragraph, max_source=5
    # will force bad groupings. Scale to 2x the ratio for safety.
    gr_per_en = len(greek_secs) / max(len(en_paragraphs), 1)
    max_source = max(5, int(gr_per_en * 2))
    if max_source > 5:
        print(f"  Section ratio: {gr_per_en:.1f}, auto max_source={max_source}")

    # Segmental DP alignment
    print("  Running segmental DP alignment...")
    groups = segmental_dp_align(
        greek_embs, en_embs, greek_lens, en_lens, expected_ratio,
        max_source=max_source
    )
    print(f"  DP produced {len(groups)} alignment groups")

    # Build set of English paragraph indices used by DP groups
    en_used = set()
    for gr_start, gr_end, en_start, en_end, score in groups:
        for ej in range(en_start, en_end):
            en_used.add(ej)

    en_skipped = len(en_paragraphs) - len(en_used)
    print(
        f"  English paragraphs: {len(en_used)} matched, "
        f"{en_skipped} unmatched, {len(en_paragraphs)} total"
    )

    # Build a mapping: English paragraph index -> list of (Greek section, score, group_id)
    # A DP group may cover multiple English paragraphs — each must appear in output.
    en_to_greek = {}  # en_idx -> list of alignment records
    for group_id, (gr_start, gr_end, en_start, en_end, score) in enumerate(groups):
        greek_refs = []
        for gi in range(gr_start, gr_end):
            gs = greek_secs[gi]
            greek_refs.append(gs)

        for ej in range(en_start, en_end):
            ep = en_paragraphs[ej]
            if ej not in en_to_greek:
                en_to_greek[ej] = []
            for gs in greek_refs:
                en_to_greek[ej].append({
                    "book": str(book_num),
                    "greek_cts_ref": gs["cts_ref"],
                    "greek_edition": gs["edition"],
                    "booth_div2_index": ep["div2_index"],
                    "booth_p_index": ep["p_index"],
                    "similarity": round(score, 4),
                    "greek_preview": gs["text"][:80],
                    "english_preview": ep["text"][:80],
                    "group_id": group_id,
                    "group_size_gr": gr_end - gr_start,
                    "group_size_en": en_end - en_start,
                    "match_type": "dp_aligned",
                })

    # Build output: one record per English paragraph, in strict order.
    # Paragraphs with Greek matches get those records; unmatched ones get a
    # placeholder. NEVER skip any English paragraph.
    book_alignments = []
    for ej in range(len(en_paragraphs)):
        if ej in en_to_greek:
            book_alignments.extend(en_to_greek[ej])
        else:
            ep = en_paragraphs[ej]
            book_alignments.append({
                "book": str(book_num),
                "greek_cts_ref": None,
                "greek_edition": None,
                "booth_div2_index": ep["div2_index"],
                "booth_p_index": ep["p_index"],
                "similarity": 0.0,
                "greek_preview": "",
                "english_preview": ep["text"][:80],
                "group_id": None,
                "group_size_gr": 0,
                "group_size_en": 1,
                "match_type": "unmatched_english",
            })

    all_alignments.extend(book_alignments)

    if en_skipped > 0:
        print(f"  Added {en_skipped} unmatched English paragraphs to output")

    # Print sample
    print("  Sample alignment groups (first 5):")
    for gr_start, gr_end, en_start, en_end, score in groups[:5]:
        gs = greek_secs[gr_start]
        ep = en_paragraphs[en_start]
        print(
            f"    gr[{gr_start}:{gr_end}] -> en[{en_start}:{en_end}]  "
            f"sim={score:.3f}  GR: {gs['text'][:40]}..."
        )

# Save JSON
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(all_alignments, f, ensure_ascii=False, indent=2)

# Save TSV
with open(OUTPUT_TSV, "w", encoding="utf-8") as f:
    header = "book\tgreek_cts_ref\tgreek_edition\tbooth_div2\tbooth_p\tsimilarity\n"
    f.write(header)
    for a in all_alignments:
        f.write(
            f"{a['book']}\t{a['greek_cts_ref']}\t{a['greek_edition']}\t"
            f"{a['booth_div2_index']}\t{a['booth_p_index']}\t{a['similarity']}\n"
        )

print(f"\nTotal alignments: {len(all_alignments)}")
print(f"Saved to {OUTPUT} and {OUTPUT_TSV}")

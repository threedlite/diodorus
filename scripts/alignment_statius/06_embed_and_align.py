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
import math
import re

import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MOZLEY = PROJECT_ROOT / "output" / "statius" / "mozley_normalised.json"
PASSAGES = PROJECT_ROOT / "output" / "statius" / "latin_passages.json"
BOOK_ALIGN = PROJECT_ROOT / "output" / "statius" / "book_alignment.json"
OUTPUT = PROJECT_ROOT / "output" / "statius" / "section_alignments.json"
OUTPUT_TSV = PROJECT_ROOT / "output" / "statius" / "section_alignments.tsv"

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


def segmental_dp_align(latin_embs, en_embs, latin_lens, en_lens, expected_ratio):
    """
    Segmental Dynamic Programming alignment.

    Aligns variable-size groups of Latin passages (1-5) to English paragraphs
    (1-2), optimizing a global score combining cosine similarity and length
    penalty.

    Args:
        latin_embs: np.array (n_lat, dim) - Latin passage embeddings
        en_embs: np.array (n_en, dim) - English paragraph embeddings
        latin_lens: list[int] - character lengths of Latin passages
        en_lens: list[int] - character lengths of English paragraphs
        expected_ratio: float - expected Latin chars / English chars ratio

    Returns:
        list of (lat_start, lat_end, en_start, en_end, score) tuples
        where lat_start:lat_end and en_start:en_end are half-open ranges
    """
    n_lat = len(latin_embs)
    n_en = len(en_embs)
    dim = latin_embs.shape[1]

    MAX_LAT = 5  # max Latin passages per group
    MAX_EN = 2   # max English paragraphs per group

    # Banding: only allow j within +/- bandwidth of expected position
    bandwidth = max(20, int(n_en * 0.15))

    # Prefix sums for efficient mean embedding computation
    prefix_lat = np.zeros((n_lat + 1, dim), dtype=np.float64)
    for i in range(n_lat):
        prefix_lat[i + 1] = prefix_lat[i] + latin_embs[i]

    prefix_en = np.zeros((n_en + 1, dim), dtype=np.float64)
    for i in range(n_en):
        prefix_en[i + 1] = prefix_en[i] + en_embs[i]

    # Prefix sums for character lengths
    prefix_lat_len = np.zeros(n_lat + 1, dtype=np.float64)
    for i in range(n_lat):
        prefix_lat_len[i + 1] = prefix_lat_len[i] + latin_lens[i]

    prefix_en_len = np.zeros(n_en + 1, dtype=np.float64)
    for i in range(n_en):
        prefix_en_len[i + 1] = prefix_en_len[i] + en_lens[i]

    # DP table: dp[i][j] = best total score aligning latin[0:i] to en[0:j]
    NEG_INF = -1e18
    dp = np.full((n_lat + 1, n_en + 1), NEG_INF, dtype=np.float64)
    dp[0][0] = 0.0

    # Parent table for backtracking
    parent = [[None] * (n_en + 1) for _ in range(n_lat + 1)]

    for i in range(n_lat + 1):
        j_expected = i * (n_en / n_lat) if n_lat > 0 else 0
        j_lo = max(0, int(j_expected - bandwidth))
        j_hi = min(n_en, int(j_expected + bandwidth))

        for j in range(j_lo, j_hi + 1):
            if dp[i][j] == NEG_INF:
                continue

            for g in range(1, MAX_LAT + 1):
                if i + g > n_lat:
                    break
                for e in range(1, MAX_EN + 1):
                    if j + e > n_en:
                        break

                    # Check that target is within band
                    tgt_j_expected = (i + g) * (n_en / n_lat) if n_lat > 0 else 0
                    if abs((j + e) - tgt_j_expected) > bandwidth:
                        continue

                    # Mean embeddings for group
                    mean_lat = (prefix_lat[i + g] - prefix_lat[i]) / g
                    mean_en = (prefix_en[j + e] - prefix_en[j]) / e

                    # Cosine similarity
                    norm_lat = np.linalg.norm(mean_lat)
                    norm_en = np.linalg.norm(mean_en)
                    if norm_lat < 1e-10 or norm_en < 1e-10:
                        cos_sim = 0.0
                    else:
                        cos_sim = float(np.dot(mean_lat, mean_en) / (norm_lat * norm_en))

                    # Length penalty
                    lat_chars = prefix_lat_len[i + g] - prefix_lat_len[i]
                    en_chars = prefix_en_len[j + e] - prefix_en_len[j]
                    if en_chars > 0 and expected_ratio > 0:
                        ratio = (lat_chars / en_chars) / expected_ratio
                        length_pen = math.exp(-0.5 * (ratio - 1.0) ** 2)
                    else:
                        length_pen = 0.5

                    score = 0.8 * cos_sim + 0.2 * length_pen
                    new_score = dp[i][j] + score

                    if new_score > dp[i + g][j + e]:
                        dp[i + g][j + e] = new_score
                        parent[i + g][j + e] = (i, j, g, e)

    # Backtrack from dp[n_lat][n_en]
    if dp[n_lat][n_en] == NEG_INF:
        # Find best reachable endpoint
        best_score = NEG_INF
        best_i, best_j = n_lat, n_en
        for i in range(max(0, n_lat - MAX_LAT), n_lat + 1):
            for j in range(max(0, n_en - MAX_EN), n_en + 1):
                if dp[i][j] > best_score:
                    best_score = dp[i][j]
                    best_i, best_j = i, j
        ci, cj = best_i, best_j
    else:
        ci, cj = n_lat, n_en

    groups = []
    while ci > 0 and cj > 0 and parent[ci][cj] is not None:
        prev_i, prev_j, g, e = parent[ci][cj]
        # Compute the score for this group
        mean_lat = (prefix_lat[ci] - prefix_lat[prev_i]) / g
        mean_en = (prefix_en[cj] - prefix_en[prev_j]) / e
        norm_lat = np.linalg.norm(mean_lat)
        norm_en = np.linalg.norm(mean_en)
        if norm_lat < 1e-10 or norm_en < 1e-10:
            cos_sim = 0.0
        else:
            cos_sim = float(np.dot(mean_lat, mean_en) / (norm_lat * norm_en))
        groups.append((prev_i, ci, prev_j, cj, cos_sim))
        ci, cj = prev_i, prev_j

    groups.reverse()
    return groups


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

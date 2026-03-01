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
import math
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BOOTH = PROJECT_ROOT / "output" / "booth_normalised.json"
PERSEUS = PROJECT_ROOT / "output" / "perseus_extracted.json"
BOOK_ALIGN = PROJECT_ROOT / "output" / "book_alignment.json"
OUTPUT = PROJECT_ROOT / "output" / "section_alignments.json"
OUTPUT_TSV = PROJECT_ROOT / "output" / "section_alignments.tsv"

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


def segmental_dp_align(greek_embs, en_embs, greek_lens, en_lens, expected_ratio):
    """
    Segmental Dynamic Programming alignment.

    Aligns variable-size groups of Greek sections (1-5) to English paragraphs
    (1-2), optimizing a global score combining cosine similarity and length
    penalty.

    Args:
        greek_embs: np.array (n_gr, dim) - Greek section embeddings
        en_embs: np.array (n_en, dim) - English paragraph embeddings
        greek_lens: list[int] - character lengths of Greek sections
        en_lens: list[int] - character lengths of English paragraphs
        expected_ratio: float - expected Greek chars / English chars ratio

    Returns:
        list of (gr_start, gr_end, en_start, en_end, score) tuples
        where gr_start:gr_end and en_start:en_end are half-open ranges
    """
    n_gr = len(greek_embs)
    n_en = len(en_embs)
    dim = greek_embs.shape[1]

    MAX_GR = 5  # max Greek sections per group
    MAX_EN = 2  # max English paragraphs per group

    # Banding: only allow j within ±bandwidth of expected position
    bandwidth = max(20, int(n_en * 0.15))

    # Prefix sums for efficient mean embedding computation
    # prefix_gr[i] = sum of greek_embs[0:i], so mean(a:b) = (prefix[b] - prefix[a]) / (b - a)
    prefix_gr = np.zeros((n_gr + 1, dim), dtype=np.float64)
    for i in range(n_gr):
        prefix_gr[i + 1] = prefix_gr[i] + greek_embs[i]

    prefix_en = np.zeros((n_en + 1, dim), dtype=np.float64)
    for i in range(n_en):
        prefix_en[i + 1] = prefix_en[i] + en_embs[i]

    # Prefix sums for character lengths
    prefix_gr_len = np.zeros(n_gr + 1, dtype=np.float64)
    for i in range(n_gr):
        prefix_gr_len[i + 1] = prefix_gr_len[i] + greek_lens[i]

    prefix_en_len = np.zeros(n_en + 1, dtype=np.float64)
    for i in range(n_en):
        prefix_en_len[i + 1] = prefix_en_len[i] + en_lens[i]

    # DP table: dp[i][j] = best total score aligning greek[0:i] to en[0:j]
    NEG_INF = -1e18
    dp = np.full((n_gr + 1, n_en + 1), NEG_INF, dtype=np.float64)
    dp[0][0] = 0.0

    # Parent table for backtracking: parent[i][j] = (prev_i, prev_j, g, e)
    parent = [[None] * (n_en + 1) for _ in range(n_gr + 1)]

    for i in range(n_gr + 1):
        # Expected English position for this Greek position
        j_expected = i * (n_en / n_gr) if n_gr > 0 else 0
        j_lo = max(0, int(j_expected - bandwidth))
        j_hi = min(n_en, int(j_expected + bandwidth))

        for j in range(j_lo, j_hi + 1):
            if dp[i][j] == NEG_INF:
                continue

            # Try all group sizes
            for g in range(1, MAX_GR + 1):
                if i + g > n_gr:
                    break
                for e in range(1, MAX_EN + 1):
                    if j + e > n_en:
                        break

                    # Check that target (i+g, j+e) is within band
                    tgt_j_expected = (i + g) * (n_en / n_gr) if n_gr > 0 else 0
                    if abs((j + e) - tgt_j_expected) > bandwidth:
                        continue

                    # Mean Greek embedding for group
                    mean_gr = (prefix_gr[i + g] - prefix_gr[i]) / g
                    # Mean English embedding for group
                    mean_en = (prefix_en[j + e] - prefix_en[j]) / e

                    # Cosine similarity
                    norm_gr = np.linalg.norm(mean_gr)
                    norm_en = np.linalg.norm(mean_en)
                    if norm_gr < 1e-10 or norm_en < 1e-10:
                        cos_sim = 0.0
                    else:
                        cos_sim = float(np.dot(mean_gr, mean_en) / (norm_gr * norm_en))

                    # Length penalty: Gaussian centered on expected_ratio
                    gr_chars = prefix_gr_len[i + g] - prefix_gr_len[i]
                    en_chars = prefix_en_len[j + e] - prefix_en_len[j]
                    if en_chars > 0 and expected_ratio > 0:
                        ratio = (gr_chars / en_chars) / expected_ratio
                        length_pen = math.exp(-0.5 * (ratio - 1.0) ** 2)
                    else:
                        length_pen = 0.5

                    score = 0.8 * cos_sim + 0.2 * length_pen
                    new_score = dp[i][j] + score

                    if new_score > dp[i + g][j + e]:
                        dp[i + g][j + e] = new_score
                        parent[i + g][j + e] = (i, j, g, e)

    # Backtrack from dp[n_gr][n_en]
    # If dp[n_gr][n_en] is unreachable, find best reachable endpoint
    if dp[n_gr][n_en] == NEG_INF:
        # Find best (i, j) near the end
        best_score = NEG_INF
        best_i, best_j = n_gr, n_en
        for i in range(max(0, n_gr - MAX_GR), n_gr + 1):
            for j in range(max(0, n_en - MAX_EN), n_en + 1):
                if dp[i][j] > best_score:
                    best_score = dp[i][j]
                    best_i, best_j = i, j
        ci, cj = best_i, best_j
    else:
        ci, cj = n_gr, n_en

    groups = []
    while ci > 0 and cj > 0 and parent[ci][cj] is not None:
        prev_i, prev_j, g, e = parent[ci][cj]
        # Compute the score for this group
        mean_gr = (prefix_gr[ci] - prefix_gr[prev_i]) / g
        mean_en = (prefix_en[cj] - prefix_en[prev_j]) / e
        norm_gr = np.linalg.norm(mean_gr)
        norm_en = np.linalg.norm(mean_en)
        if norm_gr < 1e-10 or norm_en < 1e-10:
            cos_sim = 0.0
        else:
            cos_sim = float(np.dot(mean_gr, mean_en) / (norm_gr * norm_en))
        groups.append((prev_i, ci, prev_j, cj, cos_sim))
        ci, cj = prev_i, prev_j

    groups.reverse()
    return groups


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

    # Segmental DP alignment
    print("  Running segmental DP alignment...")
    groups = segmental_dp_align(
        greek_embs, en_embs, greek_lens, en_lens, expected_ratio
    )
    print(f"  DP produced {len(groups)} alignment groups")

    # Compute English paragraph coverage
    en_used = set()
    for gr_start, gr_end, en_start, en_end, score in groups:
        for ej in range(en_start, en_end):
            en_used.add(ej)
    print(
        f"  English paragraphs used: {len(en_used)} / {len(en_paragraphs)} "
        f"({len(en_used)/len(en_paragraphs)*100:.1f}%)"
    )

    # Record alignments: one record per Greek section, with group_id
    for group_id, (gr_start, gr_end, en_start, en_end, score) in enumerate(groups):
        # For English: combine text from all paragraphs in the group
        en_preview = " | ".join(
            en_paragraphs[ej]["text"][:80] for ej in range(en_start, en_end)
        )
        for gi in range(gr_start, gr_end):
            gs = greek_secs[gi]
            # Point each Greek section to the first English paragraph in the group
            # (primary match); store full group info for downstream use
            ep = en_paragraphs[en_start]
            all_alignments.append(
                {
                    "book": str(book_num),
                    "greek_cts_ref": gs["cts_ref"],
                    "greek_edition": gs["edition"],
                    "booth_div2_index": ep["div2_index"],
                    "booth_p_index": ep["p_index"],
                    "similarity": round(score, 4),
                    "greek_preview": gs["text"][:80],
                    "english_preview": en_preview[:80],
                    "group_id": group_id,
                    "group_size_gr": gr_end - gr_start,
                    "group_size_en": en_end - en_start,
                }
            )

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

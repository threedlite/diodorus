# Segmental Dynamic Programming Alignment

**Status:** IMPLEMENTED 2026-03-01

## Overview

Section-level alignment of 8,123 Greek sections to 3,216 English paragraphs across 15 books of Diodorus Siculus. Uses Segmental DP to group variable numbers of Greek sections (1-5) onto English paragraphs (1-2), optimizing a global score.

## File

- `scripts/alignment/05_embed_and_align.py` — `segmental_dp_align()` function (lines 83-222)

## Algorithm

### State
`DP[i][j]` = best total score for aligning Greek sections `0..i-1` to English paragraphs `0..j-1`

### Transitions
For each state `(i, j)`, try all group sizes:
- `g` in {1, 2, 3, 4, 5} Greek sections consumed
- `e` in {1, 2} English paragraphs consumed
- Transition: `DP[i+g][j+e] = max(DP[i+g][j+e], DP[i][j] + score(gr[i:i+g], en[j:j+e]))`

### Scoring Function
```
score(gr_group, en_group) = 0.8 * cosine_sim(mean_embed_gr, mean_embed_en) + 0.2 * length_penalty
```
Where:
- `mean_embed_gr` = average of embeddings for Greek sections in the group
- `mean_embed_en` = average of embeddings for English paragraphs in the group
- `length_penalty` = exp(-0.5 * ((gr_chars / en_chars) / expected_ratio - 1)^2) — Gaussian penalty centered on the expected character ratio per book

### Efficient Computation
- **Prefix sums** on embedding arrays: `prefix_gr[i] = sum(greek_embs[0:i])`, so `mean(greek_embs[a:b]) = (prefix_gr[b] - prefix_gr[a]) / (b - a)`
- **Banding**: Only allow `j` within +/-bandwidth of the expected position `j_expected = i * (n_en / n_gr)`. Bandwidth = `max(20, n_en * 0.15)`.
- **Char length arrays** precomputed for length penalty

### Backtracking
`parent[i][j] = (prev_i, prev_j, g, e)` reconstructs the alignment path.

### Output Format
Each alignment record has `group_id`, `group_size_gr`, `group_size_en` fields. All existing fields (book, greek_cts_ref, greek_edition, booth_div2_index, booth_p_index, similarity, greek_preview, english_preview) are preserved for compatibility with scripts 06 and 07.

## Implementation Details

1. `segmental_dp_align()` helper function returns `(gr_start, gr_end, en_start, en_end, score)` tuples
2. Per-book character ratio computed for length penalty
3. Record creation emits one record per Greek section, all sections in a group sharing the same `group_id`
4. Cosine similarity computed on-the-fly via prefix sums (no precomputed similarity matrix needed)

## Results (2026-03-01)

| Metric | Value |
|---|---|
| English paragraphs used | 3,216 / 3,216 (100%) |
| Mean combined score | 0.412 |
| High confidence (>=0.6) | 1,211 (14.9%) |
| Medium confidence (0.3-0.6) | 4,821 (59.3%) |
| Low confidence (<0.3) | 2,091 (25.7%) |

### Per-Book Details

| Book | Greek secs | English paras | DP groups | EN coverage | Character ratio |
|---|---|---|---|---|---|
| 1 | 723 | 216 | 216 | 100% | 0.94 |
| 2 | 388 | 163 | 161 | 100% | 0.92 |
| 3 | 434 | 231 | 224 | 100% | 0.91 |
| 4 | 496 | 271 | 265 | 100% | 0.90 |
| 5 | 424 | 272 | 264 | 100% | 0.92 |
| 11 | 491 | 266 | 258 | 100% | 0.88 |
| 12 | 401 | 130 | 129 | 100% | 0.92 |
| 13 | 691 | 180 | 180 | 100% | 0.86 |
| 14 | 694 | 212 | 212 | 100% | 0.87 |
| 15 | 448 | 163 | 163 | 100% | 0.87 |
| 16 | 513 | 268 | 251 | 100% | 0.85 |
| 17 | 719 | 269 | 267 | 100% | 0.86 |
| 18 | 428 | 131 | 130 | 100% | 0.87 |
| 19 | 657 | 276 | 271 | 100% | 0.87 |
| 20 | 616 | 168 | 168 | 100% | 0.85 |

### Observations

- Later historical books (11-16) show higher per-group similarity (many 0.7-0.9 scores), likely because the narrative content is more concrete (named people, battles, dates)
- Books 1 and 17 have higher Greek:English section ratios (3.3:1 and 2.7:1), requiring more 5:1 grouping, which dilutes mean embeddings
- Character ratios are consistently 0.85-0.94 across all books (Greek slightly shorter than English, likely due to English translation expansion)
- Total runtime for DP alignment step: ~15 min (embedding ~12 min, DP computation ~3 min)

## Verification

1. Run `python scripts/alignment/05_embed_and_align.py` — completes in ~15 min total
2. Check output: `jq '.[0:5]' output/section_alignments.json` — verify all English paragraphs appear
3. Run `python scripts/alignment/06_entity_anchors.py` then `python scripts/alignment/07_generate_outputs.py`
4. Check `output/alignment_report.md` — mean combined score should be ~0.412
5. Spot-check: high-similarity pairs should show matching content (e.g., same historical events)

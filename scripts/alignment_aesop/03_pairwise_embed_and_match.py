#!/usr/bin/env python3
"""
Pairwise embedding matching for Aesop's Fables.

Instead of sequential DP, embeds all Greek fables and all English fables,
computes a full cosine similarity matrix, and does greedy 1-to-1 matching.

Inputs:
  output/aesop/greek_fables.json   -- from 01
  output/aesop/english_fables.json -- from 02

Outputs:
  output/aesop/section_alignments.json
  output/aesop/section_alignments.tsv
"""

import json
import sys
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Import shared alignment algorithms
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from align_core import pairwise_match

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GREEK = PROJECT_ROOT / "build" / "aesop" / "greek_fables.json"
ENGLISH = PROJECT_ROOT / "build" / "aesop" / "english_fables.json"
OUTPUT = PROJECT_ROOT / "build" / "aesop" / "section_alignments.json"
OUTPUT_TSV = PROJECT_ROOT / "build" / "aesop" / "section_alignments.tsv"

CUSTOM_MODEL = PROJECT_ROOT / "models" / "ancient-greek-embedding"
BASELINE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

for f, name in [(GREEK, "greek_fables.json"), (ENGLISH, "english_fables.json")]:
    if not f.exists():
        print(f"Error: {f} not found. Run previous steps first.")
        raise SystemExit(1)

with open(GREEK) as f:
    greek_fables = json.load(f)
with open(ENGLISH) as f:
    english_fables = json.load(f)

print(f"Greek fables: {len(greek_fables)}")
print(f"English fables: {len(english_fables)}")

# Load model
print("Loading sentence embedding model...")
if CUSTOM_MODEL.exists():
    print(f"  Using custom Ancient Greek model: {CUSTOM_MODEL}")
    model = SentenceTransformer(str(CUSTOM_MODEL))
else:
    print(f"  Custom model not found, using baseline: {BASELINE_MODEL}")
    model = SentenceTransformer(BASELINE_MODEL)

# Embed
print("Embedding Greek fables...")
greek_texts = [f["text"] for f in greek_fables]
greek_embs = model.encode(greek_texts, show_progress_bar=True, batch_size=32)

print("Embedding English fables...")
english_texts = [f["text"] for f in english_fables]
english_embs = model.encode(english_texts, show_progress_bar=True, batch_size=32)

# Pairwise match: Greek as source, English as target
# many_to_one=True because Greek has variant fables (4, 4b, 4c) that are
# alternate versions of the same story and should all match the same English fable
print("Running pairwise matching (many-to-one)...")
matches, sim_matrix = pairwise_match(greek_embs, english_embs, min_similarity=0.3,
                                      many_to_one=True)

matched = sum(1 for m in matches if m["match_type"] == "pairwise_top1")
unmatched = sum(1 for m in matches if m["match_type"] == "unmatched")
print(f"  Matched: {matched}, Unmatched: {unmatched}")

if matched > 0:
    matched_sims = [m["similarity"] for m in matches if m["match_type"] == "pairwise_top1"]
    print(f"  Matched similarity: min={min(matched_sims):.3f}, "
          f"max={max(matched_sims):.3f}, mean={sum(matched_sims)/len(matched_sims):.3f}")

# Build output records compatible with alignment_quality_map.py
alignments = []
for m in matches:
    gf = greek_fables[m["source_idx"]]

    rec = {
        "book": "fables",
        "greek_cts_ref": gf["fabula_n"],
        "greek_edition": gf["edition"],
        "similarity": round(m["similarity"], 4),
        "greek_preview": gf["text"][:80],
        "group_id": m["source_idx"],
        "group_size_gr": 1,
        "group_size_en": 1 if m["target_idx"] is not None else 0,
        "match_type": m["match_type"],
        "runner_up_similarity": round(m["runner_up_similarity"], 4),
    }

    if m["target_idx"] is not None:
        ef = english_fables[m["target_idx"]]
        rec["english_fable_index"] = m["target_idx"]
        rec["english_title"] = ef["title"]
        rec["english_preview"] = ef["text"][:80]
    else:
        rec["english_fable_index"] = None
        rec["english_title"] = ""
        rec["english_preview"] = ""

    alignments.append(rec)

# Save JSON
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(alignments, f, ensure_ascii=False, indent=2)

# Save TSV
with open(OUTPUT_TSV, "w", encoding="utf-8") as f:
    header = ("greek_fabula_n\tgreek_edition\tenglish_fable_index\t"
              "english_title\tsimilarity\tmatch_type\n")
    f.write(header)
    for a in alignments:
        f.write(f"{a['greek_cts_ref']}\t{a['greek_edition']}\t"
                f"{a.get('english_fable_index','')}\t"
                f"{a.get('english_title','')}\t"
                f"{a['similarity']}\t{a['match_type']}\n")

# Save similarity matrix for analysis
np.savez_compressed(
    PROJECT_ROOT / "build" / "aesop" / "similarity_matrix.npz",
    matrix=sim_matrix,
)

print(f"\nSaved: {OUTPUT}")
print(f"Saved: {OUTPUT_TSV}")
print(f"Saved: output/aesop/similarity_matrix.npz ({sim_matrix.shape})")

#!/usr/bin/env python3
"""
Generate final outputs for Aesop alignment.

Outputs:
  output/aesop/alignment_aesop_f1k.xml   — TEI standoff alignment
  output/aesop/alignment_aesop_f1k.tsv   — tabular format
  output/aesop/alignment_report.md        — quality report
"""

import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALIGNMENTS = PROJECT_ROOT / "build" / "aesop" / "entity_validated_alignments.json"
OUT_XML = PROJECT_ROOT / "build" / "aesop" / "alignment_aesop_f1k.xml"
OUT_TSV = PROJECT_ROOT / "build" / "aesop" / "alignment_aesop_f1k.tsv"
OUT_REPORT = PROJECT_ROOT / "build" / "aesop" / "alignment_report.md"

if not ALIGNMENTS.exists():
    print(f"Error: {ALIGNMENTS} not found. Run 04_entity_anchors.py first.")
    raise SystemExit(1)

with open(ALIGNMENTS) as f:
    alignments = json.load(f)

custom_model_path = PROJECT_ROOT / "models" / "ancient-greek-embedding"
model_name = (
    "Custom Ancient Greek embedding (xlm-roberta-base fine-tuned)"
    if custom_model_path.exists()
    else "paraphrase-multilingual-MiniLM-L12-v2 (generic baseline)"
)

# ---- 1. TEI Standoff XML ----
xml_lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<TEI xmlns="http://www.tei-c.org/ns/1.0">',
    "  <teiHeader>",
    "    <fileDesc>",
    "      <titleStmt>",
    "        <title>Alignment: Townsend English / First1KGreek Aesop Fabulae</title>",
    "      </titleStmt>",
    "      <publicationStmt><p>Generated automatically.</p></publicationStmt>",
    "      <sourceDesc>",
    '        <bibl xml:id="townsend">George Fyler Townsend, Three Hundred Aesop\'s Fables (1867). Public domain. Source: Project Gutenberg #21.</bibl>',
    '        <bibl xml:id="f1k">First1KGreek tlg0096.tlg002</bibl>',
    "      </sourceDesc>",
    "    </fileDesc>",
    "  </teiHeader>",
    "  <text>",
    "    <body>",
    '      <linkGrp type="alignment" subtype="fables">',
]

for a in alignments:
    if a["match_type"] == "unmatched":
        continue
    src = f"townsend:fable[{a.get('english_fable_index', '')}]"
    tgt = f"urn:cts:greekLit:tlg0096.tlg002.{a['greek_edition']}:{a['greek_cts_ref']}"
    conf = a.get("combined_score", a["similarity"])
    title = a.get("english_title", "").replace('"', "&quot;").replace("&", "&amp;")
    xml_lines.append(
        f'        <link target="{src} {tgt}" '
        f'ana="confidence:{conf}" n="{title}"/>'
    )

xml_lines += [
    "      </linkGrp>",
    "    </body>",
    "  </text>",
    "</TEI>",
]

with open(OUT_XML, "w", encoding="utf-8") as f:
    f.write("\n".join(xml_lines))

# ---- 2. TSV ----
fields = [
    "greek_fabula_n", "greek_edition", "english_fable_index",
    "english_title", "embedding_sim", "entity_score", "combined_score",
    "match_type",
]
with open(OUT_TSV, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
    writer.writeheader()
    for a in alignments:
        writer.writerow({
            "greek_fabula_n": a["greek_cts_ref"],
            "greek_edition": a["greek_edition"],
            "english_fable_index": a.get("english_fable_index", ""),
            "english_title": a.get("english_title", ""),
            "embedding_sim": a["similarity"],
            "entity_score": a.get("entity_overlap_score", ""),
            "combined_score": a.get("combined_score", a["similarity"]),
            "match_type": a["match_type"],
        })

# ---- 3. Quality Report ----
total = len(alignments)
matched = [a for a in alignments if a["match_type"] == "pairwise_top1"]
unmatched = [a for a in alignments if a["match_type"] == "unmatched"]
scores = [a.get("combined_score", a["similarity"]) for a in alignments]
matched_scores = [a.get("combined_score", a["similarity"]) for a in matched]
high = sum(1 for s in scores if s >= 0.6)
med = sum(1 for s in scores if 0.3 <= s < 0.6)
low = sum(1 for s in scores if s < 0.3)
avg_score = sum(scores) / len(scores) if scores else 0
avg_matched = sum(matched_scores) / len(matched_scores) if matched_scores else 0

report = f"""# Aesop Fables Alignment Quality Report

**Date:** {date.today().isoformat()}
**Greek source:** First1KGreek tlg0096.tlg002 (Aesop, Fabulae)
**English source:** George Fyler Townsend (1867), Project Gutenberg #21
**English license:** Public domain
**Embedding model:** {model_name}
**Alignment method:** Pairwise embedding matching (not sequential DP)

## Coverage

- **Greek fables:** {total}
- **Matched to English:** {len(matched)} ({len(matched)/total*100:.0f}%)
- **Unmatched (no English equivalent):** {len(unmatched)} ({len(unmatched)/total*100:.0f}%)

## Confidence Distribution (all {total} Greek fables)

| Band | Count | Percentage |
|---|---|---|
| High (>= 0.6) | {high} | {high/total*100:.1f}% |
| Medium (0.3-0.6) | {med} | {med/total*100:.1f}% |
| Low (< 0.3) | {low} | {low/total*100:.1f}% |

- **Mean combined score (all):** {avg_score:.3f}
- **Mean combined score (matched only):** {avg_matched:.3f}

## Methodology

1. Greek fables extracted from First1KGreek TEI (tlg0096.tlg002)
2. English fables extracted from Gutenberg #21 (Townsend, 1867)
3. All fables embedded with cross-lingual sentence embedding model
4. Full cosine similarity matrix computed (Greek x English)
5. Greedy 1-to-1 matching with minimum similarity threshold (0.3)
6. Validation via animal/character name matching (Greek -> English)
7. Combined score: 70% embedding similarity + 30% entity overlap

## Output Files

- `alignment_aesop_f1k.xml` — TEI standoff alignment
- `alignment_aesop_f1k.tsv` — tabular format with scores
- `entity_validated_alignments.json` — full alignment data
- `similarity_matrix.npz` — full pairwise similarity matrix
- `alignment_quality_map_aesop.svg` — visual heatmap
"""

with open(OUT_REPORT, "w", encoding="utf-8") as f:
    f.write(report)

print(f"Generated:")
print(f"  {OUT_XML}")
print(f"  {OUT_TSV}")
print(f"  {OUT_REPORT}")

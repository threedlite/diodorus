#!/usr/bin/env python3
"""
Generate final outputs for Marcus Aurelius alignment.

Outputs:
  output/marcus/alignment_marcus_perseus.xml  — TEI standoff
  output/marcus/alignment_marcus_perseus.tsv  — tabular
  output/marcus/alignment_report.md           — quality report
"""

import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALIGNMENTS = PROJECT_ROOT / "build" / "marcus" / "entity_validated_alignments.json"
OUT_XML = PROJECT_ROOT / "build" / "marcus" / "alignment_marcus_perseus.xml"
OUT_TSV = PROJECT_ROOT / "build" / "marcus" / "alignment_marcus_perseus.tsv"
OUT_REPORT = PROJECT_ROOT / "build" / "marcus" / "alignment_report.md"

if not ALIGNMENTS.exists():
    print(f"Error: {ALIGNMENTS} not found")
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
    "        <title>Alignment: Long English (1862) / Perseus Greek Marcus Aurelius</title>",
    "      </titleStmt>",
    "      <publicationStmt><p>Generated automatically.</p></publicationStmt>",
    "      <sourceDesc>",
    '        <bibl xml:id="long">George Long, Thoughts of Marcus Aurelius Antoninus (1862). Public domain. Source: Project Gutenberg #15877.</bibl>',
    '        <bibl xml:id="perseus">PerseusDL canonical-greekLit tlg0562.tlg001</bibl>',
    "      </sourceDesc>",
    "    </fileDesc>",
    "  </teiHeader>",
    "  <text>",
    "    <body>",
]

by_book = defaultdict(list)
for a in alignments:
    by_book[a["book"]].append(a)

for book_num in sorted(by_book.keys(), key=int):
    book_aligns = by_book[book_num]
    xml_lines.append(f'      <linkGrp type="alignment" subtype="book-{book_num}">')
    for a in book_aligns:
        src = f"long:book-{book_num}/section-{a.get('english_section', '')}"
        if a.get("greek_cts_ref") is not None:
            tgt = f"urn:cts:greekLit:tlg0562.tlg001.{a['greek_edition']}:{a['greek_cts_ref']}"
            conf = a.get("combined_score", a["similarity"])
            xml_lines.append(f'        <link target="{src} {tgt}" ana="confidence:{conf}"/>')
        else:
            xml_lines.append(f'        <link target="{src}" ana="confidence:0 match:unmatched_english"/>')
    xml_lines.append("      </linkGrp>")

xml_lines += ["    </body>", "  </text>", "</TEI>"]

with open(OUT_XML, "w", encoding="utf-8") as f:
    f.write("\n".join(xml_lines))

# ---- 2. TSV ----
fields = ["book", "greek_cts_ref", "greek_edition", "english_cts_ref",
          "embedding_sim", "entity_score", "combined_score", "match_type"]
with open(OUT_TSV, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
    writer.writeheader()
    for a in alignments:
        writer.writerow({
            "book": a["book"],
            "greek_cts_ref": a.get("greek_cts_ref", ""),
            "greek_edition": a.get("greek_edition", ""),
            "english_cts_ref": a.get("english_cts_ref", ""),
            "embedding_sim": a["similarity"],
            "entity_score": a.get("entity_overlap_score", ""),
            "combined_score": a.get("combined_score", a["similarity"]),
            "match_type": a.get("match_type", ""),
        })

# ---- 3. Quality Report ----
total = len(alignments)
scores = [a.get("combined_score", a["similarity"]) for a in alignments]
high = sum(1 for s in scores if s >= 0.6)
med = sum(1 for s in scores if 0.3 <= s < 0.6)
low = sum(1 for s in scores if s < 0.3)
avg_score = sum(scores) / len(scores) if scores else 0
unmatched = sum(1 for a in alignments if a.get("match_type") == "unmatched_english")

report = f"""# Marcus Aurelius Alignment Quality Report

**Date:** {date.today().isoformat()}
**Greek source:** Perseus canonical-greekLit tlg0562.tlg001 (Ad Se Ipsum, ed. Leopold/Teubner 1908)
**English source:** George Long (1862), Project Gutenberg #15877
**English license:** Public domain
**Embedding model:** {model_name}

## Coverage

- **Total alignment records:** {total}
- **Greek sections:** {total - unmatched}
- **Unmatched English sections:** {unmatched}

## Confidence Distribution

| Band | Count | Percentage |
|---|---|---|
| High (>= 0.6) | {high} | {high/total*100:.1f}% |
| Medium (0.3-0.6) | {med} | {med/total*100:.1f}% |
| Low (< 0.3) | {low} | {low/total*100:.1f}% |

- **Mean combined score:** {avg_score:.3f}

## Output Files

- `alignment_marcus_perseus.xml` — TEI standoff alignment
- `alignment_marcus_perseus.tsv` — tabular format
- `entity_validated_alignments.json` — full alignment data
- `alignment_quality_map_marcus.svg` — visual heatmap
"""

with open(OUT_REPORT, "w", encoding="utf-8") as f:
    f.write(report)

print(f"Generated:")
print(f"  {OUT_XML}")
print(f"  {OUT_TSV}")
print(f"  {OUT_REPORT}")

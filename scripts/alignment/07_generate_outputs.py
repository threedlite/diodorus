#!/usr/bin/env python3
"""
Generate final output files:
  1. TEI standoff alignment XML
  2. Final TSV with all scores
  3. Quality report
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALIGNMENTS = PROJECT_ROOT / "output" / "entity_validated_alignments.json"
OUT_XML = PROJECT_ROOT / "output" / "alignment_booth_perseus.xml"
OUT_TSV = PROJECT_ROOT / "output" / "alignment_booth_perseus.tsv"
OUT_REPORT = PROJECT_ROOT / "output" / "alignment_report.md"

if not ALIGNMENTS.exists():
    print(f"Error: {ALIGNMENTS} not found. Run 06_entity_anchors.py first.")
    raise SystemExit(1)

with open(ALIGNMENTS) as f:
    alignments = json.load(f)

# Detect which model was used by checking if custom model dir exists
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
    "        <title>Alignment: Booth English (1700) / Perseus Greek Diodorus Siculus</title>",
    "      </titleStmt>",
    "      <publicationStmt><p>Generated automatically.</p></publicationStmt>",
    "      <sourceDesc>",
    '        <bibl xml:id="booth">G. Booth, The Historical Library (1700). Source: EEBO-TCP (Early English Books Online Text Creation Partnership), OTA A36034. Licensed under CC0 1.0 Universal (public domain dedication).</bibl>',
    '        <bibl xml:id="perseus">PerseusDL canonical-greekLit tlg0060.tlg001</bibl>',
    "      </sourceDesc>",
    "    </fileDesc>",
    "  </teiHeader>",
    "  <text>",
    "    <body>",
]

by_book = defaultdict(list)
for a in alignments:
    by_book[a["book"]].append(a)

for book_num in sorted(by_book.keys(), key=lambda x: int(x) if x.isdigit() else 0):
    book_aligns = by_book[book_num]
    xml_lines.append(f'      <linkGrp type="alignment" subtype="book-{book_num}">')
    for a in book_aligns:
        src = f"booth:div1[@n='{book_num}']/div2[{a['booth_div2_index']}]/p[{a['booth_p_index']}]"
        tgt = f"urn:cts:greekLit:tlg0060.tlg001.{a['greek_edition']}:{a['greek_cts_ref']}"
        conf = a.get("combined_score", a["similarity"])
        xml_lines.append(
            f'        <link target="{src} {tgt}" ' f'ana="confidence:{conf}"/>'
        )
    xml_lines.append("      </linkGrp>")

xml_lines += [
    "    </body>",
    "  </text>",
    "</TEI>",
]

with open(OUT_XML, "w", encoding="utf-8") as f:
    f.write("\n".join(xml_lines))

# ---- 2. TSV ----
TSV_FIELDS = [
    "book", "greek_cts_ref", "greek_edition", "booth_div2", "booth_p",
    "embedding_sim", "entity_score", "combined_score",
]
with open(OUT_TSV, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=TSV_FIELDS, delimiter="\t")
    writer.writeheader()
    for a in alignments:
        writer.writerow({
            "book": a["book"],
            "greek_cts_ref": a["greek_cts_ref"],
            "greek_edition": a["greek_edition"],
            "booth_div2": a["booth_div2_index"],
            "booth_p": a["booth_p_index"],
            "embedding_sim": a["similarity"],
            "entity_score": a.get("entity_overlap_score", ""),
            "combined_score": a.get("combined_score", a["similarity"]),
        })

# ---- 3. Quality Report ----
total = len(alignments)
scores = [a.get("combined_score", a["similarity"]) for a in alignments]
high = sum(1 for s in scores if s >= 0.6)
med = sum(1 for s in scores if 0.3 <= s < 0.6)
low = sum(1 for s in scores if s < 0.3)
books_covered = sorted(set(a["book"] for a in alignments))
avg_score = sum(scores) / len(scores) if scores else 0

report = f"""# Alignment Quality Report

**Date:** {date.today().isoformat()}
**English source:** G. Booth (1700) — The Historical Library of Diodorus the Sicilian
**English transcription:** EEBO-TCP (Early English Books Online Text Creation Partnership), OTA A36034
**English transcription license:** CC0 1.0 Universal (public domain dedication)
**Greek source:** Perseus canonical-greekLit tlg0060.tlg001
**Embedding model:** {model_name}

## Coverage

- **Total alignments:** {total}
- **Books aligned:** {', '.join(books_covered)}
- **Books NOT aligned (no Greek or no English):** check book_alignment.json

## Confidence Distribution

| Band | Count | Percentage |
|---|---|---|
| High (>= 0.6) | {high} | {high/total*100:.1f}% |
| Medium (0.3-0.6) | {med} | {med/total*100:.1f}% |
| Low (< 0.3) -- needs review | {low} | {low/total*100:.1f}% |

- **Mean combined score:** {avg_score:.3f}

## Methodology

1. Both TEI XML sources parsed with lxml
2. Booth text normalised (archaic spelling regularisation)
3. Book-level alignment via heading matching and `n=` attributes
4. Section-level alignment via segmental dynamic programming on cross-lingual sentence embeddings (groups 1-5 Greek sections onto 1-2 English paragraphs)
5. Validation via cross-lingual named-entity fuzzy matching (Greek transliteration -> English)
6. Combined score: 70% embedding similarity + 30% entity overlap

## Output Files

- `alignment_booth_perseus.xml` -- TEI standoff alignment
- `alignment_booth_perseus.tsv` -- tabular format with scores
- `entity_validated_alignments.json` -- full alignment data with all metadata
- `book_alignment.json` -- book-level correspondence table
- `tlg0060.tlg001.perseus-eng80.xml` -- Perseus-compatible TEI English translation (step 8)
- `__cts__eng80_fragment.xml` -- CTS catalog entry for the translation (step 8)
"""

with open(OUT_REPORT, "w", encoding="utf-8") as f:
    f.write(report)

print(f"Generated:")
print(f"  {OUT_XML}")
print(f"  {OUT_TSV}")
print(f"  {OUT_REPORT}")

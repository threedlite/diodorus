#!/usr/bin/env python3
"""
Generic output generation: TEI XML, TSV, and quality report.

Inputs:
  <output_dir>/entity_validated_alignments.json
  scripts/works/<name>/config.json

Outputs:
  <output_dir>/alignment_<name>_*.xml
  <output_dir>/alignment_<name>_*.tsv
  <output_dir>/alignment_report.md
"""

import csv
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_config(work_name):
    config_path = PROJECT_ROOT / "scripts" / "works" / work_name / "config.json"
    with open(config_path) as f:
        return json.load(f)


def main(work_name):
    config = load_config(work_name)
    out_dir = PROJECT_ROOT / config["output_dir"]
    align_path = out_dir / "entity_validated_alignments.json"

    if not align_path.exists():
        print(f"Error: {align_path} not found")
        raise SystemExit(1)

    with open(align_path) as f:
        alignments = json.load(f)

    name = config["name"]
    author = config["author"]
    work_title = config["work_title"]
    cts_prefix = config.get("cts_urn_prefix", "")
    en_source = config.get("english_source", {})
    translator = en_source.get("translator", "")
    en_date = en_source.get("date", "")

    # Determine source suffix for filenames
    gr_source = config.get("greek_source", {})
    source_type = gr_source.get("type", "perseus")
    source_suffix = "f1k" if source_type == "first1kgreek" else "perseus"

    custom_model = PROJECT_ROOT / "models" / "ancient-greek-embedding"
    model_name = (
        "Custom Ancient Greek embedding (xlm-roberta-base fine-tuned)"
        if custom_model.exists()
        else "paraphrase-multilingual-MiniLM-L12-v2 (generic baseline)"
    )

    # ---- 1. TEI Standoff XML ----
    out_xml = out_dir / f"alignment_{name}_{source_suffix}.xml"

    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">',
        "  <teiHeader>",
        "    <fileDesc>",
        "      <titleStmt>",
        f"        <title>Alignment: {esc(translator)} English ({en_date}) / {esc(author)} {esc(work_title)}</title>",
        "      </titleStmt>",
        "      <publicationStmt><p>Generated automatically.</p></publicationStmt>",
        "      <sourceDesc>",
        f'        <bibl xml:id="english">{esc(translator)} ({en_date}). Public domain.</bibl>',
        f'        <bibl xml:id="source">{esc(cts_prefix)}</bibl>',
        "      </sourceDesc>",
        "    </fileDesc>",
        "  </teiHeader>",
        "  <text>",
        "    <body>",
    ]

    by_book = defaultdict(list)
    for a in alignments:
        by_book[a["book"]].append(a)

    for book_key in sorted(by_book.keys(), key=lambda x: int(x) if x.isdigit() else x):
        book_aligns = by_book[book_key]
        safe_book = str(book_key).replace(" ", "-")
        xml_lines.append(f'      <linkGrp type="alignment" subtype="{esc(safe_book)}">')
        for a in book_aligns:
            en_ref = a.get("english_cts_ref", a.get("english_section", ""))
            src = f"english:{safe_book}/section-{en_ref}"
            if a.get("greek_cts_ref") is not None:
                edition = a.get("greek_edition", "")
                tgt = f"{cts_prefix}.{edition}:{a['greek_cts_ref']}" if edition else f"{cts_prefix}:{a['greek_cts_ref']}"
                conf = a.get("combined_score", a["similarity"])
                xml_lines.append(f'        <link target="{src} {tgt}" ana="confidence:{conf}"/>')
            else:
                xml_lines.append(f'        <link target="{src}" ana="confidence:0 match:unmatched_english"/>')
        xml_lines.append("      </linkGrp>")

    xml_lines += ["    </body>", "  </text>", "</TEI>"]

    with open(out_xml, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))

    # ---- 2. TSV ----
    out_tsv = out_dir / f"alignment_{name}_{source_suffix}.tsv"
    fields = ["book", "greek_cts_ref", "greek_edition", "english_cts_ref",
              "embedding_sim", "entity_score", "combined_score", "match_type"]
    with open(out_tsv, "w", encoding="utf-8", newline="") as f:
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
    unmatched = sum(1 for a in alignments if a.get("match_type") in ("unmatched_english", "unmatched"))
    mode = config.get("alignment_mode", "dp")

    out_report = out_dir / "alignment_report.md"
    report = f"""# {author} — {work_title} Alignment Report

**Date:** {date.today().isoformat()}
**Source text:** {cts_prefix}
**English translation:** {translator} ({en_date}), public domain
**Embedding model:** {model_name}
**Alignment mode:** {mode}

## Coverage

- **Total alignment records:** {total}
- **Unmatched sections:** {unmatched}

## Confidence Distribution

| Band | Count | Percentage |
|---|---|---|
| High (>= 0.6) | {high} | {high/total*100:.1f}% |
| Medium (0.3-0.6) | {med} | {med/total*100:.1f}% |
| Low (< 0.3) | {low} | {low/total*100:.1f}% |

- **Mean combined score:** {avg_score:.3f}
"""

    with open(out_report, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Generated:")
    print(f"  {out_xml}")
    print(f"  {out_tsv}")
    print(f"  {out_report}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/pipeline/generate_outputs.py <work_name>")
        sys.exit(1)
    main(sys.argv[1])

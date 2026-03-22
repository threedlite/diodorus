#!/usr/bin/env python3
"""
Generate parallel text HTML (source left, English right) from alignment data.

Where alignment quality is low, white space appears on the weaker side,
making gaps and misalignments immediately visible.

Inputs:
  build/<name>/greek_sections.json
  build/<name>/english_sections.json
  build/<name>/entity_validated_alignments.json
  scripts/works/<name>/config.json

Outputs:
  build/<name>/<cts_id>.perseus-eng80.html  (one per work)
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

HIGH = 0.6
MED = 0.3


def load_config(work_name):
    config_path = PROJECT_ROOT / "scripts" / "works" / work_name / "config.json"
    with open(config_path) as f:
        return json.load(f)


def score_color(score):
    """Background color for a confidence score."""
    if score >= HIGH:
        return "#e8f5e9"  # light green
    elif score >= MED:
        return "#fff8e1"  # light yellow
    else:
        return "#ffebee"  # light red


def esc(s):
    """HTML-escape."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_with_footnotes(text, notes=None):
    """HTML-escape text and render footnotes distinctly.

    Footnote reference markers [A], [1] become superscript links.
    If notes list is provided, footnote bodies are rendered as
    italic blocks after the main text.
    """
    import re
    t = esc(text)
    # Wrap [A], [B], [1], [2] markers as superscript
    t = re.sub(r'\[([A-Z])\]', r'<sup class="fn-ref">[\1]</sup>', t)
    t = re.sub(r'\[(\d+)\]', r'<sup class="fn-ref">[\1]</sup>', t)

    # Append footnote bodies if available
    if notes:
        t += '<div class="fn-body">'
        for n in notes:
            marker = esc(n["marker"])
            body = esc(n["text"])
            t += f'<p class="fn"><span class="fn-marker">{marker}</span> {body}</p>'
        t += '</div>'

    return t


CSS = """
@page {
    size: A4 landscape;
    margin: 1.5cm;
}
body {
    font-family: "Georgia", "Times New Roman", serif;
    font-size: 11pt;
    line-height: 1.5;
    margin: 0;
    padding: 20px;
    color: #222;
}
h1 {
    font-size: 16pt;
    margin-bottom: 4px;
}
h2 {
    font-size: 13pt;
    margin-top: 24px;
    margin-bottom: 8px;
    border-bottom: 1px solid #999;
    padding-bottom: 4px;
}
.meta {
    font-size: 9pt;
    color: #666;
    margin-bottom: 16px;
}
table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}
td {
    vertical-align: top;
    padding: 6px 10px;
    border-bottom: 1px solid #e0e0e0;
    width: 48%;
}
td.ref {
    width: 4%;
    font-size: 8pt;
    color: #999;
    text-align: right;
    padding-right: 4px;
    vertical-align: top;
}
td.source {
    font-size: 10.5pt;
}
td.english {
    font-size: 10.5pt;
}
td.empty {
    color: #ccc;
    font-style: italic;
    font-size: 9pt;
}
.fn-ref {
    color: #999;
    font-size: 8pt;
}
.fn-body {
    margin-top: 6px;
    padding-top: 4px;
    border-top: 1px solid #ddd;
}
.fn {
    font-size: 9pt;
    color: #777;
    font-style: italic;
    margin: 2px 0;
}
.fn-marker {
    font-style: normal;
    font-weight: bold;
    color: #999;
}
tr.high td { background-color: #e8f5e9; }
tr.med td { background-color: #fff8e1; }
tr.low td { background-color: #ffebee; }
tr.unmatched td { background-color: #f5f5f5; }
.score {
    font-size: 7pt;
    color: #999;
    float: right;
}
@media print {
    h2 { page-break-before: always; }
    tr { page-break-inside: avoid; }
}
"""


def generate_html(work_name, config, alignments, greek_data, english_data):
    """Generate parallel text HTML for one work (or sub-work)."""
    out_dir = PROJECT_ROOT / config["output_dir"]

    gr_source = config.get("greek_source", {})
    tlg_id = gr_source.get("tlg_id", gr_source.get("phi_id", ""))
    work_id = gr_source.get("work_id", "")
    work_ids = gr_source.get("work_ids", [work_id] if work_id else [])

    author = config["author"]
    work_title = config["work_title"]
    en_source = config.get("english_source", {})
    translator = en_source.get("translator", "")
    en_date = en_source.get("date", "")
    source_lang = config.get("source_language", "greek")
    lang_label = "Greek" if source_lang == "greek" else "Latin"

    # Build lookup tables
    gr_by_ref = {s["cts_ref"]: s for s in greek_data["sections"]}
    en_by_ref = {str(s["cts_ref"]): s for s in english_data["sections"]}

    # Group alignments by book
    by_book = defaultdict(list)
    for a in alignments:
        by_book[a["book"]].append(a)

    for wid in work_ids:
        cts_stem = f"{tlg_id}.{wid}.perseus-eng80"
        out_path = out_dir / f"{cts_stem}.html"

        lines = []
        lines.append("<!DOCTYPE html>")
        lines.append(f'<html lang="en">')
        lines.append("<head>")
        lines.append(f"<meta charset='utf-8'>")
        lines.append(f"<title>{esc(author)} — {esc(work_title)} (Parallel Text)</title>")
        lines.append(f"<style>{CSS}</style>")
        lines.append("</head>")
        lines.append("<body>")
        lines.append(f"<h1>{esc(author)} — {esc(work_title)}</h1>")
        lines.append(f'<div class="meta">')
        lines.append(f"{lang_label}: {cts_stem}<br>")
        lines.append(f"English: {esc(translator)} ({en_date})<br>")
        lines.append(f"Alignment: embedding similarity + entity anchoring")
        lines.append("</div>")

        # Determine which books belong to this work_id
        # For single-work configs, include all books
        # For multi-work, filter by work name
        if len(work_ids) > 1:
            # Multi-work: need to figure out which books go with this wid
            # The sections have a "work" field
            work_names_for_wid = set()
            for s in greek_data["sections"]:
                if s.get("work"):
                    work_names_for_wid.add(s["work"])
            # Map work_id to work_name by checking which sections use this edition
            # This is approximate — filter books that have sections with matching edition
            relevant_books = set()
            for s in greek_data["sections"]:
                if wid in s.get("edition", ""):
                    relevant_books.add(s["book"])
            # If that didn't work, use work name matching
            if not relevant_books:
                for s in greek_data["sections"]:
                    relevant_books.add(s["book"])
        else:
            relevant_books = set(by_book.keys())

        for book_key in sorted(by_book.keys(),
                               key=lambda x: int(x) if x.isdigit() else x):
            if book_key not in relevant_books:
                continue

            book_aligns = by_book[book_key]
            book_label = f"Book {book_key}" if book_key.isdigit() else book_key

            lines.append(f"<h2>{esc(book_label)}</h2>")
            lines.append("<table>")

            # Walk through alignments in order, building side-by-side rows
            seen_en = set()
            seen_gr = set()

            for a in book_aligns:
                gr_ref = a.get("greek_cts_ref")
                en_ref = a.get("english_cts_ref")
                if en_ref is not None:
                    en_ref = str(en_ref)
                score = a.get("combined_score", a.get("similarity", 0))
                match_type = a.get("match_type", "")

                # Skip duplicate refs (multiple Greek -> same English in DP)
                gr_key = gr_ref or ""
                en_key = en_ref or ""
                pair_key = f"{gr_key}|{en_key}"

                # Determine CSS class
                if match_type in ("unmatched_english", "unmatched_target", "unmatched"):
                    css_class = "unmatched"
                elif score >= HIGH:
                    css_class = "high"
                elif score >= MED:
                    css_class = "med"
                else:
                    css_class = "low"

                # Get full texts
                gr_text = ""
                if gr_ref and gr_ref in gr_by_ref:
                    gr_text = gr_by_ref[gr_ref]["text"]

                en_text = ""
                if en_ref and en_ref in en_by_ref:
                    # Use cleaned text (no footnotes) for display; notes rendered separately
                    en_text = en_by_ref[en_ref].get("text_for_embedding", en_by_ref[en_ref]["text"])

                # Build row
                score_str = f'<span class="score">{score:.2f}</span>' if score > 0 else ""

                gr_cell = f'<td class="source">{esc(gr_text)}{score_str}</td>' if gr_text else '<td class="empty">—</td>'
                en_notes = None
                if en_ref and en_ref in en_by_ref:
                    en_notes = en_by_ref[en_ref].get("notes")
                en_cell = f'<td class="english">{render_with_footnotes(en_text, en_notes)}</td>' if en_text else '<td class="empty">—</td>'
                ref_cell = f'<td class="ref">{esc(gr_ref or en_ref or "")}</td>'

                lines.append(f'<tr class="{css_class}">{ref_cell}{gr_cell}{en_cell}</tr>')

            lines.append("</table>")

        lines.append("</body></html>")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"  Generated: {out_path.name}")


def main(work_name):
    config = load_config(work_name)
    out_dir = PROJECT_ROOT / config["output_dir"]

    greek_path = out_dir / "greek_sections.json"
    english_path = out_dir / "english_sections.json"
    align_path = out_dir / "entity_validated_alignments.json"

    for p in [greek_path, english_path, align_path]:
        if not p.exists():
            print(f"Error: {p} not found")
            raise SystemExit(1)

    with open(greek_path) as f:
        greek_data = json.load(f)
    with open(english_path) as f:
        english_data = json.load(f)
    with open(align_path) as f:
        alignments = json.load(f)

    if isinstance(greek_data, list):
        greek_data = {"sections": greek_data}
    if isinstance(english_data, list):
        english_data = {"sections": english_data}

    generate_html(work_name, config, alignments, greek_data, english_data)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/pipeline/generate_parallel_text.py <work_name>")
        sys.exit(1)
    main(sys.argv[1])

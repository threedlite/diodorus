#!/usr/bin/env python3
"""
Convert a parallel-text HTML file to a nicely formatted PDF for reading.

Strips the alignment diagnostic columns (scores, glossary, quality colors)
and reformats as a clean two-column Greek/English reader.

Usage:
    python scripts/html_to_pdf.py final/tlg0562.tlg001.perseus-eng80.html
    python scripts/html_to_pdf.py final/tlg0562.tlg001.perseus-eng80.html -o marcus.pdf
    python scripts/html_to_pdf.py final/tlg0562.tlg001.perseus-eng80.html --portrait
"""

import argparse
import re
import sys
from pathlib import Path

from lxml import etree


def clean_html_for_reading(html_text, orientation="landscape"):
    """Transform the pipeline HTML into a clean reading layout.

    Removes score bars, glossary columns, quality-color row classes,
    inline ent-name/lex-word highlighting, and score floats.
    Keeps: ref column, source (Greek/Latin) column, English column, footnotes.
    """
    parser = etree.HTMLParser(encoding="utf-8")
    doc = etree.fromstring(html_text.encode("utf-8"), parser)

    # --- Remove score <td> cells (keep glossary) ---
    for td in doc.xpath("//td[contains(@class, 'scores')]"):
        td.getparent().remove(td)

    # --- Remove quality-color classes from rows ---
    for tr in doc.xpath("//tr"):
        cls = tr.get("class", "")
        cleaned = re.sub(r"\b(high|med|low|unmatched)\b", "", cls).strip()
        if cleaned:
            tr.set("class", cleaned)
        elif "class" in tr.attrib:
            del tr.attrib["class"]

    # --- Remove inline score spans ---
    for span in doc.xpath("//span[contains(@class, 'score')]"):
        span.getparent().remove(span)

    # --- Convert ent-name spans to <b> and lex-word spans to <i> ---
    for span in doc.xpath("//span[contains(@class, 'ent-name')]"):
        span.tag = "b"
        if "class" in span.attrib:
            del span.attrib["class"]
    for span in doc.xpath("//span[contains(@class, 'lex-word')]"):
        span.tag = "i"
        if "class" in span.attrib:
            del span.attrib["class"]

    # --- Rewrite the meta div: keep source info, add glossary note ---
    for div in doc.xpath("//div[contains(@class, 'meta')]"):
        lines = []
        text = etree.tostring(div, method="text", encoding="unicode").strip()
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("Score columns:"):
                continue
            if line:
                lines.append(line)
        # Replace content
        for child in list(div):
            div.remove(child)
        div.text = None
        for i, line in enumerate(lines):
            if i == 0:
                div.text = line
            else:
                br = etree.SubElement(div, "br")
                br.tail = line
        # Add glossary explanation
        br = etree.SubElement(div, "br")
        br.tail = ""
        br2 = etree.SubElement(div, "br")
        note = etree.SubElement(div, "span")
        note.set("class", "glossary-note")
        note.text = ("The glossary column shows word-level correspondences "
                     "between the source and English text. These are generated "
                     "by statistical alignment (PMI-weighted bilingual lexicon) "
                     "and are approximate \u2014 not all matches will be accurate. "
                     "Bold = proper names, italic = lexical matches.")

    # --- Build new CSS for clean reading ---
    page_size = "A4 landscape" if orientation == "landscape" else "A4"
    # Calculate column widths based on orientation
    if orientation == "landscape":
        ref_width = "3%"
        source_width = "38%"
        english_width = "44%"
        glossary_width = "15%"
        font_size = "10pt"
    else:
        ref_width = "3%"
        source_width = "37%"
        english_width = "43%"
        glossary_width = "17%"
        font_size = "9pt"

    new_css = f"""
@page {{
    size: {page_size};
    margin: 1.8cm 1.5cm;
    @bottom-center {{
        content: counter(page);
        font-size: 8pt;
        color: #999;
    }}
}}
body {{
    font-family: "Helvetica Neue", "Helvetica", "Arial", sans-serif;
    font-size: {font_size};
    line-height: 1.6;
    margin: 0;
    padding: 0;
    color: #222;
}}
h1 {{
    font-size: 16pt;
    margin-bottom: 2px;
    text-align: center;
    font-weight: normal;
    letter-spacing: 0.5pt;
}}
h2 {{
    font-size: 12pt;
    margin-top: 18px;
    margin-bottom: 8px;
    border-bottom: 1px solid #999;
    padding-bottom: 4px;
    font-weight: normal;
    font-variant: small-caps;
    letter-spacing: 1pt;
}}
.meta {{
    font-size: 8pt;
    color: #888;
    margin-bottom: 14px;
    text-align: center;
}}
.glossary-note {{
    display: block;
    font-size: 7.5pt;
    color: #999;
    font-style: italic;
    max-width: 80%;
    margin: 4px auto 0 auto;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}}
td {{
    vertical-align: top;
    padding: 4px 8px;
    border-bottom: 1px solid #e8e8e8;
}}
td.ref {{
    width: {ref_width};
    font-size: 7pt;
    color: #aaa;
    text-align: right;
    padding-right: 6px;
    font-family: "Helvetica Neue", "Arial", sans-serif;
}}
td.source {{
    width: {source_width};
    padding-right: 12px;
    border-right: 1px solid #ddd;
}}
td.english {{
    width: {english_width};
    padding-left: 12px;
    border-right: 1px solid #e0e0e0;
}}
td.glossary {{
    width: {glossary_width};
    font-size: 7.5pt;
    color: #555;
    padding-left: 8px;
    line-height: 1.4;
}}
td.empty {{
    color: #ccc;
    font-style: italic;
    font-size: 8pt;
}}
.fn-body {{
    margin-top: 4px;
    padding-top: 3px;
    border-top: 1px solid #e0e0e0;
}}
.fn {{
    font-size: 8pt;
    color: #666;
    margin: 2px 0;
}}
.fn-marker {{
    font-weight: bold;
    color: #888;
}}
.fn-ref {{
    color: #888;
    font-size: 7pt;
}}
.heading-text {{
    font-size: 8pt;
    color: #888;
    font-style: italic;
    display: block;
    margin-bottom: 3px;
}}
@media print {{
    h2 {{ page-break-before: always; }}
    tr {{ page-break-inside: avoid; }}
}}
"""

    # Replace the <style> block
    for style in doc.xpath("//style"):
        style.text = new_css

    return etree.tostring(doc, method="html", encoding="unicode",
                          pretty_print=True)


def main():
    parser = argparse.ArgumentParser(
        description="Convert parallel-text HTML to a clean reading PDF")
    parser.add_argument("html_file", type=Path,
                        help="Input HTML file (from final/ or build/)")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output PDF path (default: same name with .pdf)")
    parser.add_argument("--portrait", action="store_true",
                        help="Use portrait orientation (default: landscape)")
    args = parser.parse_args()

    if not args.html_file.exists():
        print(f"Error: {args.html_file} not found")
        sys.exit(1)

    output = args.output
    if output is None:
        output = args.html_file.with_suffix(".pdf")

    orientation = "portrait" if args.portrait else "landscape"

    print(f"Reading: {args.html_file}")
    html_text = args.html_file.read_text(encoding="utf-8")

    print(f"Cleaning HTML for reading ({orientation})...")
    clean_html = clean_html_for_reading(html_text, orientation)

    print(f"Generating PDF: {output}")
    from weasyprint import HTML
    HTML(string=clean_html, base_url=str(args.html_file.parent)).write_pdf(
        str(output))

    size_mb = output.stat().st_size / 1024 / 1024
    print(f"Done: {output} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()

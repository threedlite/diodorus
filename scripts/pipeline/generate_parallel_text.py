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
import re
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Confidence thresholds (calibrated for multi-signal combined_score)
HIGH = 0.50
MED = 0.20


def markup_text(text, entity_words, lexicon_words, is_greek=False):
    """Add bold/italic spans for entity names and lexicon-matched words.

    entity_words: set of words to bold (lowercased)
    lexicon_words: set of words to italicize (lowercased)
    """
    import re
    if is_greek:
        # Match Greek words
        pattern = re.compile(r'([\u0370-\u03FF\u1F00-\u1FFF]+)', re.UNICODE)
    else:
        # Match English words
        pattern = re.compile(r'(\b[A-Za-z]{3,}\b)')

    def replace_word(m):
        word = m.group(1)
        wl = word.lower()
        if wl in entity_words:
            return f'<span class="ent-name">{word}</span>'
        elif wl in lexicon_words:
            return f'<span class="lex-word">{word}</span>'
        return word

    return pattern.sub(replace_word, text)


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


from html import escape as _html_escape

def esc(s):
    """HTML-escape."""
    return _html_escape(str(s))


def render_with_footnotes(text, notes=None):
    """HTML-escape text and render footnotes distinctly.

    Footnote reference markers [A], [1] become superscript links.
    If notes list is provided, footnote bodies are rendered as
    italic blocks after the main text.
    """
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
    font-family: "Helvetica Neue", "Arial", "Segoe UI", sans-serif;
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
}
td.ref {
    width: 4%;
    font-size: 8pt;
    color: #999;
    text-align: right;
    padding-right: 4px;
    vertical-align: top;
}
td.scores {
    width: 8%;
    font-size: 7pt;
    color: #888;
    vertical-align: top;
    padding: 6px 4px;
}
.bar-row { display: flex; align-items: center; margin: 1px 0; }
.bar-label { width: 10px; font-weight: bold; color: #999; }
.bar-bg { width: 40px; height: 6px; background: #eee; border-radius: 2px; margin-left: 2px; }
.bar-fill { height: 100%; border-radius: 2px; }
.bar-fill.high { background: #4caf50; }
.bar-fill.med { background: #ff9800; }
.bar-fill.low { background: #f44336; }
.ent-name { font-weight: bold; }
.lex-word { font-style: italic; }
td.glossary {
    width: 12%;
    font-size: 7pt;
    color: #666;
    vertical-align: top;
    padding: 6px 4px;
    line-height: 1.3;
}
td.source {
    font-size: 10.5pt;
    width: 33%;
}
td.english {
    font-size: 10.5pt;
    width: 40%;
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
.heading-text {
    font-size: 9pt;
    color: #888;
    font-style: italic;
    display: block;
    margin-bottom: 4px;
    padding-bottom: 3px;
    border-bottom: 1px dotted #ddd;
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
    """Generate parallel text HTML derived from TEI XML output.

    The HTML shows exactly what's in the TEI XML — same text, same order,
    same pairing. This guarantees the HTML is an accurate debug view of
    the deliverable.

    Falls back to alignment JSON if TEI XML is not available.
    """
    from lxml import etree
    TEI_NS = "{http://www.tei-c.org/ns/1.0}"

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

    # Load lexicon for word highlighting
    import pickle
    from entity_anchors import extract_greek_names, extract_english_names
    from lexical_overlap import extract_gr_words, extract_en_words
    lexicon = {}
    lex_path = PROJECT_ROOT / "build" / "global_lexical_table.pkl"
    if lex_path.exists():
        with open(lex_path, "rb") as lf:
            lex_data = pickle.load(lf)
            lexicon = lex_data.get("src2en", {})

    # For multi-work, map work_id to work names using Greek sections
    wid_to_work_names = {}
    if len(work_ids) > 1:
        for s in greek_data["sections"]:
            w = s.get("work", "")
            sid = s.get("work_id", "")
            if not sid and s.get("edition", ""):
                parts = s["edition"].split(".")
                if len(parts) >= 2:
                    sid = parts[1]
            if sid and w:
                wid_to_work_names.setdefault(sid, set()).add(w)

    # Group alignments by book
    by_book = defaultdict(list)
    for a in alignments:
        by_book[a["book"]].append(a)

    # Compute lexical P95 for bar graph normalization
    import numpy as np
    all_lex = [a.get("lexical_score", 0) for a in alignments if a.get("lexical_score", 0) > 0]
    lex_p95_display = float(np.percentile(all_lex, 95)) if all_lex else 0.25

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
        lines.append(f"Score columns: "
                     f"<b>E</b>=embedding cosine "
                     f"<b>L</b>=lexical overlap "
                     f"<b>N</b>=entity names "
                     f"<b>R</b>=length ratio "
                     f"<b>S</b>=speaker match")
        lines.append("</div>")

        # Determine which books belong to this work_id
        # For single-work configs, include all books
        # For multi-work, filter by work name
        if len(work_ids) > 1 and wid in wid_to_work_names:
            work_names = wid_to_work_names[wid]
            relevant_books = set()
            for s in greek_data["sections"]:
                if s.get("work", "") in work_names:
                    relevant_books.add(s["book"])
        else:
            relevant_books = set(by_book.keys())

        # Parse TEI XML to get the authoritative English text.
        # Milestones mark where each Greek section range starts.
        # English <p> elements between milestones belong to that range.
        # Build a mapping: greek_cts_ref → English text for all Greek
        # sections in the range (from this milestone to the next).
        xml_path = out_dir / f"{cts_stem}.xml"
        xml_en_by_gr_ref = {}  # greek_cts_ref → English text
        xml_milestone_order = []  # ordered list of milestone refs
        if xml_path.exists():
            xml_tree = etree.parse(str(xml_path))
            xml_root = xml_tree.getroot()
            # Collect milestone → paragraphs.
            # Multiple milestones can appear before the same <p> (when
            # multiple Greek sections are refined from one English section).
            # All such milestones share the same paragraph text.
            milestone_paras = {}  # milestone_ref → list of paragraph texts
            active_milestones = []  # milestones waiting for their first <p>
            for elem in xml_root.iter():
                tag = elem.tag.split('}')[-1] if '}' in str(elem.tag) else str(elem.tag)
                if tag == 'milestone' and elem.get('unit') == 'section':
                    ms_ref = elem.get('n', '')
                    if ms_ref:
                        xml_milestone_order.append(ms_ref)
                        milestone_paras[ms_ref] = []
                        active_milestones.append(ms_ref)
                elif tag == 'p' and active_milestones:
                    # Extract text, converting <note> back to [marker] form
                    # to avoid inlining footnote bodies into the main text.
                    parts = []
                    if elem.text:
                        parts.append(elem.text)
                    for child in elem:
                        child_tag = child.tag.split('}')[-1] if '}' in str(child.tag) else str(child.tag)
                        if child_tag == 'note':
                            marker = child.get('n', '')
                            if marker:
                                parts.append(f'[{marker}]')
                        else:
                            parts.append(''.join(child.itertext()))
                        if child.tail:
                            parts.append(child.tail)
                    p_text = ' '.join(''.join(parts).split()).strip()
                    if p_text:
                        for ms in active_milestones:
                            milestone_paras[ms].append(p_text)
                        # After a <p>, only the last milestone stays active
                        # for subsequent <p> elements in this range
                        active_milestones = [active_milestones[-1]]

            # Map each Greek section to its milestone's English text.
            # Use source order index for comparison (not string sort).
            all_gr_refs = [s["cts_ref"] for s in greek_data["sections"]]
            gr_ref_to_idx = {ref: i for i, ref in enumerate(all_gr_refs)}

            # Convert milestones to source indices for comparison
            ms_with_idx = [(gr_ref_to_idx.get(ms, -1), ms)
                           for ms in xml_milestone_order
                           if ms in gr_ref_to_idx]
            ms_with_idx.sort()

            # For each Greek section, find nearest preceding milestone
            for gi, gr_ref in enumerate(all_gr_refs):
                best_ms = None
                for ms_gi, ms_ref in ms_with_idx:
                    if ms_gi <= gi:
                        best_ms = ms_ref
                    else:
                        break
                if best_ms and best_ms in milestone_paras and milestone_paras[best_ms]:
                    xml_en_by_gr_ref[gr_ref] = " ".join(milestone_paras[best_ms])

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

                # Get English text from the TEI XML (authoritative source).
                # This ensures the HTML shows exactly what's in the deliverable.
                en_text = ""
                en_notes = None
                show_english = False
                en_heading = None

                if gr_ref and gr_ref in xml_en_by_gr_ref and gr_ref not in seen_en:
                    # Show English text from XML for this Greek section
                    en_text = xml_en_by_gr_ref[gr_ref]
                    show_english = True
                    seen_en.add(gr_ref)
                    # Look up footnotes from the English sections data
                    if en_ref and en_ref in en_by_ref:
                        en_notes = en_by_ref[en_ref].get("notes")
                    # Mark all Greek refs sharing this same text as seen
                    for other_ref in xml_en_by_gr_ref:
                        if xml_en_by_gr_ref[other_ref] == en_text:
                            seen_en.add(other_ref)
                elif gr_ref and gr_ref in seen_en:
                    # Already shown — display arrow
                    show_english = False
                elif not xml_en_by_gr_ref:
                    # No XML available — fall back to alignment JSON
                    if match_type == "dp_refined":
                        en_text = a.get("english_refined_text", a.get("english_preview", ""))
                        show_english = True
                        seen_en.add(en_ref)
                    elif en_ref and en_ref in en_by_ref and en_ref not in seen_en:
                        en_section = en_by_ref[en_ref]
                        en_text = en_section.get("text_for_embedding", en_section["text"])
                        en_notes = en_section.get("notes")
                        en_heading = en_section.get("heading_text")
                        if en_heading and en_text.startswith(en_heading):
                            en_text = en_text[len(en_heading):].lstrip()
                        seen_en.add(en_ref)
                        show_english = True

                # Extract entity and lexicon words for highlighting + glossary
                gr_entity_words = set()
                gr_lexicon_words = set()
                en_entity_words = set()
                en_lexicon_words = set()
                glossary_entities = []  # (greek_name, english_name)
                glossary_lexicon = []   # (greek_word, english_word)

                if gr_text:
                    gr_names = extract_greek_names(gr_text)
                    for name, lat in gr_names:
                        gr_entity_words.add(name.lower())
                    for gw in extract_gr_words(gr_text):
                        if gw in lexicon:
                            gr_lexicon_words.add(gw)

                en_display = en_text or ""
                if en_display:
                    en_names_list = extract_english_names(en_display)
                    for name in en_names_list:
                        en_entity_words.add(name)
                    en_words_set = extract_en_words(en_display)

                    # Build entity glossary
                    if gr_text:
                        from rapidfuzz import fuzz as _fuzz
                        for name, lat in gr_names:
                            for en in en_names_list:
                                if len(lat) >= 4 and len(en) >= 4 and _fuzz.partial_ratio(lat, en) > 75:
                                    glossary_entities.append((name, en))
                                    break

                    # Build lexicon glossary
                    for gw in gr_lexicon_words:
                        if gw in lexicon:
                            for ew, _ in sorted(lexicon[gw].items(),
                                                key=lambda x: -x[1]):
                                if ew in en_words_set:
                                    en_lexicon_words.add(ew)
                                    glossary_lexicon.append((gw, ew))
                                    break

                # Build row with markup
                score_str = f'<span class="score">{score:.2f}</span>' if score > 0 else ""

                if gr_text:
                    marked_gr = markup_text(esc(gr_text), gr_entity_words, gr_lexicon_words, is_greek=True)
                    gr_cell = f'<td class="source">{marked_gr}{score_str}</td>'
                else:
                    gr_cell = '<td class="empty">—</td>'

                if show_english:
                    heading_html = ""
                    if en_heading:
                        heading_html = f'<span class="heading-text">{esc(en_heading)}</span>'
                    rendered_en = render_with_footnotes(en_text, en_notes)
                    marked_en = markup_text(rendered_en, en_entity_words, en_lexicon_words, is_greek=False)
                    en_cell = f'<td class="english">{heading_html}{marked_en}</td>'
                elif en_ref and en_ref in seen_en:
                    en_cell = '<td class="empty">↑</td>'
                else:
                    en_cell = '<td class="empty">—</td>'

                # Score component columns as bar graphs
                def _bar(label, val):
                    val = max(0, min(1, val))
                    pct = int(val * 100)
                    cls = 'high' if val >= 0.5 else ('med' if val >= 0.2 else 'low')
                    return (f'<div class="bar-row"><span class="bar-label">{label}</span>'
                            f'<div class="bar-bg"><div class="bar-fill {cls}" '
                            f'style="width:{pct}%"></div></div></div>')

                emb = max(a.get("similarity", 0), 0)
                lex_s = min(a.get("lexical_score", 0) / max(lex_p95_display, 0.01), 1.0)
                ent_s = a.get("entity_overlap_score", 0)
                len_s = a.get("length_ratio_score", 0)
                spk_s = a.get("speaker_score", 0)

                bars = _bar('E', emb) + _bar('L', lex_s) + _bar('N', ent_s) + _bar('R', len_s)
                if spk_s > 0:
                    bars += _bar('S', spk_s)
                scores_cell = f'<td class="scores">{bars}</td>'

                # Glossary column: matched entity and lexicon pairs
                gloss_parts = []
                for gn, en in glossary_entities[:5]:
                    gloss_parts.append(f'<b>{esc(gn)}</b>={esc(en)}')
                for gw, ew in glossary_lexicon[:8]:
                    gloss_parts.append(f'<i>{esc(gw)}</i>={esc(ew)}')
                gloss_html = '<br>'.join(gloss_parts) if gloss_parts else ''
                gloss_cell = f'<td class="glossary">{gloss_html}</td>'

                section_id = (gr_ref or en_ref or "").replace(".", "-")
                ref_cell = f'<td class="ref">{esc(gr_ref or en_ref or "")}</td>'

                lines.append(f'<tr class="{css_class}" id="s{section_id}">{ref_cell}{gr_cell}{en_cell}{scores_cell}{gloss_cell}</tr>')

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

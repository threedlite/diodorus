#!/usr/bin/env python3
"""
Generate Perseus-compatible TEI XML for an aligned English translation.

Produces:
  <output_dir>/<cts_work_id>.perseus-eng80.xml
  <output_dir>/__cts__eng80_fragment.xml

The English text is structured with CTS-compatible divs and milestone
markers linking to the source language CTS references.
"""

import json
import re
import sys
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NSMAP = {None: TEI_NS}


def load_config(work_name):
    config_path = PROJECT_ROOT / "scripts" / "works" / work_name / "config.json"
    with open(config_path) as f:
        return json.load(f)


def _build_p_with_notes(p_elem, text, notes, ns):
    """Build a <p> element with footnote bodies wrapped in <note> tags.

    The full text has footnote bodies inline after markers. We reconstruct
    the original text faithfully: markers become <note> elements containing
    the footnote body. Markers that appear as references (not followed by
    body) become empty <note> elements.

    Strategy: scan the text, track which marker+body pairs we've consumed,
    and only put the body in the <note> when it actually follows the marker.
    """
    note_map = {n["marker"]: n["text"] for n in notes}

    # Split text on markers
    pattern = re.compile(r'(\[[A-Za-z]\]|\[\d+\])')
    parts = pattern.split(text)

    p_elem.text = parts[0] if parts else text

    prev = p_elem
    for i in range(1, len(parts), 2):
        marker = parts[i]
        after = parts[i + 1] if i + 1 < len(parts) else ""

        note_text = note_map.get(marker, "")

        # Check if the footnote body actually follows this marker instance.
        # If so, put it in <note> and strip it from the tail.
        actual_body = ""
        if note_text:
            after_stripped = after.lstrip()
            if after_stripped.startswith(note_text):
                actual_body = note_text
                after = after_stripped[len(note_text):]

        note_elem = etree.SubElement(p_elem, f"{{{ns}}}note")
        note_elem.set("type", "translator")
        note_elem.set("n", marker.strip("[]"))
        if actual_body:
            note_elem.text = actual_body
        note_elem.tail = after

        prev = note_elem


def _build_p_with_inline_notes(p_elem, text, ns):
    """Build a <p> element, wrapping any [A]/[1] markers as empty <note> refs.

    For sections where strip_notes didn't extract note bodies (e.g. notes
    were in a separate FOOTNOTES section already removed by extraction),
    we still wrap the reference markers in <note> tags.
    """
    pattern = re.compile(r'(\[[A-Za-z]\]|\[\d+\])')
    parts = pattern.split(text)

    if len(parts) <= 1:
        # No markers found — plain text
        p_elem.text = text
        return

    p_elem.text = parts[0]
    for i in range(1, len(parts), 2):
        marker = parts[i]
        after = parts[i + 1] if i + 1 < len(parts) else ""

        note_elem = etree.SubElement(p_elem, f"{{{ns}}}note")
        note_elem.set("type", "translator")
        note_elem.set("n", marker.strip("[]"))
        note_elem.tail = after


def main(work_name):
    config = load_config(work_name)
    out_dir = PROJECT_ROOT / config["output_dir"]

    align_path = out_dir / "entity_validated_alignments.json"
    english_path = out_dir / "english_sections.json"

    for p in [align_path, english_path]:
        if not p.exists():
            print(f"Error: {p} not found")
            raise SystemExit(1)

    with open(align_path) as f:
        alignments = json.load(f)
    with open(english_path) as f:
        english_data = json.load(f)

    if isinstance(english_data, list):
        english_data = {"sections": english_data}

    name = config["name"]

    # Build CTS work ID from config
    gr_source = config.get("greek_source", {})
    tlg_id = gr_source.get("tlg_id", "")
    work_id = gr_source.get("work_id", "")
    work_ids = gr_source.get("work_ids", [work_id] if work_id else [])

    en_source = config.get("english_source", {})
    translator = en_source.get("translator", "Unknown")
    en_date = en_source.get("date", "")
    author = config.get("author", "")
    work_title = config.get("work_title", "")

    # For multi-work configs, build a mapping from work_id to work_name
    # using the Greek/Latin sections data (which have both fields).
    wid_to_work_names = {}
    if len(work_ids) > 1:
        gr_path = out_dir / "greek_sections.json"
        if gr_path.exists():
            with open(gr_path) as gf:
                gr_data = json.load(gf)
            for s in gr_data["sections"]:
                w = s.get("work", "") or s.get("book", "")
                # Try work_id field first, then extract from edition
                sid = s.get("work_id", "")
                if not sid and s.get("edition", ""):
                    # e.g. "phi1020.phi001.perseus-lat2" -> "phi001"
                    parts = s["edition"].split(".")
                    if len(parts) >= 2:
                        sid = parts[1]
                if sid and w:
                    wid_to_work_names.setdefault(sid, set()).add(w)
        print(f"  Multi-work mapping: {dict((k, sorted(v)) for k, v in wid_to_work_names.items())}")

    for wid in work_ids:
        cts_work = f"{tlg_id}.{wid}"
        urn = f"urn:cts:greekLit:{cts_work}.perseus-eng80"

        out_tei = out_dir / f"{cts_work}.perseus-eng80.xml"

        print(f"Generating Perseus TEI: {out_tei.name}")

        # Build TEI document
        tei = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)

        # Header
        header = etree.SubElement(tei, f"{{{TEI_NS}}}teiHeader")
        file_desc = etree.SubElement(header, f"{{{TEI_NS}}}fileDesc")

        title_stmt = etree.SubElement(file_desc, f"{{{TEI_NS}}}titleStmt")
        title_el = etree.SubElement(title_stmt, f"{{{TEI_NS}}}title")
        title_el.text = f"{author}, {work_title}"
        author_el = etree.SubElement(title_stmt, f"{{{TEI_NS}}}author")
        author_el.text = author
        editor_el = etree.SubElement(title_stmt, f"{{{TEI_NS}}}editor")
        editor_el.set("role", "translator")
        editor_el.text = translator

        pub_stmt = etree.SubElement(file_desc, f"{{{TEI_NS}}}publicationStmt")
        pub_p = etree.SubElement(pub_stmt, f"{{{TEI_NS}}}p")
        pub_p.text = "Generated by Diodorus alignment pipeline."

        source_desc = etree.SubElement(file_desc, f"{{{TEI_NS}}}sourceDesc")
        bibl = etree.SubElement(source_desc, f"{{{TEI_NS}}}bibl")
        bibl.text = f"{translator} ({en_date}). Public domain."

        # Encoding desc with CTS refsDecl
        enc_desc = etree.SubElement(header, f"{{{TEI_NS}}}encodingDesc")
        refs_decl = etree.SubElement(enc_desc, f"{{{TEI_NS}}}refsDecl")
        refs_decl.set("n", "CTS")

        cref = etree.SubElement(refs_decl, f"{{{TEI_NS}}}cRefPattern")
        cref.set("n", "section")
        cref.set("matchPattern", r"(\w+)\.(\w+)")
        cref.set("replacementPattern",
                 "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@n='$1']/tei:p[@n='$2'])")

        # Text body
        text_el = etree.SubElement(tei, f"{{{TEI_NS}}}text")
        body = etree.SubElement(text_el, f"{{{TEI_NS}}}body")

        trans_div = etree.SubElement(body, f"{{{TEI_NS}}}div")
        trans_div.set("type", "translation")
        trans_div.set(f"{{{XML_NS}}}lang", "eng")
        trans_div.set("n", urn)

        div_per_source = config.get("xml_div_per_source_section", False)

        if div_per_source:
            # One <div> per source (Greek) section that has a matched English
            # translation.  The div n= is the Greek fable/section number.
            # Unmatched Greek sections produce no div at all.

            # Build lookup: greek_cts_ref -> english section data
            en_by_ref = {}
            for s in english_data["sections"]:
                en_by_ref[str(s.get("cts_ref", s.get("section", "")))] = s

            # Build alignment lookup: greek_cts_ref -> english_cts_ref
            gr_to_en = {}
            for a in alignments:
                gr_ref = a.get("greek_cts_ref")
                en_ref = a.get("english_cts_ref", a.get("english_section", ""))
                if gr_ref and en_ref:
                    gr_to_en[str(gr_ref)] = str(en_ref)

            # Load Greek sections to iterate in source order
            gr_path = out_dir / "greek_sections.json"
            with open(gr_path) as gf:
                gr_data = json.load(gf)
            gr_sections = gr_data if isinstance(gr_data, list) else gr_data.get("sections", [])

            emitted = 0
            for gs in gr_sections:
                gr_ref = str(gs.get("cts_ref", gs.get("section", "")))
                en_ref = gr_to_en.get(gr_ref)
                if not en_ref:
                    continue
                en_sec = en_by_ref.get(en_ref)
                if not en_sec:
                    continue

                fable_div = etree.SubElement(trans_div, f"{{{TEI_NS}}}div")
                fable_div.set("type", "textpart")
                fable_div.set("subtype", "book")
                fable_div.set("n", str(gr_ref))

                p = etree.SubElement(fable_div, f"{{{TEI_NS}}}p")
                p.set("n", "1")

                section_notes = en_sec.get("notes", [])
                if section_notes:
                    _build_p_with_notes(p, en_sec["text"], section_notes, TEI_NS)
                else:
                    _build_p_with_inline_notes(p, en_sec["text"], TEI_NS)

                emitted += 1

            print(f"  Emitted {emitted} fable divs (of {len(gr_sections)} Greek sections)")

        else:
            # Default: group English sections by book, with milestone markers
            # linking to Greek CTS references.
            from collections import defaultdict
            en_by_book = defaultdict(list)
            for s in english_data["sections"]:
                # Only include sections from this work (for multi-work configs)
                if len(work_ids) > 1 and wid in wid_to_work_names:
                    s_work = s.get("work", "") or s.get("book", "")
                    if s_work and s_work not in wid_to_work_names[wid]:
                        continue  # skip sections belonging to a different work
                en_by_book[s["book"]].append(s)

            # Build alignment lookup: english cts_ref -> list of greek cts_refs
            # Multiple Greek sections can map to the same English section
            # (via refinement), so collect all of them.
            en_to_gr_list = {}
            for a in alignments:
                en_ref = a.get("english_cts_ref", a.get("english_section", ""))
                gr_ref = a.get("greek_cts_ref")
                if en_ref and gr_ref:
                    en_to_gr_list.setdefault(str(en_ref), []).append(gr_ref)

            for book_key in sorted(en_by_book.keys(),
                                    key=lambda x: int(x) if x.isdigit() else x):
                book_secs = en_by_book[book_key]

                book_div = etree.SubElement(trans_div, f"{{{TEI_NS}}}div")
                book_div.set("type", "textpart")
                book_div.set("subtype", "book")
                book_div.set("n", str(book_key))

                for s in book_secs:
                    sec_n = s.get("section", s.get("cts_ref", ""))

                    # Add milestones for all Greek references aligned to this section
                    gr_refs = en_to_gr_list.get(str(s.get("cts_ref", "")), [])
                    for gr_ref in gr_refs:
                        ms = etree.SubElement(book_div, f"{{{TEI_NS}}}milestone")
                        ms.set("unit", "section")
                        ms.set("n", str(gr_ref))

                    # Emit chapter heading if present
                    heading_text = s.get("heading_text")
                    if heading_text:
                        head = etree.SubElement(book_div, f"{{{TEI_NS}}}head")
                        head.text = heading_text

                    p = etree.SubElement(book_div, f"{{{TEI_NS}}}p")
                    p.set("n", str(sec_n))

                    # Build mixed content with <note> elements for footnotes.
                    # The text field has footnote bodies inline after markers;
                    # text_for_embedding has markers stripped. We need text with
                    # markers but WITHOUT footnote bodies for the <p> content,
                    # then insert note bodies as <note> children.
                    section_notes = s.get("notes", [])
                    if section_notes:
                        _build_p_with_notes(p, s["text"], section_notes, TEI_NS)
                    else:
                        _build_p_with_inline_notes(p, s["text"], TEI_NS)

        # Write
        tree = etree.ElementTree(tei)
        with open(out_tei, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            tree.write(f, encoding="UTF-8", xml_declaration=False, pretty_print=True)

        # Verify well-formed
        etree.parse(str(out_tei))
        print(f"  Written and validated: {out_tei.name}")

    # CTS catalog fragment — named per work to avoid collisions
    out_cts = out_dir / f"__cts__eng80_{name}.xml"
    cts_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    cts_lines.append(f'<!-- CTS catalog entry for {author} {work_title} English translation -->')
    for wid in work_ids:
        cts_work = f"{tlg_id}.{wid}"
        urn = f"urn:cts:greekLit:{cts_work}.perseus-eng80"
        cts_lines.append(
            f'<ti:translation xmlns:ti="http://chs.harvard.edu/xmlns/cts" '
            f'urn="{urn}" workUrn="urn:cts:greekLit:{cts_work}" xml:lang="eng">'
        )
        cts_lines.append(f'  <ti:label xml:lang="eng">{translator} ({en_date})</ti:label>')
        cts_lines.append(f'  <ti:description xml:lang="eng">{translator} translation of '
                         f'{author}, {work_title}. Public domain.</ti:description>')
        cts_lines.append('</ti:translation>')

    with open(out_cts, "w", encoding="utf-8") as f:
        f.write("\n".join(cts_lines) + "\n")

    print(f"  Written: {out_cts.name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/pipeline/generate_perseus_tei.py <work_name>")
        sys.exit(1)
    main(sys.argv[1])

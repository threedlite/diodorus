#!/usr/bin/env python3
"""
Generate a Perseus-compatible TEI XML English translation of Diodorus Siculus.

Reads existing alignment data and Booth's English text, produces:
  1. output/tlg0060.tlg001.perseus-eng80.xml  — TEI translation file
  2. output/__cts__eng80_fragment.xml          — CTS catalog entry

No pipeline rerun needed; works from existing output files.
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALIGNMENTS_PATH = PROJECT_ROOT / "output" / "entity_validated_alignments.json"
BOOTH_PATH = PROJECT_ROOT / "output" / "booth_normalised.json"
OUT_TEI = PROJECT_ROOT / "output" / "tlg0060.tlg001.perseus-eng80.xml"
OUT_CTS = PROJECT_ROOT / "output" / "__cts__eng80_fragment.xml"

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NSMAP = {None: TEI_NS}

URN_BASE = "urn:cts:greekLit:tlg0060.tlg001.perseus-eng80"


def load_inputs():
    """Load alignment and Booth data, exit on missing files."""
    for path, label in [(ALIGNMENTS_PATH, "alignments"), (BOOTH_PATH, "Booth text")]:
        if not path.exists():
            print(f"Error: {label} not found at {path}")
            sys.exit(1)

    with open(ALIGNMENTS_PATH) as f:
        alignments = json.load(f)
    with open(BOOTH_PATH) as f:
        booth = json.load(f)

    return alignments, booth


def build_booth_lookup(booth):
    """Build a lookup: (book_n, div2_index, p_index) -> paragraph text."""
    lookup = {}
    for book in booth["books"]:
        book_n = book["div1_n"]
        for chapter in book["chapters"]:
            div2_idx = chapter["div2_index"]
            for para in chapter["paragraphs"]:
                p_idx = para["p_index"]
                lookup[(book_n, div2_idx, p_idx)] = para["text"]
    return lookup


def normalise_long_s(text):
    """Replace ſ (long-s U+017F) with regular s."""
    return text.replace("\u017f", "s")


def parse_cts_ref(ref):
    """Parse '1.arg.0' -> (book, chapter, section) strings."""
    parts = ref.split(".")
    return parts[0], parts[1], parts[2]


def chapter_sort_key(ch):
    """Sort chapters: 'arg' first, then numeric order."""
    if ch == "arg":
        return (-1,)
    return (int(ch),)


def section_sort_key(sec):
    """Sort sections numerically."""
    return int(sec)


def build_section_text_map(alignments, booth_lookup):
    """
    Build a map: (book, chapter, section) -> list of paragraph texts.

    Handles the N:M alignment distribution:
      - N:1 (multiple Greek sections -> 1 English paragraph): repeat at each section
      - 1:1: one paragraph per section
      - N:M where M>1: distribute paragraphs across sections using floor(i * M / N)
      - 1:M: all M paragraphs go into the single section
    """
    # First, group alignment records by (book, group_id)
    groups = defaultdict(list)
    for rec in alignments:
        groups[(rec["book"], rec["group_id"])].append(rec)

    section_texts = {}  # (book, chapter, section) -> [para_texts]
    section_scores = {}  # (book, chapter, section) -> combined_score
    section_group_info = {}  # (book, chapter, section) -> (group_id, score)

    for (book, group_id), recs in groups.items():
        # Sort records by CTS ref to get consistent ordering
        recs.sort(key=lambda r: (
            chapter_sort_key(parse_cts_ref(r["greek_cts_ref"])[1]),
            section_sort_key(parse_cts_ref(r["greek_cts_ref"])[2]),
        ))

        gr_size = recs[0]["group_size_gr"]
        en_size = recs[0]["group_size_en"]
        base_div2 = recs[0]["booth_div2_index"]
        base_p = recs[0]["booth_p_index"]

        # Collect all English paragraphs for this group
        en_paras = []
        for offset in range(en_size):
            key = (book, base_div2, base_p + offset)
            text = booth_lookup.get(key, "")
            if text:
                en_paras.append(normalise_long_s(text))

        if not en_paras:
            continue

        for i, rec in enumerate(recs):
            _, ch, sec = parse_cts_ref(rec["greek_cts_ref"])
            score = rec.get("combined_score", rec["similarity"])

            if en_size == 1:
                # N:1 — every section gets the same paragraph
                section_texts[(book, ch, sec)] = en_paras
            elif gr_size == 1:
                # 1:M — the single section gets all paragraphs
                section_texts[(book, ch, sec)] = en_paras
            else:
                # N:M — distribute paragraphs across sections
                para_idx = math.floor(i * en_size / gr_size)
                section_texts[(book, ch, sec)] = [en_paras[para_idx]]

            section_scores[(book, ch, sec)] = score
            section_group_info[(book, ch, sec)] = (group_id, score)

    return section_texts, section_group_info


def build_tei_header():
    """Build the TEI header element."""
    header = etree.SubElement(etree.Element("dummy"), f"{{{TEI_NS}}}teiHeader")
    header.set(f"{{{XML_NS}}}lang", "eng")

    # fileDesc
    file_desc = etree.SubElement(header, f"{{{TEI_NS}}}fileDesc")

    # titleStmt
    title_stmt = etree.SubElement(file_desc, f"{{{TEI_NS}}}titleStmt")
    title = etree.SubElement(title_stmt, f"{{{TEI_NS}}}title")
    title.text = "The Historical Library of Diodorus Siculus"
    title.set("type", "work")
    author = etree.SubElement(title_stmt, f"{{{TEI_NS}}}author")
    author.text = "Diodorus Siculus"
    editor = etree.SubElement(title_stmt, f"{{{TEI_NS}}}editor")
    editor.set("role", "translator")
    editor.text = "G. Booth"
    sponsor = etree.SubElement(title_stmt, f"{{{TEI_NS}}}sponsor")
    sponsor.text = "Diodorus Alignment Project"

    # publicationStmt
    pub_stmt = etree.SubElement(file_desc, f"{{{TEI_NS}}}publicationStmt")
    publisher = etree.SubElement(pub_stmt, f"{{{TEI_NS}}}publisher")
    publisher.text = "Diodorus Alignment Project"
    pub_id = etree.SubElement(pub_stmt, f"{{{TEI_NS}}}idno")
    pub_id.set("type", "filename")
    pub_id.text = "tlg0060.tlg001.perseus-eng80.xml"
    avail = etree.SubElement(pub_stmt, f"{{{TEI_NS}}}availability")
    licence = etree.SubElement(avail, f"{{{TEI_NS}}}licence")
    licence.set("target", "https://creativecommons.org/licenses/by-sa/4.0/")
    licence.text = (
        "This work is licensed under a Creative Commons "
        "Attribution-ShareAlike 4.0 International License."
    )

    # sourceDesc
    source_desc = etree.SubElement(file_desc, f"{{{TEI_NS}}}sourceDesc")
    bibl = etree.SubElement(source_desc, f"{{{TEI_NS}}}bibl")
    bibl_author = etree.SubElement(bibl, f"{{{TEI_NS}}}author")
    bibl_author.text = "Diodorus Siculus"
    bibl_title = etree.SubElement(bibl, f"{{{TEI_NS}}}title")
    bibl_title.text = "The Historical Library of Diodorus the Sicilian"
    bibl_editor = etree.SubElement(bibl, f"{{{TEI_NS}}}editor")
    bibl_editor.set("role", "translator")
    bibl_editor.text = "G. Booth"
    bibl_pub = etree.SubElement(bibl, f"{{{TEI_NS}}}pubPlace")
    bibl_pub.text = "London"
    bibl_date = etree.SubElement(bibl, f"{{{TEI_NS}}}date")
    bibl_date.text = "1700"
    bibl_note = etree.SubElement(bibl, f"{{{TEI_NS}}}note")
    bibl_note.text = "Oxford Text Archive A36034"

    # encodingDesc with refsDecl for CTS
    encoding_desc = etree.SubElement(header, f"{{{TEI_NS}}}encodingDesc")
    refs_decl = etree.SubElement(encoding_desc, f"{{{TEI_NS}}}refsDecl")
    refs_decl.set("n", "CTS")

    # Three cRefPatterns: section, chapter, book (most specific first)
    section_pat = etree.SubElement(refs_decl, f"{{{TEI_NS}}}cRefPattern")
    section_pat.set("n", "section")
    section_pat.set("matchPattern", r"(\w+)\.(\w+)\.(\w+)")
    section_pat.set(
        "replacementPattern",
        "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@n='$1']"
        "/tei:div[@n='$2']/tei:div[@n='$3'])",
    )
    section_p = etree.SubElement(section_pat, f"{{{TEI_NS}}}p")
    section_p.text = "This pointer pattern extracts book, chapter, and section."

    chapter_pat = etree.SubElement(refs_decl, f"{{{TEI_NS}}}cRefPattern")
    chapter_pat.set("n", "chapter")
    chapter_pat.set("matchPattern", r"(\w+)\.(\w+)")
    chapter_pat.set(
        "replacementPattern",
        "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@n='$1']"
        "/tei:div[@n='$2'])",
    )
    chapter_p = etree.SubElement(chapter_pat, f"{{{TEI_NS}}}p")
    chapter_p.text = "This pointer pattern extracts book and chapter."

    book_pat = etree.SubElement(refs_decl, f"{{{TEI_NS}}}cRefPattern")
    book_pat.set("n", "book")
    book_pat.set("matchPattern", r"(\w+)")
    book_pat.set(
        "replacementPattern",
        "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@n='$1'])",
    )
    book_p = etree.SubElement(book_pat, f"{{{TEI_NS}}}p")
    book_p.text = "This pointer pattern extracts book."

    # editorialDecl
    editorial_decl = etree.SubElement(encoding_desc, f"{{{TEI_NS}}}editorialDecl")
    ed_p = etree.SubElement(editorial_decl, f"{{{TEI_NS}}}p")
    ed_p.text = (
        "English text from G. Booth's 1700 translation (OTA A36034), "
        "aligned to the Perseus Greek section structure by the Diodorus "
        "Alignment Project using cross-lingual embedding similarity and "
        "named-entity anchoring. Long-s characters have been normalised to "
        "modern s. Where multiple Greek sections map to a single English "
        "paragraph, the paragraph is repeated at each section reference for "
        "CTS completeness."
    )

    return header


def build_tei(section_texts, group_info):
    """Build the complete TEI XML tree."""
    tei = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)

    # Header
    header = build_tei_header()
    tei.append(header)

    # Text body
    text = etree.SubElement(tei, f"{{{TEI_NS}}}text")
    body = etree.SubElement(text, f"{{{TEI_NS}}}body")

    # Top-level translation div
    trans_div = etree.SubElement(body, f"{{{TEI_NS}}}div")
    trans_div.set("type", "translation")
    trans_div.set(f"{{{XML_NS}}}lang", "eng")
    trans_div.set("n", URN_BASE)

    # Organise sections by book -> chapter -> section
    hierarchy = defaultdict(lambda: defaultdict(dict))
    for (book, chapter, section), texts in section_texts.items():
        hierarchy[book][chapter][section] = texts

    # Book ordering
    book_order = [str(b) for b in [1, 2, 3, 4, 5, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]]

    for book_n in book_order:
        if book_n not in hierarchy:
            continue

        book_div = etree.SubElement(trans_div, f"{{{TEI_NS}}}div")
        book_div.set("type", "textpart")
        book_div.set("subtype", "book")
        book_div.set("n", book_n)

        head = etree.SubElement(book_div, f"{{{TEI_NS}}}head")
        head.text = f"BOOK {roman(int(book_n))}"

        chapters = hierarchy[book_n]
        ch_keys = sorted(chapters.keys(), key=chapter_sort_key)

        for ch_n in ch_keys:
            ch_div = etree.SubElement(book_div, f"{{{TEI_NS}}}div")
            ch_div.set("type", "textpart")
            ch_div.set("subtype", "chapter")
            ch_div.set("n", ch_n)

            sections = chapters[ch_n]
            sec_keys = sorted(sections.keys(), key=section_sort_key)

            for sec_n in sec_keys:
                sec_div = etree.SubElement(ch_div, f"{{{TEI_NS}}}div")
                sec_div.set("type", "textpart")
                sec_div.set("subtype", "section")
                sec_div.set("n", sec_n)

                # Add alignment metadata as ana attribute
                info = group_info.get((book_n, ch_n, sec_n))
                if info:
                    gid, score = info
                    sec_div.set("ana", f"alignment:group={gid} score={score:.3f}")

                for para_text in sections[sec_n]:
                    p = etree.SubElement(sec_div, f"{{{TEI_NS}}}p")
                    p.text = para_text

    return tei


def roman(n):
    """Convert integer to Roman numeral string."""
    vals = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    result = ""
    for value, numeral in vals:
        while n >= value:
            result += numeral
            n -= value
    return result


def generate_cts_fragment():
    """Generate the CTS catalog XML fragment."""
    ti_ns = "http://chs.harvard.edu/xmlns/cts"
    nsmap = {"ti": ti_ns}

    root = etree.Element(f"{{{ti_ns}}}translation", nsmap=nsmap)
    root.set("urn", URN_BASE)
    root.set("workUrn", "urn:cts:greekLit:tlg0060.tlg001")
    root.set(f"{{{XML_NS}}}lang", "eng")

    label = etree.SubElement(root, f"{{{ti_ns}}}label")
    label.set(f"{{{XML_NS}}}lang", "eng")
    label.text = "The Historical Library"

    desc = etree.SubElement(root, f"{{{ti_ns}}}description")
    desc.set(f"{{{XML_NS}}}lang", "eng")
    desc.text = (
        "Diodorus Siculus. The Historical Library. "
        "Booth, G., translator. London, 1700. Aligned to Greek section "
        "structure by the Diodorus Alignment Project."
    )

    return root


def print_summary(alignments, section_texts, hierarchy_books):
    """Print verification summary."""
    print("\n=== TEI Generation Summary ===\n")

    total_sections = len(section_texts)
    print(f"Total section divs: {total_sections}")
    print(f"Total alignment records: {len(alignments)}")

    # Sections per book
    book_counts = defaultdict(int)
    for (book, _, _) in section_texts:
        book_counts[book] += 1

    print("\nSections per book:")
    for b in sorted(book_counts, key=lambda x: int(x)):
        print(f"  Book {b:>2}: {book_counts[b]:>4} sections")

    # Group distribution
    from collections import Counter
    gr_sizes = Counter()
    en_sizes = Counter()
    groups_seen = set()
    for a in alignments:
        key = (a["book"], a["group_id"])
        if key not in groups_seen:
            groups_seen.add(key)
            gr_sizes[a["group_size_gr"]] += 1
            en_sizes[a["group_size_en"]] += 1

    print(f"\nAlignment groups: {len(groups_seen)}")
    print("  Greek section group sizes:", dict(sorted(gr_sizes.items())))
    print("  English paragraph group sizes:", dict(sorted(en_sizes.items())))

    # Verify every CTS ref has a section
    cts_refs = set()
    for a in alignments:
        _, ch, sec = parse_cts_ref(a["greek_cts_ref"])
        cts_refs.add((a["book"], ch, sec))

    missing = cts_refs - set(section_texts.keys())
    if missing:
        print(f"\nWARNING: {len(missing)} CTS refs have no section div!")
        for m in sorted(missing)[:10]:
            print(f"  {m}")
    else:
        print("\nAll CTS refs have corresponding section divs.")


def main():
    print("Loading input files...")
    alignments, booth = load_inputs()

    print("Building Booth text lookup...")
    booth_lookup = build_booth_lookup(booth)

    print("Mapping sections to English text...")
    section_texts, group_info = build_section_text_map(alignments, booth_lookup)

    print("Building TEI XML...")
    tei = build_tei(section_texts, group_info)

    # Serialize with XML declaration and processing instruction
    tree = etree.ElementTree(tei)

    # Write TEI file
    with open(OUT_TEI, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(
            b'<?xml-model href="http://www.stoa.org/epidoc/schema/latest/tei-epidoc.rng"'
            b' schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
        )
        tree.write(f, encoding="unicode" if False else "UTF-8",
                   xml_declaration=False, pretty_print=True)

    print(f"Wrote: {OUT_TEI}")

    # Write CTS fragment
    cts = generate_cts_fragment()
    cts_tree = etree.ElementTree(cts)
    with open(OUT_CTS, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(b'<!-- Paste this into the __cts__.xml for tlg0060.tlg001 -->\n')
        cts_tree.write(f, encoding="UTF-8", xml_declaration=False, pretty_print=True)

    print(f"Wrote: {OUT_CTS}")

    # Verification
    print_summary(alignments, section_texts, None)

    # Quick well-formedness check
    print("\nValidating XML well-formedness...")
    etree.parse(str(OUT_TEI))
    print("XML is well-formed.")

    # Check long-s normalisation
    with open(OUT_TEI, "r", encoding="utf-8") as f:
        content = f.read()
    long_s_count = content.count("\u017f")
    if long_s_count > 0:
        print(f"WARNING: {long_s_count} long-s characters remain in output!")
    else:
        print("Long-s normalisation: all \u017f replaced with s.")

    print("\nDone.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate a Perseus-compatible TEI XML English translation of Diodorus Siculus.

Reads existing alignment data and Booth's English text, produces:
  1. output/tlg0060.tlg001.perseus-eng80.xml  — TEI translation file
  2. output/__cts__eng80_fragment.xml          — CTS catalog entry

No pipeline rerun needed; works from existing output files.
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALIGNMENTS_PATH = PROJECT_ROOT / "output" / "entity_validated_alignments.json"
BOOTH_PATH = PROJECT_ROOT / "output" / "booth_normalised.json"
GREEK_PATH = PROJECT_ROOT / "output" / "perseus_extracted.json"
OUT_TEI = PROJECT_ROOT / "output" / "tlg0060.tlg001.perseus-eng80.xml"
OUT_CTS = PROJECT_ROOT / "output" / "__cts__eng80_fragment.xml"
OUT_CSV = PROJECT_ROOT / "output" / "chapter_sentence_counts.csv"

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NSMAP = {None: TEI_NS}

URN_BASE = "urn:cts:greekLit:tlg0060.tlg001.perseus-eng80"


def load_inputs():
    """Load alignment, Booth, and Greek data, exit on missing files."""
    for path, label in [
        (ALIGNMENTS_PATH, "alignments"),
        (BOOTH_PATH, "Booth text"),
        (GREEK_PATH, "Greek sections"),
    ]:
        if not path.exists():
            print(f"Error: {label} not found at {path}")
            sys.exit(1)

    with open(ALIGNMENTS_PATH) as f:
        alignments = json.load(f)
    with open(BOOTH_PATH) as f:
        booth = json.load(f)
    with open(GREEK_PATH) as f:
        greek = json.load(f)

    return alignments, booth, greek


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


def build_para_milestones(alignments):
    """
    Map each Booth paragraph to its Greek section milestones.

    Returns:
        para_milestones: dict (book, div2, p_index) -> list of "chapter.section"
            strings, present only for the FIRST paragraph of each alignment group.
        total_milestones: int — total milestone count.
    """
    # Group alignment records by (book, group_id)
    groups = defaultdict(list)
    for rec in alignments:
        groups[(rec["book"], rec["group_id"])].append(rec)

    para_milestones = {}
    total_milestones = 0

    for (book, group_id), recs in groups.items():
        # Sort records by CTS ref to get consistent ordering
        recs.sort(key=lambda r: (
            chapter_sort_key(parse_cts_ref(r["greek_cts_ref"])[1]),
            section_sort_key(parse_cts_ref(r["greek_cts_ref"])[2]),
        ))

        # Build milestone labels: "chapter.section"
        milestones = []
        for rec in recs:
            _, ch, sec = parse_cts_ref(rec["greek_cts_ref"])
            milestones.append(f"{ch}.{sec}")

        total_milestones += len(milestones)

        # Attach milestones to the first Booth paragraph of the group
        base_div2 = recs[0]["booth_div2_index"]
        base_p = recs[0]["booth_p_index"]
        para_milestones[(book, base_div2, base_p)] = milestones

    return para_milestones, total_milestones


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
    sponsor.text = "Alignment Project"

    # publicationStmt
    pub_stmt = etree.SubElement(file_desc, f"{{{TEI_NS}}}publicationStmt")
    publisher = etree.SubElement(pub_stmt, f"{{{TEI_NS}}}publisher")
    publisher.text = "Alignment Project"
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
    bibl_note.text = (
        "Source: EEBO-TCP (Early English Books Online Text Creation Partnership), "
        "Oxford Text Archive A36034. Licensed under CC0 1.0 Universal "
        "(public domain dedication)."
    )

    # encodingDesc with refsDecl for CTS
    encoding_desc = etree.SubElement(header, f"{{{TEI_NS}}}encodingDesc")
    refs_decl = etree.SubElement(encoding_desc, f"{{{TEI_NS}}}refsDecl")
    refs_decl.set("n", "CTS")

    # Two cRefPatterns: chapter and book (most specific first)
    # Chapters are Booth's chapter divisions. Greek sections are milestones.
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
        "English text from G. Booth's 1700 translation, sourced from "
        "EEBO-TCP (OTA A36034, CC0 1.0 Universal). "
        "Aligned to the Perseus Greek section structure by the "
        "Alignment Project using cross-lingual embedding similarity and "
        "named-entity anchoring. Long-s characters have been normalised to "
        "modern s. The text is organised following Booth's own chapter "
        "divisions. Greek section boundaries are marked with milestone "
        "elements (unit='section', n='chapter.section') indicating where "
        "each Greek section begins within the English text. Each Booth "
        "paragraph appears exactly once in its original position."
    )

    return header


def build_tei(booth, para_milestones):
    """Build TEI XML following Booth's chapter structure with Greek milestones."""
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

    for book_data in booth["books"]:
        book_n = book_data["div1_n"]

        book_div = etree.SubElement(trans_div, f"{{{TEI_NS}}}div")
        book_div.set("type", "textpart")
        book_div.set("subtype", "book")
        book_div.set("n", book_n)

        head = etree.SubElement(book_div, f"{{{TEI_NS}}}head")
        head.text = f"BOOK {roman(int(book_n))}"

        for chapter in book_data["chapters"]:
            div2 = chapter["div2_index"]

            ch_div = etree.SubElement(book_div, f"{{{TEI_NS}}}div")
            ch_div.set("type", "textpart")
            ch_div.set("subtype", "chapter")
            ch_div.set("n", str(div2 + 1))

            for para in chapter["paragraphs"]:
                p_idx = para["p_index"]
                p_key = (book_n, div2, p_idx)

                # Emit milestones before the first paragraph of each group
                milestones = para_milestones.get(p_key, [])
                for ms_label in milestones:
                    ms = etree.SubElement(ch_div, f"{{{TEI_NS}}}milestone")
                    ms.set("unit", "section")
                    ms.set("n", ms_label)

                # Emit the paragraph
                p = etree.SubElement(ch_div, f"{{{TEI_NS}}}p")
                p.text = normalise_long_s(para["text"])

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
        "structure by the Alignment Project."
    )

    return root


def print_summary(alignments, booth, para_milestones, total_milestones):
    """Print verification summary."""
    print("\n=== TEI Generation Summary ===\n")

    total_booth_paras = sum(
        len(ch["paragraphs"])
        for book in booth["books"]
        for ch in book["chapters"]
    )
    total_booth_chapters = sum(len(book["chapters"]) for book in booth["books"])

    print(f"Booth chapters: {total_booth_chapters}")
    print(f"Booth paragraphs: {total_booth_paras}")
    print(f"Total milestone markers: {total_milestones}")
    print(f"Total alignment records: {len(alignments)}")

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

    # Verify every CTS ref is covered by a milestone
    cts_refs = set()
    for a in alignments:
        _, ch, sec = parse_cts_ref(a["greek_cts_ref"])
        cts_refs.add((a["book"], f"{ch}.{sec}"))

    all_ms = set()
    for (book, _, _), milestones in para_milestones.items():
        for ms in milestones:
            all_ms.add((book, ms))

    missing = cts_refs - all_ms
    if missing:
        print(f"\nWARNING: {len(missing)} Greek sections have no milestone!")
        for m in sorted(missing)[:10]:
            print(f"  {m}")
    else:
        print("\nAll Greek sections have corresponding milestones.")


def count_english_sentences(text):
    """Count English sentences (split on . ? !)."""
    sentences = re.findall(r'[^.!?]+[.!?]', text)
    return max(len(sentences), 1) if text.strip() else 0


def count_greek_sentences(text):
    """Count Greek sentences (split on . · ;)."""
    sentences = re.findall(r'[^.·;]+[.·;]', text)
    return max(len(sentences), 1) if text.strip() else 0


def write_chapter_csv(alignments, booth, greek_sections):
    """Write CSV comparing Greek and English sentence counts per Greek chapter."""
    # Build Greek chapter -> concatenated text
    greek_by_chapter = defaultdict(lambda: {"text": "", "sections": 0})
    for sec in greek_sections:
        key = (sec["book"], sec["chapter"])
        greek_by_chapter[key]["text"] += " " + sec["text"]
        greek_by_chapter[key]["sections"] += 1

    # Build Booth lookup: (book, div2, p_index) -> text
    booth_lookup = {}
    for book in booth["books"]:
        for ch in book["chapters"]:
            for para in ch["paragraphs"]:
                booth_lookup[(book["div1_n"], ch["div2_index"], para["p_index"])] = para["text"]

    # Map Greek chapter -> set of Booth paragraph keys via alignment groups
    groups = defaultdict(list)
    for rec in alignments:
        groups[(rec["book"], rec["group_id"])].append(rec)

    greek_ch_to_booth = defaultdict(set)
    for (book, gid), recs in groups.items():
        # Collect unique Booth paragraphs for this group
        en_size = recs[0]["group_size_en"]
        base_div2 = recs[0]["booth_div2_index"]
        base_p = recs[0]["booth_p_index"]
        booth_keys = set()
        for offset in range(en_size):
            bk = (book, base_div2, base_p + offset)
            if bk in booth_lookup:
                booth_keys.add(bk)

        # Each Greek section in the group maps to these Booth paragraphs
        for rec in recs:
            _, ch, _ = parse_cts_ref(rec["greek_cts_ref"])
            greek_ch_to_booth[(rec["book"], ch)].update(booth_keys)

    # Build rows
    rows = []
    for (book, ch), gdata in sorted(
        greek_by_chapter.items(),
        key=lambda x: (int(x[0][0]), chapter_sort_key(x[0][1])),
    ):
        greek_text = gdata["text"]
        greek_secs = gdata["sections"]
        greek_sents = count_greek_sentences(greek_text)

        booth_keys = greek_ch_to_booth.get((book, ch), set())
        en_texts = [booth_lookup[k] for k in booth_keys if k in booth_lookup]
        en_paras = len(en_texts)
        en_combined = " ".join(normalise_long_s(t) for t in en_texts)
        en_sents = count_english_sentences(en_combined)

        rows.append({
            "book": book,
            "greek_chapter": ch,
            "greek_sections": greek_secs,
            "greek_sentences": greek_sents,
            "english_paragraphs": en_paras,
            "english_sentences": en_sents,
        })

    fieldnames = [
        "book", "greek_chapter", "greek_sections", "greek_sentences",
        "english_paragraphs", "english_sentences",
    ]
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote: {OUT_CSV} ({len(rows)} rows)")


def main():
    print("Loading input files...")
    alignments, booth, greek = load_inputs()

    print("Mapping alignment groups to Booth paragraphs...")
    para_milestones, total_milestones = build_para_milestones(alignments)

    print("Building TEI XML (Booth structure with Greek milestones)...")
    tei = build_tei(booth, para_milestones)

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

    # Chapter sentence counts CSV
    print("\nWriting chapter sentence counts...")
    write_chapter_csv(alignments, booth, greek["sections"])

    # Verification
    print_summary(alignments, booth, para_milestones, total_milestones)

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

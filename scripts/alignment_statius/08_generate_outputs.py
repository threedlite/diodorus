#!/usr/bin/env python3
"""
Generate final TEI XML and reports for Statius alignment.

Follows the English-driven approach: Mozley's paragraph structure is the
TEI skeleton, Latin line milestones are inserted as <milestone> elements.

Outputs:
  output/statius/alignment_statius_perseus.xml   — TEI standoff alignment
  output/statius/alignment_statius_perseus.tsv    — tabular format
  output/statius/alignment_report.md              — quality report
  output/statius/phi1020.phi001.perseus-eng80.xml — Perseus-compatible TEI (Thebaid)
  output/statius/phi1020.phi003.perseus-eng80.xml — Perseus-compatible TEI (Achilleid)

CTS URN: urn:cts:latinLit:phi1020.phi001.perseus-eng80 (28 = Mozley 1928)
"""

import csv
import json
import re
import sys
from collections import defaultdict, Counter
from datetime import date
from pathlib import Path

from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALIGNMENTS_PATH = PROJECT_ROOT / "build" / "statius" / "entity_validated_alignments.json"
MOZLEY_PATH = PROJECT_ROOT / "build" / "statius" / "mozley_normalised.json"
PASSAGES_PATH = PROJECT_ROOT / "build" / "statius" / "latin_passages.json"

OUT_DIR = PROJECT_ROOT / "build" / "statius"
OUT_STANDOFF = OUT_DIR / "alignment_statius_perseus.xml"
OUT_TSV = OUT_DIR / "alignment_statius_perseus.tsv"
OUT_REPORT = OUT_DIR / "alignment_report.md"

# Perseus-compatible TEI files per work
OUT_TEI = {
    "Thebaid": OUT_DIR / "phi1020.phi001.perseus-eng80.xml",
    "Achilleid": OUT_DIR / "phi1020.phi003.perseus-eng80.xml",
}

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NSMAP = {None: TEI_NS}

URN_BASE = {
    "Thebaid": "urn:cts:latinLit:phi1020.phi001.perseus-eng80",
    "Achilleid": "urn:cts:latinLit:phi1020.phi003.perseus-eng80",
}

PHI_WORK = {
    "Thebaid": "phi1020.phi001",
    "Achilleid": "phi1020.phi003",
}


def load_inputs():
    """Load alignment, Mozley, and passages data."""
    for path, label in [
        (ALIGNMENTS_PATH, "alignments"),
        (MOZLEY_PATH, "Mozley text"),
        (PASSAGES_PATH, "Latin passages"),
    ]:
        if not path.exists():
            print(f"Error: {label} not found at {path}")
            sys.exit(1)

    with open(ALIGNMENTS_PATH) as f:
        alignments = json.load(f)
    with open(MOZLEY_PATH) as f:
        mozley = json.load(f)
    with open(PASSAGES_PATH) as f:
        passages = json.load(f)

    return alignments, mozley, passages


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


def build_para_milestones(alignments):
    """
    Map each Mozley paragraph to its Latin line milestones.

    Returns:
        para_milestones: dict (work, book, p_index) -> list of "book.first_line" strings
        total_milestones: int
    """
    # Group alignment records by (work, book, group_id)
    groups = defaultdict(list)
    for rec in alignments:
        groups[(rec["work"], rec["book"], rec["group_id"])].append(rec)

    para_milestones = {}
    total_milestones = 0

    for (work, book, group_id), recs in groups.items():
        # Sort by first line number
        recs.sort(key=lambda r: int(r["latin_first_line"]))

        # Build milestone labels: "book.first_line"
        milestones = []
        for rec in recs:
            milestones.append(f"{book}.{rec['latin_first_line']}")

        total_milestones += len(milestones)

        # Attach milestones to the first English paragraph of the group
        base_p = recs[0]["english_p_index"]
        para_milestones[(work, book, base_p)] = milestones

    return para_milestones, total_milestones


def build_tei_header(work_name):
    """Build the TEI header element for a specific work."""
    header = etree.SubElement(etree.Element("dummy"), f"{{{TEI_NS}}}teiHeader")
    header.set(f"{{{XML_NS}}}lang", "eng")

    # fileDesc
    file_desc = etree.SubElement(header, f"{{{TEI_NS}}}fileDesc")

    # titleStmt
    title_stmt = etree.SubElement(file_desc, f"{{{TEI_NS}}}titleStmt")
    title = etree.SubElement(title_stmt, f"{{{TEI_NS}}}title")
    title.text = f"Statius, {work_name}"
    title.set("type", "work")
    author = etree.SubElement(title_stmt, f"{{{TEI_NS}}}author")
    author.text = "P. Papinius Statius"
    editor = etree.SubElement(title_stmt, f"{{{TEI_NS}}}editor")
    editor.set("role", "translator")
    editor.text = "J.H. Mozley"
    sponsor = etree.SubElement(title_stmt, f"{{{TEI_NS}}}sponsor")
    sponsor.text = "Alignment Project"

    # publicationStmt
    pub_stmt = etree.SubElement(file_desc, f"{{{TEI_NS}}}publicationStmt")
    publisher = etree.SubElement(pub_stmt, f"{{{TEI_NS}}}publisher")
    publisher.text = "Alignment Project"
    pub_id = etree.SubElement(pub_stmt, f"{{{TEI_NS}}}idno")
    pub_id.set("type", "filename")
    pub_id.text = f"{PHI_WORK[work_name]}.perseus-eng80.xml"
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
    bibl_author.text = "P. Papinius Statius"
    bibl_title = etree.SubElement(bibl, f"{{{TEI_NS}}}title")
    bibl_title.text = f"Statius, {work_name}"
    bibl_editor = etree.SubElement(bibl, f"{{{TEI_NS}}}editor")
    bibl_editor.set("role", "translator")
    bibl_editor.text = "J.H. Mozley"
    bibl_pub = etree.SubElement(bibl, f"{{{TEI_NS}}}pubPlace")
    bibl_pub.text = "London / New York"
    bibl_publisher = etree.SubElement(bibl, f"{{{TEI_NS}}}publisher")
    bibl_publisher.text = "William Heinemann / G.P. Putnam's Sons"
    bibl_date = etree.SubElement(bibl, f"{{{TEI_NS}}}date")
    bibl_date.text = "1928"
    bibl_note = etree.SubElement(bibl, f"{{{TEI_NS}}}note")
    bibl_note.text = (
        "Loeb Classical Library. Translation is public domain "
        "(published 1928, PD in US since 2024 under 95-year rule). "
        "English text transcribed by Wikisource contributors (CC BY-SA 4.0)."
    )

    # encodingDesc with refsDecl for CTS
    encoding_desc = etree.SubElement(header, f"{{{TEI_NS}}}encodingDesc")
    refs_decl = etree.SubElement(encoding_desc, f"{{{TEI_NS}}}refsDecl")
    refs_decl.set("n", "CTS")

    # Two cRefPatterns: line and book
    line_pat = etree.SubElement(refs_decl, f"{{{TEI_NS}}}cRefPattern")
    line_pat.set("n", "line")
    line_pat.set("matchPattern", r"(\w+)\.(\w+)")
    line_pat.set(
        "replacementPattern",
        "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@n='$1']"
        "/tei:p[preceding::tei:milestone[@unit='line'][@n='$1.$2']])",
    )
    line_p = etree.SubElement(line_pat, f"{{{TEI_NS}}}p")
    line_p.text = "This pointer pattern extracts book and line."

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
        f"English text from J.H. Mozley's 1928 translation (Loeb Classical Library), "
        f"sourced from Wikisource (CC BY-SA 4.0). The translation is public domain "
        f"in the US (published 1928, PD since 2024 under the 95-year rule). "
        f"Aligned to the Perseus Latin text by the Alignment Project using "
        f"cross-lingual embedding similarity and named-entity anchoring. "
        f"The text is organised following Mozley's paragraph divisions. "
        f"Latin line boundaries are marked with milestone elements "
        f"(unit='line', n='book.line') indicating where each Latin passage "
        f"begins within the English text. Each Mozley paragraph appears "
        f"exactly once in its original position."
    )

    return header


def build_work_tei(work_name, work_data, para_milestones):
    """Build Perseus-compatible TEI XML for one work (English-driven)."""
    tei = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=NSMAP)

    # Header
    header = build_tei_header(work_name)
    tei.append(header)

    # Text body
    text = etree.SubElement(tei, f"{{{TEI_NS}}}text")
    body = etree.SubElement(text, f"{{{TEI_NS}}}body")

    # Top-level translation div
    trans_div = etree.SubElement(body, f"{{{TEI_NS}}}div")
    trans_div.set("type", "translation")
    trans_div.set(f"{{{XML_NS}}}lang", "eng")
    trans_div.set("n", URN_BASE[work_name])

    for book in work_data["books"]:
        book_n = str(book["book"])

        book_div = etree.SubElement(trans_div, f"{{{TEI_NS}}}div")
        book_div.set("type", "textpart")
        book_div.set("subtype", "book")
        book_div.set("n", book_n)

        head = etree.SubElement(book_div, f"{{{TEI_NS}}}head")
        head.text = f"BOOK {roman(int(book_n))}"

        for idx, para in enumerate(book["paragraphs"]):
            p_key = (work_name, book_n, idx)

            # Emit milestones before the paragraph
            milestones = para_milestones.get(p_key, [])
            for ms_label in milestones:
                ms = etree.SubElement(book_div, f"{{{TEI_NS}}}milestone")
                ms.set("unit", "line")
                ms.set("n", ms_label)

            # Emit the paragraph
            p = etree.SubElement(book_div, f"{{{TEI_NS}}}p")
            p.text = para.get("text_normalised", para["text"])

    return tei


def generate_standoff_xml(alignments):
    """Generate TEI standoff alignment XML."""
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">',
        "  <teiHeader>",
        "    <fileDesc>",
        "      <titleStmt>",
        "        <title>Alignment: Mozley English (1928) / Perseus Latin Statius</title>",
        "      </titleStmt>",
        "      <publicationStmt><p>Generated automatically.</p></publicationStmt>",
        "      <sourceDesc>",
        '        <bibl xml:id="mozley">J.H. Mozley, Statius (Loeb, 1928). PD in US since 2024. Transcription from Wikisource (CC BY-SA 4.0).</bibl>',
        '        <bibl xml:id="perseus">PerseusDL canonical-latinLit phi1020</bibl>',
        "      </sourceDesc>",
        "    </fileDesc>",
        "  </teiHeader>",
        "  <text>",
        "    <body>",
    ]

    by_work_book = defaultdict(list)
    for a in alignments:
        by_work_book[(a["work"], a["book"])].append(a)

    for (work, book_n) in sorted(by_work_book.keys(), key=lambda x: (x[0], int(x[1]))):
        book_aligns = by_work_book[(work, book_n)]
        phi = PHI_WORK[work]
        xml_lines.append(f'      <linkGrp type="alignment" subtype="{work}-book-{book_n}">')
        for a in book_aligns:
            src = f"mozley:{work.lower()}/book-{book_n}/p[{a['english_p_index']}]"
            tgt = (
                f"urn:cts:latinLit:{phi}.{a['latin_edition']}:"
                f"{book_n}.{a['latin_first_line']}-{a['latin_last_line']}"
            )
            conf = a.get("combined_score", a["similarity"])
            xml_lines.append(
                f'        <link target="{src} {tgt}" ana="confidence:{conf}"/>'
            )
        xml_lines.append("      </linkGrp>")

    xml_lines += [
        "    </body>",
        "  </text>",
        "</TEI>",
    ]

    with open(OUT_STANDOFF, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))


def generate_tsv(alignments):
    """Generate tabular output."""
    fields = [
        "work", "book", "latin_first_line", "latin_last_line",
        "latin_edition", "english_p_index",
        "embedding_sim", "entity_score", "combined_score",
    ]
    with open(OUT_TSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for a in alignments:
            writer.writerow({
                "work": a["work"],
                "book": a["book"],
                "latin_first_line": a["latin_first_line"],
                "latin_last_line": a["latin_last_line"],
                "latin_edition": a["latin_edition"],
                "english_p_index": a["english_p_index"],
                "embedding_sim": a["similarity"],
                "entity_score": a.get("entity_overlap_score", ""),
                "combined_score": a.get("combined_score", a["similarity"]),
            })


def generate_report(alignments):
    """Generate quality report."""
    total = len(alignments)
    scores = [a.get("combined_score", a["similarity"]) for a in alignments]
    high = sum(1 for s in scores if s >= 0.6)
    med = sum(1 for s in scores if 0.3 <= s < 0.6)
    low = sum(1 for s in scores if s < 0.3)
    avg_score = sum(scores) / len(scores) if scores else 0

    works_covered = sorted(set(a["work"] for a in alignments))
    books_covered = sorted(
        set(f"{a['work']} {a['book']}" for a in alignments)
    )

    # Detect model
    custom_model_path = PROJECT_ROOT / "models" / "latin-embedding"
    model_name = (
        "Custom Latin embedding (xlm-roberta-base fine-tuned, 92.6% Top-1)"
        if custom_model_path.exists()
        else "paraphrase-multilingual-MiniLM-L12-v2 (generic baseline)"
    )

    report = f"""# Statius Alignment Quality Report

**Date:** {date.today().isoformat()}
**English source:** J.H. Mozley (1928) — Loeb Classical Library
**English transcription:** Wikisource (CC BY-SA 4.0)
**English copyright:** Public domain in US (published 1928, PD since 2024 under 95-year rule)
**Latin source:** Perseus canonical-latinLit phi1020
**Embedding model:** {model_name}

## Coverage

- **Total alignments:** {total}
- **Works:** {', '.join(works_covered)}
- **Books aligned:** {', '.join(books_covered)}

## Confidence Distribution

| Band | Count | Percentage |
|---|---|---|
| High (>= 0.6) | {high} | {high / total * 100:.1f}% |
| Medium (0.3-0.6) | {med} | {med / total * 100:.1f}% |
| Low (< 0.3) -- needs review | {low} | {low / total * 100:.1f}% |

- **Mean combined score:** {avg_score:.3f}

## Methodology

1. Latin verse lines extracted from Perseus TEI XML (phi1020)
2. Lines grouped into ~10-line passages for embedding similarity
3. Mozley English paragraphs lightly normalised
4. Book-level 1:1 matching (Thebaid 1-12, Achilleid 1-2)
5. Section-level alignment via segmental DP on cross-lingual embeddings
   (groups 1-5 Latin passages onto 1-2 English paragraphs)
6. Validation via named-entity fuzzy matching (Latin -> English)
7. Combined score: 70% embedding similarity + 30% entity overlap

## Output Files

- `alignment_statius_perseus.xml` — TEI standoff alignment
- `alignment_statius_perseus.tsv` — tabular format with scores
- `entity_validated_alignments.json` — full alignment data
- `phi1020.phi001.perseus-eng80.xml` — Perseus-compatible TEI (Thebaid)
- `phi1020.phi003.perseus-eng80.xml` — Perseus-compatible TEI (Achilleid)
"""

    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report)


def print_summary(alignments, mozley, para_milestones, total_milestones):
    """Print verification summary."""
    print("\n=== TEI Generation Summary ===\n")

    total_paras = 0
    for work_key, work_data in mozley["works"].items():
        for book in work_data["books"]:
            total_paras += len(book["paragraphs"])

    print(f"Mozley paragraphs: {total_paras}")
    print(f"Total milestone markers: {total_milestones}")
    print(f"Total alignment records: {len(alignments)}")

    # Group distribution
    gr_sizes = Counter()
    en_sizes = Counter()
    groups_seen = set()
    for a in alignments:
        key = (a["work"], a["book"], a["group_id"])
        if key not in groups_seen:
            groups_seen.add(key)
            gr_sizes[a["group_size_lat"]] += 1
            en_sizes[a["group_size_en"]] += 1

    print(f"\nAlignment groups: {len(groups_seen)}")
    print("  Latin passage group sizes:", dict(sorted(gr_sizes.items())))
    print("  English paragraph group sizes:", dict(sorted(en_sizes.items())))

    # Check milestone coverage
    all_passage_keys = set()
    for a in alignments:
        all_passage_keys.add((a["work"], a["book"], a["latin_first_line"]))

    all_ms = set()
    for (work, book, p_idx), milestones in para_milestones.items():
        for ms in milestones:
            # ms format is "book.first_line"
            parts = ms.split(".", 1)
            all_ms.add((work, parts[0], parts[1]))

    missing = all_passage_keys - all_ms
    if missing:
        print(f"\nWARNING: {len(missing)} Latin passages have no milestone!")
        for m in sorted(missing)[:10]:
            print(f"  {m}")
    else:
        print("\nAll Latin passages have corresponding milestones.")


def main():
    print("Loading input files...")
    alignments, mozley, passages = load_inputs()

    print("Mapping alignment groups to Mozley paragraphs...")
    para_milestones, total_milestones = build_para_milestones(alignments)

    # Generate per-work Perseus-compatible TEI
    for work_name in ["Thebaid", "Achilleid"]:
        work_key = work_name.lower()
        work_data = mozley["works"].get(work_key)
        if not work_data:
            print(f"  No data for {work_name}, skipping TEI")
            continue

        print(f"\nBuilding Perseus TEI for {work_name}...")
        tei = build_work_tei(work_name, work_data, para_milestones)
        tree = etree.ElementTree(tei)

        out_path = OUT_TEI[work_name]
        with open(out_path, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(
                b'<?xml-model href="http://www.stoa.org/epidoc/schema/latest/tei-epidoc.rng"'
                b' schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
            )
            tree.write(f, encoding="UTF-8", xml_declaration=False, pretty_print=True)
        print(f"  Wrote: {out_path}")

        # Validate well-formedness
        etree.parse(str(out_path))
        print(f"  XML is well-formed.")

    # Generate standoff alignment XML
    print("\nGenerating standoff alignment XML...")
    generate_standoff_xml(alignments)
    print(f"  Wrote: {OUT_STANDOFF}")

    # Generate TSV
    print("Generating TSV...")
    generate_tsv(alignments)
    print(f"  Wrote: {OUT_TSV}")

    # Generate quality report
    print("Generating quality report...")
    generate_report(alignments)
    print(f"  Wrote: {OUT_REPORT}")

    # CTS catalog fragment
    out_cts = OUT_DIR / "__cts__eng80_statius.xml"
    cts_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<!-- CTS catalog entries for Statius English translations -->']
    for work_name, urn in URN_BASE.items():
        phi = PHI_WORK[work_name]
        cts_lines.append(
            f'<ti:translation xmlns:ti="http://chs.harvard.edu/xmlns/cts" '
            f'urn="{urn}" workUrn="urn:cts:latinLit:{phi}" xml:lang="eng">'
        )
        cts_lines.append(f'  <ti:label xml:lang="eng">J.H. Mozley (1928)</ti:label>')
        cts_lines.append(f'  <ti:description xml:lang="eng">J.H. Mozley translation of '
                         f'Statius, {work_name}. Public domain (Loeb 1928).</ti:description>')
        cts_lines.append('</ti:translation>')
    with open(out_cts, "w", encoding="utf-8") as f:
        f.write("\n".join(cts_lines) + "\n")
    print(f"  Wrote: {out_cts}")

    # Summary
    print_summary(alignments, mozley, para_milestones, total_milestones)

    print("\nDone.")


if __name__ == "__main__":
    main()

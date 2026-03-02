#!/usr/bin/env python3
"""
Build a plain-text Latin corpus from Perseus canonical-latinLit.
Target: one sentence per line, UTF-8.

Input:
  - data-sources/perseus/canonical-latinLit/data/ (all Latin editions)

Output:
  - data-sources/latin_corpus/latin_all.txt

Expected yield: 300k-800k sentences.
"""

import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT = PROJECT_ROOT / "data-sources" / "latin_corpus" / "latin_all.txt"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def extract_text_from_tei(xml_path):
    """Extract all text content from a TEI XML file."""
    try:
        parser = etree.XMLParser(load_dtd=False, no_network=True, recover=True)
        tree = etree.parse(str(xml_path), parser)
    except (etree.XMLSyntaxError, OSError):
        return ""

    root = tree.getroot()

    # Find body, namespace-agnostic
    body = root.find(".//{*}body")
    if body is None:
        return ""

    # Get all text, skip notes and apparatus
    text = []
    for el in body.iter():
        tag = etree.QName(el.tag).localname if isinstance(el.tag, str) else ""
        if tag in ("note", "app", "bibl", "ref", "fw", "gap", "figure"):
            continue
        if el.text:
            text.append(el.text)
        if el.tail:
            text.append(el.tail)

    return " ".join(text)


def is_latin(text):
    """Check if text is predominantly Latin characters (basic Latin + extended)."""
    # Latin text uses basic ASCII letters plus some accented chars
    # Exclude if predominantly Greek, Hebrew, etc.
    latin_chars = sum(1 for c in text if c.isalpha() and (
        "A" <= c <= "Z" or "a" <= c <= "z" or
        "\u00C0" <= c <= "\u024F"  # Latin Extended
    ))
    greek_chars = sum(1 for c in text if "\u0370" <= c <= "\u03FF" or "\u1F00" <= c <= "\u1FFF")
    alpha_chars = sum(1 for c in text if c.isalpha())
    if alpha_chars == 0:
        return False
    # Must be mostly Latin script, not Greek
    return latin_chars > alpha_chars * 0.5 and greek_chars < alpha_chars * 0.2


def sentence_split_latin(text):
    """Split Latin text into sentences on . ? !"""
    sents = re.split(r"(?<=[.?!])\s+", text)
    return [s.strip() for s in sents if len(s.strip()) > 10]


# Collect from Perseus canonical-latinLit
all_sentences = []

latinlit_dir = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-latinLit" / "data"
if latinlit_dir.exists():
    for xml_file in sorted(latinlit_dir.rglob("*.xml")):
        if "__cts__" in xml_file.name:
            continue
        # Only Latin editions (not English translations)
        if "-lat" not in xml_file.name and "-lat" not in xml_file.stem:
            continue
        text = extract_text_from_tei(xml_file)
        if is_latin(text) and len(text) > 100:
            sents = sentence_split_latin(text)
            all_sentences.extend(sents)
    print(f"canonical-latinLit: {len(all_sentences)} sentences extracted")
else:
    print(f"Error: canonical-latinLit not found at {latinlit_dir}")
    print("Clone it first:")
    print("  cd data-sources/perseus")
    print("  git clone --filter=blob:none --sparse https://github.com/PerseusDL/canonical-latinLit.git")
    raise SystemExit(1)

# Deduplicate and clean
seen = set()
clean_sents = []
for s in all_sentences:
    s = re.sub(r"\s+", " ", s).strip()
    if s not in seen and len(s) > 15 and is_latin(s):
        seen.add(s)
        clean_sents.append(s)

# Write out
with open(OUTPUT, "w", encoding="utf-8") as f:
    for s in clean_sents:
        f.write(s + "\n")

print(f"\nTotal unique Latin sentences: {len(clean_sents)}")
print(f"Corpus size: {OUTPUT.stat().st_size / 1024 / 1024:.1f} MB")
print(f"Saved to {OUTPUT}")

#!/usr/bin/env python3
"""
Build a plain-text Ancient Greek corpus from Perseus and First1KGreek.
Target: one sentence per line, UTF-8, polytonic Greek.

Input:
  - data-sources/perseus/canonical-greekLit/data/ (all Greek editions)
  - data-sources/greek_corpus/First1KGreek/data/

Output:
  - data-sources/greek_corpus/ancient_greek_all.txt

Expected yield: 200k-500k sentences, 20-60 MB.
"""

import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT = PROJECT_ROOT / "data-sources" / "greek_corpus" / "ancient_greek_all.txt"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def extract_text_from_tei(xml_path):
    """Extract all text content from a TEI XML file."""
    try:
        tree = etree.parse(str(xml_path))
    except etree.XMLSyntaxError:
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


def is_greek(text):
    """Check if text is predominantly Greek characters."""
    greek = sum(1 for c in text if "\u0370" <= c <= "\u03FF" or "\u1F00" <= c <= "\u1FFF")
    return greek > len(text) * 0.3


def sentence_split_greek(text):
    """Split Greek text into sentences on . ; · (ano teleia) and ·"""
    # Greek uses · (middle dot / ano teleia) as a semicolon
    # and ; as a question mark
    sents = re.split(r"(?<=[.·;])\s+", text)
    return [s.strip() for s in sents if len(s.strip()) > 10]


# Collect from all sources
all_sentences = []

# Source 1: Perseus canonical-greekLit
perseus_dir = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data"
if perseus_dir.exists():
    for xml_file in sorted(perseus_dir.rglob("*.xml")):
        if "__cts__" in xml_file.name:
            continue
        if "-grc" not in xml_file.name and "-grc" not in xml_file.stem:
            continue  # Only Greek editions
        text = extract_text_from_tei(xml_file)
        if is_greek(text):
            sents = sentence_split_greek(text)
            all_sentences.extend(sents)
    print(f"Perseus: {len(all_sentences)} sentences so far")
else:
    print(f"Warning: Perseus dir not found at {perseus_dir}")

# Source 2: First1KGreek
f1k_dir = PROJECT_ROOT / "data-sources" / "greek_corpus" / "First1KGreek" / "data"
if f1k_dir.exists():
    count_before = len(all_sentences)
    for xml_file in sorted(f1k_dir.rglob("*.xml")):
        if "__cts__" in xml_file.name:
            continue
        text = extract_text_from_tei(xml_file)
        if is_greek(text):
            sents = sentence_split_greek(text)
            all_sentences.extend(sents)
    print(f"First1KGreek: {len(all_sentences) - count_before} new sentences")
else:
    print(f"Note: First1KGreek not found at {f1k_dir} — skipping")

# Deduplicate and clean
seen = set()
clean_sents = []
for s in all_sentences:
    s = re.sub(r"\s+", " ", s).strip()
    if s not in seen and len(s) > 15 and is_greek(s):
        seen.add(s)
        clean_sents.append(s)

# Write out
with open(OUTPUT, "w", encoding="utf-8") as f:
    for s in clean_sents:
        f.write(s + "\n")

print(f"\nTotal unique Greek sentences: {len(clean_sents)}")
print(f"Corpus size: {OUTPUT.stat().st_size / 1024 / 1024:.1f} MB")
print(f"Saved to {OUTPUT}")

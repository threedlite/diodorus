#!/usr/bin/env python3
"""
Build a Greek-English parallel corpus from Perseus, which provides
aligned Greek editions and English translations of the same works.

Strategy:
  1. Find works that have both a grc and an eng edition in Perseus
  2. Extract text at the section level (CTS book.chapter.section)
  3. Pair Greek sections with their English translations
  4. Filter by length

Input:
  - data-sources/perseus/canonical-greekLit/data/

Output:
  - data-sources/parallel/grc_eng_pairs.jsonl

Expected yield: 10k-30k section-level pairs (with expanded Perseus checkout).
"""

import json
import re
from pathlib import Path
from lxml import etree
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data"
OUTPUT = PROJECT_ROOT / "data-sources" / "parallel" / "grc_eng_pairs.jsonl"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def extract_sections(xml_path):
    """Extract text keyed by CTS reference (book.chapter.section or similar)."""
    try:
        tree = etree.parse(str(xml_path))
    except etree.XMLSyntaxError:
        return {}

    root = tree.getroot()
    sections = {}

    # Find all leaf-level textpart divs
    for div in root.iter():
        tag = etree.QName(div.tag).localname if isinstance(div.tag, str) else ""
        if tag != "div":
            continue

        subtype = div.get("subtype", "")
        div_type = div.get("type", "")
        n = div.get("n", "")

        if subtype in ("section", "verse", "paragraph", "chapter") or \
           div_type == "textpart":
            # Check if this is a leaf node (no child textparts)
            child_divs = [c for c in div if
                          isinstance(c.tag, str) and
                          etree.QName(c.tag).localname == "div"]
            has_child_textparts = any(
                c.get("type") == "textpart" or c.get("subtype") in
                ("section", "verse", "paragraph", "chapter")
                for c in child_divs
            )

            if not has_child_textparts and n:
                # Build reference by walking up, but stop at edition/translation div
                # (whose n is a full URN like urn:cts:greekLit:...)
                ref_parts = [n]
                parent = div.getparent()
                while parent is not None:
                    p_tag = etree.QName(parent.tag).localname if isinstance(parent.tag, str) else ""
                    if p_tag == "div":
                        p_type = parent.get("type", "")
                        p_n = parent.get("n", "")
                        # Stop at the edition/translation wrapper div
                        if p_type in ("edition", "translation") or "urn:" in p_n:
                            break
                        if p_n:
                            ref_parts.insert(0, p_n)
                    parent = parent.getparent()

                ref = ".".join(ref_parts)
                text = re.sub(r"\s+", " ", "".join(div.itertext())).strip()
                if text:
                    sections[ref] = text

    return sections


# Scan for all text files, grouped by work (textgroup.work)
works = defaultdict(dict)  # work_id -> {"grc": {ref: text}, "eng": {ref: text}}

if PERSEUS_DIR.exists():
    for xml_file in sorted(PERSEUS_DIR.rglob("*.xml")):
        if "__cts__" in xml_file.name:
            continue

        stem = xml_file.stem  # e.g. tlg0012.tlg001.perseus-grc5
        parts = stem.split(".")
        if len(parts) < 3:
            continue

        work_id = f"{parts[0]}.{parts[1]}"
        version = parts[2]  # e.g. perseus-grc5 or perseus-eng1

        if "grc" in version:
            lang = "grc"
        elif "eng" in version:
            lang = "eng"
        else:
            continue

        sections = extract_sections(xml_file)
        if sections:
            # Merge with any existing sections for this lang
            if lang not in works[work_id]:
                works[work_id][lang] = {}
            works[work_id][lang].update(sections)
else:
    print(f"Error: Perseus dir not found at {PERSEUS_DIR}")
    print("Run Step 1.1 first to expand the sparse checkout.")
    raise SystemExit(1)

# Find works with both Greek and English
parallel_works = {wid: data for wid, data in works.items()
                  if "grc" in data and "eng" in data}

print(f"Found {len(parallel_works)} works with both Greek and English editions")
for wid in sorted(parallel_works):
    grc_n = len(parallel_works[wid]["grc"])
    eng_n = len(parallel_works[wid]["eng"])
    common = len(set(parallel_works[wid]["grc"].keys()) & set(parallel_works[wid]["eng"].keys()))
    print(f"  {wid}: {grc_n} grc, {eng_n} eng, {common} common refs")

# Create pairs by matching CTS references
pairs = []
for work_id, data in sorted(parallel_works.items()):
    grc = data["grc"]
    eng = data["eng"]

    common_refs = set(grc.keys()) & set(eng.keys())
    for ref in sorted(common_refs):
        g_text = grc[ref]
        e_text = eng[ref]

        # Skip very short or very long sections
        if len(g_text) < 20 or len(e_text) < 20:
            continue
        if len(g_text) > 2000 or len(e_text) > 2000:
            continue

        pairs.append({
            "work": work_id,
            "ref": ref,
            "grc": g_text,
            "eng": e_text
        })

# Write JSONL
with open(OUTPUT, "w", encoding="utf-8") as f:
    for p in pairs:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")

print(f"\nTotal parallel pairs: {len(pairs)}")
print(f"Saved to {OUTPUT}")

# Show sample
if pairs:
    p = pairs[0]
    print(f"\nSample pair ({p['work']} {p['ref']}):")
    print(f"  GRC: {p['grc'][:100]}...")
    print(f"  ENG: {p['eng'][:100]}...")

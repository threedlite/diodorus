#!/usr/bin/env python3
"""
Build a Latin-English parallel corpus from Perseus canonical-latinLit.

Strategy:
  1. Find works that have both a lat and an eng edition
  2. Extract text at MULTIPLE granularity levels (section, chapter, book)
  3. Match at the finest level that produces common refs
  4. Fallback: match at coarser levels with aggregated text
  5. Filter by length

Handles: different reference depths between Latin and English editions
(e.g., Latin book.chapter.section vs English book.chapter).

Input:
  - data-sources/perseus/canonical-latinLit/data/

Output:
  - data-sources/latin_parallel/lat_eng_pairs.jsonl
"""

import json
import re
from pathlib import Path
from lxml import etree
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PERSEUS_DIR = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-latinLit" / "data"
OUTPUT = PROJECT_ROOT / "data-sources" / "latin_parallel" / "lat_eng_pairs.jsonl"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def extract_multilevel(xml_path):
    """Extract text at ALL textpart levels, keyed by reference path.

    Returns dict of {depth_level: {ref: text}} where depth_level is the
    number of reference components (e.g., 1=book, 2=book.chapter, etc.)
    """
    try:
        parser = etree.XMLParser(load_dtd=False, no_network=True, recover=True)
        tree = etree.parse(str(xml_path), parser)
    except (etree.XMLSyntaxError, OSError):
        return {}

    root = tree.getroot()
    levels = defaultdict(dict)  # depth -> {ref: text}

    # Types that indicate structural divisions (both old and new Perseus TEI)
    TEXTPART_TYPES = {
        "textpart", "section", "verse", "paragraph", "chapter",
        "line", "card", "book", "letter", "poem", "speech",
        "act", "scene", "entry", "article",
    }

    def _walk_textparts(div, ref_prefix):
        """Recursively walk textpart divs, extracting at every level."""
        child_textparts = []
        for child in div:
            if not isinstance(child.tag, str):
                continue
            ctag = etree.QName(child.tag).localname
            if ctag == "div":
                ct = child.get("type", "")
                cs = child.get("subtype", "")
                cn = child.get("n", "")
                # Match both new format (type="textpart" subtype="chapter")
                # and old format (type="chapter")
                if ct in TEXTPART_TYPES or cs in TEXTPART_TYPES:
                    if cn:
                        child_textparts.append((child, cn))

        if child_textparts:
            # This div has child textparts — recurse into them
            for child, cn in child_textparts:
                child_ref = f"{ref_prefix}.{cn}" if ref_prefix else cn
                _walk_textparts(child, child_ref)

            # Also extract aggregated text at THIS level
            if ref_prefix:
                text = re.sub(r"\s+", " ", "".join(div.itertext())).strip()
                if text:
                    depth = ref_prefix.count(".") + 1
                    levels[depth][ref_prefix] = text
        else:
            # Leaf node — extract text
            if ref_prefix:
                text = re.sub(r"\s+", " ", "".join(div.itertext())).strip()
                if text:
                    depth = ref_prefix.count(".") + 1
                    levels[depth][ref_prefix] = text

    # Find the edition/translation root div (new format)
    found_root = False
    for div in root.iter():
        tag = etree.QName(div.tag).localname if isinstance(div.tag, str) else ""
        if tag == "div":
            dtype = div.get("type", "")
            if dtype in ("edition", "translation"):
                _walk_textparts(div, "")
                found_root = True
                break

    # Fallback: old format where structural divs are directly under body
    if not found_root:
        body = root.find(".//{*}body")
        if body is not None:
            _walk_textparts(body, "")

    return dict(levels)


# Scan for all text files, grouped by work
works = defaultdict(dict)
# work_id -> {"lat": {depth: {ref: text}}, "eng": {depth: {ref: text}}}

if PERSEUS_DIR.exists():
    for xml_file in sorted(PERSEUS_DIR.rglob("*.xml")):
        if "__cts__" in xml_file.name:
            continue

        stem = xml_file.stem
        parts = stem.split(".")
        if len(parts) < 3:
            continue

        work_id = f"{parts[0]}.{parts[1]}"
        version = parts[2]

        if "lat" in version:
            lang = "lat"
        elif "eng" in version:
            lang = "eng"
        else:
            continue

        multilevel = extract_multilevel(xml_file)
        if multilevel:
            if lang not in works[work_id]:
                works[work_id][lang] = {}
            # Merge levels
            for depth, sections in multilevel.items():
                if depth not in works[work_id][lang]:
                    works[work_id][lang][depth] = {}
                works[work_id][lang][depth].update(sections)
else:
    print(f"Error: Perseus dir not found at {PERSEUS_DIR}")
    raise SystemExit(1)

# Find works with both Latin and English
parallel_works = {wid: data for wid, data in works.items()
                  if "lat" in data and "eng" in data}

print(f"Found {len(parallel_works)} works with both Latin and English editions\n")

# For each work, find the best matching level
pairs = []
for work_id in sorted(parallel_works):
    lat_levels = parallel_works[work_id]["lat"]
    eng_levels = parallel_works[work_id]["eng"]

    best_common = 0
    best_depth = None
    best_lat_depth = None
    best_eng_depth = None

    # Try matching at each pair of depth levels
    for ld, lat_refs in lat_levels.items():
        for ed, eng_refs in eng_levels.items():
            common = len(set(lat_refs.keys()) & set(eng_refs.keys()))
            if common > best_common:
                best_common = common
                best_lat_depth = ld
                best_eng_depth = ed

    if best_common == 0:
        # Try normalizing refs: strip leading zeros, "pr" -> "0", etc.
        for ld, lat_refs in lat_levels.items():
            lat_norm = {}
            for ref, text in lat_refs.items():
                norm = re.sub(r"\.pr\b", ".0", ref)
                norm = re.sub(r"\b0+(\d)", r"\1", norm)
                lat_norm[norm] = text

            for ed, eng_refs in eng_levels.items():
                eng_norm = {}
                for ref, text in eng_refs.items():
                    norm = re.sub(r"\.pr\b", ".0", ref)
                    norm = re.sub(r"\b0+(\d)", r"\1", norm)
                    eng_norm[norm] = text

                common_refs = set(lat_norm.keys()) & set(eng_norm.keys())
                if len(common_refs) > best_common:
                    best_common = len(common_refs)
                    # Store the normalized refs
                    best_lat_depth = (ld, lat_norm)
                    best_eng_depth = (ed, eng_norm)

    if best_common == 0:
        print(f"  {work_id}: NO matching refs at any level")
        lat_depths_info = {d: len(r) for d, r in lat_levels.items()}
        eng_depths_info = {d: len(r) for d, r in eng_levels.items()}
        print(f"    lat levels: {lat_depths_info}")
        print(f"    eng levels: {eng_depths_info}")
        continue

    # Extract pairs at the best matching level
    work_pairs = 0
    if isinstance(best_lat_depth, tuple):
        # We used normalized refs
        _, lat_refs = best_lat_depth
        _, eng_refs = best_eng_depth
    else:
        lat_refs = lat_levels[best_lat_depth]
        eng_refs = eng_levels[best_eng_depth]

    common_refs = set(lat_refs.keys()) & set(eng_refs.keys())
    for ref in sorted(common_refs):
        l_text = lat_refs[ref]
        e_text = eng_refs[ref]

        if len(l_text) < 20 or len(e_text) < 20:
            continue
        if len(l_text) > 3000 or len(e_text) > 3000:
            continue

        pairs.append({
            "work": work_id,
            "ref": ref,
            "lat": l_text,
            "eng": e_text
        })
        work_pairs += 1

    ld_info = best_lat_depth[0] if isinstance(best_lat_depth, tuple) else best_lat_depth
    ed_info = best_eng_depth[0] if isinstance(best_eng_depth, tuple) else best_eng_depth
    print(f"  {work_id}: {work_pairs} pairs (lat depth {ld_info}, eng depth {ed_info}, {best_common} common refs)")

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
    print(f"  LAT: {p['lat'][:100]}...")
    print(f"  ENG: {p['eng'][:100]}...")

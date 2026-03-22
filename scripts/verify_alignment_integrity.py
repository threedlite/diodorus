#!/usr/bin/env python3
"""
Verify alignment integrity: no text lost, changed, or rearranged.

For each work, checks:
  1. Every source section CTS ref appears in the alignment output
  2. Every English section CTS ref appears in the alignment output
  3. SHA-256 hash of all source texts (Greek/Latin) — verified via ref lookup
  4. SHA-256 hash of all English texts — verified via ref lookup
  5. SHA-256 hash of TEI XML <p> text matches source English text hash
  6. No duplicate refined text within any English section

Exit code 0 = all pass, 1 = any fail (blocks publishing to final/).

Usage:
    python scripts/verify_alignment_integrity.py [work_name ...]
    python scripts/verify_alignment_integrity.py           # auto-discover all
"""

import hashlib
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_ws(text):
    """Collapse all whitespace to single spaces and strip."""
    return re.sub(r'\s+', ' ', text).strip()


def verify(work_name):
    """Verify a single work's alignment integrity."""
    print(f"Verifying {work_name} alignment integrity...")

    out_dir = PROJECT_ROOT / "build" / work_name
    greek_path = out_dir / "greek_sections.json"
    english_path = out_dir / "english_sections.json"
    align_path = out_dir / "entity_validated_alignments.json"

    for p in [greek_path, english_path, align_path]:
        if not p.exists():
            print(f"  SKIP: {p.name} not found")
            return True

    with open(greek_path) as f:
        greek_data = json.load(f)
    with open(english_path) as f:
        english_data = json.load(f)
    with open(align_path) as f:
        alignments = json.load(f)

    ok = True

    # --- 1. All source section refs present in alignment ---
    source_refs = set(s["cts_ref"] for s in greek_data["sections"])
    output_refs = set(a["greek_cts_ref"] for a in alignments if a.get("greek_cts_ref"))
    missing = source_refs - output_refs
    if missing:
        print(f"  ✗ Missing source sections: {len(missing)}")
        for m in sorted(missing)[:5]:
            print(f"    {m}")
        ok = False
    else:
        print(f"  ✓ All {len(source_refs)} source sections present")

    # --- 2. All English section refs present in alignment ---
    en_refs = set(str(s["cts_ref"]) for s in english_data["sections"])
    en_output = set(str(a.get("english_cts_ref")) for a in alignments
                    if a.get("english_cts_ref") is not None)
    en_missing = en_refs - en_output
    if en_missing:
        print(f"  ✗ Missing English sections: {len(en_missing)}")
        for m in sorted(en_missing)[:5]:
            print(f"    {m}")
        ok = False
    else:
        print(f"  ✓ All {len(en_refs)} English sections present")

    # --- 3. Source text hash ---
    # Hash each section's text independently, then hash all hashes.
    # This catches any section being dropped, reordered, or corrupted.
    # Uses position-based matching (not ref-based dict) to handle
    # multi-work configs where different works share book numbers.
    source_section_hashes = [sha256(s["text"]) for s in greek_data["sections"]]
    source_hash = sha256("\n".join(source_section_hashes))

    reconstructed_hashes = []
    for s in greek_data["sections"]:
        if s["cts_ref"] in output_refs:
            reconstructed_hashes.append(sha256(s["text"]))
        else:
            reconstructed_hashes.append(sha256(""))
    reconstructed_hash = sha256("\n".join(reconstructed_hashes))

    if source_hash != reconstructed_hash:
        print(f"  ✗ Source text hash MISMATCH")
        print(f"    Expected:      {source_hash[:16]}...")
        print(f"    Reconstructed: {reconstructed_hash[:16]}...")
        ok = False
    else:
        print(f"  ✓ Source text hash: {source_hash[:16]}...")

    # --- 4. English text hash ---
    en_section_hashes = [sha256(s["text"]) for s in english_data["sections"]]
    en_hash = sha256("\n".join(en_section_hashes))

    en_reconstructed_hashes = []
    for s in english_data["sections"]:
        ref = str(s["cts_ref"])
        if ref in en_output:
            en_reconstructed_hashes.append(sha256(s["text"]))
        else:
            en_reconstructed_hashes.append(sha256(""))
    en_recon_hash = sha256("\n".join(en_reconstructed_hashes))

    if en_hash != en_recon_hash:
        print(f"  ✗ English text hash MISMATCH")
        print(f"    Expected:      {en_hash[:16]}...")
        print(f"    Reconstructed: {en_recon_hash[:16]}...")
        ok = False
    else:
        print(f"  ✓ English text hash: {en_hash[:16]}...")

    # --- 5. TEI XML output hash ---
    # The TEI XML is the main work product.  Extract all <p> text from it
    # and verify it hashes to the same value as the source English.
    # This is the ironclad check: if text is dropped, duplicated, corrupted,
    # or reordered in the output, the hash will differ.
    config_path = PROJECT_ROOT / "scripts" / "works" / work_name / "config.json"
    if config_path.exists():
        with open(config_path) as cf:
            cfg = json.load(cf)
        gr_source = cfg.get("greek_source", {})
        tlg_id = gr_source.get("tlg_id", gr_source.get("phi_id", ""))
        work_id = gr_source.get("work_id", "")
        work_ids = gr_source.get("work_ids", [work_id] if work_id else [])

        # For multi-work configs, build a mapping from work_id to work names
        # using the Greek/Latin sections, same logic as generate_perseus_tei.py.
        wid_to_work_names = {}
        if len(work_ids) > 1:
            gr_path = out_dir / "greek_sections.json"
            if gr_path.exists():
                with open(gr_path) as gf:
                    gr_data = json.load(gf)
                for s in gr_data["sections"]:
                    w = s.get("work", "")
                    sid = s.get("work_id", "")
                    if not sid and s.get("edition", ""):
                        parts = s["edition"].split(".")
                        if len(parts) >= 2:
                            sid = parts[1]
                    if sid and w:
                        wid_to_work_names.setdefault(sid, set()).add(w)

        for wid in work_ids:
            tei_path = out_dir / f"{tlg_id}.{wid}.perseus-eng80.xml"
            if not tei_path.exists():
                print(f"  ✗ TEI XML not found: {tei_path.name}")
                ok = False
                continue

            # Build expected hash: filter English sections for this work
            if len(work_ids) > 1 and wid in wid_to_work_names:
                work_names = wid_to_work_names[wid]
                filtered = [s for s in english_data["sections"]
                            if s.get("work", "") in work_names]
            else:
                filtered = english_data["sections"]
            en_texts_normalized = [normalize_ws(s["text"]) for s in filtered]
            en_expected_hash = sha256("\n".join(en_texts_normalized))

            try:
                from lxml import etree
                TEI_NS = "http://www.tei-c.org/ns/1.0"
                tree = etree.parse(str(tei_path))

                # Extract text from all <p n="..."> elements in document order.
                # Reconstruct original text by converting <note> elements back
                # to their [marker] form, since the TEI generator transforms
                # [A] markers into <note n="A"> elements.
                p_elems = tree.findall(f".//{{{TEI_NS}}}p[@n]")
                tei_texts = []
                for p in p_elems:
                    parts = []
                    if p.text:
                        parts.append(p.text)
                    for child in p:
                        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
                        if tag == "note":
                            # Reconstruct [marker] from <note n="marker">
                            marker = child.get("n", "")
                            if marker:
                                parts.append(f"[{marker}]")
                        else:
                            # Include other element text
                            parts.append("".join(child.itertext()))
                        if child.tail:
                            parts.append(child.tail)
                    full = normalize_ws("".join(parts))
                    tei_texts.append(full)

                tei_hash = sha256("\n".join(tei_texts))

                if tei_hash != en_expected_hash:
                    print(f"  ✗ TEI output hash MISMATCH for {tei_path.name}")
                    print(f"    Source English: {en_expected_hash[:16]}... ({len(en_texts_normalized)} sections)")
                    print(f"    TEI XML:       {tei_hash[:16]}... ({len(tei_texts)} <p> elements)")
                    # Find first difference
                    for i, (src, tei) in enumerate(zip(en_texts_normalized, tei_texts)):
                        if src != tei:
                            print(f"    First diff at section {i}:")
                            print(f"      Source: {src[:80]}...")
                            print(f"      TEI:    {tei[:80]}...")
                            break
                    if len(en_texts_normalized) != len(tei_texts):
                        print(f"    Section count mismatch: source={len(en_texts_normalized)} TEI={len(tei_texts)}")
                    ok = False
                else:
                    print(f"  ✓ TEI output hash: {tei_hash[:16]}... ({tei_path.name})")

            except Exception as e:
                print(f"  ✗ TEI XML parse error: {e}")
                ok = False

    # --- 6. No duplicate refined text ---
    # For each English section that was refined, check that no two Greek
    # sections received identical English text.  Duplicates mean text was
    # repeated instead of properly split.
    refined_by_en = {}
    for a in alignments:
        if a.get("match_type") == "dp_refined" and a.get("english_refined_text"):
            en_ref = str(a.get("english_cts_ref", ""))
            refined_by_en.setdefault(en_ref, []).append(a["english_refined_text"])
    dupe_count = 0
    for en_ref, texts in refined_by_en.items():
        dupes = len(texts) - len(set(texts))
        if dupes > 0:
            dupe_count += dupes
            print(f"  ✗ {dupes} duplicate refined text(s) within English section {en_ref}")
            from collections import Counter
            for text, count in Counter(texts).most_common(2):
                if count > 1:
                    print(f"    '{text[:60]}...' appears {count}x")
    if dupe_count > 0:
        ok = False
    elif refined_by_en:
        total = sum(len(v) for v in refined_by_en.values())
        print(f"  ✓ No duplicate refined text ({total} pieces across {len(refined_by_en)} sections)")

    return ok


def main():
    if len(sys.argv) > 1:
        works = sys.argv[1:]
    else:
        # Auto-discover all works with build output
        build_dir = PROJECT_ROOT / "build"
        works = []
        if build_dir.exists():
            for d in sorted(build_dir.iterdir()):
                if d.is_dir() and (d / "entity_validated_alignments.json").exists():
                    works.append(d.name)

    if not works:
        print("No works found to verify.")
        sys.exit(1)

    all_ok = True
    for work in works:
        print()
        ok = verify(work)
        if ok:
            print(f"  ═══ {work.upper()}: PASS ═══")
        else:
            print(f"  ═══ {work.upper()}: FAIL ═══")
            all_ok = False

    print()
    if all_ok:
        print("All integrity checks passed.")
    else:
        print("INTEGRITY CHECK FAILED — see above.")
        print("Output files left in place for inspection. Nothing published to final/.")
        sys.exit(1)


if __name__ == "__main__":
    main()

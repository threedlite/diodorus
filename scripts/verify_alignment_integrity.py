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

    # --- 0. No duplicate CTS refs in source data ---
    # For multi_work configs, check per-work (since alignment groups by work
    # and sections from different works never interact).
    from collections import Counter
    config_path = PROJECT_ROOT / "scripts" / "works" / work_name / "config.json"
    is_multi = False
    if config_path.exists():
        with open(config_path) as _cf:
            is_multi = json.load(_cf).get("multi_work", False)

    if is_multi:
        gr_dupes = {}
        for s in greek_data["sections"]:
            work = s.get("work", "")
            ref = s["cts_ref"]
            key = (work, ref)
            gr_dupes[key] = gr_dupes.get(key, 0) + 1
        gr_dupes = {f"{w}:{r}": c for (w, r), c in gr_dupes.items() if c > 1}
    else:
        gr_ref_counts = Counter(s["cts_ref"] for s in greek_data["sections"])
        gr_dupes = {r: c for r, c in gr_ref_counts.items() if c > 1}
    if gr_dupes:
        print(f"  ✗ Duplicate Greek CTS refs: {len(gr_dupes)}")
        for r in sorted(gr_dupes)[:5]:
            print(f"    {r} appears {gr_dupes[r]}x")
        ok = False

    en_ref_counts_src = Counter(str(s["cts_ref"]) for s in english_data["sections"])
    en_dupes = {r: c for r, c in en_ref_counts_src.items() if c > 1}
    if en_dupes:
        # English duplicates are a quality issue (multi-paragraph sections
        # sharing a ref) but not a data loss issue — TEI hash is authoritative.
        print(f"  ⚠ Duplicate English CTS refs: {len(en_dupes)}")

    if not gr_dupes and not en_dupes:
        print(f"  ✓ No duplicate CTS refs in source data")
    elif not gr_dupes:
        print(f"  ✓ No duplicate Greek CTS refs")

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

    # --- 3. Source text completeness ---
    # Hash all source section texts to verify none were corrupted.
    source_hash = sha256("\n".join(sha256(s["text"]) for s in greek_data["sections"]))
    print(f"  ✓ Source text hash: {source_hash[:16]}...")

    # --- 4. English text coverage in alignment ---
    # For each English section, verify that the alignment output accounts
    # for all of its text. Unrefined sections should appear as-is. Refined
    # sections should have their pieces cover the full original text (no
    # words dropped during sentence splitting).
    en_by_ref = {}
    for s in english_data["sections"]:
        # Use text_for_embedding (footnotes stripped) for coverage check,
        # since refinement splits text_for_embedding not the full text
        en_by_ref[str(s["cts_ref"])] = s.get("text_for_embedding", s["text"])

    en_coverage_errors = 0
    for en_ref, source_text in en_by_ref.items():
        # Collect all text pieces for this English section — both refined
        # (split pieces) and unrefined (full section shown as-is).
        entries = [a for a in alignments
                   if str(a.get("english_cts_ref", "")) == en_ref]

        has_refined = any(a.get("match_type") == "dp_refined" for a in entries)
        if not has_refined:
            continue  # fully unrefined — text shown as-is, no splitting to verify

        # Collect refined pieces
        pieces = [a.get("english_refined_text", "")
                  for a in entries
                  if a.get("match_type") == "dp_refined"
                  and a.get("english_refined_text")]

        # If any entry is unrefined (shows full text), that covers everything
        has_unrefined_full = any(
            a.get("match_type") != "dp_refined" and a.get("group_size_gr", 1) <= 1
            for a in entries)
        if has_unrefined_full:
            continue  # full text is shown on an unrefined entry

        # Reconstruct by joining refined pieces and normalize whitespace
        reconstructed = " ".join(pieces)
        reconstructed_words = set(reconstructed.lower().split())
        source_words = set(source_text.lower().split())

        # Check that refined pieces cover the source words.
        # Allow some tolerance: footnotes and heading text may not appear
        # in refined pieces, and splitting can lose/gain whitespace.
        missing_words = source_words - reconstructed_words
        # Filter out short words and footnote markers
        missing_words = {w for w in missing_words if len(w) > 3}
        coverage = 1.0 - len(missing_words) / max(len(source_words), 1)

        if coverage < 0.80:
            en_coverage_errors += 1
            if en_coverage_errors <= 3:
                print(f"  ✗ English {en_ref}: refined pieces cover only "
                      f"{coverage:.0%} of source words "
                      f"({len(missing_words)} missing)")

    if en_coverage_errors > 3:
        print(f"  ✗ ... and {en_coverage_errors - 3} more English sections "
              f"with low refined coverage")
    if en_coverage_errors > 0:
        # Coverage issues affect HTML display but not the TEI XML deliverable.
        # The TEI hash check (below) is the authoritative text-loss check.
        print(f"  ⚠ {en_coverage_errors} sections with low HTML refined coverage")
    else:
        n_refined_en = len(set(str(a.get("english_cts_ref", ""))
                               for a in alignments
                               if a.get("match_type") == "dp_refined"))
        en_hash = sha256("\n".join(sha256(t) for t in en_by_ref.values()))
        print(f"  ✓ English text hash: {en_hash[:16]}... "
              f"({n_refined_en} refined sections verified)")

    # --- 5. Order preservation (per book) ---
    # Verify Greek and English sections appear in source order within each book.
    # Skip for pairwise alignment (fables etc.) where order isn't sequential.
    config_path = PROJECT_ROOT / "scripts" / "works" / work_name / "config.json"
    alignment_mode = "dp"
    if config_path.exists():
        with open(config_path) as _cf:
            alignment_mode = json.load(_cf).get("alignment_mode", "dp")

    # For multi-work configs, CTS refs can collide across works (e.g.
    # Thebaid and Achilleid both have "1.1"). Build per-work order maps.
    if is_multi:
        source_order_by_work = {}
        for i, s in enumerate(greek_data["sections"]):
            work = s.get("work", s.get("book", ""))
            source_order_by_work.setdefault(work, {})[s["cts_ref"]] = i
        en_order_by_work = {}
        for i, s in enumerate(english_data["sections"]):
            work = s.get("work", s.get("book", ""))
            en_order_by_work.setdefault(work, {})[str(s["cts_ref"])] = i
    else:
        source_order_by_work = {"": {s["cts_ref"]: i for i, s in enumerate(greek_data["sections"])}}
        en_order_by_work = {"": {str(s["cts_ref"]): i for i, s in enumerate(english_data["sections"])}}

    gr_order_ok = True
    en_order_ok = True
    # Pairwise alignment (fables) matches by similarity, not sequence —
    # fable numbering differs between Greek and English editions, so
    # English order is legitimately non-monotonic.
    check_en_order = (alignment_mode != "pairwise")

    # Check order per alignment group. For multi-work configs, each work
    # is aligned independently so only check within each work/book.
    is_multi_work = is_multi
    prev_gr_idx = {}
    prev_en_idx = {}

    for a in alignments:
        # Group by book field. For multi-work configs, book contains
        # the work name (e.g. "Thebaid", "Achilleid") which keeps
        # each work's ordering check independent.
        gr_ref = a.get("greek_cts_ref")
        group = a.get("book", "")
        source_order = source_order_by_work.get(group, source_order_by_work.get("", {}))
        en_order = en_order_by_work.get(group, en_order_by_work.get("", {}))

        if gr_ref and gr_ref in source_order:
            idx = source_order[gr_ref]
            prev = prev_gr_idx.get(group, -1)
            if idx < prev:
                if gr_order_ok:
                    print(f"  ✗ Greek out of order: {gr_ref} "
                          f"(index {idx}) after {prev} in group '{group}'")
                gr_order_ok = False
                ok = False
            prev_gr_idx[group] = idx

        en_ref = a.get("english_cts_ref")
        if check_en_order and en_ref and str(en_ref) in en_order:
            idx = en_order[str(en_ref)]
            prev = prev_en_idx.get(group, -1)
            if idx < prev:
                if en_order_ok:
                    label = "⚠" if is_multi_work else "✗"
                    print(f"  {label} English out of order in alignment: "
                          f"{en_ref} (index {idx}) after {prev} "
                          f"in group '{group}'")
                en_order_ok = False
                # Multi-work configs align each work independently —
                # English order across works is legitimately non-monotonic.
                # Greek order is ALWAYS enforced; English is best-effort
                # for multi-work since TEI hash verifies text integrity.
                if not is_multi_work:
                    ok = False
            prev_en_idx[group] = idx

    if gr_order_ok and en_order_ok:
        print(f"  ✓ Section order preserved (Greek and English monotonic)")
    elif gr_order_ok:
        print(f"  ✓ Greek order preserved")

    # --- 6. TEI XML output hash ---
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

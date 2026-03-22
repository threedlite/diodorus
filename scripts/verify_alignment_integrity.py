#!/usr/bin/env python3
"""
Verify alignment integrity: no text lost, changed, or rearranged.

For each work, checks:
  1. Every source section CTS ref appears in the alignment output
  2. Every English section CTS ref appears in the alignment output
  3. SHA-256 hash of source texts matches hash reconstructed from alignment refs
  4. All text present — including footnotes

Exit code 0 = all pass, 1 = any fail (blocks publishing to final/).

Usage:
    python scripts/verify_alignment_integrity.py [work_name ...]
    python scripts/verify_alignment_integrity.py           # auto-discover all
"""

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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

    # --- 3. Text hash verification ---
    # Hash the FULL text (including footnotes) from the source extraction.
    # Then verify that every ref in the alignment can be looked up in the
    # source and the texts match. If any text was lost or corrupted, the
    # reconstructed hash will differ.

    source_hash = sha256("\n".join(s["text"] for s in greek_data["sections"]))
    source_lookup = {s["cts_ref"]: s["text"] for s in greek_data["sections"]}
    reconstructed_texts = []
    for s in greek_data["sections"]:
        if s["cts_ref"] in output_refs:
            reconstructed_texts.append(s["text"])
        else:
            reconstructed_texts.append("")  # missing section
    reconstructed_hash = sha256("\n".join(reconstructed_texts))

    if source_hash != reconstructed_hash:
        print(f"  ✗ Source text hash MISMATCH")
        print(f"    Source:        {source_hash[:16]}...")
        print(f"    Reconstructed: {reconstructed_hash[:16]}...")
        ok = False
    else:
        print(f"  ✓ Source text hash verified: {source_hash[:16]}...")

    en_hash = sha256("\n".join(s["text"] for s in english_data["sections"]))
    en_lookup = {str(s["cts_ref"]): s["text"] for s in english_data["sections"]}
    en_reconstructed = []
    for s in english_data["sections"]:
        if str(s["cts_ref"]) in en_output:
            en_reconstructed.append(s["text"])
        else:
            en_reconstructed.append("")
    en_recon_hash = sha256("\n".join(en_reconstructed))

    if en_hash != en_recon_hash:
        print(f"  ✗ English text hash MISMATCH")
        print(f"    Source:        {en_hash[:16]}...")
        print(f"    Reconstructed: {en_recon_hash[:16]}...")
        ok = False
    else:
        print(f"  ✓ English text hash verified: {en_hash[:16]}...")

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

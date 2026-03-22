#!/usr/bin/env python3
"""
Generic pipeline runner.

Usage:
    python scripts/pipeline/run.py <work_name>        # run one work
    python scripts/pipeline/run.py --all              # run all works
    python scripts/pipeline/run.py --list             # list available works

Steps:
    1. Extract source language text (per-work script)
    2. Extract English text (per-work script)
    3. Embed & align (generic)
    4. Entity anchor validation (generic)
    5. Generate outputs (generic)
    6. Quality map (generic)
    7. Integrity check (generic)
    8. Publish to final/ (generic)
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORKS_DIR = PROJECT_ROOT / "scripts" / "works"


def list_works():
    """List all available works."""
    works = []
    for d in sorted(WORKS_DIR.iterdir()):
        config_path = d / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            legacy = " (legacy)" if config.get("legacy_pipeline") else ""
            works.append((config["name"], config["author"], config["work_title"], legacy))
    return works


def run_step(description, cmd):
    """Run a pipeline step, abort on failure."""
    print(f"\n=== {description} ===")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"FAILED: {description}")
        sys.exit(1)


def run_work(work_name):
    """Run the full pipeline for one work."""
    config_path = WORKS_DIR / work_name / "config.json"
    if not config_path.exists():
        print(f"Error: no config.json for '{work_name}'")
        print(f"Available works: {[w[0] for w in list_works()]}")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    author = config["author"]
    title = config["work_title"]
    out_dir = config["output_dir"]
    print(f"\n{'='*60}")
    print(f"  {author} — {title}")
    print(f"{'='*60}")

    # Ensure output directory exists
    (PROJECT_ROOT / out_dir).mkdir(parents=True, exist_ok=True)

    # Step 1: Extract source text
    lang = config.get("source_language", "greek")
    extract_source = WORKS_DIR / work_name / f"extract_{lang}.py"
    if not extract_source.exists():
        extract_source = WORKS_DIR / work_name / "extract_greek.py"
    run_step(f"Extract {lang} text", [sys.executable, str(extract_source)])

    # Step 2: Extract English text
    extract_english = WORKS_DIR / work_name / "extract_english.py"
    run_step("Extract English text", [sys.executable, str(extract_english)])

    # Step 3: Embed & Align
    run_step("Embed & Align",
             [sys.executable, "scripts/pipeline/align.py", work_name])

    # Step 4: Entity Anchors
    run_step("Entity Anchor Validation",
             [sys.executable, "scripts/pipeline/entity_anchors.py", work_name])

    # Step 5: Generate Outputs
    run_step("Generate Outputs",
             [sys.executable, "scripts/pipeline/generate_outputs.py", work_name])

    # Step 6: Generate Perseus TEI
    run_step("Generate Perseus TEI",
             [sys.executable, "scripts/pipeline/generate_perseus_tei.py", work_name])

    # Step 6b: Generate Parallel Text HTML
    run_step("Generate Parallel Text",
             [sys.executable, "scripts/pipeline/generate_parallel_text.py", work_name])

    # Step 7: Quality Map — one SVG per Perseus TEI XML, matching its filename
    gr_source = config.get("greek_source", {})
    tlg_id = gr_source.get("tlg_id", gr_source.get("phi_id", ""))
    work_id = gr_source.get("work_id", "")
    work_ids = gr_source.get("work_ids", [work_id] if work_id else [])
    align_json = f"{out_dir}/entity_validated_alignments.json"

    for wid in work_ids:
        cts_stem = f"{tlg_id}.{wid}.perseus-eng80"
        run_step(f"Quality Map ({cts_stem})",
                 [sys.executable, "scripts/alignment_quality_map.py",
                  "--prefix", cts_stem, align_json])

    # Step 7: Integrity Check
    run_step("Integrity Check",
             [sys.executable, "scripts/verify_alignment_integrity.py", work_name])

    # Step 8: Publish to final/
    run_step("Publish to final/",
             [sys.executable, "scripts/publish_to_final.py", work_name, out_dir])

    print(f"\n{'='*60}")
    print(f"  {work_name}: COMPLETE")
    print(f"{'='*60}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/pipeline/run.py <work_name>")
        print("  python scripts/pipeline/run.py --all")
        print("  python scripts/pipeline/run.py --list")
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "--list":
        works = list_works()
        print(f"Available works ({len(works)}):")
        for name, author, title, legacy in works:
            print(f"  {name:<20s} {author} — {title}{legacy}")
        return

    if arg == "--all":
        works = list_works()
        for name, _, _, _ in works:
            run_work(name)
        return

    run_work(arg)


if __name__ == "__main__":
    main()

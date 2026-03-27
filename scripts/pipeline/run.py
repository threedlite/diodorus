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


def print_quality_summary():
    """Print a summary table of alignment quality across all works."""
    rows = []
    for d in sorted(WORKS_DIR.iterdir()):
        config_path = d / "config.json"
        if not config_path.exists():
            continue
        with open(config_path) as f:
            cfg = json.load(f)
        align_path = PROJECT_ROOT / cfg["output_dir"] / "entity_validated_alignments.json"
        gr_path = PROJECT_ROOT / cfg["output_dir"] / "greek_sections.json"
        en_path = PROJECT_ROOT / cfg["output_dir"] / "english_sections.json"
        if not align_path.exists():
            continue

        with open(align_path) as f:
            aligns = json.load(f)
        with open(gr_path) as f:
            gd = json.load(f)
        with open(en_path) as f:
            ed = json.load(f)

        gs = gd["sections"] if isinstance(gd, dict) else gd
        es = ed["sections"] if isinstance(ed, dict) else ed
        scores = [a.get("combined_score", 0) for a in aligns]
        n = len(scores)
        if n == 0:
            continue
        avg = sum(scores) / n
        h = sum(1 for s in scores if s >= 0.5) / n * 100
        m = sum(1 for s in scores if 0.2 <= s < 0.5) / n * 100
        l = sum(1 for s in scores if s < 0.2) / n * 100
        shared = sum(1 for a in aligns if a.get("sharing_penalty"))

        # Component averages (only over sections that have the score)
        def avg_field(field):
            vals = [a.get(field, 0) for a in aligns if a.get(field) is not None]
            return sum(vals) / len(vals) if vals else 0.0

        cos = avg_field("similarity")
        lex = avg_field("lexical_score")
        ent = avg_field("entity_overlap_score")
        lrt = avg_field("length_ratio_score")
        spk = avg_field("speaker_score")

        rows.append((avg, cfg["name"], cfg["author"][:20], len(gs), len(es),
                      avg, h, m, l, cos, lex, ent, lrt, spk, shared))

    rows.sort(reverse=True)

    hdr = (f"{'Work':<28s} {'Author':<20s} {'Gr':>5s} {'En':>5s} "
           f"{'Avg':>5s} {'H%':>5s} {'L%':>5s} "
           f"{'Emb':>5s} {'Lex':>5s} {'Ent':>5s} {'Len':>5s} {'Spk':>5s} {'Shrd':>5s}")
    sep = "-" * len(hdr)
    print(f"\n{sep}")
    print(f"  ALIGNMENT QUALITY SUMMARY")
    print(sep)
    print(hdr)
    print(sep)
    for (_, name, author, n_gr, n_en, avg, h, m, l,
         cos, lex, ent, lrt, spk, shared) in rows:
        spk_str = f"{spk:5.2f}" if spk > 0 else "    -"
        ent_str = f"{ent:5.2f}" if ent > 0 else "    -"
        print(f"{name:<28s} {author:<20s} {n_gr:5d} {n_en:5d} "
              f"{avg:5.3f} {h:5.1f} {l:5.1f} "
              f"{cos:5.2f} {lex:5.3f} {ent_str} {lrt:5.2f} {spk_str} {shared:5d}")
    print(sep)


def load_previous_metrics():
    """Load the last published quality metrics from final/quality_metrics.json."""
    prev_path = PROJECT_ROOT / "final" / "quality_metrics.json"
    if prev_path.exists():
        with open(prev_path) as f:
            return json.load(f).get("works", {})
    return {}


def check_regression(work_name, new_entry, previous_metrics):
    """Compare new metrics against previous and warn on regressions."""
    prev = previous_metrics.get(work_name)
    if not prev:
        return  # no previous data to compare

    warnings = []
    if new_entry["high_pct"] < prev["high_pct"]:
        warnings.append(
            f"high dropped {prev['high_pct']}% → {new_entry['high_pct']}%")
    if new_entry["low_pct"] > prev["low_pct"]:
        warnings.append(
            f"low rose {prev['low_pct']}% → {new_entry['low_pct']}%")
    if new_entry["avg"] < prev["avg"]:
        warnings.append(
            f"avg dropped {prev['avg']:.3f} → {new_entry['avg']:.3f}")

    if warnings:
        print(f"\n  ⚠ QUALITY REGRESSION for {work_name}:")
        for w in warnings:
            print(f"    {w}")


def save_metrics(work_name, out_dir, build_time=None, previous_metrics=None):
    """Append quality metrics for this work to build/quality_metrics.json."""
    from datetime import datetime

    align_path = PROJECT_ROOT / out_dir / "entity_validated_alignments.json"
    if not align_path.exists():
        return

    with open(align_path) as f:
        data = json.load(f)

    scores = [a.get("combined_score", a.get("similarity", 0)) for a in data]
    n = len(scores)
    if n == 0:
        return

    # Load config for source info
    config_path = WORKS_DIR / work_name / "config.json"
    source_info = {}
    xml_files = []
    if config_path.exists():
        with open(config_path) as cf:
            cfg = json.load(cf)
        source_info = {
            "author": cfg.get("author", ""),
            "work_title": cfg.get("work_title", ""),
            "source_type": cfg.get("greek_source", {}).get("type", ""),
            "english_source": cfg.get("english_source", {}).get("type", ""),
            "translator": cfg.get("english_source", {}).get("translator", ""),
            "english_date": cfg.get("english_source", {}).get("date", ""),
        }
        gr = cfg.get("greek_source", {})
        tlg = gr.get("tlg_id", gr.get("phi_id", ""))
        wid = gr.get("work_id", "")
        wids = gr.get("work_ids", [wid] if wid else [])
        xml_files = [f"{tlg}.{w}.perseus-eng80.xml" for w in wids]

    entry = {
        **source_info,
        "xml_files": xml_files,
        "sections": n,
        "high_pct": round(sum(1 for s in scores if s >= 0.5) / n * 100, 1),
        "med_pct": round(sum(1 for s in scores if 0.2 <= s < 0.5) / n * 100, 1),
        "low_pct": round(sum(1 for s in scores if s < 0.2) / n * 100, 1),
        "avg": round(sum(scores) / n, 3),
        "build_time_seconds": round(build_time, 1) if build_time else None,
        "timestamp": datetime.now().isoformat(),
    }

    # Compare against previous metrics
    if previous_metrics is not None:
        check_regression(work_name, entry, previous_metrics)

    metrics_path = PROJECT_ROOT / "build" / "quality_metrics.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            metrics = json.load(f)
    else:
        metrics = {"works": {}}

    metrics["works"][work_name] = entry

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)


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


def run_work(work_name, previous_metrics=None):
    """Run the full pipeline for one work."""
    config_path = WORKS_DIR / work_name / "config.json"
    if not config_path.exists():
        print(f"Error: no config.json for '{work_name}'")
        print(f"Available works: {[w[0] for w in list_works()]}")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    build_start = __import__('time').time()

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

    # Step 9: Save quality metrics and check for regressions
    build_end = __import__('time').time()
    save_metrics(work_name, out_dir, build_time=build_end - build_start,
                 previous_metrics=previous_metrics)

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
        prev = load_previous_metrics()
        works = list_works()
        for name, _, _, _ in works:
            run_work(name, previous_metrics=prev)
        # Copy quality metrics to final/ if all passed
        import shutil
        metrics_path = PROJECT_ROOT / "build" / "quality_metrics.json"
        if metrics_path.exists():
            final_dir = PROJECT_ROOT / "final"
            final_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(metrics_path, final_dir / "quality_metrics.json")
            print(f"\nPublished quality_metrics.json to final/")
        # Regenerate word count comparison report
        word_count_script = PROJECT_ROOT / "scripts" / "word_count_report.py"
        if word_count_script.exists():
            subprocess.run([sys.executable, str(word_count_script)], cwd=str(PROJECT_ROOT))
        # Print quality summary table
        print_quality_summary()
        return

    prev = load_previous_metrics()
    run_work(arg, previous_metrics=prev)


if __name__ == "__main__":
    main()

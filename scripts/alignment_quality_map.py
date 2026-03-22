#!/usr/bin/env python3
"""
Alignment quality map — shows at a glance which regions of a work
are well-aligned and which are not.

Works with any entity_validated_alignments.json from the pipeline
(Diodorus, Statius, Marcus Aurelius, or any future author).

Usage:
    python scripts/alignment_quality_map.py [alignments_json ...]

    If no argument given, scans output/**/entity_validated_alignments.json

Outputs (next to each input file):
    alignment_quality_map.txt   — terminal-friendly block heatmap
    alignment_quality_map.tsv   — per-book summary stats
    alignment_quality_map.svg   — visual heatmap for browsers/docs
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Confidence thresholds
HIGH = 0.6
MED = 0.3

# ANSI colors for terminal
GREEN = "\033[42m"   # high
YELLOW = "\033[43m"  # medium
RED = "\033[41m"     # low
RESET = "\033[0m"

# Block characters (no-color fallback)
BLOCK_HIGH = "█"
BLOCK_MED = "▒"
BLOCK_LOW = "░"

# SVG colors
SVG_HIGH = "#2d8a4e"
SVG_MED = "#e8b83d"
SVG_LOW = "#c9493b"
SVG_BG = "#f5f5f5"
SVG_TEXT = "#333333"
SVG_TEXT_LIGHT = "#888888"


def load_alignments(path):
    """Load alignment JSON and detect format automatically."""
    with open(path) as f:
        data = json.load(f)

    if not data:
        return [], "unknown", ""

    sample = data[0]

    # Detect format by checking which fields exist
    if "latin_first_line" in sample:
        fmt = "verse"  # line-based (Statius, verse authors)
    elif "greek_cts_ref" in sample:
        fmt = "prose_greek"  # section-based Greek (Diodorus, Marcus Aurelius, etc.)
    elif "latin_cts_ref" in sample:
        fmt = "prose_latin"  # section-based Latin
    else:
        fmt = "generic"

    # Derive author/work title from Perseus CTS metadata if available
    title = _resolve_title(data, fmt)

    return data, fmt, title


def _resolve_title(records, fmt):
    """Try to resolve author and work name from Perseus CTS XML."""
    sample = records[0]

    # Extract the CTS identifier from the alignment record
    cts_id = None
    if fmt == "verse":
        cts_id = sample.get("latin_cts_work") or sample.get("latin_edition", "")
    elif fmt == "prose_greek":
        cts_id = sample.get("greek_edition", "")
    elif fmt == "prose_latin":
        cts_id = sample.get("latin_edition", "")

    if not cts_id:
        return ""

    # Parse out author and work IDs: "tlg0060.tlg001.perseus-grc5" -> ("tlg0060", "tlg001")
    parts = cts_id.split(".")
    if len(parts) < 2:
        return ""
    author_id, work_id = parts[0], parts[1]

    # Search for __cts__.xml in Perseus data dirs
    perseus_roots = [
        PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data",
        PROJECT_ROOT / "data-sources" / "perseus" / "canonical-latinLit" / "data",
    ]

    author_name = ""
    work_name = ""

    for root in perseus_roots:
        author_dir = root / author_id
        if not author_dir.exists():
            continue

        # Read author name from author-level __cts__.xml
        author_cts = author_dir / "__cts__.xml"
        if author_cts.exists():
            author_name = _extract_cts_name(author_cts, "groupname")

        # Read work name from work-level __cts__.xml
        work_dir = author_dir / work_id
        if work_dir and work_dir.exists():
            work_cts = work_dir / "__cts__.xml"
            if work_cts.exists():
                work_name = _extract_cts_name(work_cts, "title")

        if author_name:
            break

    # Check for explicit "work" field values (e.g. Statius has "Thebaid", "Achilleid")
    explicit_works = set(r.get("work", "") for r in records)
    explicit_works.discard("")
    if explicit_works:
        # Multiple works in one alignment — use explicit names instead of CTS title
        work_name = ", ".join(sorted(explicit_works))

    if author_name and work_name:
        return f"{author_name} — {work_name}"
    elif author_name:
        return author_name
    elif work_name:
        return work_name
    else:
        return ""


def _extract_cts_name(cts_path, tag_suffix):
    """Extract a name from a CTS XML file by matching a tag ending in tag_suffix."""
    import re
    try:
        text = cts_path.read_text(encoding="utf-8")
        # Match <ti:groupname ...>Name</ti:groupname> or <ti:title ...>Name</ti:title>
        # Namespace-agnostic: match any prefix before the tag name
        pattern = rf'<[^>]*{tag_suffix}[^>]*>([^<]+)<'
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ""


def get_book_key(rec, fmt):
    """Return (work_or_empty, book) tuple."""
    work = rec.get("work", "")
    return (work, str(rec["book"]))


def get_section_label(rec, fmt):
    """Return a short section label for display."""
    if fmt == "verse":
        return f"{rec['latin_first_line']}-{rec['latin_last_line']}"
    elif fmt == "prose_greek":
        ref = rec.get("greek_cts_ref")
        if ref:
            return ref
        # Unmatched English — use whatever English ref is available
        en_ref = rec.get("english_cts_ref")
        if en_ref:
            return f"en:{en_ref}"
        return f"en:{rec.get('booth_div2_index', '?')}/{rec.get('booth_p_index', '?')}"
    elif fmt == "prose_latin":
        return rec.get("latin_cts_ref", str(rec.get("group_id", "?")))
    else:
        return str(rec.get("group_id", "?"))


def get_score(rec):
    """Extract the display score from a record."""
    return rec.get("combined_score", rec.get("similarity", 0))


def format_book_label(work, book):
    """Format a book label for display."""
    if work:
        return f"{work} {book}"
    return f"Book {book}"


def compute_book_stats(records):
    """Compute summary statistics for a list of alignment records."""
    scores = [get_score(r) for r in records]
    n = len(scores)
    if n == 0:
        return {}

    high = sum(1 for s in scores if s >= HIGH)
    med = sum(1 for s in scores if MED <= s < HIGH)
    low = sum(1 for s in scores if s < MED)
    avg = sum(scores) / n
    unmatched = sum(1 for r in records if r.get("match_type") == "unmatched")

    return {
        "n": n,
        "high": high,
        "med": med,
        "low": low,
        "high_pct": high / n * 100,
        "med_pct": med / n * 100,
        "low_pct": low / n * 100,
        "avg": avg,
        "min": min(scores),
        "max": max(scores),
        "unmatched": unmatched,
    }


def score_to_color(score):
    """Map score to SVG color."""
    if score >= HIGH:
        return SVG_HIGH
    elif score >= MED:
        return SVG_MED
    else:
        return SVG_LOW


def score_to_block(score, use_color=True):
    """Convert a score to a colored block character."""
    if score >= HIGH:
        return f"{GREEN} {RESET}" if use_color else BLOCK_HIGH
    elif score >= MED:
        return f"{YELLOW} {RESET}" if use_color else BLOCK_MED
    else:
        return f"{RED} {RESET}" if use_color else BLOCK_LOW


def find_low_runs(records, fmt, threshold=MED, min_run=3):
    """Find consecutive runs of low-confidence alignments."""
    runs = []
    current_run = []

    for r in records:
        if get_score(r) < threshold:
            current_run.append(r)
        else:
            if len(current_run) >= min_run:
                scores = [get_score(x) for x in current_run]
                runs.append((
                    get_section_label(current_run[0], fmt),
                    get_section_label(current_run[-1], fmt),
                    sum(scores) / len(scores),
                    len(current_run),
                ))
            current_run = []

    if len(current_run) >= min_run:
        scores = [get_score(x) for x in current_run]
        runs.append((
            get_section_label(current_run[0], fmt),
            get_section_label(current_run[-1], fmt),
            sum(scores) / len(scores),
            len(current_run),
        ))

    runs.sort(key=lambda x: -x[3])
    return runs


# --------------- TEXT HEATMAP ---------------

def render_heatmap(records, fmt, title="", use_color=True):
    """Render a full heatmap string."""
    by_book = defaultdict(list)
    for r in records:
        by_book[get_book_key(r, fmt)].append(r)

    heading = "ALIGNMENT QUALITY MAP"
    if title:
        heading += f" — {title}"

    lines = []
    lines.append("")
    lines.append(heading)
    lines.append("=" * max(60, len(heading)))

    if use_color:
        lines.append(f"  {GREEN} {RESET} High (≥{HIGH})  "
                      f"{YELLOW} {RESET} Medium ({MED}-{HIGH})  "
                      f"{RED} {RESET} Low (<{MED})")
    else:
        lines.append(f"  {BLOCK_HIGH} High (≥{HIGH})  "
                      f"{BLOCK_MED} Medium ({MED}-{HIGH})  "
                      f"{BLOCK_LOW} Low (<{MED})")
    lines.append("")

    book_keys = sorted(by_book.keys(), key=lambda k: (
        k[0], int(k[1]) if k[1].isdigit() else 0,
    ))

    total_stats = {"n": 0, "high": 0, "med": 0, "low": 0, "scores": []}

    for work, book in book_keys:
        recs = by_book[(work, book)]
        stats = compute_book_stats(recs)
        label = format_book_label(work, book)

        total_stats["n"] += stats["n"]
        total_stats["high"] += stats["high"]
        total_stats["med"] += stats["med"]
        total_stats["low"] += stats["low"]
        total_stats["scores"].extend(get_score(r) for r in recs)

        header = (f"  {label:<20s}  n={stats['n']:>4d}  "
                  f"avg={stats['avg']:.3f}  "
                  f"H={stats['high_pct']:4.0f}%  "
                  f"M={stats['med_pct']:4.0f}%  "
                  f"L={stats['low_pct']:4.0f}%")
        if stats.get("unmatched", 0) > 0:
            header += f"  U={stats['unmatched']}"
        lines.append(header)

        scores = [get_score(r) for r in recs]
        blocks = [score_to_block(s, use_color) for s in scores]

        MAX_BLOCKS = 80
        for start in range(0, len(blocks), MAX_BLOCKS):
            lines.append("  " + "".join(blocks[start:start + MAX_BLOCKS]))

        low_runs = find_low_runs(recs, fmt)
        if low_runs:
            lines.append(f"    ⚠ Low-confidence regions:")
            for run_start, run_end, run_avg, count in low_runs[:5]:
                lines.append(f"      {run_start} → {run_end}  "
                              f"({count} sections, avg={run_avg:.3f})")
        lines.append("")

    n = total_stats["n"]
    if n > 0:
        all_scores = total_stats["scores"]
        lines.append("=" * 60)
        lines.append(f"  TOTAL: {n} sections  "
                      f"avg={sum(all_scores)/n:.3f}  "
                      f"H={total_stats['high']/n*100:4.0f}%  "
                      f"M={total_stats['med']/n*100:4.0f}%  "
                      f"L={total_stats['low']/n*100:4.0f}%")
        lines.append("")

    return "\n".join(lines)


# --------------- SVG HEATMAP ---------------

def generate_svg(records, fmt, out_path, title=""):
    """Generate an SVG heatmap of alignment quality."""
    by_book = defaultdict(list)
    for r in records:
        by_book[get_book_key(r, fmt)].append(r)

    book_keys = sorted(by_book.keys(), key=lambda k: (
        k[0], int(k[1]) if k[1].isdigit() else 0,
    ))

    # Layout constants
    CELL_W = 4          # width of each section cell
    CELL_H = 16         # height of each section cell
    LABEL_W = 160       # space for book label
    STATS_W = 220       # space for stats text
    ROW_GAP = 6         # gap between book rows
    HEADER_H = 60       # space for title + legend
    FOOTER_H = 50       # space for totals
    MAX_CELLS = 200     # max cells per row before wrapping
    WRAP_INDENT = 10    # indent for wrapped rows
    LOW_RUN_H = 14      # height per low-run warning line
    MARGIN = 20

    # Pre-compute layout: figure out how many rows each book needs
    book_layouts = []
    for work, book in book_keys:
        recs = by_book[(work, book)]
        n = len(recs)
        n_rows = max(1, math.ceil(n / MAX_CELLS))
        low_runs = find_low_runs(recs, fmt)
        n_warnings = min(len(low_runs), 3)
        row_height = (n_rows * CELL_H) + (n_warnings * LOW_RUN_H) + ROW_GAP
        book_layouts.append((work, book, recs, n_rows, low_runs, n_warnings, row_height))

    total_content_h = sum(bl[6] for bl in book_layouts)
    svg_w = MARGIN + LABEL_W + (MAX_CELLS * CELL_W) + STATS_W + MARGIN
    svg_h = MARGIN + HEADER_H + total_content_h + FOOTER_H + MARGIN

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{svg_w}" height="{svg_h}" '
                 f'viewBox="0 0 {svg_w} {svg_h}">')
    parts.append(f'<rect width="{svg_w}" height="{svg_h}" fill="{SVG_BG}"/>')

    # Fonts
    parts.append('<style>')
    parts.append('  text { font-family: "SF Mono", "Menlo", "Monaco", monospace; }')
    parts.append('  .title { font-size: 16px; font-weight: bold; }')
    parts.append('  .subtitle { font-size: 11px; fill: #888; }')
    parts.append('  .label { font-size: 11px; fill: #333; }')
    parts.append('  .stats { font-size: 10px; fill: #666; }')
    parts.append('  .warn { font-size: 9px; fill: #c9493b; }')
    parts.append('  .total { font-size: 12px; font-weight: bold; fill: #333; }')
    parts.append('  .legend-text { font-size: 10px; fill: #555; }')
    parts.append('</style>')

    # Title
    display_title = title or "Alignment"
    tx = MARGIN
    ty = MARGIN + 18
    parts.append(f'<text x="{tx}" y="{ty}" class="title">'
                 f'Alignment Quality Map — {_svg_escape(display_title)}</text>')

    # Legend
    ly = ty + 22
    lx = tx
    legend_items = [
        (SVG_HIGH, f"High (≥{HIGH})"),
        (SVG_MED, f"Medium ({MED}–{HIGH})"),
        (SVG_LOW, f"Low (<{MED})"),
    ]
    for color, label in legend_items:
        parts.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" '
                     f'fill="{color}" rx="2"/>')
        parts.append(f'<text x="{lx + 16}" y="{ly}" class="legend-text">'
                     f'{_svg_escape(label)}</text>')
        lx += 140

    # Books
    cy = MARGIN + HEADER_H

    all_scores = []

    for work, book, recs, n_rows, low_runs, n_warnings, row_height in book_layouts:
        stats = compute_book_stats(recs)
        scores = [get_score(r) for r in recs]
        all_scores.extend(scores)
        label = format_book_label(work, book)

        # Book label
        parts.append(f'<text x="{MARGIN}" y="{cy + 12}" class="label">'
                     f'{_svg_escape(label)}</text>')

        # Stats text (right side)
        stats_x = MARGIN + LABEL_W + (MAX_CELLS * CELL_W) + 8
        stats_text = (f'n={stats["n"]}  avg={stats["avg"]:.3f}  '
                     f'H={stats["high_pct"]:.0f}%  M={stats["med_pct"]:.0f}%  '
                     f'L={stats["low_pct"]:.0f}%')
        parts.append(
            f'<text x="{stats_x}" y="{cy + 12}" class="stats">'
            f'{_svg_escape(stats_text)}</text>'
        )

        # Heatmap cells
        bx = MARGIN + LABEL_W
        by = cy
        for i, s in enumerate(scores):
            col = i % MAX_CELLS
            row = i // MAX_CELLS
            x = bx + col * CELL_W
            y = by + row * CELL_H
            color = score_to_color(s)
            parts.append(f'<rect x="{x}" y="{y}" '
                         f'width="{CELL_W}" height="{CELL_H - 1}" '
                         f'fill="{color}"/>')

        # Low-run warnings
        warn_y = cy + n_rows * CELL_H + 2
        for run_start, run_end, run_avg, count in low_runs[:n_warnings]:
            parts.append(
                f'<text x="{MARGIN + LABEL_W}" y="{warn_y + 9}" class="warn">'
                f'⚠ {_svg_escape(run_start)} → {_svg_escape(run_end)}  '
                f'({count} sections, avg={run_avg:.3f})</text>'
            )
            warn_y += LOW_RUN_H

        cy += row_height

    # Footer totals
    n = len(all_scores)
    if n > 0:
        avg = sum(all_scores) / n
        high = sum(1 for s in all_scores if s >= HIGH)
        med = sum(1 for s in all_scores if MED <= s < HIGH)
        low = sum(1 for s in all_scores if s < MED)

        # Separator line
        parts.append(f'<line x1="{MARGIN}" y1="{cy + 5}" '
                     f'x2="{svg_w - MARGIN}" y2="{cy + 5}" '
                     f'stroke="#ccc" stroke-width="1"/>')

        total_text = (f'TOTAL: {n} sections   avg={avg:.3f}   '
                     f'High={high/n*100:.0f}%   Med={med/n*100:.0f}%   '
                     f'Low={low/n*100:.0f}%')
        parts.append(
            f'<text x="{MARGIN}" y="{cy + 25}" class="total">'
            f'{_svg_escape(total_text)}</text>'
        )

        # Stacked bar summary
        bar_y = cy + 32
        bar_w = svg_w - 2 * MARGIN
        bar_h = 10
        h_w = high / n * bar_w
        m_w = med / n * bar_w
        l_w = low / n * bar_w
        bx = MARGIN
        parts.append(f'<rect x="{bx}" y="{bar_y}" width="{h_w}" '
                     f'height="{bar_h}" fill="{SVG_HIGH}" rx="2"/>')
        bx += h_w
        parts.append(f'<rect x="{bx}" y="{bar_y}" width="{m_w}" '
                     f'height="{bar_h}" fill="{SVG_MED}"/>')
        bx += m_w
        parts.append(f'<rect x="{bx}" y="{bar_y}" width="{l_w}" '
                     f'height="{bar_h}" fill="{SVG_LOW}" rx="2"/>')

    parts.append('</svg>')

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


def _svg_escape(s):
    """Escape text for SVG XML."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------- TSV SUMMARY ---------------

def generate_tsv(records, fmt, out_path):
    """Write per-book summary stats as TSV."""
    by_book = defaultdict(list)
    for r in records:
        by_book[get_book_key(r, fmt)].append(r)

    book_keys = sorted(by_book.keys(), key=lambda k: (
        k[0], int(k[1]) if k[1].isdigit() else 0,
    ))

    with open(out_path, "w") as f:
        f.write("work\tbook\tsections\tavg_score\thigh_pct\tmed_pct\t"
                "low_pct\tmin_score\tmax_score\tworst_run_len\tworst_run_ref\n")
        for work, book in book_keys:
            recs = by_book[(work, book)]
            stats = compute_book_stats(recs)
            low_runs = find_low_runs(recs, fmt)
            worst_run_len = low_runs[0][3] if low_runs else 0
            worst_run_ref = (f"{low_runs[0][0]}..{low_runs[0][1]}"
                            if low_runs else "")
            f.write(f"{work}\t{book}\t{stats['n']}\t{stats['avg']:.4f}\t"
                    f"{stats['high_pct']:.1f}\t{stats['med_pct']:.1f}\t"
                    f"{stats['low_pct']:.1f}\t{stats['min']:.4f}\t"
                    f"{stats['max']:.4f}\t{worst_run_len}\t{worst_run_ref}\n")


# --------------- MAIN ---------------

def _make_prefix(title, path):
    """Derive a filename prefix from the title or input path.

    E.g. "Diodorus Siculus — Historical Library" -> "diodorus_siculus"
         "Statius, P. Papinius — Achilleid, Thebaid" -> "statius"
         Falls back to parent directory name.
    """
    if title:
        # Take the author part (before —) and simplify
        author = title.split("—")[0].split(",")[0].strip()
        prefix = author.lower().replace(" ", "_")
        # Remove non-alphanumeric
        prefix = "".join(c for c in prefix if c.isalnum() or c == "_")
        if prefix:
            return prefix
    # Fallback: use parent directory name
    return path.parent.name or "alignment"


def process_file(path, prefix=None):
    """Process a single alignment JSON file."""
    print(f"\nProcessing: {path}")
    records, fmt, title = load_alignments(path)
    if not records:
        print(f"  No records found, skipping.")
        return

    print(f"  Format: {fmt}, {len(records)} records, title: {title or '(unknown)'}")

    if prefix is None:
        prefix = _make_prefix(title, path)

    # Terminal output (with color)
    heatmap = render_heatmap(records, fmt, title=title, use_color=True)
    print(heatmap)

    # Save plain text version (no color)
    txt_path = path.parent / f"{prefix}.txt"
    plain = render_heatmap(records, fmt, title=title, use_color=False)
    with open(txt_path, "w") as f:
        f.write(plain)
    print(f"  Saved: {txt_path}")

    # Save TSV summary
    tsv_path = path.parent / f"{prefix}.tsv"
    generate_tsv(records, fmt, tsv_path)
    print(f"  Saved: {tsv_path}")

    # Save SVG — name matches the alignment XML (same stem, .svg extension)
    svg_path = path.parent / f"{prefix}.svg"
    generate_svg(records, fmt, svg_path, title=title)
    print(f"  Saved: {svg_path}")


def main():
    # Parse args: [--prefix NAME] [paths...]
    args = sys.argv[1:]
    prefix = None
    if "--prefix" in args:
        idx = args.index("--prefix")
        prefix = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    if args:
        paths = [Path(p) for p in args]
    else:
        # Auto-discover all alignment files under output/
        output_dir = PROJECT_ROOT / "build"
        paths = sorted(output_dir.rglob("entity_validated_alignments.json"))

    if not paths:
        print("No alignment files found.")
        print("Usage: python scripts/alignment_quality_map.py [--prefix NAME] <path_to_alignments.json>")
        sys.exit(1)

    for p in paths:
        if p.exists():
            process_file(p, prefix=prefix)


if __name__ == "__main__":
    main()

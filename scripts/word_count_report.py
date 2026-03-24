#!/usr/bin/env python3
"""
Generate final/word_count_comparison.md by parsing HTML parallel text files.

For each work in scripts/works/*/config.json, counts words in the Greek (source)
and English columns of the corresponding HTML file(s) in final/.

Multi-work configs (multiple work_ids) sum word counts across all sub-files,
but only if the sub-files have distinct content (detects duplicates by size).

Usage:
    python scripts/word_count_report.py
"""

import json
import os
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKS_DIR = PROJECT_ROOT / "scripts" / "works"
FINAL_DIR = PROJECT_ROOT / "final"


class WordCounter(HTMLParser):
    """Count words in source (Greek/Latin) and English columns of parallel HTML."""

    def __init__(self):
        super().__init__()
        self.source_words = 0
        self.english_words = 0
        self._current = None

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            cls = dict(attrs).get("class", "")
            if "source" in cls:
                self._current = "source"
            elif "english" in cls:
                self._current = "english"
            else:
                self._current = None
        elif tag == "span" and self._current:
            cls = dict(attrs).get("class", "")
            if any(x in cls for x in ("fn", "score", "heading-text")):
                self._current = None

    def handle_endtag(self, tag):
        if tag == "td":
            self._current = None

    def handle_data(self, data):
        if self._current == "source":
            self.source_words += len(data.split())
        elif self._current == "english":
            self.english_words += len(data.split())


def count_words_in_html(html_path):
    """Parse an HTML file and return (source_words, english_words)."""
    counter = WordCounter()
    with open(html_path, encoding="utf-8") as f:
        counter.feed(f.read())
    return counter.source_words, counter.english_words


def collect_work_data():
    """Iterate over all work configs and collect word count data."""
    results = []

    for config_path in sorted(WORKS_DIR.glob("*/config.json")):
        with open(config_path) as f:
            cfg = json.load(f)

        author = cfg["author"]
        title = cfg["work_title"]
        name = cfg["name"]
        lang = cfg.get("source_language", "greek")

        gr = cfg.get("greek_source", {})
        tlg_id = gr.get("tlg_id", gr.get("phi_id", ""))
        work_id = gr.get("work_id", "")
        work_ids = gr.get("work_ids", [work_id] if work_id else [])

        html_files = []
        for wid in work_ids:
            html_path = FINAL_DIR / f"{tlg_id}.{wid}.perseus-eng80.html"
            if html_path.exists():
                html_files.append(html_path)

        if not html_files:
            results.append({
                "author": author,
                "title": title,
                "name": name,
                "lang": lang,
                "source_words": 0,
                "english_words": 0,
                "html_count": 0,
                "note": "no HTML files found",
            })
            continue

        # Count words per file
        file_counts = []
        for hp in html_files:
            sw, ew = count_words_in_html(hp)
            file_counts.append((sw, ew, os.path.getsize(hp)))

        # For multi-work: detect duplicated files (same size AND same word counts)
        # and only count unique content
        if len(file_counts) > 1:
            seen = set()
            total_source = 0
            total_english = 0
            unique_count = 0
            for sw, ew, sz in file_counts:
                key = (sw, ew, sz)
                if key not in seen:
                    seen.add(key)
                    total_source += sw
                    total_english += ew
                    unique_count += 1
            note = ""
            if unique_count < len(file_counts):
                note = f"{len(file_counts)} files but only {unique_count} unique"
        else:
            total_source = file_counts[0][0]
            total_english = file_counts[0][1]
            unique_count = 1
            note = ""

        if total_source == 0 and total_english == 0:
            note = "HTML files exist but contain no parallel text"

        results.append({
            "author": author,
            "title": title,
            "name": name,
            "lang": lang,
            "source_words": total_source,
            "english_words": total_english,
            "html_count": len(html_files),
            "note": note,
        })

    return results


def generate_report(results):
    """Generate the markdown report."""
    # Separate works with data from those without
    with_data = [r for r in results if r["source_words"] > 0 or r["english_words"] > 0]
    without_data = [r for r in results if r["source_words"] == 0 and r["english_words"] == 0]

    # Compute ratio and sort
    for r in with_data:
        sw, ew = r["source_words"], r["english_words"]
        r["ratio"] = min(sw, ew) / max(sw, ew) if max(sw, ew) > 0 else 0
        avg = (sw + ew) / 2
        r["pct_diff"] = abs(sw - ew) / avg * 100 if avg > 0 else 0

    with_data.sort(key=lambda r: -r["ratio"])

    src_label = "Source Words"
    lines = [
        "# Greek vs English Word Count Comparison",
        "",
        "Ranked by how close the source and English word counts are per work (ratio = min/max words).",
        "",
        f"| Rank | Work | Author | {src_label} | English Words | Ratio | % Diff |",
        f"|------|------|--------|{'-' * 12}:|{'-' * 13}:|------:|-------:|",
    ]

    for i, r in enumerate(with_data, 1):
        ratio_str = f"{r['ratio']:.3f}"
        pct_str = f"{r['pct_diff']:.1f}%"
        note = f" *" if r.get("note") else ""
        lines.append(
            f"| {i} | {r['title']}{note} | {r['author']} "
            f"| {r['source_words']:,} | {r['english_words']:,} "
            f"| {ratio_str} | {pct_str} |"
        )

    # Add works with no data
    for r in without_data:
        lines.append(
            f"| — | {r['title']} | {r['author']} "
            f"| 0 | 0 | N/A | N/A |"
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- **Ratio** = min(source, english) / max(source, english). 1.0 = perfect match.")
    lines.append("- **% Diff** = absolute difference / average of the two counts.")
    lines.append("- Word counts are raw whitespace-split tokens from the HTML parallel text columns.")
    lines.append("- English translations are typically wordier than Greek, so English > Greek is expected for well-aligned works.")

    # Add notes for specific issues
    noted = [r for r in with_data if r.get("note")]
    if noted:
        lines.append("- Works marked with * have notes:")
        for r in noted:
            lines.append(f"  - **{r['title']}** ({r['author']}): {r['note']}")

    if without_data:
        notes = []
        for r in without_data:
            notes.append(f"{r['title']} ({r['author']}): {r.get('note', 'no HTML output')}")
        lines.append("- Works with no parallel text: " + "; ".join(notes))

    lines.append("- Works where source >> English may have alignment issues or source text that includes apparatus/scholia.")
    lines.append("")

    return "\n".join(lines)


def main():
    results = collect_work_data()
    report = generate_report(results)

    out_path = FINAL_DIR / "word_count_comparison.md"
    with open(out_path, "w") as f:
        f.write(report)

    print(f"Report written to {out_path}")
    print(f"  {len([r for r in results if r['source_words'] > 0 or r['english_words'] > 0])} works with data")
    print(f"  {len([r for r in results if r['source_words'] == 0 and r['english_words'] == 0])} works without data")


if __name__ == "__main__":
    main()

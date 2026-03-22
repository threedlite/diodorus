#!/usr/bin/env python3
"""
Copy verified alignment XML and SVG files to the final/ directory.

Only runs after integrity checks pass. Never deletes anything in final/ —
only adds or updates files.

Usage:
    python scripts/publish_to_final.py <pipeline_name> <output_dir>

Example:
    python scripts/publish_to_final.py diodorus output/
    python scripts/publish_to_final.py statius output/statius/
    python scripts/publish_to_final.py marcus output/marcus/
"""

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FINAL_DIR = PROJECT_ROOT / "final"


def publish(pipeline_name, output_dir):
    """Copy XML and SVG files from output_dir to final/."""
    output_dir = Path(output_dir)
    if not output_dir.exists():
        print(f"Error: {output_dir} does not exist")
        return False

    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    # Only publish files matching the documented naming patterns:
    #   *.perseus-eng80.xml        — Perseus-compatible TEI translation
    #   __cts__eng80_fragment.xml  — CTS catalog entry
    #   alignment_*_perseus.xml    — standoff alignment (Perseus source)
    #   alignment_*_f1k.xml        — standoff alignment (First1KGreek source)
    #   alignment_quality_map_*.svg — quality heatmap
    copied = 0
    for src in sorted(output_dir.glob("*")):
        name = src.name

        publish = False
        if name.endswith(".perseus-eng80.xml"):
            publish = True
        elif name.endswith(".perseus-eng80.svg"):
            publish = True
        elif name.endswith(".perseus-eng80.html"):
            publish = True
        elif name.startswith("__cts__eng80") and name.endswith(".xml"):
            publish = True

        if not publish:
            continue

        dest = FINAL_DIR / name
        shutil.copy2(src, dest)
        print(f"  {name} -> final/{name}")
        copied += 1

    if copied == 0:
        print(f"  No XML or SVG files found in {output_dir}")
        return False

    print(f"  Published {copied} files to final/")
    return True


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/publish_to_final.py <pipeline_name> <output_dir>")
        sys.exit(1)

    pipeline_name = sys.argv[1]
    output_dir = sys.argv[2]

    print(f"Publishing {pipeline_name} to final/...")
    ok = publish(pipeline_name, output_dir)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

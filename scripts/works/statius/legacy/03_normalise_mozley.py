#!/usr/bin/env python3
"""
Light normalisation of Mozley's English translation text.

Mozley (1928) is modern English — much less normalisation needed
than Booth (1700). Main tasks:
  - Normalise whitespace (collapse runs, strip HTML artifacts)
  - Fix encoding oddities (smart quotes, em-dashes, etc.)
  - Strip any residual HTML tags or entities
  - Remove line-number references embedded in the text [1] [50] etc.

Input:
  data-sources/statius_mozley/thebaid_raw.json
  data-sources/statius_mozley/achilleid_raw.json

Output:
  output/statius/mozley_normalised.json
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data-sources" / "statius_mozley"
THEBAID_RAW = DATA_DIR / "thebaid_raw.json"
ACHILLEID_RAW = DATA_DIR / "achilleid_raw.json"
OUTPUT = PROJECT_ROOT / "build" / "statius" / "mozley_normalised.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def normalise_text(text):
    """Apply light normalisation to Mozley's English text."""
    t = text

    # Remove embedded line-number references like [1] [50] [100]
    t = re.sub(r"\[\d+\]", "", t)

    # Strip any residual HTML tags
    t = re.sub(r"<[^>]+>", "", t)

    # Normalise smart quotes and apostrophes
    t = t.replace("\u2018", "'").replace("\u2019", "'")  # single quotes
    t = t.replace("\u201c", '"').replace("\u201d", '"')  # double quotes

    # Normalise dashes
    t = t.replace("\u2014", " -- ")  # em-dash
    t = t.replace("\u2013", " - ")   # en-dash

    # Normalise ellipsis
    t = t.replace("\u2026", "...")

    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()

    return t


def process_work(input_path, work_name):
    """Normalise all paragraphs in a work."""
    if not input_path.exists():
        print(f"  Error: {input_path} not found. Run 01_scrape_mozley.py first.")
        return None

    with open(input_path) as f:
        data = json.load(f)

    total_modified = 0

    for book in data["books"]:
        for para in book["paragraphs"]:
            original = para["text"]
            normalised = normalise_text(original)
            para["text_normalised"] = normalised
            para["char_count"] = len(normalised)
            if normalised != original:
                total_modified += 1

    total_paras = sum(len(b["paragraphs"]) for b in data["books"])
    print(f"  {work_name}: {total_paras} paragraphs, {total_modified} modified")

    return data


def main():
    result = {
        "source": "Theoi.com — Statius (Mozley, 1928), normalised",
        "works": {},
    }

    for input_path, work_name in [
        (THEBAID_RAW, "Thebaid"),
        (ACHILLEID_RAW, "Achilleid"),
    ]:
        print(f"\n=== Normalising {work_name} ===")
        data = process_work(input_path, work_name)
        if data is None:
            raise SystemExit(1)
        result["works"][work_name.lower()] = data

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()

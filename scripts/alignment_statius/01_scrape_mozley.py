#!/usr/bin/env python3
"""
Fetch J.H. Mozley's English translations of Statius from Wikisource.

Source: Wikisource "Statius (Mozley 1928)" — hand-transcribed, CC BY-SA.
  - Vol 1: Thebaid Books 1-4
  - Vol 2: Thebaid Books 5-12, Achilleid Books 1-2

Uses the MediaWiki parse API to get clean HTML, then extracts <p> elements.
Rate-limits requests (1s delay between pages).
Caches locally — only fetches if output files don't already exist.

Outputs:
  data-sources/statius_mozley/thebaid_raw.json
  data-sources/statius_mozley/achilleid_raw.json
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = PROJECT_ROOT / "data-sources" / "statius_mozley"
OUT_DIR.mkdir(parents=True, exist_ok=True)

THEBAID_OUT = OUT_DIR / "thebaid_raw.json"
ACHILLEID_OUT = OUT_DIR / "achilleid_raw.json"

API_URL = "https://en.wikisource.org/w/api.php"

# Wikisource page titles for each book
THEBAID_PAGES = {
    1: "Statius_(Mozley_1928)_v1/Thebaid/Book_1",
    2: "Statius_(Mozley_1928)_v1/Thebaid/Book_2",
    3: "Statius_(Mozley_1928)_v1/Thebaid/Book_3",
    4: "Statius_(Mozley_1928)_v1/Thebaid/Book_4",
    5: "Statius_(Mozley_1928)_v2/Thebaid/Book_5",
    6: "Statius_(Mozley_1928)_v2/Thebaid/Book_6",
    7: "Statius_(Mozley_1928)_v2/Thebaid/Book_7",
    8: "Statius_(Mozley_1928)_v2/Thebaid/Book_8",
    9: "Statius_(Mozley_1928)_v2/Thebaid/Book_9",
    10: "Statius_(Mozley_1928)_v2/Thebaid/Book_10",
    11: "Statius_(Mozley_1928)_v2/Thebaid/Book_11",
    12: "Statius_(Mozley_1928)_v2/Thebaid/Book_12",
}

ACHILLEID_PAGES = {
    1: "Statius_(Mozley_1928)_v2/Achilleid/Book_1",
    2: "Statius_(Mozley_1928)_v2/Achilleid/Book_2",
}

HEADERS = {
    "User-Agent": "DiodorusAlignmentProject/1.0 (academic research; statius alignment)"
}


def fetch_wikisource_html(page_title):
    """Fetch parsed HTML for a Wikisource page via the API."""
    print(f"  Fetching {page_title} ...")
    params = {
        "action": "parse",
        "page": page_title,
        "prop": "text",
        "format": "json",
    }
    resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"Wikisource API error: {data['error']}")

    time.sleep(1)  # rate-limit
    return data["parse"]["text"]["*"]


def extract_paragraphs(html):
    """
    Extract prose translation paragraphs from Wikisource HTML.

    Wikisource Mozley pages have a consistent structure:
      - Header/nav elements with class 'ws-noexport', 'noprint'
      - A few short <p> elements for layout/titles
      - Long <p> elements containing the actual translation prose

    We filter for substantial paragraphs (>100 chars) that contain
    actual translation text.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove navigation/header elements
    for el in soup.select(".ws-noexport, .ws-header, .wst-header, .noprint"):
        el.decompose()

    paragraphs = []

    for p in soup.find_all("p"):
        text = p.get_text(separator=" ", strip=True)

        # Normalise Wikisource footnote markers like [ 2 ] or [2]
        text = re.sub(r'\[\s*\d+\s*\]', '', text)

        # Collapse whitespace after removing markers
        text = re.sub(r'\s+', ' ', text).strip()

        # Skip empty, short, or non-prose paragraphs
        if len(text) < 100:
            continue

        paragraphs.append({
            "text": text,
            "char_count": len(text),
        })

    return paragraphs


def process_work(work_name, pages, output_path):
    """Fetch and parse all books for a work."""
    if output_path.exists():
        print(f"  {output_path.name} already exists, loading cached version.")
        with open(output_path) as f:
            return json.load(f)

    result = {
        "source": f"Wikisource — Statius (Mozley 1928), {work_name}",
        "license": "CC BY-SA (Wikisource)",
        "translator": "J.H. Mozley",
        "date": "1928",
        "books": [],
    }

    for book_num in sorted(pages.keys()):
        page_title = pages[book_num]
        html = fetch_wikisource_html(page_title)

        # Cache raw HTML
        safe_name = page_title.replace("/", "_") + ".html"
        with open(OUT_DIR / safe_name, "w", encoding="utf-8") as f:
            f.write(html)

        paragraphs = extract_paragraphs(html)
        print(f"    Book {book_num}: {len(paragraphs)} paragraphs extracted")

        result["books"].append({
            "book": book_num,
            "paragraphs": paragraphs,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def main():
    print("\n=== Processing Thebaid ===")
    theb = process_work("Thebaid", THEBAID_PAGES, THEBAID_OUT)
    total_paras = sum(len(b["paragraphs"]) for b in theb["books"])
    total_chars = sum(p["char_count"] for b in theb["books"] for p in b["paragraphs"])
    print(f"  Total: {len(theb['books'])} books, {total_paras} paragraphs, {total_chars:,} chars")

    print("\n=== Processing Achilleid ===")
    ach = process_work("Achilleid", ACHILLEID_PAGES, ACHILLEID_OUT)
    total_paras = sum(len(b["paragraphs"]) for b in ach["books"])
    total_chars = sum(p["char_count"] for b in ach["books"] for p in b["paragraphs"])
    print(f"  Total: {len(ach['books'])} books, {total_paras} paragraphs, {total_chars:,} chars")

    print("\nDone. Outputs:")
    print(f"  {THEBAID_OUT}")
    print(f"  {ACHILLEID_OUT}")


if __name__ == "__main__":
    main()

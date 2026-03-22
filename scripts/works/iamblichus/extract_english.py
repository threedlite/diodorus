#!/usr/bin/env python3
"""
Extract English chapters from Taylor's translations of Iamblichus.

Handles both Life of Pythagoras (#63300) and De Mysteriis (#72815).

Input:  data-sources/gutenberg/iamblichus/
Output: output/iamblichus/english_sections.json
"""

import json
import re
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CACHE_DIR = PROJECT_ROOT / "data-sources" / "gutenberg" / "iamblichus"
OUTPUT = PROJECT_ROOT / "build" / "iamblichus" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

WORKS = [
    {
        "title": "De Vita Pythagorica",
        "file": "life_pythagoras_63300.txt",
        "url": "https://www.gutenberg.org/cache/epub/63300/pg63300.txt",
        "chapter_pattern": r"^\s*CHAP\.\s+(I{1,3}|IV|V|VI{0,3}|IX|X|XI{0,3}|XII{0,3}|"
                           r"XIV|XV|XVI{0,3}|XIX|XX|XXI{0,3}|XXIV|XXV|XXVI{0,3}|XXIX|"
                           r"XXX|XXXI{0,3}|XXXIV|XXXV|XXXVI)\.\s*$",
    },
    {
        "title": "De Mysteriis",
        "file": "de_mysteriis_72815.txt",
        "url": "https://www.gutenberg.org/cache/epub/72815/pg72815.txt",
        "chapter_pattern": None,  # Will determine after inspection
    },
]

ROMAN = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
    "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
    "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17,
    "XVIII": 18, "XIX": 19, "XX": 20, "XXI": 21, "XXII": 22,
    "XXIII": 23, "XXIV": 24, "XXV": 25, "XXVI": 26, "XXVII": 27,
    "XXVIII": 28, "XXIX": 29, "XXX": 30, "XXXI": 31, "XXXII": 32,
    "XXXIII": 33, "XXXIV": 34, "XXXV": 35, "XXXVI": 36,
    "XXXVII": 37,
}


def download_if_needed(work):
    path = CACHE_DIR / work["file"]
    if not path.exists():
        print(f"  Downloading {work['url']}...")
        urllib.request.urlretrieve(work["url"], path)
    return path


def extract_life_of_pythagoras(path):
    """Extract chapters from Life of Pythagoras."""
    text = path.read_text(encoding="utf-8-sig")
    text = text.replace("\r\n", "\n")

    # Find chapter markers: "CHAP. I." etc.
    chapter_pattern = re.compile(r"^\s*CHAP\.\s+([IVXL]+)\.\s*$", re.MULTILINE)
    matches = list(chapter_pattern.finditer(text))

    print(f"  Found {len(matches)} chapters")

    sections = []
    for i, m in enumerate(matches):
        roman_num = m.group(1)
        chapter_num = ROMAN.get(roman_num)
        if chapter_num is None:
            continue

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        # Stop at "Fragments" or "END OF"
        for stop in ["Fragments of the Ethical", "*** END OF"]:
            idx = text.find(stop, start, end)
            if idx != -1:
                end = idx

        body = text[start:end].strip()
        # Remove footnotes (lines starting with [number] or indented with [)
        body = re.sub(r"\n\s*\[\d+\].*", "", body)
        body = re.sub(r"\n    \[.*?\n\n", "\n\n", body, flags=re.DOTALL)
        body = " ".join(body.split())

        if body and len(body) > 20:
            sections.append({
                "work": "De Vita Pythagorica",
                "book": str(chapter_num),
                "section": "1",
                "cts_ref": str(chapter_num),
                "text": body,
                "char_count": len(body),
            })

    return sections


def extract_de_mysteriis(path):
    """Extract sections from De Mysteriis."""
    text = path.read_text(encoding="utf-8-sig")
    text = text.replace("\r\n", "\n")

    # Check structure
    # De Mysteriis has SECTION markers or CHAPTER markers
    sec_pattern = re.compile(r"^\s*SECTION\s+([IVXL]+)\.\s*$", re.MULTILINE)
    chap_pattern = re.compile(r"^\s*CHAP(?:TER|\.)\s+([IVXL]+)\.\s*$", re.MULTILINE)

    matches = list(sec_pattern.finditer(text))
    if not matches:
        matches = list(chap_pattern.finditer(text))
    if not matches:
        # Try "CHAPTER I." or numbered sections
        matches = list(re.finditer(r"^\s*(?:CHAPTER|SECTION|CHAP\.)\s+([IVXL]+)\.?\s*$",
                                   text, re.MULTILINE))

    if not matches:
        # Fallback: split on double blank lines after finding text start
        print("  Warning: no chapter/section markers found, using paragraph splitting")
        gut_start = text.find("*** START OF THE PROJECT GUTENBERG EBOOK")
        gut_end = text.find("*** END OF THE PROJECT GUTENBERG EBOOK")
        body = text[gut_start:gut_end] if gut_start != -1 else text

        # Find the actual content start (after intro/preface)
        # Look for "SECTION I" or the first substantial paragraph
        content_start = body.find("SECTION I")
        if content_start == -1:
            content_start = body.find("CHAPTER I")
        if content_start == -1:
            content_start = 0

        body = body[content_start:]
        blocks = re.split(r"\n{3,}", body)

        sections = []
        for i, block in enumerate(blocks):
            block = block.strip()
            if not block or len(block) < 50:
                continue
            block = " ".join(block.split())
            sections.append({
                "work": "De Mysteriis",
                "book": "1",
                "section": str(i + 1),
                "cts_ref": str(i + 1),
                "text": block,
                "char_count": len(block),
            })
        return sections

    print(f"  Found {len(matches)} sections")

    sections = []
    for i, m in enumerate(matches):
        roman_num = m.group(1)
        sec_num = ROMAN.get(roman_num, i + 1)

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        for stop in ["*** END OF", "ADDITIONAL NOTES", "FOOTNOTES"]:
            idx = text.find(stop, start, end)
            if idx != -1:
                end = idx

        body = text[start:end].strip()
        body = re.sub(r"\n\s*\[\d+\].*", "", body)
        body = " ".join(body.split())

        if body and len(body) > 20:
            sections.append({
                "work": "De Mysteriis",
                "book": str(sec_num),
                "section": "1",
                "cts_ref": str(sec_num),
                "text": body,
                "char_count": len(body),
            })

    return sections


all_sections = []

# Life of Pythagoras
print("=== De Vita Pythagorica ===")
lp_path = download_if_needed(WORKS[0])
lp_sections = extract_life_of_pythagoras(lp_path)
print(f"  Extracted {len(lp_sections)} chapters")
all_sections.extend(lp_sections)

# De Mysteriis
print("\n=== De Mysteriis ===")
dm_path = download_if_needed(WORKS[1])
dm_sections = extract_de_mysteriis(dm_path)
print(f"  Extracted {len(dm_sections)} sections")
all_sections.extend(dm_sections)

print(f"\nTotal: {len(all_sections)} sections")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

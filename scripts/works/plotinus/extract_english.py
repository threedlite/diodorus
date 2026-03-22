#!/usr/bin/env python3
"""
Extract English sections from Guthrie's Enneads translation (Gutenberg).

4 volumes (#42930-42933). The text is organized chronologically, not by
Ennead order. Each tractate is headed like "FIRST ENNEAD, BOOK SIXTH."
where "BOOK" refers to the tractate number within that Ennead.

Sections within each tractate are numbered (1., 2., etc.).
The book/chapter structure maps to Ennead/tractate.

Input:  data-sources/gutenberg/plotinus/enneads_v{1-4}_4293{0-3}.txt
Output: build/plotinus/english_sections.json
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data-sources" / "gutenberg" / "plotinus"
OUTPUT = PROJECT_ROOT / "build" / "plotinus" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

INPUT_FILES = [
    INPUT_DIR / "enneads_v1_42930.txt",
    INPUT_DIR / "enneads_v2_42931.txt",
    INPUT_DIR / "enneads_v3_42932.txt",
    INPUT_DIR / "enneads_v4_42933.txt",
]

ENNEAD_WORDS = {
    "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4,
    "FIFTH": 5, "SIXTH": 6,
}

BOOK_WORDS = {
    "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOUR": 4, "FOURTH": 4,
    "FIVE": 5, "FIFTH": 5, "SIX": 6, "SIXTH": 6,
    "SEVEN": 7, "SEVENTH": 7, "EIGHT": 8, "EIGHTH": 8,
    "NINE": 9, "NINTH": 9,
}


def strip_gutenberg(text):
    """Remove Gutenberg header and footer."""
    start = text.find("*** START OF THE PROJECT GUTENBERG EBOOK")
    if start != -1:
        start = text.find("\n", start) + 1
    else:
        start = 0
    end = text.find("*** END OF THE PROJECT GUTENBERG EBOOK")
    if end == -1:
        end = len(text)
    return text[start:end]


def clean_text(text):
    """Normalize whitespace, remove footnote references."""
    # Remove footnote reference numbers like [114], [322]
    text = re.sub(r'\[\d+\]', '', text)
    # Normalize whitespace
    text = " ".join(text.split())
    return text.strip()


# Pattern to match tractate headings like "FIRST ENNEAD, BOOK SIXTH."
# Some have footnote refs like "FIRST ENNEAD,[322] BOOK TWO."
tractate_pattern = re.compile(
    r'^(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH)\s+ENNEAD,?\s*(?:\[\d+\])?\s*BOOK\s+'
    r'(FIRST|SECOND|THIRD|FOUR(?:TH)?|FIVE|FIFTH|SIX(?:TH)?|SEVEN(?:TH)?|EIGHT(?:TH)?|NINE|NINTH)\b',
    re.MULTILINE
)

all_tractates = []  # list of (ennead_num, tractate_num, text)

for input_file in INPUT_FILES:
    if not input_file.exists():
        print(f"Error: {input_file} not found")
        raise SystemExit(1)

    text = input_file.read_text(encoding="utf-8-sig")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = strip_gutenberg(text)

    matches = list(tractate_pattern.finditer(text))
    print(f"Found {len(matches)} tractate headers in {input_file.name}")

    for i, m in enumerate(matches):
        ennead_word = m.group(1)
        book_word = m.group(2)
        ennead_num = ENNEAD_WORDS[ennead_word]
        tractate_num = BOOK_WORDS[book_word]

        start = m.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        tractate_text = text[start:end].strip()

        # Remove trailing footnotes section if present
        fn_start = re.search(r'\n\s*FOOTNOTES?\s*\n', tractate_text)
        if fn_start:
            tractate_text = tractate_text[:fn_start.start()]

        # Remove trailing footnote blocks
        tractate_text = re.sub(r'\[Footnote \d+:.*?\]', '', tractate_text, flags=re.DOTALL)

        all_tractates.append((ennead_num, tractate_num, tractate_text))

# Now extract numbered sections from each tractate
all_sections = []

for ennead_num, tractate_num, tractate_text in all_tractates:
    # Split on section numbers: "1. ", "2. " etc. at start of line or after blank
    section_pattern = re.compile(r'(?:^|\n\s*\n)\s*(\d+)\.\s+')

    parts = section_pattern.split(tractate_text)
    # parts[0] = preamble/title text before section 1
    # parts[1] = "1", parts[2] = section 1 text
    # parts[3] = "2", parts[4] = section 2 text, etc.

    if len(parts) >= 3:
        # Has numbered sections
        for j in range(1, len(parts) - 1, 2):
            sec_num = parts[j]
            sec_text = parts[j + 1].strip()
            sec_text = clean_text(sec_text)
            if sec_text:
                cts_ref = f"{ennead_num}.{tractate_num}.{sec_num}"
                all_sections.append({
                    "book": str(ennead_num),
                    "chapter": str(tractate_num),
                    "section": sec_num,
                    "cts_ref": cts_ref,
                    "text": sec_text,
                    "char_count": len(sec_text),
                })
    else:
        # No numbered sections — treat whole tractate as section 1
        sec_text = clean_text(tractate_text)
        if sec_text:
            cts_ref = f"{ennead_num}.{tractate_num}.1"
            all_sections.append({
                "book": str(ennead_num),
                "chapter": str(tractate_num),
                "section": "1",
                "cts_ref": cts_ref,
                "text": sec_text,
                "char_count": len(sec_text),
            })


# Sort by ennead, tractate, section
def sort_key(s):
    parts = s["cts_ref"].split(".")
    return tuple(int(p) for p in parts if p.isdigit())


all_sections.sort(key=sort_key)

# Deduplicate: some tractates appear in the appendix/summary of vol 4
# Keep the first (longest) occurrence of each cts_ref
seen = {}
deduped = []
for s in all_sections:
    ref = s["cts_ref"]
    if ref not in seen or s["char_count"] > seen[ref]["char_count"]:
        seen[ref] = s

for ref in sorted(seen.keys(), key=lambda r: tuple(int(p) for p in r.split(".") if p.isdigit())):
    deduped.append(seen[ref])

all_sections = deduped

print(f"\nExtracted {len(all_sections)} English sections")
enneads = sorted(set(s["book"] for s in all_sections), key=int)
for ennead in enneads:
    ennead_secs = [s for s in all_sections if s["book"] == ennead]
    tractates = sorted(set(s["chapter"] for s in ennead_secs), key=int)
    print(f"  Ennead {ennead}: {len(ennead_secs)} sections across {len(tractates)} tractates")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

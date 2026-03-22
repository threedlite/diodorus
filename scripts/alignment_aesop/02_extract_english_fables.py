#!/usr/bin/env python3
"""
Extract English fables from Gutenberg Townsend translation (#21).

Downloads if not cached, then parses into individual fables by splitting
on the uppercase title pattern.

Input:  Gutenberg ebook #21 (cached in data-sources/gutenberg/aesop/)
Output: output/aesop/english_fables.json
"""

import json
import re
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = PROJECT_ROOT / "data-sources" / "gutenberg" / "aesop"
CACHE_FILE = CACHE_DIR / "townsend_21.txt"
OUTPUT = PROJECT_ROOT / "build" / "aesop" / "english_fables.json"

GUTENBERG_URL = "https://www.gutenberg.org/cache/epub/21/pg21.txt"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Download if not cached
if not CACHE_FILE.exists():
    print(f"Downloading Gutenberg #21...")
    urllib.request.urlretrieve(GUTENBERG_URL, CACHE_FILE)
    print(f"  Saved: {CACHE_FILE}")
else:
    print(f"Using cached: {CACHE_FILE}")

text = CACHE_FILE.read_text(encoding="utf-8-sig")
# Normalize line endings and smart quotes
text = text.replace("\r\n", "\n").replace("\r", "\n")
text = text.replace("\u2019", "'").replace("\u2018", "'")
text = text.replace("\u201c", '"').replace("\u201d", '"')
# Normalize Æ variants
text = text.replace("\xc6", "AE")  # Æ -> AE

end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK"

# The fable text starts after the preface. Find "The Lion And The Mouse"
# or the first actual fable title (after CONTENTS and LIFE OF AESOP sections).
# Strategy: find the line "AESOP'S FABLES" or similar, then skip forward
# past the preface until we hit actual fable titles.
# Simpler: find first fable by looking for well-known first fable title.
import re as _re
# Find where the actual fable bodies start (not the TOC).
# Strategy: the TOC has fable titles indented, one per line, no periods.
# The actual fables have a title line followed by paragraph body with periods.
# Find the first fable title that is followed within 300 chars by a period.
first_fable_titles = [
    "The Wolf and the Lamb",
    "The Lion and the Mouse",
]
start_idx = -1
for pat in first_fable_titles:
    search_start = 0
    while True:
        idx = text.lower().find(pat.lower(), search_start)
        if idx == -1:
            break
        # Check if this occurrence has body text (a period within 300 chars)
        after = text[idx + len(pat):idx + len(pat) + 300]
        if "." in after:
            # Back up to the start of the line containing this title
            line_start = text.rfind("\n", 0, idx)
            start_idx = line_start + 1 if line_start != -1 else idx
            break
        search_start = idx + len(pat)
    if start_idx != -1:
        break

if start_idx == -1:
    print("Error: could not find start of fable bodies")
    raise SystemExit(1)

# Extract fable text starting from the first fable
fable_text = text[start_idx:]

end_idx = fable_text.find(end_marker)
if end_idx != -1:
    fable_text = fable_text[:end_idx]

# Split into individual fables.
# Townsend's format: fables separated by 4+ newlines.
# Each fable: title line(s), then 2-3 blank lines, then body paragraph(s).
# Example:
#   \n\n\n\n\nThe Wolf And The Lamb\n\n\nWOLF, meeting with...tyranny.\n\n\n\n\n

# Split on 4+ consecutive newlines to get fable blocks
blocks = re.split(r"\n{4,}", fable_text)

fables = []
for block in blocks:
    block = block.strip()
    if not block:
        continue

    # Split block into title and body at the first double-newline
    parts = re.split(r"\n{2,}", block, maxsplit=1)
    if len(parts) < 2:
        continue

    title_part = parts[0].strip()
    body_part = parts[1].strip()

    # Validate: title should be short, body should have sentences
    if not title_part or not body_part:
        continue
    if len(title_part) > 120:  # too long for a title
        continue
    if "." not in body_part:  # body needs at least one sentence
        continue
    # Skip non-fable sections
    skip_words = ["FOOTNOTE", "PREFACE", "LIFE OF", "CONTENTS", "INDEX"]
    if any(w in title_part.upper() for w in skip_words):
        continue

    # Clean title: join multi-line titles
    title = " ".join(title_part.split())
    # Clean body: normalize whitespace
    body = " ".join(body_part.split())

    if len(body) > 20:
        fables.append({
            "fable_index": len(fables),
            "title": title,
            "text": body,
            "char_count": len(body),
        })

print(f"Extracted {len(fables)} English fables")
if fables:
    print(f"  Char sizes: min={min(f['char_count'] for f in fables)}, "
          f"max={max(f['char_count'] for f in fables)}, "
          f"mean={sum(f['char_count'] for f in fables) // len(fables)}")
    print(f"  First 5 titles: {[f['title'][:50] for f in fables[:5]]}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(fables, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

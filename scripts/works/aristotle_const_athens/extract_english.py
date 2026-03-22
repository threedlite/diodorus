#!/usr/bin/env python3
"""
Extract English sections from Kenyon's Aristotle Constitution of Athens (Gutenberg #26095).

Exceptionally clean text: 69 Parts matching the Greek's 69 sections.
Almost nothing to strip — no introduction, no appendices, no endnotes.

The Greek has subsections within each of the 69 sections. We extract
one English section per Part, and the pipeline's DP alignment will refine
by matching paragraphs within each Part to Greek subsections.

Input:  data-sources/gutenberg/aristotle_const_athens/pg26095.txt
Output: build/aristotle_const_athens/english_sections.json
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT = PROJECT_ROOT / "data-sources" / "gutenberg" / "aristotle_const_athens" / "pg26095.txt"
OUTPUT = PROJECT_ROOT / "build" / "aristotle_const_athens" / "english_sections.json"

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from pipeline.strip_notes import strip_notes

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

if not INPUT.exists():
    print(f"Error: {INPUT} not found")
    raise SystemExit(1)

text = INPUT.read_text(encoding="utf-8-sig")
text = text.replace("\r\n", "\n").replace("\r", "\n")

# Strip Gutenberg header/footer
start = text.find("*** START OF THE PROJECT GUTENBERG EBOOK")
end = text.find("*** END OF THE PROJECT GUTENBERG EBOOK")
if start != -1:
    text = text[text.find("\n", start) + 1:]
if end != -1:
    text = text[:end]

# Remove "THE END" marker
text = re.sub(r'\n\s*THE END\s*\n', '\n', text)

# Split on "Part N" headers
part_pattern = re.compile(r'^Part\s+(\d+)\s*$', re.MULTILINE)
matches = list(part_pattern.finditer(text))

print(f"Found {len(matches)} Part markers")

all_sections = []

for i, m in enumerate(matches):
    part_num = int(m.group(1))
    start_pos = m.end()
    end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
    raw_text = text[start_pos:end_pos].strip()

    # Strip notes (there are almost none in this text)
    clean, notes = strip_notes(raw_text)
    clean = " ".join(clean.split())
    full = " ".join(raw_text.split())

    if not clean:
        print(f"  Warning: Part {part_num} is empty")
        continue

    all_sections.append({
        "book": str(part_num),
        "section": "1",
        "cts_ref": f"{part_num}.1",
        "text": full,
        "text_for_embedding": clean,
        "notes": notes,
        "char_count": len(full),
    })

# Sort by part number
all_sections.sort(key=lambda s: int(s["book"]))

print(f"\nExtracted {len(all_sections)} English sections (Parts)")
# Show first and last few
for s in all_sections[:3]:
    print(f"  Part {s['book']}: {s['char_count']} chars — {s['text'][:60]}...")
print(f"  ...")
for s in all_sections[-3:]:
    print(f"  Part {s['book']}: {s['char_count']} chars — {s['text'][:60]}...")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

#!/usr/bin/env python3
"""
Extract English text from LacusCurtius HTML files for Dionysius Roman Antiquities.

48 HTML files covering Books I-XX. Section markers use:
  <A CLASS="chapter" NAME="N">N</A> for chapters
  <A CLASS="sec" NAME="N.M">M</A> for sections

We extract text between section markers, stripping footnotes, page numbers,
and editorial apparatus.

Input:  data-sources/dionysius_roman_antiquities/html/
Output: build/dionysius_ant/english_sections.json
"""

import json
import re
from pathlib import Path
from html.parser import HTMLParser

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
HTML_DIR = PROJECT_ROOT / "data-sources" / "dionysius_roman_antiquities" / "html"
OUTPUT = PROJECT_ROOT / "build" / "dionysius_ant" / "english_sections.json"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


class SectionExtractor(HTMLParser):
    """Parse LacusCurtius HTML and extract text by section."""

    def __init__(self):
        super().__init__()
        self.sections = {}  # {(book, chapter, section): text}
        self.current_book = None
        self.current_chapter = None
        self.current_section = None
        self.current_key = None
        self.text_parts = []
        self.in_endnotes = False
        self.skip_depth = 0  # for skipping footnote refs, pagenum spans

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tag_lower = tag.lower()

        # Detect endnotes section
        if tag_lower == "hr" and attrs_dict.get("class", "") == "endnotes":
            self._flush()
            self.in_endnotes = True
            return

        if self.in_endnotes:
            return

        # Skip pagenum spans
        if tag_lower == "span" and "pagenum" in attrs_dict.get("class", ""):
            self.skip_depth += 1
            return

        # Skip footnote reference links
        if tag_lower == "a" and attrs_dict.get("class", "") == "ref":
            self.skip_depth += 1
            return

        # Detect chapter marker: <A CLASS="chapter" NAME="N">
        if tag_lower == "a" and attrs_dict.get("class", "") == "chapter":
            name = attrs_dict.get("name", "")
            if name and re.match(r'^\d+$', name):
                self._flush()
                self.current_chapter = name
                self.current_section = "1"  # default
                self.current_key = (self.current_book, self.current_chapter, self.current_section)
                self.skip_depth += 1  # skip the chapter number text
                return

        # Detect section marker: <A CLASS="sec" NAME="chapter.section">
        if tag_lower == "a" and attrs_dict.get("class", "") == "sec":
            name = attrs_dict.get("name", "")
            if name and "." in name:
                parts = name.split(".")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    self._flush()
                    self.current_chapter = parts[0]
                    self.current_section = parts[1]
                    self.current_key = (self.current_book, self.current_chapter, self.current_section)
                    self.skip_depth += 1  # skip the section number text
                    return

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in ("span", "a") and self.skip_depth > 0:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.in_endnotes or self.skip_depth > 0:
            return
        if self.current_key:
            self.text_parts.append(data)

    def _flush(self):
        if self.current_key and self.text_parts:
            text = " ".join("".join(self.text_parts).split())
            if text:
                self.sections.setdefault(self.current_key, []).append(text)
        self.text_parts = []

    def finalize(self):
        self._flush()


# Map filenames to book numbers
# Format: 1A_star.html → Book 1, 10C_star.html → Book 10, 17_18_star.html → Books 17-18
def filename_to_book(fname):
    """Extract book number from filename like '1A_star.html' or '17_18_star.html'."""
    base = fname.replace("_star.html", "")
    # Handle ranges like "17_18"
    parts = base.split("_")
    num_part = parts[0]
    # Strip letter suffix (A, B, C, D)
    num = re.match(r'(\d+)', num_part)
    return int(num.group(1)) if num else 0


# Process all HTML files
all_sections = {}

for html_file in sorted(HTML_DIR.glob("*_star.html")):
    book_num = filename_to_book(html_file.name)
    if book_num == 0:
        continue

    html = html_file.read_text(encoding="utf-8", errors="replace")

    parser = SectionExtractor()
    parser.current_book = str(book_num)
    parser.feed(html)
    parser.finalize()

    for key, texts in parser.sections.items():
        full_text = " ".join(texts)
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        if full_text and len(full_text) >= 10:
            all_sections[key] = full_text

    chapter_count = len(set(k[1] for k in parser.sections if k[0] == str(book_num)))
    section_count = len(parser.sections)
    print(f"  {html_file.name}: Book {book_num}, {chapter_count} chapters, {section_count} sections")

# Build output
sections_list = []
for (book, chapter, section), text in sorted(all_sections.items(),
                                              key=lambda x: (int(x[0][0]), int(x[0][1]), int(x[0][2]))):
    sections_list.append({
        "book": book,
        "chapter": chapter,
        "section": section,
        "cts_ref": f"{book}.{chapter}.{section}",
        "text": text,
        "char_count": len(text),
    })

print(f"\nExtracted {len(sections_list)} English sections across "
      f"{len(set(s['book'] for s in sections_list))} books")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": sections_list}, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUTPUT}")

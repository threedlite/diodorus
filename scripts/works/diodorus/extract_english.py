#!/usr/bin/env python3
"""
Extract and normalise Booth's 1700 English translation from TEI XML.

Combines extraction + early-modern spelling normalisation + flattening
into standard sections format.

Input:  data-sources/booth/A36034.xml
Output: build/diodorus/english_sections.json
"""

import json
import re
from pathlib import Path
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT = PROJECT_ROOT / "data-sources" / "booth" / "A36034.xml"
OUTPUT = PROJECT_ROOT / "build" / "diodorus" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

if not INPUT.exists():
    print(f"Error: Booth TEI not found at {INPUT}")
    raise SystemExit(1)

NS = "{http://www.tei-c.org/ns/1.0}"

# --- Spelling normalisation ---
SPELLING_MAP = {
    r"\bdoth\b": "does", r"\bhath\b": "has",
    r"\bthou\b": "you", r"\bthee\b": "you",
    r"\bthy\b": "your", r"\bthine\b": "yours",
    r"\bwhereof\b": "of which", r"\bthereof\b": "of that",
    r"\bhereof\b": "of this", r"\bhereafter\b": "after this",
    r"\bwherefore\b": "therefore", r"\bwhilst\b": "while",
    r"\bamongst\b": "among", r"\btill\b": "until",
    r"\b(\w+)eth\b": r"\1es", r"\b(\w+)est\b": r"\1",
}
LETTER_SUBS = [
    (r"\u2223", ""), (r"\u3008.*?\u3009", ""),
]

# Short words that legitimately stand alone (not fragments of broken words)
_SHORT_WORDS = frozenset(
    "a an as at be by do go he if in is it me my no of oh on or so to up us we "
    "am an ar be da de di do el en er es go ha he hi ho id il in io is it la le "
    "li lo ma me mi mo mu my na ne ni no nu od of oh ok on op or os ow ox pa "
    "pi po re si so st su ta te ti to un up us ut we wo ye".split()
)


def dehyphenate(text):
    """Rejoin words broken by OCR line-break artifacts.

    The Booth 1700 EEBO/TCP text has words split across print lines where
    the hyphen was lost in digitisation, leaving e.g. 'Lacedae monians'
    (Lacedaemonians), 'se cret' (secret), 'involv d' (involved).

    Strategy: when a short fragment (1-3 lowercase chars) appears between
    two word parts AND it's not a common short English word, join it with
    its left neighbor.
    """
    def _fix(m):
        left, fragment, right_start = m.group(1), m.group(2), m.group(3)
        if fragment.lower() in _SHORT_WORDS:
            return m.group(0)  # keep as-is
        # Join fragment with left word
        return left + fragment + " " + right_start

    # Pattern: word-ending lowercase + space + 1-3 lowercase chars + space + next word
    result = re.sub(r'([a-zA-Z]{2,}) ([a-z]{1,3}) ([a-zA-Z])', _fix, text)
    return result


def normalise(text):
    t = text
    # Long-s normalisation
    t = t.replace("\u017f", "s")
    for pat, rep in LETTER_SUBS:
        t = re.sub(pat, rep, t)
    for pat, rep in SPELLING_MAP.items():
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()


def get_text(el):
    parts = []
    if el.text:
        parts.append(el.text)
    for child in el:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag == "g" and child.get("ref") == "char:EOLhyphen":
            # End-of-line hyphen — skip it to rejoin the broken word.
            # The tail (text after </g>) continues the word.
            if child.tail:
                parts.append(child.tail)
        elif tag not in ("note", "gap", "figure", "fw"):
            parts.append(get_text(child))
            if child.tail:
                parts.append(child.tail)
        elif child.tail:
            parts.append(child.tail)
    return " ".join(parts)


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def roman_to_int(s):
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    s = s.upper().strip()
    total = 0
    for i, c in enumerate(s):
        if c not in vals:
            return None
        v = vals[c]
        if i + 1 < len(s) and vals.get(s[i + 1], 0) > v:
            total -= v
        else:
            total += v
    return total


# --- Parse TEI ---
tree = etree.parse(str(INPUT))
root = tree.getroot()

group = root.find(f".//{NS}group")
if group is None:
    bodies = root.findall(f".//{NS}body")
else:
    bodies = group.findall(f"{NS}text/{NS}body")

all_sections = []
para_idx = 0

for body in bodies:
    for book_div in body.findall(f"{NS}div"):
        if book_div.get("type", "") != "book":
            continue

        head_el = book_div.find(f"{NS}head")
        head_text = clean(get_text(head_el)) if head_el is not None else ""

        book_num = None
        m = re.search(r"BOOK\s+([IVXLC]+)", head_text, re.IGNORECASE)
        if m:
            book_num = roman_to_int(m.group(1))

        book_str = str(book_num) if book_num else ""

        # Collect all chapters (may be nested under "part" divs)
        chapter_divs = []
        for sub_div in book_div.findall(f"{NS}div"):
            sub_type = sub_div.get("type", "")
            if sub_type == "chapter":
                chapter_divs.append(sub_div)
            elif sub_type == "part":
                for ch_div in sub_div.findall(f"{NS}div"):
                    if ch_div.get("type", "") == "chapter":
                        chapter_divs.append(ch_div)

        # If no chapters, extract paragraphs directly from book
        if not chapter_divs:
            chapter_divs = [book_div]

        for ch_idx, ch_div in enumerate(chapter_divs):
            # Use sequential chapter index — Booth's chapter numbers don't
            # correspond to Greek chapter numbers (different editions, different
            # divisions) so using them would create false CTS matches.
            ch_num = str(ch_idx)

            # Check for chapter heading in the TEI <head> element
            ch_head = ch_div.find(f"{NS}head")

            for p_idx, p in enumerate(ch_div.findall(f".//{NS}p")):
                raw = clean(get_text(p))
                if not raw:
                    continue
                text = normalise(raw)
                cts_ref = f"{book_str}.{ch_num}.{p_idx}"

                # Detect Booth's chapter argument/summary headings:
                # First paragraph of each chapter, short and terse.
                # These list topics ("Of X. The Y. How Z.") not narrative.
                is_heading = p_idx == 0 and len(text) < 500

                section = {
                    "book": book_str,
                    "section": f"{ch_idx}.{p_idx}",
                    "cts_ref": cts_ref,
                    "text": text,
                    "text_original": raw,
                    "char_count": len(text),
                }
                if is_heading:
                    section["is_heading"] = True
                    section["text_for_embedding"] = ""
                all_sections.append(section)

print(f"Extracted {len(all_sections)} English paragraphs")
books = sorted(set(s["book"] for s in all_sections))
for b in books:
    n = sum(1 for s in all_sections if s["book"] == b)
    print(f"  Book {b}: {n} paragraphs")

# Long-s normalisation check
long_s_count = sum(1 for s in all_sections if "\u017f" in s.get("text_original", ""))
if long_s_count:
    print(f"Long-s normalisation: {long_s_count} paragraphs had \u017f")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

#!/usr/bin/env python3
"""
Extract English sections from Walter Miller's De Officiis (Gutenberg #47001).

The Gutenberg edition is a bilingual Latin/English text. Within each book the
Latin and English alternate in chapter-sized blocks: Latin chapter I, then
English chapter I, then Latin chapter II, then English chapter II, and so on.
Section markers (``*N*``) appear exactly twice per book — once on each side.

Strategy:
  1. Strip the Gutenberg header/footer and front matter; isolate the body
     (BOOK I onward, INDEX excluded).
  2. Split into 3 books at "BOOK II" / "BOOK III" markers.
  3. For each book, find every ``*N*`` marker and classify it as Latin or
     English by inspecting the words that follow it. Latin and English have
     entirely distinct function-word vocabularies, so a small lookup of
     "et/sed/cum/quod/..." vs "the/and/of/that/..." in the next ~80 chars
     is unambiguous.
  4. Pull indented lettered/numeric footnote definitions out of the book
     text first (so they don't pollute section text), keeping a marker→body
     map. (Note bodies are not classified by language; numeric notes are
     Latin variants and lettered notes are English explanatory.)
  5. For each English ``*N*`` marker, the section text spans from this
     marker to the next ENGLISH marker (skipping the Latin block in between
     by truncating at the first Latin marker we encounter).
  6. Normalise text and attach inline footnote markers from the body.

Known Gutenberg issues handled here:
  - Book 3 section 70 Latin marker has a missing leading asterisk (``70*``
    instead of ``*70*``). This is on the Latin side and does not affect
    English extraction.
  - Book 2 section 44 chapter heading is parenthesised ("(XIII.)") on both
    sides — body content; not relevant to marker-based extraction.
  - Book 3's English chapter XXVII heading appears inline within section
    100's text rather than at the start of a line — handled because we do
    not rely on chapter headings to identify language blocks.

Input:  data-sources/gutenberg/cicero_de_officiis/pg47001.txt
Output: build/cicero_de_officiis/english_sections.json
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT = PROJECT_ROOT / "data-sources" / "gutenberg" / "cicero_de_officiis" / "pg47001.txt"
OUTPUT = PROJECT_ROOT / "build" / "cicero_de_officiis" / "english_sections.json"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

if not INPUT.exists():
    print(f"Error: {INPUT} not found")
    raise SystemExit(1)


# ---------- regexes ----------

SECTION_MARK_RE = re.compile(r"\*(\d+)\*")
# Sidenote spans #...# possibly across line breaks (re.DOTALL on `.`).
SIDENOTE_RE = re.compile(r"#[^#]*?#", re.DOTALL)
FOOTNOTE_START_RE = re.compile(r"^[ ]{4,}\[([A-Z]{1,3}|\d+)\]\s*(.*)")
INLINE_NOTE_MARKER_RE = re.compile(r"\[([A-Z]{1,3}|\d+)\]")
SUPERSCRIPT_RE = re.compile(r"\^\d+")
ITALIC_RE = re.compile(r"_([^_]+)_")
# Split paragraphs on blank lines.
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")


# ---------- load and trim ----------

text = INPUT.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")

start = text.find("*** START OF THE PROJECT GUTENBERG EBOOK")
if start != -1:
    nl = text.find("\n", start)
    text = text[nl + 1:] if nl != -1 else text[start:]

end = text.find("*** END OF THE PROJECT GUTENBERG EBOOK")
if end != -1:
    text = text[:end]

idx = text.rfind("\nINDEX\n")
if idx != -1:
    text = text[:idx]

body_start_re = re.compile(r"^BOOK I\s*$", re.MULTILINE)
m = body_start_re.search(text)
if m is None:
    raise SystemExit("Could not locate 'BOOK I' marker")
text = text[m.start():]


# ---------- split into books ----------

book_split_re = re.compile(r"^BOOK (I{1,3}|IV|V|VI{0,3})\s*$", re.MULTILINE)
ROMAN_TO_INT = {"I": 1, "II": 2, "III": 3}

book_marks = list(book_split_re.finditer(text))
if len(book_marks) < 3:
    raise SystemExit(f"Expected 3 BOOK markers, found {len(book_marks)}")

book_blocks = []
for i, mk in enumerate(book_marks):
    book_num = ROMAN_TO_INT[mk.group(1)]
    block_start = mk.end()
    block_end = book_marks[i + 1].start() if i + 1 < len(book_marks) else len(text)
    book_blocks.append((book_num, text[block_start:block_end]))


# ---------- helpers ----------

# Function words used to detect the language of text following a *N* marker.
# These are strict closed-class words that don't overlap between Latin and
# English. Each set is matched as whole words (with word boundaries).
LATIN_WORDS = {
    "et", "sed", "cum", "non", "ut", "qui", "quae", "quod", "in", "ad",
    "est", "sunt", "esse", "ab", "ex", "de", "si", "nec", "neque", "atque",
    "autem", "enim", "igitur", "tamen", "vero", "quam", "quoniam", "quidem",
    "ipse", "nam", "hoc", "haec", "ille", "ipsa", "ergo", "ita", "ille",
    "iam", "etiam",
}
ENGLISH_WORDS = {
    "the", "and", "of", "to", "is", "are", "in", "on", "that", "which",
    "but", "or", "for", "with", "as", "by", "from", "this", "he", "we",
    "they", "you", "i", "be", "have", "has", "had", "not", "no", "my",
    "his", "her", "their", "our", "if", "so", "would", "should", "will",
    "do", "does", "did", "an", "a",
}
WORD_RE = re.compile(r"\b([A-Za-z]+)\b")


def detect_language(snippet):
    """Return 'latin' or 'english' based on function-word counts in snippet."""
    lat = eng = 0
    for w in WORD_RE.findall(snippet):
        wl = w.lower()
        if wl in LATIN_WORDS:
            lat += 1
        elif wl in ENGLISH_WORDS:
            eng += 1
    if lat == 0 and eng == 0:
        return None
    return "latin" if lat > eng else "english"


def classify_markers(book_text, markers):
    """Classify each marker as Latin or English by sampling the text after it."""
    classes = []
    for i, m in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(book_text)
        snippet = book_text[m.end():min(m.end() + 200, end)]
        # Drop chapter Roman-numeral prefix if present (e.g. " I. " or " (XIII.) ")
        snippet = re.sub(r"^\s*\(?[IVXL]+\.\)?\s+", " ", snippet)
        lang = detect_language(snippet)
        if lang is None:
            # Fallback: assume same as previous (rare; only for very short snippets)
            lang = classes[-1] if classes else "latin"
        classes.append(lang)
    return classes


def pull_indented_notes(eng_text):
    """Extract indented [X]/[N] footnote blocks; return (clean_body, notes).

    ``notes`` is a dict marker→body. The clean body has those indented blocks
    removed but preserves inline body text untouched.
    """
    lines = eng_text.split("\n")
    body = []
    notes = {}

    cur_marker = None
    cur_lines = []
    in_note = False

    def flush():
        nonlocal cur_marker, cur_lines, in_note
        if cur_marker is not None:
            joined = " ".join(s.strip() for s in cur_lines if s.strip())
            if joined:
                notes.setdefault(cur_marker, joined)
        cur_marker = None
        cur_lines = []
        in_note = False

    for line in lines:
        m = FOOTNOTE_START_RE.match(line)
        if m:
            flush()
            cur_marker = m.group(1)
            rest = m.group(2)
            cur_lines = [rest] if rest else []
            in_note = True
            continue

        if in_note:
            if line.strip() == "":
                cur_lines.append("")
                continue
            if re.match(r"^[ ]{4,}", line):
                cur_lines.append(line)
                continue
            flush()
        body.append(line)

    flush()
    return "\n".join(body), notes


def keep_english_paragraphs(s):
    """Split into paragraphs and drop any whose language detects as Latin.

    Used for sections that span a chapter break: the inter-marker span
    contains the English fragment, then the entire next Latin chapter, then
    the English fragment continuing. Per-paragraph filtering keeps only
    the English parts in original order."""
    paragraphs = PARAGRAPH_SPLIT_RE.split(s)
    kept = []
    for p in paragraphs:
        if not p.strip():
            continue
        lang = detect_language(p)
        if lang == "latin":
            continue
        kept.append(p)
    return "\n\n".join(kept)


def normalise_inline(s):
    """Section ``text`` field: drop sidenotes and italic delimiters,
    preserve note markers, collapse whitespace.

    Caller must pre-filter Latin paragraphs."""
    s = SIDENOTE_RE.sub("", s)
    s = ITALIC_RE.sub(r"\1", s)
    s = " ".join(s.split())
    return s


def to_embedding_text(s):
    """Section ``text_for_embedding``: drop everything not part of the
    translation prose. Caller must pre-filter Latin paragraphs."""
    s = SIDENOTE_RE.sub("", s)
    s = ITALIC_RE.sub(r"\1", s)
    s = SECTION_MARK_RE.sub("", s)
    s = SUPERSCRIPT_RE.sub("", s)
    s = INLINE_NOTE_MARKER_RE.sub("", s)
    s = " ".join(s.split())
    return s


# ---------- per-book extraction ----------

all_sections = []
for book_num, raw_block in book_blocks:
    # First, pull all indented [X]/[N] footnote definitions out of the
    # whole book block (Latin and English notes both, but they coexist).
    cleaned_block, note_bodies = pull_indented_notes(raw_block)

    # Find every section marker, classify each by language.
    markers = list(SECTION_MARK_RE.finditer(cleaned_block))
    classes = classify_markers(cleaned_block, markers)

    # English markers only, with their original positions
    eng_marker_indices = [i for i, c in enumerate(classes) if c == "english"]

    sec_count = 0
    for j, idx in enumerate(eng_marker_indices):
        m = markers[idx]
        sec_num = m.group(1)
        text_start = m.end()
        # Section text ends at the NEXT ENGLISH marker (not the next marker
        # overall). When the section spans a chapter break, the inter-marker
        # span will contain a full Latin chapter; per-paragraph language
        # filtering downstream removes those Latin paragraphs while
        # preserving the English fragments before and after.
        if j + 1 < len(eng_marker_indices):
            text_end = markers[eng_marker_indices[j + 1]].start()
        else:
            text_end = len(cleaned_block)
        raw = cleaned_block[text_start:text_end]

        # Filter out Latin paragraphs first; then run all downstream
        # processing on the English-only span.
        eng_only = keep_english_paragraphs(raw)
        text_field = normalise_inline(eng_only)
        embed_field = to_embedding_text(eng_only)
        if not embed_field:
            continue

        markers_in_body = INLINE_NOTE_MARKER_RE.findall(eng_only)
        seen = []
        section_notes = []
        for mk in markers_in_body:
            if mk in seen:
                continue
            seen.append(mk)
            body = note_bodies.get(mk)
            if body:
                section_notes.append({"marker": f"[{mk}]", "text": body})

        all_sections.append({
            "book": str(book_num),
            "section": sec_num,
            "cts_ref": f"{book_num}.{sec_num}",
            "text": text_field,
            "text_for_embedding": embed_field,
            "notes": section_notes,
            "char_count": len(text_field),
        })
        sec_count += 1

    print(f"  Book {book_num}: {sec_count} sections, {len(note_bodies)} footnote bodies")


# Sort and report
all_sections.sort(key=lambda s: (int(s["book"]), int(s["section"])))

print(f"\nExtracted {len(all_sections)} English sections")
for book in sorted(set(s["book"] for s in all_sections), key=int):
    book_secs = [s for s in all_sections if s["book"] == book]
    nums = sorted(int(s["section"]) for s in book_secs)
    expected = list(range(1, max(nums) + 1))
    missing = sorted(set(expected) - set(nums))
    extra = sorted(set(nums) - set(expected))
    msg = f"  Book {book}: {len(book_secs)} sections, max={max(nums)}"
    if missing:
        msg += f", missing={missing}"
    if extra:
        msg += f", extra={extra}"
    print(msg)

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

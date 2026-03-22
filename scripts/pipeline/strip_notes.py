#!/usr/bin/env python3
"""
Generic footnote/note detection and stripping for Gutenberg texts.

Handles three common patterns:
  1. Indented blocks starting with [A], [B], [1], etc. (Long's Marcus)
  2. FOOTNOTES sections at end of chapters with [N] or [Footnote N: ...] blocks
  3. Inline [Sidenote: ...] markers

Returns both the clean text AND the notes separately, so notes can be
preserved in the output (e.g. in <note> tags) while being excluded from
embedding.

Usage:
    from strip_notes import strip_notes
    clean_text, notes = strip_notes(raw_text)
"""

import re


def strip_notes(raw_text):
    """Strip footnotes and editorial notes from raw Gutenberg text.

    Args:
        raw_text: the original text with line breaks preserved

    Returns:
        (clean_text, notes) where:
        - clean_text: text with all notes removed (translation content only)
        - notes: list of {"marker": "[A]", "text": "..."} dicts
    """
    lines = raw_text.split("\n")
    clean_lines = []
    notes = []
    in_footnote_section = False
    in_indented_note = False
    current_note_marker = None
    current_note_lines = []

    for line in lines:
        stripped = line.strip()

        # Detect FOOTNOTES section header
        if stripped in ("FOOTNOTES", "FOOTNOTES:", "NOTES", "NOTES:"):
            in_footnote_section = True
            _flush_note(current_note_marker, current_note_lines, notes)
            current_note_marker = None
            current_note_lines = []
            continue

        # Inside a FOOTNOTES section — everything is a note
        if in_footnote_section:
            # [Footnote N: text] format
            m = re.match(r'\[Footnote\s+(\d+):\s*(.*)', stripped)
            if m:
                _flush_note(current_note_marker, current_note_lines, notes)
                current_note_marker = f"[{m.group(1)}]"
                rest = m.group(2)
                # Check for single-line [Footnote N: text]
                if rest.endswith("]"):
                    notes.append({"marker": current_note_marker, "text": rest[:-1].strip()})
                    current_note_marker = None
                    current_note_lines = []
                else:
                    current_note_lines = [rest]
                continue

            # [N] format (Procopius/Plotinus style)
            m = re.match(r'^\[(\d+)\]\s*$', stripped)
            if m:
                _flush_note(current_note_marker, current_note_lines, notes)
                current_note_marker = f"[{m.group(1)}]"
                current_note_lines = []
                continue

            # Continuation of current note or start of note text
            if current_note_marker:
                if stripped.endswith("]") and stripped.startswith("["):
                    # Close of multi-line [Footnote] block
                    current_note_lines.append(stripped[:-1])
                    _flush_note(current_note_marker, current_note_lines, notes)
                    current_note_marker = None
                    current_note_lines = []
                else:
                    current_note_lines.append(stripped)
                continue

            # Blank line or unattached text in footnote section — skip
            continue

        # Not in footnote section — check for inline notes

        # Indented note blocks: 4+ spaces followed by [A], [B], [1], etc.
        if re.match(r'^    \[([A-Za-z]|\d+)\]', line):
            _flush_note(current_note_marker, current_note_lines, notes)
            m = re.match(r'^    \[([A-Za-z]|\d+)\]\s*(.*)', line)
            current_note_marker = f"[{m.group(1)}]"
            current_note_lines = [m.group(2)] if m.group(2) else []
            in_indented_note = True
            continue

        # Continuation of indented note (4+ spaces, not a new marker)
        if in_indented_note:
            if line.startswith("    ") and stripped:
                current_note_lines.append(stripped)
                continue
            elif stripped == "":
                # Blank line might end the note or be between notes
                continue
            else:
                # Non-indented line ends the note block
                _flush_note(current_note_marker, current_note_lines, notes)
                current_note_marker = None
                current_note_lines = []
                in_indented_note = False

        # [Sidenote: ...] inline markers
        line = re.sub(r'\[Sidenote:[^\]]*\]', '', line)

        clean_lines.append(line)

    # Flush any remaining note
    _flush_note(current_note_marker, current_note_lines, notes)

    clean_text = "\n".join(clean_lines)

    # Also strip footnote reference markers from the clean text: [A], [1], etc.
    # But preserve editorial brackets like [I learned] that are part of translation
    clean_text = re.sub(r'\[([A-Z])\]', '', clean_text)  # [A], [B], etc.
    clean_text = re.sub(r'\[(\d+)\]', '', clean_text)     # [1], [2], etc.

    return clean_text, notes


def _flush_note(marker, lines, notes_list):
    """Save accumulated note lines to notes list."""
    if marker and lines:
        text = " ".join(l.strip() for l in lines if l.strip())
        if text:
            notes_list.append({"marker": marker, "text": text})


def strip_notes_from_sections(sections):
    """Strip notes from a list of section dicts.

    For each section, adds:
    - text_for_embedding: cleaned text without footnotes
    - notes: list of extracted notes

    The original 'text' field is NEVER modified.
    If the extraction script already set text_for_embedding and notes,
    those are preserved.
    """
    for s in sections:
        if "text_for_embedding" not in s:
            clean, notes = strip_notes(s["text"])
            clean = " ".join(clean.split())
            s["text_for_embedding"] = clean
            s["notes"] = notes
        elif "notes" not in s:
            _, notes = strip_notes(s["text"])
            s["notes"] = notes

    return sections

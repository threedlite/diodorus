#!/usr/bin/env python3
"""
Extract English character sketches from Bennett & Hammond's Theophrastus (Gutenberg #58242).

The translation reorders the 30 characters from the 1897 Leipziger edition,
which uses a different numbering than the Diels 1909 edition used by Perseus.
We match each English character to its Greek chapter by comparing the Greek
term given in parentheses below each English title (e.g. "(Εἰρωνεία)") to
the chapter headings in the Perseus XML.

The Epistle Dedicatory maps to Greek chapter 0 (Proem).

Input:  data-sources/gutenberg/theophrastus/pg58242.txt
Output: build/theophrastus/english_sections.json
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INPUT = PROJECT_ROOT / "data-sources" / "gutenberg" / "theophrastus" / "pg58242.txt"
OUTPUT = PROJECT_ROOT / "build" / "theophrastus" / "english_sections.json"

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

# Mapping from Greek term root (as it appears in the English text) to
# the Perseus/Diels chapter number. The English text gives the nominative
# form while the Greek XML has the genitive; we normalize to match.
# Built by matching each English sketch's Greek term to the XML headings.
GREEK_TERM_TO_CHAPTER = {
    "Εἰρωνεία": 1,        # εἰρωνείας
    "Κολακεία": 2,        # κολακείας
    "Ἀδολεσχία": 3,       # ἀδολεσχίας
    "Ἀγροικία": 4,        # ἀγροικίας
    "Ἀρέσκεια": 5,        # Ἀρεσκειάς
    "Ἀπόνοια": 6,         # Ἀπονοιάς
    "Λαλία": 7,           # Λαλιάς (may appear as Δαλία due to OCR)
    "Δαλία": 7,           # OCR variant
    "Λογοποιία": 8,       # λογοποιίας
    "Λογοπολιία": 8,      # OCR variant (ι→λ)
    "Ἀναισχυντία": 9,     # ἀναισχυντίας
    "Μικρολογία": 10,     # μικρολογίας
    "Βδελυρία": 11,       # βδελυρίας
    "Ἀκαιρία": 12,        # ἀκαιρίας
    "Περιεργία": 13,      # περιεργίας
    "Ἀναισθησία": 14,     # ἀναισθησίας
    "Αὐθάδεια": 15,       # αὐθαδείας
    "Δεισιδαιμονία": 16,  # δεισιδαιμονίας
    "Μεμψιμοιρία": 17,    # μεμψιμοιρίας
    "Ἀπιστία": 18,        # ἀπιστίας
    "Δυσχέρεια": 19,      # Δυσχέρειας
    "Ἀηδία": 20,          # ἀηδίας
    "Μικροφιλοτιμία": 21, # Μικροφιλοτιμίας
    "Ἀνελευθερία": 22,    # ἀνελευθερίας
    "Ἀλαζονεία": 23,      # ἀλαζονείας
    "Ὑπερηφανία": 24,     # ὑπερηφανίας
    "Δειλία": 25,         # δειλίας
    "Ὀλιγαρχία": 26,      # ὀλιγαρχίας
    "Ὀψιμαθία": 27,       # Ὀψιμαθίας
    "Κακολογία": 28,       # κακολογίας
    "Φιλοπονηρία": 29,    # Φιλοπονηρίας
    "Αἰσχροκέρδεια": 30,  # Αἰσχροκερδειάς
}

# Find the Epistle Dedicatory (maps to Greek chapter 0 = Proem)
epistle_match = re.search(r'\n_Epistle Dedicatory_\s*\n', text)
first_char_match = re.search(r'\nI _The Dissembler_\s*\n', text)

all_sections = []

if epistle_match and first_char_match:
    epistle_text = text[epistle_match.end():first_char_match.start()].strip()
    # Remove the "THEOPHRASTUS TO POLYCLES:" salutation line
    epistle_text = re.sub(r'^THEOPHRASTUS TO POLYCLES:\s*', '', epistle_text)
    clean, notes = strip_notes(epistle_text)
    clean = " ".join(clean.split())
    full = " ".join(epistle_text.split())

    if clean:
        all_sections.append({
            "book": "0",
            "section": "1",
            "cts_ref": "0.1",
            "text": full,
            "text_for_embedding": clean,
            "notes": notes,
            "char_count": len(full),
        })
        print(f"  Epistle Dedicatory (chapter 0): {len(full)} chars")

# Find all character sketch boundaries
# Pattern: Roman numeral followed by _Title_ on its own line
char_pattern = re.compile(r'^([IVXL]+)\s+_(.+?)_\s*$', re.MULTILINE)
char_matches = list(char_pattern.finditer(text))

print(f"Found {len(char_matches)} character sketches")

for i, m in enumerate(char_matches):
    bennett_roman = m.group(1)
    title = m.group(2)

    # Extract text from after the title line to the next character
    start_pos = m.end()
    end_pos = char_matches[i + 1].start() if i + 1 < len(char_matches) else len(text)
    raw_text = text[start_pos:end_pos].strip()

    # Extract the Greek term from the first line (e.g. "(Εἰρωνεία)")
    greek_term_match = re.match(r'\s*\(([^\)]*[\u0370-\u03FF\u1F00-\u1FFF][^\)]*)\)', raw_text)
    if not greek_term_match:
        print(f"  Warning: no Greek term found for {bennett_roman} {title}")
        continue

    greek_term = greek_term_match.group(1).strip()
    greek_chapter = GREEK_TERM_TO_CHAPTER.get(greek_term)
    if greek_chapter is None:
        print(f"  Warning: unrecognized Greek term '{greek_term}' for {bennett_roman} {title}")
        continue

    # Remove the Greek term line
    raw_text = raw_text[greek_term_match.end():].strip()

    # Strip notes
    clean, notes = strip_notes(raw_text)
    clean = " ".join(clean.split())
    full = " ".join(raw_text.split())

    if not clean:
        continue

    all_sections.append({
        "book": str(greek_chapter),
        "section": "1",
        "cts_ref": f"{greek_chapter}.1",
        "text": full,
        "text_for_embedding": clean,
        "notes": notes,
        "char_count": len(full),
        "heading_text": title,
    })
    print(f"  {bennett_roman} '{title}' ({greek_term}) → chapter {greek_chapter}")

# Sort by Greek chapter number
all_sections.sort(key=lambda s: int(s["book"]))

# Verify we got all 31 sections (0 + 1-30)
chapters_found = sorted(int(s["book"]) for s in all_sections)
expected = list(range(31))
if chapters_found != expected:
    missing = set(expected) - set(chapters_found)
    extra = set(chapters_found) - set(expected)
    if missing:
        print(f"\n  WARNING: missing chapters: {sorted(missing)}")
    if extra:
        print(f"\n  WARNING: unexpected chapters: {sorted(extra)}")

print(f"\nExtracted {len(all_sections)} English sections (chapters 0-30)")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"sections": all_sections}, f, ensure_ascii=False, indent=2)

print(f"Saved: {OUTPUT}")

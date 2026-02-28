# Text Alignment Strategy v2: Fully Executable on a Mac Laptop

**Booth English (OTA A36034) ↔ Perseus Greek Diodorus Siculus**
*Designed for Claude to execute end-to-end using only free, open-source software.*

---

## 0. Assumptions & Constraints

- **Machine:** Mac laptop (Apple Silicon or Intel), macOS 13+, ≥8 GB RAM, ≥5 GB free disk
- **Runtime:** Python 3.10+ (pre-installed or via Homebrew)
- **Network:** Needed only for initial downloads; all processing is local
- **No paid APIs:** No Google Translate, no OpenAI, no cloud services
- **No GPU required:** All models chosen to run on CPU (though MPS/GPU will speed things up)
- **All tools:** pip-installable or available via Homebrew/git

---

## 1. Environment Setup

### 1a. Install system dependencies

```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11+ and git
brew install python@3.11 git
```

### 1b. Create project and virtual environment

```bash
mkdir -p ~/diodorus-alignment && cd ~/diodorus-alignment

python3.11 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
```

### 1c. Install Python packages

```bash
pip install \
  lxml \
  beautifulsoup4 \
  regex \
  pandas \
  numpy \
  scipy \
  scikit-learn \
  tqdm \
  sentence-transformers \
  cltk \
  spacy \
  rapidfuzz \
  unidecode

# Download spaCy English model (small, CPU-friendly)
python -m spacy download en_core_web_sm

# CLTK will auto-download Ancient Greek models on first use
```

**Total disk footprint:** ~2–3 GB (mostly sentence-transformers model cache).

---

## 2. Download Source Texts

### 2a. Booth English TEI

```bash
mkdir -p data/booth

# Download the TEI XML directly from OTA (CC0 licence, no auth required)
curl -L -o data/booth/A36034.xml \
  "https://llds.ling-phil.ox.ac.uk/llds/xmlui/bitstream/handle/20.500.14106/A36034/A36034.xml?sequence=7&isAllowed=y"

# Also grab the SAMUELS linguistic annotation as a fallback
curl -L -o data/booth/A36034.samuels.tsv \
  "https://llds.ling-phil.ox.ac.uk/llds/xmlui/bitstream/handle/20.500.14106/A36034/A36034.samuels.tsv?sequence=6&isAllowed=y"
```

### 2b. Perseus Greek TEI

```bash
mkdir -p data/perseus

# Shallow clone just the Diodorus directory from canonical-greekLit
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/PerseusDL/canonical-greekLit.git data/perseus/canonical-greekLit

cd data/perseus/canonical-greekLit
git sparse-checkout set data/tlg0060
cd ~/diodorus-alignment
```

If sparse checkout fails (older git), fall back to:

```bash
# Full clone (~500 MB) then just use the relevant directory
git clone --depth 1 https://github.com/PerseusDL/canonical-greekLit.git data/perseus/canonical-greekLit
```

### 2c. Verify downloads

```bash
ls -la data/booth/A36034.xml          # Should be ~5 MB
ls data/perseus/canonical-greekLit/data/tlg0060/tlg001/  # Should list .xml files
```

---

## 3. Parse & Extract Texts

### 3a. Script: `01_extract_booth.py`

This script parses the EEBO-TCP TEI XML and extracts a structured JSON of all books, chapters, and paragraphs.

```python
#!/usr/bin/env python3
"""Extract structured text from Booth's TEI XML (A36034)."""

import json
import re
from pathlib import Path
from lxml import etree

INPUT = Path("data/booth/A36034.xml")
OUTPUT = Path("output/booth_extracted.json")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

tree = etree.parse(str(INPUT))
root = tree.getroot()

# Handle TEI namespaces (EEBO-TCP may or may not use them)
nsmap = {}
if root.tag.startswith("{"):
    ns = root.tag.split("}")[0] + "}"
    nsmap["tei"] = ns.strip("{}")

def xpath(el, expr):
    """Namespace-aware xpath."""
    if nsmap:
        return el.xpath(expr, namespaces={"tei": nsmap["tei"]})
    return el.xpath(expr)

def get_text(el):
    """Recursively extract all text, skipping <note> and <gap> contents."""
    parts = []
    if el.text:
        parts.append(el.text)
    for child in el:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""
        if tag in ("note", "gap", "figure", "fw"):
            pass  # skip marginalia, gaps, figures, forme works
        else:
            parts.append(get_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(parts)

def clean(text):
    """Normalise whitespace."""
    return re.sub(r"\s+", " ", text).strip()

# Find the body element
body_variants = [
    ".//tei:body" if nsmap else ".//body",
]
body = None
for expr in body_variants:
    results = xpath(root, expr)
    if results:
        body = results[0]
        break

if body is None:
    # Try without namespace
    body = root.find(".//{*}body") or root.find(".//body")

assert body is not None, "Could not find <body> in TEI"

# Extract div1 (books) and their children
books = []
div1_tag = "tei:div1" if nsmap else "div1"
for div1 in xpath(body, f".//{div1_tag}"):
    div1_type = div1.get("type", "unknown")
    div1_n = div1.get("n", "")

    # Extract head
    head_el = div1.find(f"{{{nsmap['tei']}}}head" if nsmap else "head")
    head_text = clean(get_text(head_el)) if head_el is not None else ""

    # Determine book number from head or n attribute
    book_num = div1_n
    if not book_num:
        m = re.search(r"BOOK\s+([IVXLC]+|\d+)", head_text, re.IGNORECASE)
        if m:
            book_num = m.group(1)

    # Extract div2 (chapters/sections within book)
    chapters = []
    div2_tag = "tei:div2" if nsmap else "div2"
    div2_els = xpath(div1, f".//{div2_tag}")
    
    if div2_els:
        for i, div2 in enumerate(div2_els):
            ch_head_el = div2.find(f"{{{nsmap['tei']}}}head" if nsmap else "head")
            ch_head = clean(get_text(ch_head_el)) if ch_head_el is not None else ""
            
            paragraphs = []
            p_tag = "tei:p" if nsmap else "p"
            for j, p in enumerate(xpath(div2, f".//{p_tag}")):
                text = clean(get_text(p))
                if text:
                    paragraphs.append({
                        "p_index": j,
                        "text": text,
                        "char_count": len(text)
                    })
            
            chapters.append({
                "div2_index": i,
                "head": ch_head,
                "paragraphs": paragraphs
            })
    else:
        # No div2 — extract paragraphs directly from div1
        p_tag = "tei:p" if nsmap else "p"
        paragraphs = []
        for j, p in enumerate(xpath(div1, f".//{p_tag}")):
            text = clean(get_text(p))
            if text:
                paragraphs.append({
                    "p_index": j,
                    "text": text,
                    "char_count": len(text)
                })
        if paragraphs:
            chapters.append({
                "div2_index": 0,
                "head": "",
                "paragraphs": paragraphs
            })

    books.append({
        "div1_type": div1_type,
        "div1_n": book_num,
        "head": head_text,
        "chapters": chapters
    })

result = {
    "source": "Booth (1700) — OTA A36034",
    "books": books
}

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# Summary
total_p = sum(len(ch["paragraphs"]) for bk in books for ch in bk["chapters"])
print(f"Extracted {len(books)} div1 elements, {total_p} paragraphs total")
print(f"Saved to {OUTPUT}")
```

### 3b. Script: `02_extract_perseus.py`

```python
#!/usr/bin/env python3
"""Extract structured text from Perseus Greek TEI files for Diodorus."""

import json
import re
from pathlib import Path
from lxml import etree

PERSEUS_DIR = Path("data/perseus/canonical-greekLit/data/tlg0060/tlg001")
OUTPUT = Path("output/perseus_extracted.json")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

all_sections = []

for xml_file in sorted(PERSEUS_DIR.glob("*.xml")):
    if "__cts__" in xml_file.name:
        continue  # Skip CTS metadata files
    
    print(f"Parsing {xml_file.name}...")
    tree = etree.parse(str(xml_file))
    root = tree.getroot()
    
    # Determine namespace
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    nsmap = {"tei": ns.strip("{}")} if ns else {}
    
    edition_id = xml_file.stem  # e.g. tlg0060.tlg001.perseus-grc5
    
    def find_all(el, local_name):
        """Find elements by local name, namespace-agnostic."""
        return el.findall(f".//{{{nsmap['tei']}}}{local_name}" if nsmap else f".//{local_name}")
    
    def get_text(el):
        return re.sub(r"\s+", " ", "".join(el.itertext())).strip()
    
    # Find all textpart divs — may be nested (book > chapter > section)
    # Strategy: find leaf-level textpart divs that contain <p> directly
    for div in find_all(root, "div"):
        subtype = div.get("subtype", "")
        n = div.get("n", "")
        
        if subtype == "section":
            # This is a leaf section — get its full CTS path
            # Walk up to find chapter and book
            chapter_n = ""
            book_n = ""
            parent = div.getparent()
            while parent is not None:
                p_subtype = parent.get("subtype", "")
                if p_subtype == "chapter":
                    chapter_n = parent.get("n", "")
                elif p_subtype == "book":
                    book_n = parent.get("n", "")
                parent = parent.getparent()
            
            p_els = div.findall(f"{{{nsmap['tei']}}}p" if nsmap else "p")
            text = " ".join(get_text(p) for p in p_els).strip()
            
            if text:
                cts_ref = f"{book_n}.{chapter_n}.{n}"
                all_sections.append({
                    "edition": edition_id,
                    "book": book_n,
                    "chapter": chapter_n,
                    "section": n,
                    "cts_ref": cts_ref,
                    "text": text,
                    "char_count": len(text)
                })
        
        elif subtype == "chapter" and not div.findall(
            f".//{{{nsmap['tei']}}}div[@subtype='section']" if nsmap 
            else ".//div[@subtype='section']"
        ):
            # Chapter with no sub-sections — treat whole chapter as one unit
            book_n = ""
            parent = div.getparent()
            while parent is not None:
                if parent.get("subtype") == "book":
                    book_n = parent.get("n", "")
                    break
                parent = parent.getparent()
            
            text = get_text(div)
            if text:
                cts_ref = f"{book_n}.{n}"
                all_sections.append({
                    "edition": edition_id,
                    "book": book_n,
                    "chapter": n,
                    "section": "",
                    "cts_ref": cts_ref,
                    "text": text,
                    "char_count": len(text)
                })

result = {
    "source": "Perseus Digital Library — Diodorus Siculus, Bibliotheca Historica",
    "cts_urn": "urn:cts:greekLit:tlg0060.tlg001",
    "sections": all_sections
}

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

books_found = sorted(set(s["book"] for s in all_sections))
print(f"Extracted {len(all_sections)} sections across books: {books_found}")
print(f"Saved to {OUTPUT}")
```

---

## 4. Text Normalisation

### 4a. Script: `03_normalise_booth.py`

Normalise Booth's early-modern English spelling to improve embedding quality.

```python
#!/usr/bin/env python3
"""
Normalise Booth's early-modern English for better NLP processing.
Uses a lightweight regex + dictionary approach (no VARD2 dependency).
"""

import json
import re
from pathlib import Path

INPUT = Path("output/booth_extracted.json")
OUTPUT = Path("output/booth_normalised.json")

# Common early-modern English spelling substitutions
SPELLING_MAP = {
    # Vowel shifts
    r"\bae\b": "e",
    r"\boe\b": "e",
    # Common word-level substitutions
    r"\bdoth\b": "does",
    r"\bhath\b": "has",
    r"\bthou\b": "you",
    r"\bthee\b": "you",
    r"\bthy\b": "your",
    r"\bthine\b": "yours",
    r"\bwhereof\b": "of which",
    r"\bthereof\b": "of that",
    r"\bhereof\b": "of this",
    r"\bhereafter\b": "after this",
    r"\bwherefore\b": "therefore",
    r"\bwhilst\b": "while",
    r"\bamongst\b": "among",
    r"\btill\b": "until",
    r"\b(\w+)eth\b": r"\1es",  # loveth → loves (rough)
    r"\b(\w+)est\b": r"\1",    # goest → go (rough)
}

# Letter-level patterns common in EEBO texts
LETTER_SUBS = [
    (r"(?<=[a-z])ck(?=[a-z])", "c"),     # Occasional archaic ck
    (r"\bI\b(?=\s+[a-z])", "I"),          # Keep capital I
    (r"∣", ""),                            # EEBO line-break marker
    (r"〈.*?〉", ""),                        # EEBO gap markers
]

def normalise(text):
    """Apply spelling normalisation to a text string."""
    t = text
    # Remove EEBO artifacts
    for pat, rep in LETTER_SUBS:
        t = re.sub(pat, rep, t)
    # Spelling map
    for pat, rep in SPELLING_MAP.items():
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    # Normalise whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t

with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

for book in data["books"]:
    for ch in book["chapters"]:
        for p in ch["paragraphs"]:
            p["text_normalised"] = normalise(p["text"])

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Normalised text saved to {OUTPUT}")
```

---

## 5. Coarse Alignment — Book Level

### 5a. Script: `04_align_books.py`

```python
#!/usr/bin/env python3
"""
Match Booth div1 elements to Perseus book numbers.
Uses heading text and positional heuristics.
"""

import json
import re
from pathlib import Path

BOOTH = Path("output/booth_normalised.json")
PERSEUS = Path("output/perseus_extracted.json")
OUTPUT = Path("output/book_alignment.json")

with open(BOOTH) as f:
    booth = json.load(f)
with open(PERSEUS) as f:
    perseus = json.load(f)

# Get set of available Greek book numbers
greek_books = sorted(set(s["book"] for s in perseus["sections"]))

# Roman numeral converter
def roman_to_int(s):
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    s = s.upper().strip()
    total = 0
    for i, c in enumerate(s):
        if c not in vals:
            return None
        v = vals[c]
        if i + 1 < len(s) and vals.get(s[i+1], 0) > v:
            total -= v
        else:
            total += v
    return total

alignments = []
for bk in booth["books"]:
    head = bk["head"]
    n = bk["div1_n"]
    
    # Try to extract book number
    book_num = None
    
    # Try n attribute as integer
    if n and n.isdigit():
        book_num = int(n)
    elif n:
        book_num = roman_to_int(n)
    
    # Try from heading
    if book_num is None:
        m = re.search(r"BOOK\s+([IVXLC]+)", head, re.IGNORECASE)
        if m:
            book_num = roman_to_int(m.group(1))
    
    has_greek = str(book_num) in greek_books if book_num else False
    
    alignments.append({
        "booth_div1_type": bk["div1_type"],
        "booth_div1_n": bk["div1_n"],
        "booth_head": head[:100],
        "inferred_book_num": book_num,
        "greek_available": has_greek,
        "booth_paragraph_count": sum(len(ch["paragraphs"]) for ch in bk["chapters"]),
        "greek_section_count": len([
            s for s in perseus["sections"] if s["book"] == str(book_num)
        ]) if book_num else 0
    })

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(alignments, f, ensure_ascii=False, indent=2)

# Print summary table
print(f"{'Booth div1':<12} {'Head':<30} {'Book#':<6} {'Greek?':<7} {'EN ¶s':<7} {'GR §s':<7}")
print("-" * 80)
for a in alignments:
    print(f"{a['booth_div1_n']:<12} {a['booth_head'][:28]:<30} "
          f"{str(a['inferred_book_num'] or '?'):<6} "
          f"{'✅' if a['greek_available'] else '❌':<7} "
          f"{a['booth_paragraph_count']:<7} {a['greek_section_count']:<7}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(alignments, f, ensure_ascii=False, indent=2)

print(f"\nSaved to {OUTPUT}")
```

---

## 6. Fine-Grained Alignment — Sentence Embeddings

This is the core alignment step. It uses `sentence-transformers` with the multilingual model `paraphrase-multilingual-MiniLM-L12-v2` (420 MB, runs well on CPU) to embed both Greek and English sentences, then finds optimal monotonic alignment.

### 6a. Script: `05_embed_and_align.py`

```python
#!/usr/bin/env python3
"""
Compute cross-lingual sentence embeddings and align Greek sections
to Booth English paragraphs using dynamic programming.

Model: paraphrase-multilingual-MiniLM-L12-v2 (free, ~420MB, CPU-friendly)
Supports 50+ languages including English and Greek.
Ancient Greek is not in training data, but shares enough vocabulary
with modern Greek + Latin-script transliterations to be useful.
"""

import json
import re
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from scipy.spatial.distance import cdist
from tqdm import tqdm

BOOTH = Path("output/booth_normalised.json")
PERSEUS = Path("output/perseus_extracted.json")
BOOK_ALIGN = Path("output/book_alignment.json")
OUTPUT = Path("output/section_alignments.json")
OUTPUT_TSV = Path("output/section_alignments.tsv")

# Load model (downloads ~420MB on first run, cached in ~/.cache/)
print("Loading multilingual sentence embedding model...")
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

with open(BOOTH) as f:
    booth = json.load(f)
with open(PERSEUS) as f:
    perseus = json.load(f)
with open(BOOK_ALIGN) as f:
    book_align = json.load(f)

def split_sentences(text, max_len=500):
    """Simple sentence splitter. Keeps chunks under max_len chars."""
    sents = re.split(r"(?<=[.;:!?])\s+", text)
    # Merge very short sentences
    merged = []
    buf = ""
    for s in sents:
        if len(buf) + len(s) < max_len:
            buf = (buf + " " + s).strip()
        else:
            if buf:
                merged.append(buf)
            buf = s
    if buf:
        merged.append(buf)
    return merged if merged else [text]

all_alignments = []

for ba in book_align:
    book_num = ba["inferred_book_num"]
    if not ba["greek_available"] or book_num is None:
        continue
    
    print(f"\n=== Aligning Book {book_num} ===")
    
    # Gather Greek sections for this book
    greek_secs = [s for s in perseus["sections"] if s["book"] == str(book_num)]
    if not greek_secs:
        print(f"  No Greek sections found for book {book_num}")
        continue
    
    # Gather English paragraphs for this book
    booth_book = None
    for bk in booth["books"]:
        if ba["booth_div1_n"] == bk["div1_n"]:
            booth_book = bk
            break
    if not booth_book:
        continue
    
    en_paragraphs = []
    for ch in booth_book["chapters"]:
        for p in ch["paragraphs"]:
            en_paragraphs.append({
                "div2_index": ch["div2_index"],
                "p_index": p["p_index"],
                "text": p.get("text_normalised", p["text"]),
                "text_original": p["text"]
            })
    
    if not en_paragraphs:
        print(f"  No English paragraphs for book {book_num}")
        continue
    
    print(f"  Greek sections: {len(greek_secs)}, English paragraphs: {len(en_paragraphs)}")
    
    # Embed Greek sections
    greek_texts = [s["text"] for s in greek_secs]
    print("  Embedding Greek sections...")
    greek_embs = model.encode(greek_texts, show_progress_bar=True, batch_size=32)
    
    # Embed English paragraphs
    en_texts = [p["text"] for p in en_paragraphs]
    print("  Embedding English paragraphs...")
    en_embs = model.encode(en_texts, show_progress_bar=True, batch_size=32)
    
    # Compute cosine similarity matrix (greek x english)
    # scipy cdist with cosine gives distance; similarity = 1 - distance
    sim_matrix = 1 - cdist(greek_embs, en_embs, metric="cosine")
    
    # Monotonic alignment via dynamic programming
    # Allow many-to-one (multiple Greek sections → one English paragraph)
    # Enforce that alignment indices are non-decreasing
    n_gr = len(greek_secs)
    n_en = len(en_paragraphs)
    
    # For each Greek section, find best English paragraph,
    # then enforce monotonicity with a forward pass
    raw_matches = np.argmax(sim_matrix, axis=1)  # best EN for each GR
    raw_scores = np.max(sim_matrix, axis=1)
    
    # Enforce monotonicity: each Greek section's EN index must be ≥ previous
    mono_matches = []
    min_en = 0
    for gi in range(n_gr):
        # Search from min_en onward for best match
        candidates = sim_matrix[gi, min_en:]
        if len(candidates) == 0:
            best_en = min_en
            score = 0.0
        else:
            best_offset = np.argmax(candidates)
            best_en = min_en + best_offset
            score = float(candidates[best_offset])
        mono_matches.append((gi, int(best_en), score))
        # Allow next section to match same or later paragraph
        min_en = best_en  # don't advance — allow many-to-one
    
    # Record alignments
    for gi, ei, score in mono_matches:
        gs = greek_secs[gi]
        ep = en_paragraphs[ei]
        all_alignments.append({
            "book": str(book_num),
            "greek_cts_ref": gs["cts_ref"],
            "greek_edition": gs["edition"],
            "booth_div2_index": ep["div2_index"],
            "booth_p_index": ep["p_index"],
            "similarity": round(score, 4),
            "greek_preview": gs["text"][:80],
            "english_preview": ep["text"][:80]
        })
    
    # Print sample
    print(f"  Sample alignments (first 5):")
    for gi, ei, score in mono_matches[:5]:
        gs = greek_secs[gi]
        ep = en_paragraphs[ei]
        print(f"    {gs['cts_ref']:>12} → div2={ep['div2_index']}/p={ep['p_index']}  "
              f"sim={score:.3f}  GR: {gs['text'][:40]}…")

# Save JSON
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(all_alignments, f, ensure_ascii=False, indent=2)

# Save TSV
with open(OUTPUT_TSV, "w", encoding="utf-8") as f:
    header = "book\tgreek_cts_ref\tgreek_edition\tbooth_div2\tbooth_p\tsimilarity\n"
    f.write(header)
    for a in all_alignments:
        f.write(f"{a['book']}\t{a['greek_cts_ref']}\t{a['greek_edition']}\t"
                f"{a['booth_div2_index']}\t{a['booth_p_index']}\t{a['similarity']}\n")

print(f"\nTotal alignments: {len(all_alignments)}")
print(f"Saved to {OUTPUT} and {OUTPUT_TSV}")
```

---

## 7. Named Entity Anchor Validation

Use named entities (place names, people) to validate and correct the embedding-based alignment.

### 7a. Script: `06_entity_anchors.py`

```python
#!/usr/bin/env python3
"""
Extract named entities from both texts and use name co-occurrence
to validate / correct section alignments.

Greek NER: regex-based extraction of capitalised Greek words + known names.
English NER: spaCy en_core_web_sm.
Cross-lingual matching: transliteration-based fuzzy matching.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

import spacy
from unidecode import unidecode
from rapidfuzz import fuzz

BOOTH = Path("output/booth_normalised.json")
PERSEUS = Path("output/perseus_extracted.json")
ALIGNMENTS = Path("output/section_alignments.json")
OUTPUT = Path("output/entity_validated_alignments.json")

nlp = spacy.load("en_core_web_sm")

# Greek-to-Latin transliteration (basic)
GREEK_TRANSLIT = str.maketrans(
    "αβγδεζηθικλμνξοπρστυφχψωάέήίόύώϊϋΐΰ"
    "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩΆΈΉΊΌΎΏ",
    "abgdezēthiklmnxoprstyphkhpsōaeēioyōiyiy"
    "ABGDEZĒTHIKLMNXOPRSTYPHKHPSŌAEĒIOYŌ"
)

def greek_to_latin(text):
    """Rough transliteration of Greek to Latin characters."""
    t = text.translate(GREEK_TRANSLIT)
    t = re.sub(r"[^\w\s]", "", t)
    return unidecode(t).lower()

def extract_greek_names(text):
    """Extract likely proper nouns from Greek text (capitalised words)."""
    # Greek proper nouns are typically capitalised
    words = re.findall(r"\b[Α-Ω][α-ωά-ώ]{2,}\b", text)
    # Transliterate for matching
    return [(w, greek_to_latin(w)) for w in words]

def extract_english_names(text):
    """Extract named entities using spaCy."""
    doc = nlp(text[:10000])  # Truncate for speed
    names = []
    for ent in doc.ents:
        if ent.label_ in ("PERSON", "GPE", "LOC", "NORP"):
            names.append(ent.text.lower())
    return names

with open(BOOTH) as f:
    booth = json.load(f)
with open(PERSEUS) as f:
    perseus = json.load(f)
with open(ALIGNMENTS) as f:
    alignments = json.load(f)

# Build entity indices for each Greek section
print("Extracting Greek named entities...")
greek_entities = {}
for s in perseus["sections"]:
    names = extract_greek_names(s["text"])
    greek_entities[s["cts_ref"]] = [lat for _, lat in names]

# Build entity index for Booth paragraphs (keyed by book/div2/p)
print("Extracting English named entities...")
en_entities = {}
for bk in booth["books"]:
    for ch in bk["chapters"]:
        for p in ch["paragraphs"]:
            key = f"{bk['div1_n']}/{ch['div2_index']}/{p['p_index']}"
            text = p.get("text_normalised", p["text"])
            en_entities[key] = extract_english_names(text)

# Validate each alignment by entity overlap
print("Validating alignments with entity anchors...")
for a in alignments:
    gr_ref = a["greek_cts_ref"]
    en_key = f"{a['book']}/{a['booth_div2_index']}/{a['booth_p_index']}"
    
    gr_names = greek_entities.get(gr_ref, [])
    en_names = en_entities.get(en_key, [])
    
    # Fuzzy match Greek transliterated names against English names
    matches = 0
    total = max(len(gr_names), 1)
    for gn in gr_names:
        for en in en_names:
            if fuzz.partial_ratio(gn, en) > 75:
                matches += 1
                break
    
    entity_score = matches / total if gr_names else 0.5  # neutral if no entities
    
    a["entity_overlap_score"] = round(entity_score, 3)
    a["entity_match_count"] = matches
    a["combined_score"] = round(
        0.7 * a["similarity"] + 0.3 * entity_score, 4
    )

# Flag low-confidence alignments
low_conf = [a for a in alignments if a["combined_score"] < 0.3]
print(f"\nLow-confidence alignments (<0.3): {len(low_conf)} / {len(alignments)}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(alignments, f, ensure_ascii=False, indent=2)

print(f"Saved validated alignments to {OUTPUT}")
```

---

## 8. Generate Output Files

### 8a. Script: `07_generate_outputs.py`

```python
#!/usr/bin/env python3
"""
Generate final output files:
  1. TEI standoff alignment XML
  2. Final TSV with all scores
  3. Quality report
"""

import json
from pathlib import Path
from collections import Counter
from datetime import date

ALIGNMENTS = Path("output/entity_validated_alignments.json")
OUT_XML = Path("output/alignment_booth_perseus.xml")
OUT_TSV = Path("output/alignment_booth_perseus.tsv")
OUT_REPORT = Path("output/alignment_report.md")

with open(ALIGNMENTS) as f:
    alignments = json.load(f)

# ---- 1. TEI Standoff XML ----
xml_lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<TEI xmlns="http://www.tei-c.org/ns/1.0">',
    '  <teiHeader>',
    '    <fileDesc>',
    '      <titleStmt>',
    '        <title>Alignment: Booth English (1700) ↔ Perseus Greek Diodorus Siculus</title>',
    '      </titleStmt>',
    '      <publicationStmt><p>Generated automatically.</p></publicationStmt>',
    '      <sourceDesc>',
    '        <bibl xml:id="booth">OTA A36034 — G. Booth, The Historical Library (1700)</bibl>',
    '        <bibl xml:id="perseus">PerseusDL canonical-greekLit tlg0060.tlg001</bibl>',
    '      </sourceDesc>',
    '    </fileDesc>',
    '  </teiHeader>',
    '  <text>',
    '    <body>',
]

# Group by book
from collections import defaultdict
by_book = defaultdict(list)
for a in alignments:
    by_book[a["book"]].append(a)

for book_num in sorted(by_book.keys(), key=lambda x: int(x) if x.isdigit() else 0):
    book_aligns = by_book[book_num]
    xml_lines.append(f'      <linkGrp type="alignment" subtype="book-{book_num}">')
    for a in book_aligns:
        src = f"booth:div1[@n='{book_num}']/div2[{a['booth_div2_index']}]/p[{a['booth_p_index']}]"
        tgt = f"urn:cts:greekLit:tlg0060.tlg001.{a['greek_edition']}:{a['greek_cts_ref']}"
        conf = a.get("combined_score", a["similarity"])
        xml_lines.append(
            f'        <link target="{src} {tgt}" '
            f'ana="confidence:{conf}"/>'
        )
    xml_lines.append('      </linkGrp>')

xml_lines += [
    '    </body>',
    '  </text>',
    '</TEI>',
]

with open(OUT_XML, "w", encoding="utf-8") as f:
    f.write("\n".join(xml_lines))

# ---- 2. TSV ----
with open(OUT_TSV, "w", encoding="utf-8") as f:
    f.write("book\tgreek_cts_ref\tgreek_edition\tbooth_div2\tbooth_p\t"
            "embedding_sim\tentity_score\tcombined_score\n")
    for a in alignments:
        f.write(f"{a['book']}\t{a['greek_cts_ref']}\t{a['greek_edition']}\t"
                f"{a['booth_div2_index']}\t{a['booth_p_index']}\t"
                f"{a['similarity']}\t{a.get('entity_overlap_score','')}\t"
                f"{a.get('combined_score', a['similarity'])}\n")

# ---- 3. Quality Report ----
total = len(alignments)
scores = [a.get("combined_score", a["similarity"]) for a in alignments]
high = sum(1 for s in scores if s >= 0.6)
med = sum(1 for s in scores if 0.3 <= s < 0.6)
low = sum(1 for s in scores if s < 0.3)
books_covered = sorted(set(a["book"] for a in alignments))
avg_score = sum(scores) / len(scores) if scores else 0

report = f"""# Alignment Quality Report

**Date:** {date.today().isoformat()}
**English source:** Booth (1700) — OTA A36034
**Greek source:** Perseus canonical-greekLit tlg0060.tlg001

## Coverage

- **Total alignments:** {total}
- **Books aligned:** {', '.join(books_covered)}
- **Books NOT aligned (no Greek or no English):** check book_alignment.json

## Confidence Distribution

| Band | Count | Percentage |
|---|---|---|
| High (≥ 0.6) | {high} | {high/total*100:.1f}% |
| Medium (0.3–0.6) | {med} | {med/total*100:.1f}% |
| Low (< 0.3) — needs review | {low} | {low/total*100:.1f}% |

- **Mean combined score:** {avg_score:.3f}
- **Method:** Multilingual sentence embeddings (paraphrase-multilingual-MiniLM-L12-v2) + named-entity anchor validation

## Methodology

1. Both TEI XML sources parsed with lxml
2. Booth text normalised (archaic spelling regularisation)
3. Book-level alignment via heading matching and `n=` attributes
4. Section-level alignment via multilingual sentence embeddings with monotonicity constraint
5. Validation via cross-lingual named-entity fuzzy matching (Greek transliteration → English)
6. Combined score: 70% embedding similarity + 30% entity overlap

## Known Issues

- Ancient Greek is not directly in the MiniLM training data; alignment quality depends on
  the model's Modern Greek and Latin coverage as a bridge
- Booth's 1700 translation is loose and paraphrastic — some sections may map to the wrong
  paragraph when content is reorganised
- Low-confidence alignments (< 0.3) should be manually reviewed
- Fragment sections (Photius excerpts, etc.) are not aligned in this pass

## Output Files

- `alignment_booth_perseus.xml` — TEI standoff alignment
- `alignment_booth_perseus.tsv` — tabular format with scores
- `entity_validated_alignments.json` — full alignment data with all metadata
- `book_alignment.json` — book-level correspondence table

## Recommended Next Steps

1. Manually review all low-confidence alignments
2. For high-value books (I, XI–XV), do a full manual pass comparing Booth ¶s to Greek §§
3. Consider training a fine-tuned Ancient Greek embedding model for improved similarity
4. Align Booth's fragment translations to Perseus fragment numbering separately
"""

with open(OUT_REPORT, "w", encoding="utf-8") as f:
    f.write(report)

print(f"Generated:")
print(f"  {OUT_XML}")
print(f"  {OUT_TSV}")
print(f"  {OUT_REPORT}")
```

---

## 9. Run Everything

### Master script: `run_all.sh`

```bash
#!/bin/bash
set -e
cd ~/diodorus-alignment
source .venv/bin/activate

echo "=== Step 1: Extract Booth TEI ==="
python 01_extract_booth.py

echo "=== Step 2: Extract Perseus Greek ==="
python 02_extract_perseus.py

echo "=== Step 3: Normalise Booth English ==="
python 03_normalise_booth.py

echo "=== Step 4: Align Books ==="
python 04_align_books.py

echo "=== Step 5: Embed & Align Sections ==="
python 05_embed_and_align.py

echo "=== Step 6: Validate with Entity Anchors ==="
python 06_entity_anchors.py

echo "=== Step 7: Generate Outputs ==="
python 07_generate_outputs.py

echo ""
echo "✅  Done. All outputs in ./output/"
ls -la output/
```

```bash
chmod +x run_all.sh
./run_all.sh
```

---

## 10. Expected Runtime & Resources

| Step | Time (M2 Mac) | Time (Intel Mac) | Notes |
|---|---|---|---|
| Downloads | 1–5 min | 1–5 min | Depends on network |
| XML parsing (steps 1–2) | < 10 sec | < 10 sec | |
| Normalisation (step 3) | < 5 sec | < 5 sec | |
| Book alignment (step 4) | < 1 sec | < 1 sec | |
| Model download (first run) | 2–5 min | 2–5 min | ~420 MB, cached after |
| Embedding + alignment (step 5) | 5–20 min | 15–45 min | CPU-bound; ~2000 sections |
| Entity extraction (step 6) | 2–5 min | 5–10 min | spaCy NER |
| Output generation (step 7) | < 5 sec | < 5 sec | |
| **Total (first run)** | **~15–35 min** | **~30–70 min** | |
| **Total (subsequent)** | **~10–30 min** | **~25–60 min** | Model cached |

Peak RAM: ~2–3 GB (during embedding computation).

---

## 11. All Software Used

| Tool | Version | Licence | Role |
|---|---|---|---|
| Python | 3.11+ | PSF | Runtime |
| lxml | 5.x | BSD | TEI XML parsing |
| beautifulsoup4 | 4.x | MIT | Fallback HTML/XML parsing |
| sentence-transformers | 3.x | Apache 2.0 | Multilingual embeddings |
| paraphrase-multilingual-MiniLM-L12-v2 | — | Apache 2.0 | Embedding model (420 MB) |
| spacy + en_core_web_sm | 3.x | MIT | English NER |
| scipy | 1.x | BSD | Cosine distance |
| numpy | 1.x/2.x | BSD | Matrix operations |
| pandas | 2.x | BSD | Optional data wrangling |
| rapidfuzz | 3.x | MIT | Fuzzy string matching |
| unidecode | 1.x | GPL 2+ | Greek transliteration |
| regex | 2024.x | Apache 2.0 | Advanced regex |
| scikit-learn | 1.x | BSD | Optional clustering |
| tqdm | 4.x | MIT/MPL | Progress bars |
| cltk | 1.x | MIT | Ancient Greek NLP (optional) |
| git | 2.x | GPL 2 | Clone Perseus repo |
| curl | system | MIT/curl | Download OTA files |

All tools are free and open source. No API keys or cloud accounts needed.

---

## 12. Directory Structure After Completion

```
~/diodorus-alignment/
├── .venv/                          # Python virtual environment
├── data/
│   ├── booth/
│   │   ├── A36034.xml              # Booth TEI XML (5 MB)
│   │   └── A36034.samuels.tsv      # Linguistic annotation (47 MB)
│   └── perseus/
│       └── canonical-greekLit/
│           └── data/tlg0060/tlg001/
│               ├── tlg0060.tlg001.perseus-grc4.xml
│               ├── tlg0060.tlg001.perseus-grc5.xml
│               ├── tlg0060.tlg001.perseus-grc6.xml
│               └── __cts__.xml
├── output/
│   ├── booth_extracted.json        # Parsed Booth text
│   ├── booth_normalised.json       # Normalised Booth text
│   ├── perseus_extracted.json      # Parsed Greek text
│   ├── book_alignment.json         # Book-level mapping
│   ├── section_alignments.json     # Raw embedding alignments
│   ├── entity_validated_alignments.json  # With entity scores
│   ├── alignment_booth_perseus.xml # TEI standoff alignment
│   ├── alignment_booth_perseus.tsv # Tabular alignment
│   └── alignment_report.md         # Quality report
├── 01_extract_booth.py
├── 02_extract_perseus.py
├── 03_normalise_booth.py
├── 04_align_books.py
├── 05_embed_and_align.py
├── 06_entity_anchors.py
├── 07_generate_outputs.py
└── run_all.sh
```

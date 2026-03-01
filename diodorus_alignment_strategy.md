# Text Alignment Strategy: Booth English TEI ↔ Perseus Greek Diodorus Siculus

> **Superseded.** See `plans/segmental_dp_alignment_plan.md` and `README.md`.

## 1. Source Identification

### English Source — Booth (1700) via OTA / EEBO-TCP

| Field | Value |
|---|---|
| **Title** | *The Historical Library of Diodorus the Sicilian in Fifteen Books* |
| **Translator** | George Booth (17th/18th c.) |
| **Original publication** | London, 1700 (printed by Edw. Jones for Awnsham & John Churchill) |
| **Digital source** | Oxford Text Archive (OTA), identifier `ota:A36034` |
| **Repository URL** | <https://llds.ling-phil.ox.ac.uk/llds/xmlui/handle/20.500.14106/A36034> |
| **Upstream** | EEBO-TCP (Text Creation Partnership), ID `A36034.0001.001` |
| **Format** | TEI XML (P4/P5 via TCP-to-TEI pipeline), plus EPUB and HTML derivatives |
| **Licence** | CC0 — No Rights Reserved |
| **Coverage** | Books I–XV of the *Bibliotheca Historica*, plus Photius excerpts, fragments from Valesius, Rhodomannus, and Ursinus |
| **Additional resource** | SAMUELS linguistically-annotated TSV (`A36034.samuels.tsv`, 46.76 MB) |

### Greek Source — Perseus Digital Library / canonical-greekLit

| Field | Value |
|---|---|
| **Work** | Diodorus Siculus, *Bibliotheca Historica* |
| **CTS URN** | `urn:cts:greekLit:tlg0060.tlg001` |
| **Repository** | `PerseusDL/canonical-greekLit` on GitHub |
| **File path pattern** | `data/tlg0060/tlg001/tlg0060.tlg001.perseus-grc{N}.xml` |
| **Known editions** | `perseus-grc5` (Bekker-Dindorf-Vogel, Teubner 1888-1890, Books I–V), `perseus-grc6` (Bekker-Dindorf-Vogel-Fischer, Teubner 1903-1906, Books XVIII–XX), `perseus-grc4` (Oldfather/Sherman/Welles, Loeb 1946-1963, Books XI–XVII) |
| **Licence** | CC BY-SA 3.0 US |
| **Citation structure** | `book.chapter.section` (e.g. `1.1.1`, `5.55.3`) |
| **Reference URIs** | `http://data.perseus.org/texts/urn:cts:greekLit:tlg0060.tlg001.perseus-grc{N}` |

---

## 2. Structural Analysis

### 2.1 Booth English TEI (EEBO-TCP)

The EEBO-TCP encoding follows a `div1 > div2 > div3` nesting scheme:

```
<TEI>
  <teiHeader>...</teiHeader>
  <text>
    <front>
      <div1 type="dedication">...</div1>
      <div1 type="to_the_reader">...</div1>
      <div1 type="preface">...</div1>
    </front>
    <body>
      <div1 type="book" n="1">          ← Book I
        <div2 type="chapter">           ← Thematic/narrative section
          <head>...</head>
          <p>...</p>                     ← Prose paragraphs
        </div2>
        ...
      </div1>
      <div1 type="book" n="2">          ← Book II
        ...
      </div1>
      ...
    </body>
    <back>
      <div1 type="fragments">...</div1>  ← Photius excerpts, Valesius, etc.
      <div1 type="index">...</div1>
    </back>
  </text>
</TEI>
```

**Key characteristics:**

- Paragraphs (`<p>`) are the atomic text unit; there are **no section numbers** corresponding to modern Diodorus chapter.section references.
- `<pb>` (page break) elements reference the 1700 folio pagination.
- `<gap>` elements mark illegible or missing text from the original print.
- Marginal notes are encoded as `<note place="margin">`.
- The text is early-modern English with archaic spelling (e.g. "Aegyptians", "Demy-Gods").
- Front matter includes Booth's dedication, a reader's preface, and a thematic table of contents.
- Back matter includes fragment translations from Photius, Valesius, Rhodomannus, and Ursinus.

### 2.2 Perseus Greek TEI (CTS/EpiDoc)

The Perseus files use TEI with CTS (Canonical Text Services) referencing:

```
<TEI>
  <teiHeader>
    <refsDecl n="CTS">
      <cRefPattern n="section" matchPattern="(\w+).(\w+).(\w+)"
                   replacementPattern="#xpath(/tei:TEI/tei:text/tei:body/
                   tei:div/tei:div[@n='$1']/tei:div[@n='$2']/
                   tei:div[@n='$3'])"/>
    </refsDecl>
  </teiHeader>
  <text>
    <body>
      <div type="edition" n="urn:cts:greekLit:tlg0060.tlg001.perseus-grc5">
        <div type="textpart" subtype="book" n="1">
          <div type="textpart" subtype="chapter" n="1">
            <div type="textpart" subtype="section" n="1">
              <p>Τοῖς τὰς κοινὰς ἱστορίας πραγματευσαμένοις...</p>
            </div>
            <div type="textpart" subtype="section" n="2">
              <p>...</p>
            </div>
          </div>
        </div>
      </div>
    </body>
  </text>
</TEI>
```

**Key characteristics:**

- Three-level CTS citation: **book → chapter → section** (e.g. `1.1.1`).
- Each `<div type="textpart" subtype="section">` contains exactly one `<p>`.
- Sections are stable, canonical reference points used by all modern scholarship.
- Multiple edition files split across Teubner and Loeb volumes (grc5 = Bks I–V, grc6 = Bks XVIII–XX, grc4 = Bks XI–XVII via Loeb). Books VI–X survive only as fragments and are not in this repo.
- Not all 40 books survive intact: Books I–V and XI–XX are complete; VI–X exist only as fragments.

---

## 3. Core Alignment Challenges

| Challenge | Description | Severity |
|---|---|---|
| **Missing canonical sections in English** | Booth's TEI has no `book.chapter.section` numbers; only `div1/div2` book/chapter divisions and `<p>` elements | 🔴 Critical |
| **Scope mismatch** | Booth covers Books I–XV; Perseus Greek covers Books I–V plus XI–XX (and fragments of VI–X). Overlap is Books I–V and XI–XV. | 🟡 Moderate |
| **Granularity mismatch** | Greek sections (~1–3 sentences) vs. English paragraphs (variable, often multi-section) | 🟡 Moderate |
| **Translation freedom** | Booth's 1700 translation is loose, paraphrastic, and sometimes rearranges content | 🟡 Moderate |
| **Spelling variance** | Early-modern English orthography complicates NLP tokenisation | 🟢 Low |
| **Fragment handling** | Booth's back-matter fragments (Photius, etc.) correspond to Perseus `perseus-grc4` fragment numbering but with different structures | 🟡 Moderate |
| **Multi-file Greek source** | Greek text split across `grc4`, `grc5`, `grc6` files with overlapping or complementary book coverage | 🟢 Low |

---

## 4. Alignment Strategy

### Phase 1 — Preparation & Normalisation

#### 1a. Parse & extract both corpora

- **English (Booth):** Parse `A36034.xml` using an XML parser (lxml, BeautifulSoup, or Saxon). Extract all `<div1 type="book">` elements. For each book, extract child `<div2>` and their `<p>` elements. Preserve `<pb>` page-break references as metadata.
- **Greek (Perseus):** Clone `PerseusDL/canonical-greekLit`. Parse each `tlg0060.tlg001.perseus-grc{N}.xml` file. Extract text keyed by `book.chapter.section` CTS reference.

#### 1b. Normalise English text

- Modernise spelling using VARD2, MorphAdorner, or a custom early-modern English normalisation dictionary.
- Alternatively, leverage the SAMUELS-annotated TSV file (`A36034.samuels.tsv`) which provides lemmatised tokens.
- Strip `<gap>`, `<note>`, and `<figure>` elements or preserve them as metadata annotations.

#### 1c. Build a unified book index

Construct a lookup table mapping book numbers across both corpora:

| Diodorus Book | Booth English | Perseus grc5 | Perseus grc4 | Perseus grc6 |
|---|---|---|---|---|
| I | ✅ div1 n="1" | ✅ | — | — |
| II | ✅ div1 n="2" | ✅ | — | — |
| III | ✅ div1 n="3" | ✅ | — | — |
| IV | ✅ div1 n="4" | ✅ | — | — |
| V | ✅ div1 n="5" | ✅ | — | — |
| VI–X | ❌ (fragments only) | — | — | — |
| XI | ✅ div1 n="6" (or "11") | — | ✅ | — |
| XII | ✅ | — | ✅ | — |
| XIII | ✅ | — | ✅ | — |
| XIV | ✅ | — | ✅ | — |
| XV | ✅ | — | ✅ | — |
| XVI–XVII | ❌ (not in Booth) | — | ✅ | — |
| XVIII–XX | ❌ (not in Booth) | — | — | ✅ |

> **Note:** Booth's `div1 n=` numbering may not directly match Diodorus book numbers. Verification is required by inspecting `<head>` elements (e.g. `<head>BOOK I.</head>`).

### Phase 2 — Coarse Alignment (Book + Chapter)

#### 2a. Book-level alignment

Match Booth `<div1 type="book">` elements to Perseus `<div type="textpart" subtype="book">` by their `n=` attribute and/or `<head>` text.

#### 2b. Chapter-level alignment

For each book, map Booth `<div2>` divisions to Perseus `chapter` divisions:

- **Strategy A — Heading matching:** Booth's `<div2><head>` elements often contain thematic summaries (e.g. "The First way of Living of the Egyptians: Gods and Demy-Gods"). Compare these against the known chapter content of the Greek text using a bilingual concordance or existing translation (e.g. Oldfather Loeb).
- **Strategy B — Positional/sequential matching:** Within each book, assume roughly sequential correspondence. Use the first and last sentences of each Booth `<div2>` to find their Greek equivalents via sentence-level alignment (Phase 3), then infer chapter boundaries.

### Phase 3 — Fine-Grained Alignment (Section + Sentence)

This is the most labour-intensive phase. Three complementary approaches:

#### 3a. Anchor-point alignment using named entities and numbers

1. Extract named entities (personal names, place names, numbers, dates) from both English and Greek texts.
2. Named entities in early translations are often close transliterations of Greek (e.g. "Sesostris" ← Σέσωστρις, "Osiris" ← Ὄσιρις).
3. Build a bilingual entity gazetteer and match entity sequences across the two texts.
4. Numbers (regnal years, distances, army sizes) are strong anchors.
5. Use these anchor points to establish section boundaries within the English text.

#### 3b. Machine translation back-alignment

1. Machine-translate each Greek section (e.g. via Google Translate, DeepL, or a fine-tuned NMT model for Ancient Greek) into modern English.
2. Compute sentence-level similarity (cosine similarity on sentence embeddings, e.g. using `sentence-transformers`) between each machine-translated Greek section and each Booth English paragraph.
3. Use a dynamic programming / monotonic alignment algorithm (similar to Gale-Church or Vecalign) to find the optimal mapping, enforcing monotonicity (sections should appear in order).

#### 3c. Vecalign / Bleualign sentence-level alignment

1. Segment both texts into sentences.
2. Use [Vecalign](https://github.com/thompsonb/vecalign) with multilingual sentence embeddings (e.g. LaBSE, SONAR, or multilingual-e5) to align Greek sentences to English sentences.
3. Since Booth's English is early-modern, consider first normalising it (Phase 1b) before computing embeddings.
4. Post-process: map sentence alignments back to Perseus CTS section references.

### Phase 4 — Annotation & Storage

#### 4a. Standoff annotation format

Store alignments in a standoff annotation file (separate from both source TEI files) using one of these formats:

**Option A — TEI `<linkGrp>` (recommended for TEI ecosystem):**

```xml
<linkGrp type="alignment"
         source="A36034.xml"
         target="tlg0060.tlg001.perseus-grc5.xml">
  <link type="section"
        source="#booth-bk1-p3"
        target="urn:cts:greekLit:tlg0060.tlg001.perseus-grc5:1.2.1"/>
  <link type="section"
        source="#booth-bk1-p3"
        target="urn:cts:greekLit:tlg0060.tlg001.perseus-grc5:1.2.2"/>
  <link type="section"
        source="#booth-bk1-p4"
        target="urn:cts:greekLit:tlg0060.tlg001.perseus-grc5:1.2.3"/>
  <!-- ... -->
</linkGrp>
```

**Option B — CSV/TSV for computational use:**

```
booth_book,booth_div2,booth_p_index,perseus_urn,confidence,method
1,1,3,urn:cts:greekLit:tlg0060.tlg001.perseus-grc5:1.2.1,0.87,vecalign
1,1,3,urn:cts:greekLit:tlg0060.tlg001.perseus-grc5:1.2.2,0.82,vecalign
1,1,4,urn:cts:greekLit:tlg0060.tlg001.perseus-grc5:1.2.3,0.91,entity_anchor
```

**Option C — JSON-LD with Web Annotation model:**

```json
{
  "@context": "http://www.w3.org/ns/anno.jsonld",
  "type": "Annotation",
  "motivation": "linking",
  "body": {
    "source": "https://llds.ling-phil.ox.ac.uk/.../A36034.xml",
    "selector": { "type": "XPathSelector", "value": "//div1[@n='1']/div2[1]/p[3]" }
  },
  "target": {
    "source": "urn:cts:greekLit:tlg0060.tlg001.perseus-grc5:1.2.1"
  }
}
```

#### 4b. Back-inject CTS references into Booth TEI

Optionally, create a derivative of the Booth TEI with inline CTS milestone markers:

```xml
<p>
  <milestone unit="section" edRef="perseus-grc5" n="1.2.1"/>
  It is fitting that all Men should ever accord great Gratitude...
  <milestone unit="section" edRef="perseus-grc5" n="1.2.2"/>
  For although the Learning which is acquired...
</p>
```

### Phase 5 — Validation & Quality Assurance

1. **Spot-check sample:** Manually verify alignment for a sample of 50–100 sections across multiple books, prioritising:
   - Book I (Egyptian material, high name density → good anchors)
   - Book XI (beginning of historical narrative, well-studied)
   - Fragment sections (highest risk of misalignment)
2. **Confidence scoring:** Flag any alignment with confidence < 0.7 for manual review.
3. **Consistency checks:**
   - Verify monotonicity (no crossing alignments within a book).
   - Verify completeness (every Greek section maps to at least one English passage and vice versa).
   - Check for 1:many and many:1 mappings and validate them.
4. **Community review:** Publish preliminary alignments on GitHub for scholarly review.

---

## 5. Recommended Tool Stack

| Task | Tool | Notes |
|---|---|---|
| XML parsing | `lxml` (Python) | For both EEBO-TCP and Perseus TEI |
| Spelling normalisation | VARD2 or SAMUELS TSV | The SAMUELS file provides pre-lemmatised tokens |
| NER | spaCy + `en_core_web_trf` | For English; supplement with custom gazetteer for ancient names |
| Greek NER | Stanza Ancient Greek model | Or custom regex for known name patterns |
| Sentence embeddings | LaBSE or multilingual-e5-large | Cross-lingual similarity |
| Sentence alignment | Vecalign or Bleualign | Monotonic bilingual alignment |
| Ancient Greek MT | Helsinki-NLP OPUS-MT `grc→en` | For back-translation comparison |
| Alignment storage | TEI `<linkGrp>` + TSV | Dual format for interoperability |
| Visualisation | Alpheios, Ugarit aligner, or custom web app | For review and correction |

---

## 6. Expected Outputs

1. **`alignment_booth_perseus.xml`** — TEI standoff alignment file with `<linkGrp>` elements mapping Booth paragraphs to Perseus CTS sections.
2. **`alignment_booth_perseus.tsv`** — Tabular alignment with confidence scores and method labels.
3. **`A36034_with_milestones.xml`** — Derivative Booth TEI with injected CTS `<milestone>` elements.
4. **`alignment_report.md`** — Quality report with coverage statistics, confidence distributions, and notes on problematic passages.
5. **`entity_gazetteer.json`** — Bilingual named-entity gazetteer extracted during alignment.

---

## 7. Known Limitations

- **Booth covers only Books I–XV.** Alignment for Books XVI–XX is not possible with this English source. For those books, the Oldfather Loeb translation (available on Perseus as `perseus-eng{N}`) could be used instead.
- **Fragment alignment is uncertain.** Booth's fragment translations from Photius, Valesius, and others do not have a clean 1:1 correspondence with Perseus fragment numbering.
- **Booth's translation is pre-critical.** It predates modern critical editions (Bekker, Vogel, Fischer) and may follow a different Greek text tradition, leading to passages present in one source but absent in the other.
- **OCR/transcription artefacts.** The EEBO-TCP text was produced from early print page images and may contain `<gap>` elements or transcription errors.
- **The SAMUELS linguistic annotation** covers the entire A36034 text but its tokenisation may not align perfectly with the TEI `<p>` boundaries.

---

## 8. References

- Booth, G. (1700). *The Historical Library of Diodorus the Sicilian*. London.
- Bekker, I., Dindorf, L., & Vogel, F. (eds.) (1888–1890). *Diodori Bibliotheca Historica*, Vols. 1–2. Leipzig: Teubner.
- Fischer, K. T. (ed.) (1903–1906). *Diodori Bibliotheca Historica*, Vols. 4–5. Leipzig: Teubner.
- Oldfather, C. H. (trans.) (1933–1967). *Diodorus of Sicily*. Loeb Classical Library. Cambridge, MA: Harvard University Press.
- Thompson, B. & Koehn, P. (2019). "Vecalign: Improved Sentence Alignment in Linear Time and Space." *EMNLP*.
- Crane, G. et al. Perseus Digital Library. <https://www.perseus.tufts.edu/>
- Text Creation Partnership. <https://textcreationpartnership.org/>
- Oxford Text Archive. <https://llds.ling-phil.ox.ac.uk/llds/xmlui/>

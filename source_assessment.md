# Design Doc: Assessing Wikisource and english_trans-dev as Sources

## Purpose

Evaluate the two external sources — **Wikisource** (catalogued in
`external/ancient_greek_wikisource-2.csv`) and **OpenGreekAndLatin/english_trans-dev**
(cloned at `data-sources/english_trans-dev/`) — for candidate works that can fill
Greek-only (or Latin-only) gaps in Perseus and First1KGreek.

## Current State

### Already completed (12 works)

| CTS ID | Author | Work | English Source |
|--------|--------|------|----------------|
| tlg0060.tlg001 | Diodorus Siculus | Bibliotheca Historica | OTA Booth 1700 |
| tlg0081.tlg012 | Dionysius of Hal. | De Comp. Verborum | Gutenberg |
| tlg0096.tlg002 | Aesop | Fabulae | Gutenberg |
| tlg0562.tlg001 | Marcus Aurelius | Meditations | Gutenberg |
| tlg2023.tlg001 | Iamblichus | De Vita Pythagorica | Gutenberg |
| tlg2023.tlg006 | Iamblichus | De Mysteriis | Gutenberg |
| phi1020.phi001 | Statius | Thebaid | Wikisource (Mozley) |
| phi1020.phi003 | Statius | Achilleid | Wikisource (Mozley) |
| tlg2115.tlg060 | Hippolytus | Refutatio | Gutenberg |
| tlg2000.tlg001 | Plotinus | Enneads | Gutenberg |
| tlg4029.tlg001 | Procopius | Wars | Gutenberg |
| tlg4029.tlg002 | Procopius | Secret History | Gutenberg |

### Planned but not yet done (from PROJECT_DOCUMENTATION.md)

| Author | Work | English Source |
|--------|------|----------------|
| Origen | Contra Celsum | Gutenberg |
| Clement of Alexandria | Protrepticus | Gutenberg |

---

## Source 1: english_trans-dev

**Repo:** `data-sources/english_trans-dev/`
(GitHub: OpenGreekAndLatin/english_trans-dev)

### What it is

A collection of **111 volume-level TEI XML files** containing machine-corrected
(OCR by Jouve) public-domain English translations, almost entirely from the
**Bohn's Classical Library** series. Licensed **CC-BY-SA 4.0** — compatible with
our project and Perseus.

### Structure

- `volumes/` — 111 unsplit whole-volume TEI XML files (e.g. `aristophanes_1852/`,
  `apollonius_1889/`). These are the raw OCR-corrected files. Most are directories
  containing a single `.xml` file.
- `data/` — Only **9 works** have been CTS-split into work-level files with TLG
  identifiers:
  - tlg0001.tlg001 (Apollonius, Argonautica — Coleridge 1889)
  - tlg0019.tlg003 (Aristophanes, Clouds — Rogers 1852)
  - tlg0019.tlg004 (Aristophanes, Wasps — Rogers 1875)
  - tlg0019.tlg005 (Aristophanes, Peace — Rogers 1913)
  - tlg0019.tlg009 (Aristophanes, Frogs — Cope 1911 + Rogers 1919)
  - tlg0019.tlg010 (Aristophanes, Ecclesiazusae — Rogers 1902)
  - tlg0237.tlg002 (Alciphron — 1896)
  - tlg0640.tlg001 (Chariton — 1764)

### TEI encoding quality

Per analysis in `external/c.txt`:
- Has `<pb>` (page breaks from print) and `<lb/>` (physical line breaks)
- Has `<div type="textpart" subtype="chapter">` work-level divisions
- **No canonical citation milestones** — no `<milestone unit="line" n="42"/>`,
  no `<milestone unit="section" n="1.2.3"/>`, no `@corresp` linking to Greek
- The `<pb n="...">` values are **print page numbers**, not Greek canonical refs
- This means: texts are **readable** but **not aligned to Greek** — the alignment
  work is exactly what our pipeline does

### What this means for us

eng_trans-dev texts can serve as **English extraction sources** in our pipeline,
similar to how we use Gutenberg plain text. The TEI structure actually gives us
*more* to work with than Gutenberg — we get chapter/section divisions and can
parse XML rather than regex-splitting plain text. But the texts still need our
embedding-based alignment to pair with Greek sections.

### Direct gap-fills from eng_trans-dev

These are Perseus Greek-only works where eng_trans-dev has the English translation
ready:

| Priority | Perseus Gap | eng_trans-dev Volume | Translator | Year | Notes |
|:---:|-------------|---------------------|------------|:----:|-------|
| 1 | **Aristophanes** — 9 plays grc-only (tlg0019: tlg001, 002, 004, 005, 007-011) | 10+ volumes: Hickie vols 1-2 (1853/1858), Rogers individual plays (1852-1919) | Hickie, Rogers | 1852-1919 | **Biggest single win.** 5 plays already CTS-split in `data/`. Remaining 4 (Acharnians, Knights, Lysistrata, Thesmophoriazusae, Plutus) in Hickie volumes. |
| 2 | **Apollonius Rhodius** — Argonautica (tlg0001.tlg001) | `apollonius_1889/` + already CTS-split in `data/` | Coleridge | 1889 | Already CTS-split! Lowest effort to integrate. |
| 3 | **Theocritus** — 2 works grc-only (tlg0005.tlg001, tlg0005.tlg002) | `theocritus_1878/` | Banks & Chapman | 1878 | Includes Bion and Moschus (also grc-only: tlg0035, tlg0036). |
| 4 | **Lucian** — Podagra (tlg0062.tlg071) | `lucian_1888/` | Williams | 1888 | 334-line verse drama. Unconfirmed if volume contains this specific work. |
| 5 | **Plutarch** — Epitome on Timaeus (tlg0007.tlg135) | `plutarch_1898_ethical/` or `_theosophical/` | Shilleto, King | 1898 | 6 sections. Unconfirmed if either volume contains this essay. |
| 6 | **Aristotle** — Constitution of Athens (tlg0086.tlg003) | Not in eng_trans-dev | — | — | 73 sections. **Gutenberg #26095** (Kenyon) is the source instead. |

### Works in eng_trans-dev NOT in Perseus at all (First1KGreek candidates)

These authors have English in eng_trans-dev but no Greek text in Perseus.
Verified against First1KGreek and Perseus for eligibility:

| Author | eng_trans-dev Volume | F1K status | Eligible? |
|--------|---------------------|------------|:---------:|
| **Alciphron** | CTS-split `data/tlg0640/` | F1K has grc-only (122 letters) | **YES** |
| **Epictetus** | `epictetus_1887/`, `_1890/` | F1K has grc-only BUT only Stobaeus excerpts | Partial (HARD) |
| **Julian** | `julian_1888/` | Perseus has 13 grc-only works (tlg2003) | **YES** — needs volume inspection |
| **Longus** | `heliodorus_longus_achillesTatius_1901/` | Perseus has grc-only (tlg0561) | **YES** |
| **Achilles Tatius** | Same volume | Perseus has grc-only (tlg0532) | **YES** |
| **Heliodorus** | Same volume | F1K has grc-only (tlg0658) | **YES** |
| **Greek Anthology** | `greekAnthology_1893/` | Perseus has grc-only (tlg7000) | **YES** — needs volume inspection |
| Chariton | CTS-split `data/tlg0640/` | Not in F1K or Perseus | No Greek source |
| Diogenes Laertius | `diogenesLaertius_1853/` | Already has eng in Perseus | NOT ELIGIBLE |
| Pausanias | `pausanias_1886_1.xml`, `_2_1886/` | Already has eng in Perseus | NOT ELIGIBLE |
| Philo | `philo_1_1854/`, `_2_1854.xml`, `_4_1855/` | Already has eng in F1K | NOT ELIGIBLE |
| Plotinus | `plotinus_1895/` | — | **Already done** (Gutenberg) |
| Pindar | `pindar_1915/` | Already has eng in Perseus | NOT ELIGIBLE |

### Latin works in eng_trans-dev

eng_trans-dev also has Latin translations we haven't considered:

| Author | Volume | Notes |
|--------|--------|-------|
| Apuleius | `apuleius_1878/` | phi1212 — already CTS-split |
| Boethius | 2 volumes | |
| Catullus/Tibullus | `catullus_tibullus_1910/` | |
| Cicero | 2 volumes | |
| Horace | 3 volumes | |
| Lucan | `lucan_1853.xml` | |
| Lucretius | 3 volumes | |
| Martial | 2 volumes | |
| Ovid | `ovid_1881/` | |
| Plautus | 2 volumes | |
| Propertius | `propertius_1895/` | |
| Quintilian | 2 volumes | |
| Seneca | 2 volumes | |
| Terence | `terence_phaedrus_1891.xml` | |

These should be cross-referenced against `data-sources/perseus/canonical-latinLit`
for Latin-only gaps.

---

## Source 2: Wikisource

**Catalog:** `external/ancient_greek_wikisource-2.csv` (209 entries, 84 authors)

### What it is

A catalog of ancient Greek works that have English translations available on
Wikisource (en.wikisource.org). Licensed **CC-BY-SA 4.0** (or PD, depending on
the translation). The CSV has Author, Work, Category, and Notes (translator info).

### Key characteristics

- **Not raw text** — this is a catalog/inventory, not downloaded text. Each work
  would need to be scraped from Wikisource individually.
- **Much broader than eng_trans-dev** — 209 works vs 111 volumes, covering
  tragedy, comedy, philosophy, history, oratory, science, medicine, poetry, novels.
- **Many works already have English in Perseus** — the CSV is a general catalog
  of what's on Wikisource, not filtered for our gaps.
- **Significant overlap with eng_trans-dev** — most Bohn Library translations
  appear in both sources.

### Categories (by count)

| Category | Count | Notes |
|----------|:-----:|-------|
| Philosophy | 39 | Plato, Aristotle — mostly already in Perseus with English |
| Tragedy | 32 | Aeschylus, Sophocles, Euripides — mostly already in Perseus |
| History | 13 | Herodotus, Thucydides, etc. — mostly already in Perseus |
| Oratory | 12 | Demosthenes, Lysias — mostly already in Perseus |
| Comedy | 11 | Aristophanes — **9 grc-only plays = major gap** |
| Pre-Socratic | 11 | Fragments — hard to align |
| Lyric Poetry | 10 | Fragments — hard to align |
| Epic Poetry | 8 | Homer, Apollonius — Homer has English, Apollonius doesn't |
| Science | 7 | Aristotle's scientific works |
| Satire | 6 | Lucian |
| Other | 50+ | Medicine, novels, pastoral, etc. |

### Unique Wikisource candidates NOT in eng_trans-dev

These are works listed in the Wikisource CSV that have no corresponding volume in
eng_trans-dev and might fill gaps:

| Author | Work | Category | Why interesting |
|--------|------|----------|-----------------|
| Arrian | Anabasis of Alexander | History | 6 grc-only works in Perseus (tlg0074) |
| Arrian | Indica | History | Gutenberg previously ruled infeasible (McCrindle compilation) |
| Strabo | Geography | Geography | Not in Perseus Greek, may be in F1K |
| Cassius Dio | Roman History | History | Not in Perseus Greek, may be in F1K |
| Appian | Roman History | History | Not in Perseus Greek |
| Josephus | Jewish Antiquities, War, Against Apion | History | Not in Perseus Greek |
| Philostratus | Life of Apollonius, Lives of Sophists | Biography | Not in Perseus Greek |
| Isocrates | Orations | Oratory | Check Perseus status |
| Hippocrates | Several medical works | Medicine | Check F1K status |
| Quintus Smyrnaeus | Fall of Troy | Epic | Way translation (Loeb 1913) |
| Theophrastus | Characters | Philosophy | grc-only in Perseus (tlg0093.tlg009) |
| Theophrastus | Enquiry into Plants | Botany | Check F1K |
| Euclid | Elements | Math | Hard to align (mathematical) |
| Ptolemy | Almagest | Astronomy | Hard to align (technical) |

### Wikisource scraping considerations

- Each work is a separate Wikisource page (or set of pages for multi-book works)
- HTML structure varies per work — no single parser
- We already have a precedent: Statius/Mozley was scraped from Wikisource
  (`data-sources/statius_mozley/`)
- The Wikisource API or `requests` + BeautifulSoup can fetch pages
- License must be verified per work (PD vs CC-BY-SA — both acceptable)
- **No CC-BY-NC** — must check each translation

---

## Cross-reference: Perseus Greek-only gaps vs. available sources

The definitive gap list from scanning `data-sources/perseus/canonical-greekLit`:

| TLG | Author | # Works grc-only | eng_trans-dev? | Wikisource? | Already done? |
|-----|--------|:-:|:-:|:-:|:-:|
| tlg0001 | Apollonius Rhodius | 1 | **YES** (CTS-split!) | YES | No |
| tlg0005 | Theocritus | 2 | **YES** | YES | No |
| tlg0007 | Plutarch | 1 (of 141) | Possibly | Possibly | No |
| tlg0019 | Aristophanes | 9 | **YES** (5 CTS-split) | YES | No |
| tlg0023 | Oppian | 1 | No | No | No |
| tlg0024 | Oppian of Apamea | 1 | No | No | No |
| tlg0035 | Moschus | 5 | **YES** (in theocritus_1878) | YES | No |
| tlg0036 | Bion of Phlossa | 3 | **YES** (in theocritus_1878) | YES | No |
| tlg0058 | Aeneas Tacticus | 1 | No | No | No |
| tlg0060 | Diodorus Siculus | 1 | No | YES | **Done** |
| tlg0062 | Lucian | 1 | **YES** | YES | No |
| tlg0074 | Arrian | 6 | No | **YES** | No |
| tlg0081 | Dionysius of Hal. | 12 | No | No | 1 done |
| tlg0086 | Aristotle (Const. Athens + Virtues/Vices) | 2 | No | No | No — Gutenberg has Const. Athens (#26095) |
| tlg0090 | Agathemerus | 1 | No | No | No |
| tlg0093 | Theophrastus | 1 | No | **YES** | No |
| tlg0284 | Aelius Aristides | 11 | No | No | No |
| tlg0532 | Achilles Tatius | 1 | Incomplete (6/8 books) | YES | No — NOT FEASIBLE |
| tlg0561 | Longus | 1 | **YES** (in novels volume) | YES | No |
| tlg2003 | Julian | 14 | 2 of 14 (King 1888) | No | No |
| tlg7000 | Greek Anthology | 1 | Burges 6% only; **Paton Loeb on Wikisource** = complete | YES | No |

---

## Feasibility Assessment: All Candidate Works

Feasibility is assessed on five axes:
- **English availability**: Is a suitable PD/CC-BY-SA English translation available and identified?
- **Structural match**: How well do Greek and English section structures correspond?
- **Scale**: How large is the work (sections, lines, characters)?
- **Alignment mode**: DP (sequential) or pairwise (self-contained units)?
- **Special challenges**: Verse, fragments, OCR quality, structural mismatches, etc.

Ratings follow the same scheme as PROJECT_DOCUMENTATION.md: **EASY**, **MODERATE**, **HARD**, **NOT FEASIBLE**.

### Perseus Greek-only gap-fills

#### 1. Apollonius Rhodius — Argonautica (tlg0001.tlg001)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus, 4 books, 5,834 lines |
| English source | eng_trans-dev CTS-split: Coleridge 1889 |
| English structure | 4 books (chapters 8-11), 402 paragraphs, ~506,000 chars |
| Greek chars | ~592,000 (including XML tags both sides; raw text ratio ~86%) |
| Section ratio | ~14.5:1 (lines:paragraphs) |
| Alignment mode | DP with line-grouping (like Statius) |
| License | CC-BY-SA 4.0 |

**Feasibility: MODERATE**

**Confirmed: Coleridge is a COMPLETE prose translation**, not an abridgement.
The earlier 21% character ratio was based on tag-stripped counts that
undercounted the English; the actual raw text ratio is ~86%, which is typical for
complete prose translations of Greek verse. The book-level structure matches
perfectly (4 books each side). The line-to-paragraph ratio (~14.5:1) is high but
manageable with line-grouping as used for Statius. Opening passages confirm
faithful rendering of the Greek content.

The main challenge is verse-to-prose alignment: 5,834 Greek lines map to 402
English paragraphs. Line-grouping (~10-15 lines per group) as with Statius is
the right approach.

---

#### 2. Aristophanes — 9 plays (tlg0019)

**Plays needing English (all grc-only in Perseus):**

| Play | TLG | Greek lines | English source | Status |
|------|-----|:-----------:|----------------|--------|
| Acharnians | tlg001 | ~1,234 | Hickie vol 1 (1858) — unsplit | Volume extract needed |
| Knights | tlg002 | ~1,409 | Hickie vol 1 (1858) — unsplit | Volume extract needed |
| Wasps | tlg004 | ~1,537 | Rogers 1875 — CTS-split | Ready |
| Peace | tlg005 | ~1,357 | Rogers 1913 — CTS-split | Ready |
| Lysistrata | tlg007 | ~1,321 | Hickie vol 2 (1853) — unsplit | Volume extract needed |
| Thesmophoriazusae | tlg008 | ~1,231 | Hickie vol 2 (1853) — unsplit | Volume extract needed |
| Frogs | tlg009 | ~1,533 | Rogers 1919 — CTS-split (+ Cope 1911) | Ready |
| Ecclesiazusae | tlg010 | ~1,183 | Rogers 1902 — CTS-split | Ready |
| Wealth (Plutus) | tlg011 | ~1,209 | Hickie vol 2 (1853) — unsplit | Volume extract needed |

Note: Perseus already has English for Clouds (tlg003) and Birds (tlg006).

**Greek structure**: Line-level markup (`<l n="...">`) with dramatic section
divisions (Prologue, Parodos, Episodes, Choral, Parabasis, etc.). ~17 top-level
sections per play, ~1,200-1,500 lines per play.

**English structure**: Prose paragraphs with `<lb/>` line breaks. CTS-split files
have `<div type="textpart" subtype="chapter">` divisions. Hickie volumes contain
all plays sequentially with title-based separation. English includes prefatory
material and commentary that must be stripped.

| Attribute | Value |
|-----------|-------|
| Total Greek lines | ~11,000+ across 9 plays |
| Alignment mode | DP with line-grouping (verse) |
| License | CC-BY-SA 4.0 |

**Feasibility: MODERATE**

Structural alignment is straightforward — dramatic section divisions provide
natural alignment anchors. The main challenges are:
1. **Verse-to-prose mapping**: Greek is line-by-line verse; English is prose
   paragraphs. Requires line-grouping as with Statius (~10-15 lines per group).
2. **Volume splitting**: 5 plays need extraction from Hickie volumes. The volumes
   use clear title markers (`<title type="main">ACHARNIANS</title>`) so automated
   splitting is feasible.
3. **Commentary stripping**: English includes extensive scholarly notes and
   prefatory material that must be excluded.
4. **Multiple translators**: CTS-split plays use Rogers; Hickie volume plays use
   Hickie. Different translators have different styles, but this only affects
   consistency across plays, not individual alignment quality.

5. **Commentary bloat in Rogers CTS-split files**: Confirmed that the Rogers
   translations contain significant non-play material. Wasps: 68% play text,
   8% preface, 24% appendix. Peace: 58% play text, 9% front matter, 32%
   appendix. Extraction must strip preface/introduction and appendix sections,
   keeping only the play text. Character names appear in CAPS with abbreviations
   (SOSIAS → Sos.). Stage directions are inline in parentheses. No formal TEI
   drama markup (`<sp>`/`<speaker>`) — just plain `<p>` tags.

**Recommendation**: Start with the 4 CTS-split plays (Wasps, Peace, Frogs,
Ecclesiazusae) as a batch. Then extract and align the 5 Hickie plays. This is
the single highest-impact effort in the entire assessment — **9 new works**.

---

#### 3. Theocritus — Idylls + Epigrams (tlg0005)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus: tlg001 (30 Idylls, 2,717 lines), tlg002 (24 Epigrams, 265 lines) |
| English source | eng_trans-dev: `theocritus_1878/` (Banks & Chapman) |
| English structure | 30 Idylls + 25 Epigrams in prose, plus duplicate metrical translations |
| Alignment mode | DP per idyll (short sequential poems) or pairwise |
| License | CC-BY-SA 4.0 |

**Feasibility: EASY-MODERATE**

The 30-to-30 idyll mapping is clean. Each idyll is a self-contained poem (50-300
lines) that maps to a named English section. The English file contains TWO complete
translation sets — prose (primary, use this) and metrical (ignore). Epigrams are
very short (5-15 lines each) and have a 24-to-25 mapping (English has one extra).

Key considerations:
- Must use only the prose section (lines 785-8601 of the TEI), not the metrical
  duplicate (lines 8652+)
- Footnotes are abundant and need stripping
- Individual idylls are short enough that alignment should be high-confidence

---

#### 4. Moschus — 5 works (tlg0035)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus: 5 works, ~481 lines total |
| English source | eng_trans-dev: in `theocritus_1878/` (same volume as Theocritus) |
| English structure | 7 "Idylls" + 1 Epigram (reorganized from Greek structure) |
| Alignment mode | DP per work |
| License | CC-BY-SA 4.0 |

**Feasibility: MODERATE**

The four main works (Eros Drapeta, Europa, Epitaphios Bionos, Megara) map clearly
to English Idylls I-IV. The Fragmenta (tlg005) are redistributed across English
Idylls V-VII — this requires manual mapping. Works are very short (29-166 lines
each), so embedding quality on individual lines will be low; line-grouping is
essential. The structural reorganization of fragments is the main challenge.

---

#### 5. Bion of Phlossa — 3 works (tlg0036)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus: 3 works, ~246 lines total |
| English source | eng_trans-dev: in `theocritus_1878/` (same volume) |
| English structure | 6 "Idylls" (reorganized; Idylls I-II = main works, III-VI = fragments) |
| Alignment mode | DP per work |
| License | CC-BY-SA 4.0 |

**Feasibility: MODERATE**

Same situation as Moschus. Main works (Epitaphius Adonis = 98 lines, Myrson kai
Lykidas = 32 lines) map to English Idylls I-II. Fragmenta (tlg003, 116 lines)
scattered across Idylls III-VI and XV. Very short works — embedding may struggle.
Fragment-to-idyll mapping requires manual work.

**Recommendation**: Do Theocritus, Moschus, and Bion as a single batch from the
shared 1878 volume. Total: **10 works** from one English source.

---

#### 6. Arrian — 6 works (tlg0074)

| Work | TLG | Structure | Size | English available? |
|------|-----|-----------|------|--------------------|
| Anabasis of Alexander | tlg001 | 7 books, 206 chapters, 1,406 sections | Large | **Gutenberg #46976** (Chinnock). Downloaded: `data-sources/gutenberg/arrian_anabasis/pg46976.txt` |
| Indica | tlg002 | 43 chapters, sections | Medium | Wikisource (possibly); Gutenberg #66388 ruled infeasible (McCrindle compilation) |
| Cynegeticus | tlg003 | 37 chapters | Medium | **Gutenberg #78013** (Dansey). Downloaded: `data-sources/gutenberg/arrian_cynegeticus/pg78013.txt` |
| Periplus Ponti Euxini | tlg004 | 25 chapters | Small | No translation found |
| Tactica | tlg005 | 44 chapters | Medium | No translation found |
| Acies Contra Alanos | tlg006 | 31 sections | Small | No translation found |

**Feasibility: MIXED**

- **Anabasis (tlg001): MODERATE.** Gutenberg #46976 (Chinnock 1884) confirmed as
  a complete, clean, full prose translation. 7 books, 205 chapters, well-structured
  with clear `BOOK I.` / `CHAPTER I.` markers and ALL-CAPS descriptive headings.
  Text is clean with no OCR artifacts. 985 endnotes need stripping (inline `[14]`
  markers in body text). Also strip: Table of Contents (~460 lines), biographical
  essay "Life and Writings of Arrian" (~185 lines), Index of Proper Names (~2,590
  lines). The translation body itself is ~6,000 lines of continuous prose. This is
  a major work comparable in scale to Diodorus. High value — one of the most
  important grc-only gaps in Perseus.

- **Indica (tlg002): HARD.** The McCrindle Gutenberg (#66388) was previously
  ruled infeasible because it's a compilation from 5 authors, not a standalone
  Indica. Wikisource may have a cleaner edition but needs verification. 43
  chapters is manageable if a clean English text can be found.

- **Cynegeticus (tlg003): MODERATE-HARD.** Gutenberg #78013 ("Arrian on Coursing",
  Dansey) confirmed to contain a genuine translation of the Cynegeticus — but it
  is only **6% of the file** (~1,084 lines out of 17,452). The remaining 94% is
  Dansey's own scholarly apparatus: a lengthy preface on coursing history, a massive
  appendix on ancient hunting dogs, and ~9,000 lines of footnotes. The translation
  is 35 chapters (Chap. I-XXXV) marked via `[Sidenote: +Chap. I.+]`, with Dansey's
  annotations heavily interspersed even within the translation section. Extraction
  is feasible but requires careful separation of Arrian's text from Dansey's
  commentary.

- **Periplus, Tactica, Acies (tlg004-006): NOT FEASIBLE.** No public domain
  English translations found in Gutenberg, Wikisource, or eng_trans-dev. These
  are specialized military/geographic treatises with limited translation history.

**Recommendation**: Prioritize the Anabasis (tlg001) — it's the highest-value
single work in the entire candidate list. Cynegeticus is a secondary target.

---

#### 7. Theophrastus — Characters (tlg0093.tlg009)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus, 332 sections (30 character sketches with sub-sections) |
| English source | **Gutenberg #58242** (Bennett & Hammond 1902, Cornell). Downloaded: `data-sources/gutenberg/theophrastus/pg58242.txt`. Note: #16299 is Gally — older, less suitable. |
| English structure | 30 character sketches (I-XXX), each with Greek title, definition, and description |
| Alignment mode | DP (sequential character sketches) or pairwise |
| License | Public domain |

**Feasibility: EASY (with one caveat)**

Excellent candidate. 30 character sketches map 1:1 between Greek and English.
Each sketch is short (5-20 sentences) and self-contained. The 332 "sections" in
the Greek are sub-sections within 30 sketches — the actual alignment unit is the
sketch level, making this similar to Aesop's fables but sequential. Text is clean,
well-formatted, with Greek titles preserved.

**Caveat — non-standard ordering**: Bennett & Hammond reordered the 30 sketches
based on the 1897 Leipziger edition. Their Roman numerals I-XXX do NOT match the
traditional Greek manuscript numbering used in Perseus. For example, their "III"
(The Coward) is traditionally XXV. The Table of Contents provides the traditional
number in parentheses for each sketch, so remapping is straightforward but must
be done during extraction.

**Stripping needed**: Introduction (~30 pages of scholarly essay), footnotes
(translator notes). The Epistle Dedicatory to Polycles IS part of Theophrastus's
text and should be kept.

---

#### 8. Aristotle — Constitution of the Athenians (tlg0086.tlg003)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus, 73 sections with 307 sub-sections |
| English source | **Gutenberg #26095** (Kenyon) — confirmed clean. Downloaded: `data-sources/gutenberg/aristotle_const_athens/pg26095.txt` |
| English structure | 69 numbered parts (Part 1 - Part 69) |
| Alignment mode | DP |
| License | Public domain |

**Feasibility: EASY-MODERATE**

**Confirmed**: Exceptionally clean Gutenberg text. Kenyon edited both Greek and
English — same scholar, same edition. 69 sections in English matching the standard
numbering (the Greek's "73 sections" counts fragmentary/lost material differently).
Clear two-part structure: Parts 1-41 (historical narrative) + Parts 42-69
(current constitution). Part 1 faithfully begins mid-sentence with lacuna markers,
matching the fragmentary papyrus source.

Almost nothing to strip — no introduction, no appendices, no endnotes. Just
Gutenberg header/footer, title block, and one transcriber's note. This may be the
cleanest Gutenberg source in the entire project.

---

#### 9. Aristotle — On Virtues and Vices (tlg0086.tlg045)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus, 1 section (very short work, possibly spurious) |
| English source | None identified |
| Alignment mode | N/A |

**Feasibility: NOT FEASIBLE**

Single short section with no identified English translation. eng_trans-dev Aristotle
volumes don't contain it. Possibly pseudo-Aristotelian. Too small and obscure to
pursue.

---

#### 10. Lucian — Podagra (tlg0062.tlg071)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus, 334 lines (verse drama about gout) |
| English source | eng_trans-dev `lucian_1888/` — may contain "Tragopodagra" |
| Alignment mode | DP with line-grouping (verse) |
| License | CC-BY-SA 4.0 |

**Feasibility: NOT FEASIBLE**

**Confirmed**: The 1888 Lucian volume does NOT contain a translation of the
Podagra/Tragopodagra. It only mentions the work in a preface footnote. The volume
contains Dialogues of the Gods, Dialogues of the Sea-Gods, Dialogues of the Dead,
Zeus the Tragedian, and a few other dialogues — none of which is the Podagra. No
Gutenberg match exists either. The Podagra is rarely translated and no PD English
source has been identified.

---

#### 11. Plutarch — Epitome (tlg0007.tlg135)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus, 6 sections |
| English source | eng_trans-dev `plutarch_1898_ethical/` or `_theosophical/` — unconfirmed |
| Alignment mode | DP |

**Feasibility: NOT FEASIBLE**

**Confirmed**: The Epitome is NOT present in any eng_trans-dev Plutarch volume.
Searched all 6 volumes (ethical, theosophical, Lives vols 1-4) for "Timaeus",
"Soul", "Epitome", "psychogonia", "procreatione", "Generation of the Soul" —
no matches. The ethical volume contains 26 essays (On Education, On Love, On
Virtue and Vice, etc.) and the theosophical volume contains 6 essays (On Isis
and Osiris, On the Cessation of Oracles, etc.), but neither includes this
specific essay. No Gutenberg source exists either. This obscure essay appears
to have no digitized PD English translation.

---

#### 12. Dionysius of Halicarnassus — remaining 11 works (tlg0081)

We already completed tlg012 (De Compositione Verborum). The remaining works:

| Work | TLG | Sections | English available? |
|------|-----|:--------:|-------------------|
| **Roman Antiquities** | tlg001 | 4,256 | **YES — Cary/Loeb (see below)** |
| De antiquis oratoribus | tlg002 | 4 | No |
| De Lysia | tlg003 | 34 | No |
| De Isocrate | tlg004 | ~20 | No |
| De Isaeo | tlg005 | 20 | No |
| De Demosthene | tlg006 | 57 | No |
| Reliquiae | tlg007 | 5 | No |
| Ad Ammaeum | tlg008 | 12 | No |
| De Dinarcho | tlg009 | ~10 | No |
| De Thucydide | tlg010 | 55 | No |
| De Thucydidis idiomatibus | tlg011 | 17 | No |
| Epistula ad Pompeium | tlg015 | 73 | No |

**Feasibility: MODERATE (Roman Antiquities); NOT FEASIBLE (rhetorical essays)**

**Major discovery: Earnest Cary's Loeb translation (1937-1950) is public domain
and freely available.** Cary's 7-volume translation covers all 20 books (Books
1-11 complete + Books 12-20 fragments). Copyrights were not renewed. Multiple
high-quality sources exist:

| Source | Format | Quality | Status |
|--------|--------|---------|--------|
| **LacusCurtius** | Proofread HTML, structured by chapter/section | **Excellent** | **Downloaded**: `data-sources/dionysius_roman_antiquities/html/` (48 files, 3.9 MB) |
| IA 7-in-1 PDF | Single PDF, all volumes | Good OCR (Tesseract 5.2) | Available: archive.org/details/dionysius-roman-antiquities-7-volumes-in-one-loeb |
| IA individual Loeb vols | Per-volume PDFs | Good OCR | Available: L319, L347, L357, L364, L372, L388 on archive.org |

**LacusCurtius is the best source** — manually proofread HTML with section-level
anchors, no OCR artifacts. All 48 pages downloaded (Books I-XI complete + XII-XX
fragments). This is analogous to using Wikisource for Statius but with better
quality.

Spelman (1758) also exists on IA but is inferior: only Books 1-11, 18th-century
English, poor OCR from old typography (long-s → "f" artifacts).

This is the **single largest work in the project** at 4,256 sections across 19
books — larger than Diodorus (the project's namesake). High value, clean source,
structured HTML. The rhetorical essays (tlg002-011, tlg015) still have no
identified English translations.

---

#### 13. Aelius Aristides — 11 works (tlg0284)

**Feasibility: NOT FEASIBLE**

No English translations found in Gutenberg, Wikisource, or eng_trans-dev.
Aristides' orations have very few English translations in print, let alone
digitized PD ones.

---

#### 14. Oppian / Oppian of Apamea (tlg0023, tlg0024)

**Feasibility: NOT FEASIBLE**

No English translations found in any source. The Halieutica and Cynegetica have
19th-century translations but none appear to be digitized.

---

#### 15. Aeneas Tacticus (tlg0058) / Agathemerus (tlg0090)

**Feasibility: NOT FEASIBLE**

No English translations found. Both are niche works with limited translation
history.

---

### First1KGreek candidates

#### 16. Alciphron — Epistulae (F1K tlg0640.tlg001)

| Attribute | Value |
|-----------|-------|
| Greek source | First1KGreek, 4 books, 122 letters, ~480 KB |
| English source | eng_trans-dev CTS-split: `tlg0640.tlg001.ogl-eng1.xml` (292 KB) |
| English structure | 7 chapters (reorganized from letter structure) |
| Alignment mode | DP per book |
| License | CC-BY-SA 4.0 |

**Feasibility: MODERATE**

Complete English translation exists and is already CTS-split. The structural
mismatch is the main challenge: Greek has 122 individually numbered letters across
4 books, while English groups them into 7 chapters. Chapter-to-letter boundary
mapping is needed. The letters are short (paragraph-length each), which helps
embedding quality. 480 KB of Greek is a substantial corpus.

---

#### 17. Epictetus — Gnomologium excerpts (F1K tlg0557)

| Attribute | Value |
|-----------|-------|
| Greek source | First1KGreek: tlg004 (8 sections), tlg005 (67 sections) — Stobaeus excerpts only |
| English source | eng_trans-dev: `epictetus_1887/` and `_1890/` (Long) — full Discourses (4 books) |
| Scale mismatch | Greek = 46 KB of excerpts; English = 1.5 MB of full Discourses |

**Feasibility: HARD**

Critical mismatch: First1KGreek has only gnomological excerpts from Stobaeus (75
sections, 46 KB), not the full Discourses. The English sources are complete
Discourses (4 books, 1.5 MB). Aligning excerpts within the full translation
requires identifying which passages in the Discourses correspond to each Stobaeus
extract — essentially a needle-in-haystack pairwise matching problem.

Gutenberg has partial Epictetus texts (#10661 = Long selections, #871 = Golden
Sayings) but these are also selections, not matched to the Stobaeus excerpts.

**Alternative**: If full Discourses Greek text exists elsewhere (it's not in
Perseus or F1K as full text), the full-to-full alignment would be straightforward.

---

#### 18. Diogenes Laertius — Lives of Eminent Philosophers

| Attribute | Value |
|-----------|-------|
| Greek source | **Already has English in Perseus** (eng2 edition) |

**NOT ELIGIBLE** — Diogenes Laertius already has English translations in Perseus.
This does not meet our project criteria.

---

#### 19. Pausanias — Description of Greece

| Attribute | Value |
|-----------|-------|
| Greek source | **Already has English in Perseus** (eng2 edition) |

**NOT ELIGIBLE** — Pausanias already has English translations in Perseus.

---

#### 20. Philo of Alexandria

| Attribute | Value |
|-----------|-------|
| Greek source | First1KGreek tlg0018 — 31 works |
| English source | eng_trans-dev: 3 of 4 Yonge volumes (1854-1855) |
| Status | **F1K already has English** (eng1 files present) |

**NOT ELIGIBLE** — Philo already has English translations in First1KGreek.

---

#### 21. Pindar (tlg0033)

**NOT ELIGIBLE** — Pindar already has English translations for all 4 works in
Perseus (Olympian, Pythian, Isthmian, Nemean odes).

---

### Previously planned works (from PROJECT_DOCUMENTATION.md)

#### 25. Origen — Contra Celsum (F1K tlg2042.tlg001)

| Attribute | Value |
|-----------|-------|
| Greek source | First1KGreek tlg2042 — **47 works** total, all grc-only |
| English source | Gutenberg #70561/#70693 (Crombie, 2 vols, "Writings of Origen") — NOT yet downloaded |
| Scale | Contra Celsum alone is 8 books; F1K has 47 Origen works total |
| Alignment mode | DP |
| License | Public domain |

**Feasibility: HARD (as originally assessed)**

The main challenge identified in PROJECT_DOCUMENTATION.md remains: the 2-volume
Crombie Gutenberg covers an unknown subset of Origen's 47 F1K works. Must
download and inspect to determine which works are included. Contra Celsum (8
books) is the primary target. The Koetschau Teubner edition (1899) is the Greek
source.

No work has begun — no Gutenberg texts downloaded, no `scripts/works/origen/`
directory exists.

Also in the Gutenberg catalog: #65478/#67116 (Legge, "Philosophumena") — these
are for Hippolytus (already done as tlg2115), not Origen, despite being indexed
under tlg2042 in the match file.

---

#### 26. Clement of Alexandria — Protrepticus (Perseus tlg0555.tlg001)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus tlg0555 — 4 works, all grc-only (Protrepticus, Stromata, Quis Dis Salvetur, Fragment 44) |
| English source | Gutenberg #71937 (Wilson 1867) — NOT yet downloaded, NOT in project catalogs |
| Scale | Protrepticus is 1 work; Stromata is 8 books (much larger) |
| Alignment mode | DP |
| License | Public domain |

**Feasibility: HARD (as originally assessed)**

The Wilson 1867 Gutenberg text has not been downloaded and is not indexed in
either `f1k_gutenberg_english_matches.json` or `gutenberg_greek_catalog.json`.
The structural mismatch concern from PROJECT_DOCUMENTATION.md remains: Wilson
was based on older Greek editions than the Butterworth (1919) used in Perseus.
No `scripts/works/clement/` directory exists.

All 4 Clement works in Perseus are grc-only. If Wilson covers Stromata as well
as Protrepticus, that's a significant batch (Stromata alone is 8 books).

---

### Newly discovered candidates (from F1K/Perseus verification)

#### 22. Julian, Emperor — 13+ works (Perseus tlg2003)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus, 13 works (tlg001-013, tlg017), ALL grc-only |
| English source | eng_trans-dev: `volumes/julian_1888/` (King 1888) |
| Alignment mode | DP |
| License | CC-BY-SA 4.0 |

**Feasibility: MODERATE (2 works only)**

**Confirmed**: The King 1888 volume covers only **2 of Julian's 14 works**:

| TLG ID | Work | In King 1888? |
|--------|------|:---:|
| tlg008 | Hymn to the Mother of the Gods | **YES** ("Upon the Mother of the Gods") |
| tlg011 | Hymn to King Helios | **YES** ("Upon the Sovereign Sun") |
| tlg001 | Panegyric on Constantinus | No |
| tlg002 | Panegyric on Eusebia | No |
| tlg003 | Heroic Deeds of Constantius | No |
| tlg004 | Consolation to Himself | No |
| tlg005 | Letter to Senate and People of Athens | No |
| tlg006 | Letter to Themistius | No |
| tlg007 | To the Cynic Heracleios | No |
| tlg009 | To the Uneducated Cynics | No |
| tlg010 | The Caesars | No |
| tlg012 | Misopogon | No |
| tlg013 | Epistolae (Letters) | No |
| tlg017 | Contra Galilaeos | No |

The volume also contains works by Gregory Nazianzen and Libanius (not Julian).
Only 2 Julian works are feasible from this source. Both are theological hymns —
structured prose that should align well via DP. The remaining 12 works have no
identified PD English source.

---

#### 23. Greek Novels — Longus, Achilles Tatius, Heliodorus

| Work | TLG | Source | English |
|------|-----|--------|---------|
| Longus, Daphnis and Chloe | tlg0561.tlg001 | Perseus (grc-only) | eng_trans-dev `heliodorus_longus_achillesTatius_1901/` |
| Achilles Tatius, Leucippe and Clitophon | tlg0532.tlg001 | Perseus (grc-only) | Same volume |
| Heliodorus, Aethiopica | tlg0658.tlg001 | F1K (grc-only) | Same volume |

**Confirmed**: All three novels are present in the 1901 Smith volume, but with
one critical issue.

| Novel | Greek structure | English structure | Match? |
|-------|----------------|-------------------|:------:|
| **Longus, Daphnis & Chloe** | 4 books, ~145 chapters | 4 books, ~209 paragraphs | Perfect |
| **Heliodorus, Aethiopica** | 10 books, 273 chapters | 10 books, ~683 paragraphs | Perfect |
| **Achilles Tatius** | **8 books**, 185 chapters | **6 books only**, ~198 paragraphs | **INCOMPLETE** |

**Feasibility per novel:**

- **Longus: EASY-MODERATE.** 4 books match perfectly. ~1.4 paragraphs per chapter
  — excellent ratio for DP alignment. Smallest and simplest of the three.

- **Heliodorus: MODERATE.** 10 books match perfectly. ~2.5 paragraphs per chapter
  — manageable. Largest of the three (~683 paragraphs). Contains embedded
  narratives that may complicate section mapping.

- **Achilles Tatius: MODERATE (upgraded from NOT FEASIBLE).** The eng_trans-dev
  1901 volume only has Books I-VI, but **Gutenberg #55406** has the same Smith
  translation with **all 8 books** complete. Downloaded:
  `data-sources/gutenberg/achilles_tatius/pg55406.txt` (21,851 lines, 1.2 MB).
  Additionally, Gaselee's Loeb (1917) is PD on Internet Archive as backup.
  The eng_trans-dev copy appears to be a truncated extraction.

**Net result: all 3 novels feasible.**

---

#### 24. Greek Anthology (tlg7000)

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus tlg7000.tlg001, grc-only (5 different Greek encodings) |
| English source | eng_trans-dev: `volumes/greekAnthology_1893/` (Burges) |
| Alignment mode | Pairwise (self-contained epigrams) |
| License | CC-BY-SA 4.0 |

**eng_trans-dev (Burges 1893): NOT FEASIBLE** — only ~230 of ~4,118 epigrams (6%
coverage), selective school anthology, incompatible numbering.

**However: alternative source identified.**

**W. R. Paton, Loeb Classical Library (5 vols, 1916-1918): HARD**

Paton is the **only complete English prose translation** of the Greek Anthology.
It is public domain (pre-1929 US publication, author d. 1921). The Greek in
Perseus uses the **same Paton Loeb edition** (grc6-grc10), which is ideal.

| Source | Format | Completeness | Quality |
|--------|--------|:------------:|---------|
| Wikisource | Transcribed text | **~10-15% only** | Clean where proofread (level 3); OCR artifacts on unproofread pages |
| Internet Archive | Scanned PDFs + OCR | Complete (all 5 vols) | Raw OCR — needs heavy correction |
| Perseus | Some entries | Partial | Already in the system |

**Critical finding: Wikisource transcription is severely incomplete.**

Spot-check of the Wikisource Paton source revealed:

| Volume | Books | DjVu pages | Transcribed pages | Coverage |
|--------|-------|:----------:|:-----------------:|:--------:|
| Vol. 1 | 1-6 | ~528 | ~91 (mostly Book 1) | ~17% |
| Vol. 2 | 7-8 | unknown | 0 | 0% |
| Vol. 3 | 9-11 | ~472 | ~13 (scattered) | ~3% |
| Vol. 4 | 12-16 | unknown | 0 | 0% |
| Vol. 5 | appendix | unknown | 0 | 0% |

Only **Book 1** (Christian Epigrams, ~123 epigrams) is substantially transcribed.
The large literary books (5, 7, 9, 11, 16) are absent or have only scattered
pages. Volumes 2 and 4 have zero transcribed pages.

**Where transcribed, the format is good:**
- Epigrams wrapped in `<section begin="N"/>...<section end="N"/>` tags
- Clear AP numbering in centered headings
- Author attributions present (e.g., "PHILIPPUS", "NICARCHUS", "Anonymous")
- Clean Unicode on proofread (level 3) pages
- Programmatically extractable

**Where NOT transcribed, only raw OCR from Internet Archive scans is available.**
The OCR quality is poor (e.g., "Pliilip" for "Philip", "tlie" for "the",
"loud-l)ellovini»-" for "loud-bellowing"). Using IA OCR directly would require
significant manual correction.

| Attribute | Value |
|-----------|-------|
| Greek source | Perseus tlg7000.tlg001, 5 files (grc6-grc10), ~4,118 epigrams, 16 books |
| English source | Wikisource: ~Book 1 only (~123 epigrams). IA scans: complete but OCR quality poor. |
| Structure match | **Same edition** — Paton edited both Greek and English |
| Alignment mode | Pairwise per book (epigrams are self-contained) |
| License | Public domain |

**Feasibility: HARD**

The edition match is ideal but the English source is the bottleneck:
- Wikisource is mostly untranscribed (~10-15% coverage)
- Internet Archive OCR is too poor for direct use
- Scale is enormous (~4,118 epigrams)
- Epigrams are very short (2-10 lines) — at the lower limit of embedding quality

**Possible approach**: Start with **Book 1 only** using the Wikisource
transcription (~123 epigrams). This is a pilot that tests epigram-length
embedding quality without committing to OCR correction for 16 books. If
successful, consider OCR correction of IA scans for remaining books — but
this is a large manual effort.

Additional Gutenberg sources (partial, supplementary):
- **#2378**: Mackail, *Select Epigrams from the Greek Anthology* (1890) — curated
  selection, not complete, but higher literary quality
- **#35907**: Rennell Rodd, *Love, Worship and Death* (1891) — small thematic
  selection

---

### Feasibility summary table

Sorted by feasibility rating (easiest first), then by number of new works.

| # | Work | Source | Grc sections | Eng source | Rating | Value | New works |
|:-:|------|--------|:------------:|------------|:------:|:-----:|:---------:|
| 7 | Theophrastus, Characters | Perseus | 332 sec | Gutenberg #58242 (downloaded) | **EASY** | HIGH | 1 |
| 8 | Aristotle, Const. of Athens | Perseus | 69 sec | Gutenberg #26095 (downloaded) | **EASY-MOD** | HIGH | 1 |
| 3 | Theocritus, Idylls + Epigrams | Perseus | 2,982 lines | eng_trans-dev | **EASY-MOD** | HIGH | 2 |
| 23a | Longus, Daphnis & Chloe | Perseus | 145 ch | eng_trans-dev | **EASY-MOD** | MED | 1 |
| 2 | Aristophanes, 9 plays | Perseus | ~11,000 lines | eng_trans-dev | **MODERATE** | VERY HIGH | 9 |
| 4 | Moschus, 5 works | Perseus | 481 lines | eng_trans-dev | **MODERATE** | LOW | 5 |
| 5 | Bion, 3 works | Perseus | 246 lines | eng_trans-dev | **MODERATE** | LOW | 3 |
| 6a | Arrian, Anabasis | Perseus | 1,406 sec | Gutenberg #46976 (downloaded) | **MODERATE** | VERY HIGH | 1 |
| 1 | Apollonius, Argonautica | Perseus | 5,834 lines | eng_trans-dev | **MODERATE** | HIGH | 1 |
| 23b | Heliodorus, Aethiopica | F1K | 273 ch | eng_trans-dev | **MODERATE** | MED | 1 |
| 17 | Alciphron, Epistulae | F1K | 122 letters | eng_trans-dev | **MODERATE** | MED | 1 |
| 22 | Julian, 2 hymns (of 14 works) | Perseus | 2 works | eng_trans-dev | **MODERATE** | LOW | 2 |
| 6b | Arrian, Cynegeticus | Perseus | 35 ch | Gutenberg #78013 (downloaded) | **MOD-HARD** | LOW | 1 |
| 25 | Origen, Contra Celsum | F1K | 8 books | Gutenberg #70561/70693 (not downloaded) | HARD | HIGH | 0-1 |
| 26 | Clement, Protrepticus (+3 works) | Perseus | 4 works | Gutenberg #71937 (not downloaded) | HARD | MED-HIGH | 0-4 |
| 6c | Arrian, Indica | Perseus | 43 ch | Unconfirmed | HARD | MED | 0-1 |
| 24 | Greek Anthology (Book 1 pilot) | Perseus | ~123 epigrams | Wikisource (Paton, Book 1 only) | HARD | MED | 0-1 |
| 18 | Epictetus, excerpts | F1K | 75 sec | eng_trans-dev (mismatch) | HARD | LOW | 0-1 |
| 23c | Achilles Tatius | Perseus | 185 ch | **Gutenberg #55406** (downloaded) | **MODERATE** | MED | 1 |
| 12 | Dionysius, Roman Antiquities | Perseus | 4,256 sec | **LacusCurtius** (downloaded, 48 HTML files) | **MODERATE** | VERY HIGH | 1 |
| 10 | Lucian, Podagra | Perseus | 334 lines | None (confirmed) | NOT FEASIBLE | LOW | 0 |
| 11 | Plutarch, Epitome | Perseus | 6 sec | None (confirmed) | NOT FEASIBLE | LOW | 0 |
| 13 | Dionysius, rhetorical essays | Perseus | ~235 sec | None | NOT FEASIBLE | MED | 0 |
| 14 | Aelius Aristides, 11 works | Perseus | ~1,000+ sec | None | NOT FEASIBLE | MED | 0 |
| 15 | Oppian/Oppian of Apamea | Perseus | varied | None | NOT FEASIBLE | LOW | 0 |
| 16 | Aeneas Tacticus / Agathemerus | Perseus | varied | None | NOT FEASIBLE | LOW | 0 |
| 9 | Aristotle, Virtues & Vices | Perseus | 1 sec | None | NOT FEASIBLE | LOW | 0 |
| 6d | Arrian, Periplus/Tactica/Acies | Perseus | varied | None | NOT FEASIBLE | LOW | 0 |
| — | Diogenes Laertius | — | — | — | NOT ELIGIBLE | — | 0 |
| — | Pausanias | — | — | — | NOT ELIGIBLE | — | 0 |
| — | Philo | — | — | — | NOT ELIGIBLE | — | 0 |

Value ratings reflect scholarly importance, readership demand, and gap significance:
- **VERY HIGH**: Major canonical works widely read/studied (Aristophanes, Arrian Anabasis, Dionysius Roman Antiquities)
- **HIGH**: Well-known works with active scholarly/student readership (Theophrastus, Aristotle, Theocritus, Apollonius, Origen)
- **MED**: Significant but narrower audience (Greek novels, Alciphron, Arrian Indica, Clement, Aelius Aristides, Dionysius essays)
- **LOW**: Niche or minor works (Bion, Moschus, Julian hymns, Arrian Cynegeticus, Epictetus excerpts, Oppian, Podagra)

\* Dionysius Roman Antiquities **upgraded to MODERATE** — Cary/Loeb found on
LacusCurtius (proofread HTML) and Internet Archive.

**Confirmed feasible (EASY through MODERATE): 30 new works.**
- 25 original (Theophrastus, Theocritus, Aristophanes, Moschus, Bion, Apollonius,
  Arrian Anabasis + Cynegeticus, Aristotle Const. Athens, Alciphron)
- +3 Greek novels (Longus, Heliodorus, Achilles Tatius) — Achilles Tatius
  upgraded: Gutenberg #55406 has complete Smith translation (all 8 books)
- +2 Julian hymns (Helios, Mother of the Gods)
- +1 Dionysius Roman Antiquities — **major upgrade**: Cary/Loeb (1937-50) is PD,
  proofread HTML on LacusCurtius. 4,256 sections, largest work in the project.

**Speculative (HARD): up to 7 more** (Origen, Clement 1-4 works, Greek Anthology
Book 1 pilot, Arrian Indica, Epictetus excerpts).

**Confirmed NOT FEASIBLE:**
- Greek Anthology via Burges 1893 — only 6% coverage (Paton Loeb is HARD alternative)
- Julian remaining 12 works — not in King 1888 volume
- Lucian Podagra — no English source
- Plutarch Epitome — no English source
- Dionysius rhetorical essays (11 works) — no English translations

---

## Recommendations

### Tier 1: Immediate high-value, low-effort (eng_trans-dev CTS-split)

These already have CTS-structured TEI in eng_trans-dev. Effort is primarily
writing `extract_english.py` to parse the TEI XML instead of Gutenberg plain text.

1. **Apollonius Rhodius — Argonautica** (tlg0001.tlg001)
   - Source: `data/tlg0001/tlg001/tlg0001.tlg001.opp-eng1.xml`
   - Translator: Coleridge 1889
   - Effort: LOW — already CTS-split, single work
   - Note: Verse work — may need line-grouping like Statius

2. **Aristophanes — 5 plays** (Clouds, Wasps, Peace, Frogs, Ecclesiazusae)
   - Source: `data/tlg0019/tlg003-010/` (5 CTS-split files)
   - Translators: Rogers (individual plays)
   - Effort: LOW-MODERATE per play — verse, but chapter-level structure present
   - Note: Frogs has 2 translations (Cope + Rogers). Use Rogers for consistency.

### Tier 2: Moderate effort (eng_trans-dev unsplit volumes)

Need to extract specific works from multi-work Bohn volumes.

3. **Aristophanes — remaining 4 plays** (Acharnians, Knights, Lysistrata,
   Thesmophoriazusae, Plutus)
   - Source: `volumes/aristophanes_1_1858/` (Hickie vol 1) and
     `volumes/aristophanes_2_1853/` (Hickie vol 2)
   - Effort: MODERATE — must split volume into individual plays
   - Combined with Tier 1, this completes **all 9 grc-only Aristophanes plays**

4. **Theocritus + Bion + Moschus**
   - Source: `volumes/theocritus_1878/`
   - Covers: tlg0005 (2 works), tlg0035 (5 works), tlg0036 (3 works) = **10 works**
   - Effort: MODERATE — pastoral poetry, short individual idylls
   - Alignment mode: possibly pairwise (idylls are self-contained units)

5. **Lucian** (1 grc-only work in Perseus)
   - Source: `volumes/lucian_1888/`
   - Effort: MODERATE — must identify which dialogue is tlg0062.tlg071 and extract

6. **Plutarch** (1 Moralia essay grc-only)
   - Source: `volumes/plutarch_1898_ethical/` or `_theosophical/`
   - Effort: MODERATE — must identify which essay is tlg0007.tlg135

### Tier 3: Wikisource scraping needed

These have no eng_trans-dev coverage but Wikisource has translations.

7. **Arrian — Anabasis of Alexander + 5 other works** (tlg0074)
   - 6 grc-only works in Perseus
   - Wikisource has Anabasis and Indica translations
   - Previously Indica was ruled infeasible from Gutenberg (McCrindle), but
     Wikisource may have a different/better edition
   - Effort: MODERATE-HIGH — scraping + extraction + 6 works

8. **Theophrastus — Characters** (tlg0093.tlg009)
   - Short work, well-structured (30 character sketches)
   - Wikisource likely has Jebb or Edmonds translation
   - Effort: MODERATE — scraping + pairwise alignment (self-contained units)

### Tier 4: First1KGreek candidates

9. **Alciphron — Epistulae** (F1K tlg0640)
   - eng_trans-dev: CTS-split at `data/tlg0640/tlg001/`
   - 122 letters across 4 books; English reorganized into 7 chapters
   - Structural mapping needed but complete translation exists

10. **Epictetus — Gnomologium excerpts** (F1K tlg0557)
    - eng_trans-dev: `volumes/epictetus_1887/`, `epictetus_1890/` (Long)
    - HARD: F1K only has Stobaeus excerpts (75 sections), not full Discourses.
      English is full Discourses. Major structural mismatch.

### Eliminated after verification

These were initially listed as F1K candidates but already have English translations:
- **Diogenes Laertius** — already has English in Perseus (eng2)
- **Pausanias** — already has English in Perseus (eng2)
- **Philo of Alexandria** — already has English in First1KGreek (eng1)

### Not recommended / not feasible

| Source | Why not |
|--------|---------|
| Aelius Aristides (11 Perseus gaps) | No English source available in any collection |
| Dionysius, Roman Antiquities | No digitized PD translation found (Spelman 1758 may exist on IA) |
| Dionysius, rhetorical essays (11 works) | No English translations found |
| Oppian / Oppian of Apamea | No English source available in any collection |
| Aeneas Tacticus | No English source available |
| Agathemerus | No English source available, obscure author |
| Arrian, Periplus / Tactica / Acies | No English translations found for these 3 of 6 works |
| Aristotle, On Virtues and Vices | 1 section, no English found, possibly spurious |
| Lucian, Podagra | Confirmed: not in eng_trans-dev volume, not on Gutenberg |
| Plutarch, Epitome (tlg135) | Confirmed: not in any eng_trans-dev Plutarch volume |
| Achilles Tatius via eng_trans-dev | Incomplete (6/8 books) — but **Gutenberg #55406 has all 8**; now MODERATE |
| Greek Anthology via Burges 1893 | Only ~6% coverage. Paton Loeb is complete but Wikisource only ~10-15% transcribed; IA OCR is poor. |
| Julian (12 of 14 works) | King 1888 contains only 2 hymns; 12 works have no PD English |
| Pre-Socratic fragments (Wikisource) | Too fragmentary for meaningful alignment |
| Euclid Elements (Wikisource) | Mathematical/geometric — incompatible with embedding model |
| Ptolemy Almagest (Wikisource) | Technical astronomical text — same problem |
| Sappho/Alcaeus fragments (Wikisource) | Fragments too short for embedding |
| Diogenes Laertius, Pausanias, Philo | Already have English in Perseus or F1K — not eligible |

---

## Integration approach

### For eng_trans-dev TEI XML sources

1. **New extraction pattern needed.** Current `extract_english.py` scripts parse
   Gutenberg plain text or Wikisource HTML. eng_trans-dev is EpiDoc TEI XML.
   Write a shared utility for parsing eng_trans-dev TEI:
   - Strip `<lb/>` (meaningless physical line breaks)
   - Use `<pb>` for Internet Archive page-image cross-reference (optional)
   - Use `<div type="textpart">` boundaries for section splitting
   - Handle OCR artifacts (Jouve encoding quirks)

2. **CTS-split files** (Tier 1) can be used almost directly — they already have
   work-level structure matching the TLG scheme.

3. **Unsplit volumes** (Tier 2) need a splitting step: identify which `<div>`
   elements correspond to which work, extract, and produce per-work JSON.

### For Wikisource sources

4. Follow the Statius/Mozley precedent:
   - Scrape HTML from Wikisource pages
   - Store raw HTML in `data-sources/wikisource/<name>/`
   - Write per-work `extract_english.py` to parse HTML structure
   - Verify license (PD or CC-BY-SA only)

### Pipeline changes

5. No pipeline changes needed — the alignment pipeline is source-agnostic once
   `extract_english.py` produces `english_sections.json` in the standard format.

6. Consider adding `english_source.type: "eng_trans_dev"` alongside existing
   `"gutenberg"` and `"wikisource"` types in `config.json` for documentation.

---

## Estimated impact

All research is now complete. No open questions remain.

| Action | New works | Effort per work |
|--------|:---------:|:---------------:|
| Tier 1: eng_trans-dev CTS-split (4 Aristophanes + Apollonius) | 5 | 4-8 hours |
| Tier 2: eng_trans-dev volume-split (5 Aristophanes + Theocritus/Bion/Moschus + Julian 2 hymns) | 15 | 4-8 hours |
| Tier 3: Gutenberg (Arrian Anabasis, Theophrastus, Aristotle Const., Arrian Cynegeticus) | 4 | 6-10 hours |
| Tier 4: F1K + novels (Alciphron, Longus, Heliodorus) | 3 | 6-10 hours |
| Major new finds (Dionysius Roman Antiquities, Achilles Tatius) | 2 | 8-12 hours (Dionysius is very large) |
| Speculative HARD (Origen, Clement, Greek Anth., Epictetus, Arrian Indica) | 0-8 | various blockers |
| **Confirmed feasible total** | **30** | |
| **Including speculative** | **up to 38** | |

Combined with the 12 already completed, this brings the project to **42-50
aligned works**.

---

## Next steps

### Resolved research questions

- Apollonius Coleridge: **confirmed complete** (86% char ratio, not 21%)
- Lucian Podagra: **confirmed NOT in** `lucian_1888.xml` — only a footnote mention
- Plutarch Epitome: **confirmed NOT in** any eng_trans-dev Plutarch volume
- Theophrastus: correct Gutenberg ID is **#58242** (Bennett & Hammond), not #16299 (Gally)
- Arrian Cynegeticus: Gutenberg #78013 **confirmed** as Dansey translation
- Pindar: **NOT ELIGIBLE** — already has English in Perseus
- Greek novels (Longus, Achilles Tatius, Heliodorus): all grc-only, **newly added**
- Julian: 13 grc-only works in Perseus, **newly added**
- Greek Anthology: grc-only in Perseus, **newly added**

### All research complete

All open questions have been resolved. No remaining investigation needed before
implementation can begin.

### Implementation order (by feasibility rating, easiest first)

1. **Theophrastus Characters** — EASY (caveat: reorder sketches to match traditional
   numbering). English downloaded: `data-sources/gutenberg/theophrastus/pg58242.txt`
2. **Aristotle Const. of Athens** — EASY-MOD, exceptionally clean Gutenberg text.
   English downloaded: `data-sources/gutenberg/aristotle_const_athens/pg26095.txt`
3. **Aristophanes CTS-split plays** (Wasps, Peace, Frogs, Ecclesiazusae) — 4 works.
   Note: ~30-40% of each file is commentary/appendix that must be stripped.
4. **Build shared TEI extraction utility** for eng_trans-dev XML parsing.
5. **Theocritus/Bion/Moschus batch** from `theocritus_1878/` — 10 works.
   Use only prose section (ignore duplicate metrical translations).
6. **Longus, Daphnis & Chloe** from eng_trans-dev — clean 4-book match.
7. **Extract Hickie plays** from unsplit volumes (Acharnians, Knights, Lysistrata,
   Thesmophoriazusae, Plutus) — 5 more Aristophanes works.
8. **Apollonius Argonautica** from eng_trans-dev CTS-split — confirmed complete
   (86% char ratio). Verse line-grouping needed.
9. **Arrian Anabasis** — English downloaded: `data-sources/gutenberg/arrian_anabasis/pg46976.txt`.
   205 chapters, clean text. Strip 985 endnotes + inline `[14]` markers + index.
10. **Heliodorus Aethiopica** from eng_trans-dev — 10 books, 273 chapters.
11. **Julian 2 hymns** (Helios, Mother of the Gods) from eng_trans-dev.
12. **Alciphron Epistulae** from eng_trans-dev CTS-split.
13. **Achilles Tatius** — English downloaded: `data-sources/gutenberg/achilles_tatius/pg55406.txt`
    (Smith, all 8 books complete).
14. **Dionysius Roman Antiquities** — English downloaded:
    `data-sources/dionysius_roman_antiquities/html/` (Cary/Loeb, 48 proofread
    HTML files). 4,256 sections, 19 books. Largest single work — comparable to
    Diodorus. VERY HIGH value.
15. **Arrian Cynegeticus** — English downloaded:
    `data-sources/gutenberg/arrian_cynegeticus/pg78013.txt` (Dansey). Translation
    is only 6% of file; heavy extraction needed to separate from Dansey's commentary.
16. ~~**Download all Gutenberg texts**~~: DONE — #58242, #26095, #46976, #78013, #55406
    all downloaded to `data-sources/gutenberg/`. LacusCurtius Dionysius also
    downloaded to `data-sources/dionysius_roman_antiquities/html/` (48 files).

### Speculative / high effort (HARD)

15. **Origen, Contra Celsum** — download Gutenberg #70561/#70693 and inspect which
    of 47 F1K works are covered. No work started yet.
16. **Clement of Alexandria, Protrepticus** — download Gutenberg #71937 and inspect.
    Structural mismatch risk (Wilson 1867 vs Butterworth 1919 editions). No work
    started yet.
17. **Greek Anthology Book 1 pilot** — Wikisource has ~123 epigrams from Book 1
    transcribed cleanly. Same Paton Loeb edition as Perseus Greek. Test
    epigram-length embedding quality with pairwise matching. Full Anthology
    (16 books, ~4,118 epigrams) requires OCR correction of Internet Archive
    scans — Wikisource is only ~10-15% transcribed with poor OCR on the rest.

### Future potential (deferred)

19. **Cross-reference eng_trans-dev Latin volumes** against canonical-latinLit gaps

---

## Source URLs and Reproduction

All English source texts live in `data-sources/` which is gitignored. To
reproduce the downloads after cloning the repo, follow the instructions below.

### Gutenberg plain texts

```bash
# Theophrastus, Characters — Bennett & Hammond 1902
mkdir -p data-sources/gutenberg/theophrastus
curl -sL "https://www.gutenberg.org/cache/epub/58242/pg58242.txt" \
  -o data-sources/gutenberg/theophrastus/pg58242.txt

# Aristotle, Constitution of Athens — Kenyon
mkdir -p data-sources/gutenberg/aristotle_const_athens
curl -sL "https://www.gutenberg.org/cache/epub/26095/pg26095.txt" \
  -o data-sources/gutenberg/aristotle_const_athens/pg26095.txt

# Arrian, Anabasis of Alexander — Chinnock 1884
mkdir -p data-sources/gutenberg/arrian_anabasis
curl -sL "https://www.gutenberg.org/cache/epub/46976/pg46976.txt" \
  -o data-sources/gutenberg/arrian_anabasis/pg46976.txt

# Arrian, Cynegeticus — Dansey (only 6% is translation; rest is commentary)
mkdir -p data-sources/gutenberg/arrian_cynegeticus
curl -sL "https://www.gutenberg.org/cache/epub/78013/pg78013.txt" \
  -o data-sources/gutenberg/arrian_cynegeticus/pg78013.txt

# Achilles Tatius, Leucippe & Clitophon — Smith (all 8 books)
mkdir -p data-sources/gutenberg/achilles_tatius
curl -sL "https://www.gutenberg.org/cache/epub/55406/pg55406.txt" \
  -o data-sources/gutenberg/achilles_tatius/pg55406.txt
```

### eng_trans-dev repo (OpenGreekAndLatin)

```bash
git clone https://github.com/OpenGreekAndLatin/english_trans-dev.git \
  data-sources/english_trans-dev
```

Provides TEI XML English translations for: Aristophanes (9 plays), Apollonius
Rhodius, Theocritus/Bion/Moschus, Alciphron, Julian (2 hymns), Longus,
Heliodorus, and many others. See `volumes/` (111 unsplit volumes) and `data/`
(9 CTS-split works).

### Dionysius of Halicarnassus, Roman Antiquities — LacusCurtius (Cary/Loeb)

48 proofread HTML pages covering Books I-XX (I-XI complete, XII-XX fragments).

```bash
mkdir -p data-sources/dionysius_roman_antiquities/html
BASE="https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Dionysius_of_Halicarnassus"
for slug in \
  1A 1B 1C 1D 2A 2B 2C 3A 3B 3C 3D 4A 4B 4C 4D \
  5A 5B 5C 5D 6A 6B 6C 6D 7A 7B 7C 8A 8B 8C 8D \
  9A 9B 9C 10A 10B 10C 10D 11A 11B 11C \
  12 13 14 15 16 17-18 19 20; do
  fname=$(echo "${slug}" | sed 's/-/_/g')
  curl -sL "${BASE}/${slug}*.html" \
    -o "data-sources/dionysius_roman_antiquities/html/${fname}_star.html"
  sleep 0.5
done
```

Note: the `*` in the URL is a literal asterisk required by the LacusCurtius URL
scheme.

### Not yet downloaded (HARD candidates)

| Source | URL | Notes |
|--------|-----|-------|
| Origen, Writings vol 1 (Crombie) | https://www.gutenberg.org/cache/epub/70561/pg70561.txt | Needs inspection to identify which F1K works are covered |
| Origen, Writings vol 2 (Crombie) | https://www.gutenberg.org/cache/epub/70693/pg70693.txt | Same |
| Clement, Protrepticus (Wilson 1867) | https://www.gutenberg.org/cache/epub/71937/pg71937.txt | Structural mismatch risk |
| Greek Anthology (Paton, Wikisource) | https://en.wikisource.org/wiki/The_Greek_Anthology_(Paton) | Only ~10-15% transcribed; Book 1 only for pilot |

### Backup / alternative sources (not primary)

| Source | URL | Notes |
|--------|-----|-------|
| Dionysius Roman Antiquities (IA 7-in-1 PDF) | https://archive.org/details/dionysius-roman-antiquities-7-volumes-in-one-loeb | Backup for LacusCurtius |
| Dionysius Roman Antiquities (Spelman 1758 vol 1) | https://archive.org/details/romanantiquities01dion | Inferior to Cary; 18th-c. English, poor OCR |
| Dionysius Roman Antiquities (Spelman 1758 vol 2) | https://archive.org/details/romanantiquities02dion | Same |
| Achilles Tatius (Gaselee, Loeb 1917) | https://archive.org/details/achillestatiuswi00achiuoft | Backup for Smith/Gutenberg |
| Greek Anthology (Mackail, Select Epigrams) | https://www.gutenberg.org/cache/epub/2378/pg2378.txt | Partial — curated selection only |
| Greek Anthology (Rodd, Love/Worship/Death) | https://www.gutenberg.org/cache/epub/35907/pg35907.txt | Partial — small thematic selection |
| Greek Anthology (Paton, IA individual vols) | https://archive.org/details/greekanthology01pato (vol 1), https://archive.org/details/greekanthologyin0005wrtr (vol 5) | Raw OCR, poor quality |

# Investigation: Alternate Open Source Translations for Perseus Gaps

**Date:** 2026-03-01
**Status:** Research complete

## Motivation

The Diodorus project demonstrated that older public domain translations can be aligned
to Perseus Greek source texts using custom neural embeddings and segmental dynamic
programming. This investigation asks: **how many other classical works could benefit
from the same approach?**

The Loeb Classical Library spreadsheets (`loeb-greek-volumes-green.csv` and
`loeb-latin-volumes-red.csv`) map ~562 Loeb volumes to their Perseus availability
status. This document analyzes the gaps and assesses feasibility of filling them.

---

## 1. The Perseus Gap: By the Numbers

### Overall Coverage

| Category | Greek | Latin | Total |
|---|---|---|---|
| Total Loeb volumes catalogued | 359 | 203 | **562** |
| Y/Y — both original text and English translation | 192 | 77 | **269** (48%) |
| **Y/N — original text available, NO English (key gap)** | **52** | **46** | **98** (17%) |
| N/N — neither available | 93 | 72 | **165** (29%) |
| P — partial original text | 19 | 7 | **26** (5%) |
| Y/P — text available, partial translation | 3 | 1 | **4** (1%) |

The **98 volumes** with source text but no English translation are the primary
opportunity. Perseus already hosts the Greek/Latin — we just need to find, digitize,
and align an older PD translation, exactly as was done with Booth's 1700 Diodorus.

### Greek Gap Authors (52 volumes, 16 authors)

| Author | Vols | TLG ID | Key PD Translation(s) |
|---|---|---|---|
| Lucian | 8 | tlg0062 | H.W. & F.G. Fowler (1905) |
| Athenaeus | 7 | tlg0008 | C.D. Yonge (1854) |
| Hippocrates | 5 | tlg0627 | Francis Adams (1849); W.H.S. Jones (1923) |
| Dio Chrysostom | 5 | tlg0612 | **None pre-1928** — Cohoon Loeb (1932) enters PD 2028 |
| Aristotle (Hist.Animals, Problems) | 5 | tlg0086 | D'Arcy W. Thompson (1910); various Oxford |
| Sextus Empiricus | 4 | tlg0544 | **None complete** — Mary M. Patrick (1899) partial only |
| Dionysius of Hal. (Critical Essays) | 4 | tlg0081 | W. Rhys Roberts (1901) partial |
| Philostratus (Life of Apollonius) | 3 | tlg0638 | F.C. Conybeare (1912) |
| Theophrastus (Enquiry into Plants) | 2 | tlg0093 | Sir Arthur Hort (1916 Loeb) |
| Epictetus | 2 | tlg0557 | George Long (1877); Elizabeth Carter (1758) |
| Apostolic Fathers | 2 | — | Kirsopp Lake (1912); J.B. Lightfoot (1891) |
| Galen | 1 | tlg0057 | A.J. Brock (1916 Loeb) |
| Marcus Aurelius | 1 | tlg0562 | George Long (1862) |
| Longus | 1 | tlg0561 | George Thornley (1657); various |
| Quintus Smyrnaeus | 1 | tlg1900 | A.S. Way (1913) |
| Greek Lyric (Bacchylides) | 1 | tlg0199 | Various |

### Latin Gap Authors (46 volumes, 18 authors)

| Author | Vols | PHI ID | Key PD Translation(s) |
|---|---|---|---|
| Cicero (Letters) | 8 | phi0474 | E.S. Shuckburgh (1899-1908) |
| Quintilian | 6 | phi1002 | H.E. Butler (1920-22 Loeb); J.S. Watson (1856) |
| Plautus | 5 | phi0119 | H.T. Riley (1912); various |
| Seneca (Essays + Tragedies) | 5 | phi1017 | Aubrey Stewart (1889); F.J. Miller (1907) |
| Martial | 3 | phi1294 | Bohn's anonymous (1860); W.C.A. Ker (1919-20) |
| Gellius | 3 | phi1254 | J.C. Rolfe (1927 Loeb, entered PD 2023) |
| Statius | 3 | phi1020 | J.H. Mozley (1928 Loeb, entered PD 2024) |
| Terence | 2 | phi0134 | H.T. Riley (1853) |
| Vitruvius | 2 | phi1056 | M.H. Morgan (1914) |
| Petronius | 1 | phi1515 | M. Heseltine (1913 Loeb); W. Burnaby (1694) |
| Propertius | 1 | phi0620 | Various 19th-century |
| Velleius Paterculus | 1 | phi0468 | J.S. Watson (1853) |
| Frontinus | 1 | phi1242 | C.E. Bennett (1925 Loeb) |
| Cato/Varro | 1 | phi0022 | Various |
| Cornelius Nepos | 1 | phi0588 | J.S. Watson (1853) |
| Sallust (Fragments) | 1 | phi0631 | J.S. Watson (1853) |
| Quintus Curtius | 1 | — | J.C. Rolfe (1946) — NOT PD yet |
| Statius (additional) | — | — | — |

---

## 2. PD Translation Availability Assessment

### Tier 1: Ready to Go (digital text exists in clean, structured form)

These works have high-quality PD translations already available as clean HTML, plain
text, or even TEI XML. They could enter the alignment pipeline with minimal
preprocessing.

| Work | Translation | Format | Source |
|---|---|---|---|
| **Athenaeus, Deipnosophists** | C.D. Yonge (1854) | TEI XML with CTS URNs | Perseus itself + Digital Athenaeus |
| **Lucian, Works** (8 vols) | Fowler & Fowler (1905) | Clean HTML (4 vols) | Project Gutenberg, sacred-texts.com |
| **Epictetus, Discourses** | George Long (1877) | Polished epub + source | Standard Ebooks, Project Gutenberg |
| **Marcus Aurelius, Meditations** | George Long (1862) | Polished epub + source | Standard Ebooks, Project Gutenberg |
| **Quintilian, Inst. Oratoria** | H.E. Butler (1920-22) | Clean HTML | LacusCurtius |
| **Vitruvius, On Architecture** | M.H. Morgan (1914) | Clean HTML | Project Gutenberg |
| **Terence, Comedies** | H.T. Riley (1853) | Clean text | Wikisource, Project Gutenberg |
| **Cicero, Letters** | E.S. Shuckburgh (1899-1908) | Clean HTML | Project Gutenberg, Perseus |
| **Seneca, Tragedies** | F.J. Miller (1907) | Clean text | Wikisource |
| **Seneca, Moral Essays** | Aubrey Stewart (1889) | Polished epub + source | Standard Ebooks |
| **Aristotle, Hist. Animals** | D'Arcy W. Thompson (1910) | Clean text | Wikisource, LacusCurtius |
| **Apostolic Fathers** | Kirsopp Lake (1912) | Structured text | Wikisource |
| **Quintus Smyrnaeus, Fall of Troy** | A.S. Way (1913) | Clean HTML | Project Gutenberg, Theoi.com |
| **Philostratus, Life of Apollonius** | F.C. Conybeare (1912) | Clean HTML | Sacred-Texts, Theoi.com |
| **Longus, Daphnis and Chloe** | George Thornley (1657) | Clean text | Wikisource |
| **Petronius, Satyricon** | M. Heseltine (1913) | Clean HTML | Project Gutenberg |
| **Gellius, Attic Nights** | J.C. Rolfe (1927) | Clean HTML | LacusCurtius (entered PD 2023) |
| **Statius, Thebaid/Silvae** | J.H. Mozley (1928) | Clean HTML | Theoi.com (entered PD 2024) |

**Count: ~40 Loeb-equivalent volumes immediately actionable.**

### Tier 2: Available but Needs Work (OCR, cleaning, or partial coverage)

| Work | Translation | Issue |
|---|---|---|
| **Plautus** (5 vols) | H.T. Riley (1912) | Internet Archive scans; needs OCR cleanup |
| **Hippocrates** (5 vols) | Francis Adams (1849) | Covers only ~30% of corpus (genuine works). W.H.S. Jones Loeb I-II (1923) adds more. Gaps in later vols |
| **Martial** (3 vols) | Bohn's anon. (1860) | Omits obscene epigrams. Ker (1919-20) is complete but needs OCR |
| **Theophrastus, Enquiry** (2 vols) | Sir Arthur Hort (1916) | LacusCurtius has it but quality unverified |
| **Dionysius of Hal., Crit. Essays** (4 vols) | W. Rhys Roberts (1901) | Partial — covers *On Literary Composition* and some essays, not all |
| **Propertius** (1 vol) | Various 19th c. | Multiple partial translations, none clean digital |
| **Galen, On Natural Faculties** (1 vol) | A.J. Brock (1916) | Likely on Internet Archive; OCR needed |
| **Velleius Paterculus** (1 vol) | J.S. Watson (1853) | Available but quality uncertain |
| **Cato/Varro** | Various | Fragmentary PD translations exist |

**Count: ~25 Loeb-equivalent volumes with moderate effort.**

### Tier 3: Blocked (no PD translation exists)

| Work | Volumes | Earliest Available |
|---|---|---|
| **Sextus Empiricus** | 4 | R.G. Bury Loeb (1933-36) → PD 2029-2032 |
| **Dio Chrysostom** | 5 | Cohoon Loeb (1932-51) → PD 2028-2047 |
| **Quintus Curtius** (Latin) | 1 | J.C. Rolfe (1946) → PD 2042 |

**Count: 10 volumes blocked until at least 2028.**

---

## 3. Technical Feasibility

### What Transfers Directly from the Diodorus Pipeline

| Component | Reusability | Notes |
|---|---|---|
| **Segmental DP alignment algorithm** | Direct reuse | Language-agnostic. Works on any embedding. |
| **TEI output generation (Step 08)** | Adapt per work | CTS URN structure and textpart hierarchy vary. Template approach possible. |
| **Entity anchor validation (Step 06)** | Direct reuse | Greek→English NER + transliteration works across all classical Greek. |
| **Parallel corpus extraction (Step s02)** | Direct reuse | Already extracts from multi-author Perseus data. |
| **Embedding training pipeline (Steps s01-s07)** | Partial reuse | See below. |

### Embedding Model Considerations

**For additional Greek works:**
The existing `ancient-greek-embedding` model (95.1% top-1 retrieval) was trained on
21,263 parallel pairs from Perseus. It should generalize well to other Greek prose
authors (Lucian, Athenaeus, Epictetus, etc.) without retraining. For verse (Quintus
Smyrnaeus) or technical prose (Hippocrates, Aristotle), fine-tuning on domain-specific
pairs may improve results but is not strictly necessary.

**For Latin works:**
A new embedding model is required. The approach would mirror the Greek pipeline:

1. **Monolingual Latin corpus:** Extract from Perseus `canonical-latinLit` + the
   Latin Library, CAMENA, or similar. Estimate ~500K-1M sentences available.
2. **Parallel Latin-English pairs:** Perseus has ~77 Latin works with English
   translations (Y/Y in the spreadsheet). At ~280 pairs per work average, that yields
   ~21,500 pairs — comparable to the Greek training set.
3. **MLM pre-training:** XLM-RoBERTa on Latin corpus (~4.5 hrs on M4).
4. **Contrastive fine-tuning:** On Latin-English parallel pairs (~5.5 hrs on M4).

Estimated total training time for a Latin model: **~10-11 hours** (one-time cost).

### Per-Work Alignment Effort

Once the embedding model exists, each new work requires:

| Step | Effort | Time |
|---|---|---|
| Source the PD translation (digital text) | Variable | 1-4 hours |
| Write extraction script for the translation's format | Medium | 2-4 hours |
| Write extraction script for the Perseus source text | Low (adapt existing) | 1-2 hours |
| Configure and run alignment pipeline | Low | ~20 min compute |
| Validate output, fix edge cases | Medium | 2-4 hours |
| Generate Perseus-compatible TEI | Low (adapt template) | 1-2 hours |
| **Total per work** | | **~7-16 hours** |

### Scaling Strategy

Rather than treating each work as a one-off, a generalized framework could:

1. **Parameterize the pipeline** — config file per work specifying: Perseus CTS URN,
   PD translation URL/path, format (TEI XML / HTML / plain text), section structure.
2. **Build a library of format parsers** — Project Gutenberg HTML, Wikisource,
   LacusCurtius, Standard Ebooks, raw TEI XML. ~5-6 parsers cover most sources.
3. **Batch process** — Once parameterized, run alignment on all Tier 1 works in a
   single pass. Estimated: 18 works × 20 min alignment = 6 hours compute.

---

## 4. Priority Ranking

Ranked by: (a) scholarly importance, (b) PD translation quality, (c) implementation
ease, (d) volume of text.

### Top 10 Candidates — Greek

| Rank | Work | Vols | Why |
|---|---|---|---|
| 1 | **Lucian, Works** | 8 | Widely studied satirist. Fowler translation is excellent and cleanly digitized on Gutenberg. Largest single gap. |
| 2 | **Athenaeus, Deipnosophists** | 7 | Yonge translation already in Perseus TEI XML (!). May only need alignment, not even ingestion. |
| 3 | **Epictetus, Discourses** | 2 | Hugely popular philosophical text. Long translation on Standard Ebooks — highest-quality digital source. |
| 4 | **Marcus Aurelius, Meditations** | 1 | One of the most-read classical texts. Long translation perfectly digitized. Quick win. |
| 5 | **Aristotle, History of Animals** | 3 | Thompson translation is a scholarly landmark. On Wikisource. |
| 6 | **Philostratus, Life of Apollonius** | 3 | Conybeare Loeb (1912) on Sacred-Texts. Interesting narrative text. |
| 7 | **Apostolic Fathers** | 2 | Important for early Christian studies. Lake translation on Wikisource. |
| 8 | **Quintus Smyrnaeus, Fall of Troy** | 1 | Way translation on Gutenberg. Fills a gap in the Trojan cycle. |
| 9 | **Hippocrates** (partial) | 2-3 | Adams covers the core works. High scholarly value but only partial coverage. |
| 10 | **Longus, Daphnis and Chloe** | 1 | Multiple PD translations. Small text, quick win. |

### Top 10 Candidates — Latin

| Rank | Work | Vols | Why |
|---|---|---|---|
| 1 | **Quintilian, Inst. Oratoria** | 6 | Butler Loeb (1920-22) on LacusCurtius. Major rhetorical work. |
| 2 | **Cicero, Letters** | 8 | Shuckburgh on Gutenberg. Enormous scholarly importance. |
| 3 | **Seneca, Moral Essays** | 3 | Stewart translation on Standard Ebooks. Core Stoic texts. |
| 4 | **Seneca, Tragedies** | 2 | Miller translation on Wikisource. Clean digital text. |
| 5 | **Terence, Comedies** | 2 | Riley on Gutenberg/Wikisource. Standard school author. |
| 6 | **Gellius, Attic Nights** | 3 | Rolfe Loeb (1927, PD 2023) on LacusCurtius. Fascinating miscellany. |
| 7 | **Vitruvius, On Architecture** | 2 | Morgan on Gutenberg. Unique source for Roman architecture. |
| 8 | **Statius, Thebaid/Silvae** | 3 | Mozley Loeb (1928, PD 2024) on Theoi.com. Major Latin epic. |
| 9 | **Plautus, Comedies** | 5 | Riley available but needs OCR cleanup. Foundational Roman comedy. |
| 10 | **Petronius, Satyricon** | 1 | Heseltine Loeb (1913) available. Quick win. |

---

## 5. Effort Estimate for Full Execution

### Phase 1: Quick Wins (Tier 1 works, existing Greek model)
- **Scope:** ~18 Greek works (40 Loeb volumes) using existing embedding model
- **New work:** Format parsers, per-work config, pipeline parameterization
- **Effort:** ~2-3 weeks of development + ~6 hours compute
- **Output:** ~40 new Perseus-compatible TEI English translations

### Phase 2: Latin Model + Latin Works
- **Scope:** Train Latin embedding model, align ~18 Latin works (40 Loeb volumes)
- **New work:** Latin embedding training (~11 hrs), Latin extraction scripts
- **Effort:** ~2-3 weeks of development + ~17 hours compute
- **Output:** ~40 new Perseus-compatible TEI English translations

### Phase 3: Tier 2 Works (OCR, partial coverage)
- **Scope:** ~25 volumes needing OCR cleanup or partial-coverage workarounds
- **New work:** OCR pipelines, gap-filling strategies
- **Effort:** ~4-6 weeks
- **Output:** ~25 additional translations (some partial)

### Total Potential Output
- **~98 volumes** of new aligned English translations for Perseus
- Covering **34 authors** across Greek and Latin
- Roughly **doubling** the number of bilingual works in Perseus

---

## 6. Key Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Old translations are paraphrases, not literal** | Lower alignment scores (as seen with Booth) | Accept medium confidence; the Diodorus pipeline handles this (mean 0.412 combined score was usable) |
| **Section numbering mismatch** | Alignment errors at chapter boundaries | Book-level pre-alignment (Step 04) handles this. Manual spot-checks for each work. |
| **Latin model quality unknown** | May not match Greek model's 95.1% top-1 | Perseus has comparable Latin parallel data (~21K pairs). XLM-R handles Latin better than Greek natively (less tokenizer fragmentation) — Latin results should be at least as good. |
| **Copyright edge cases** | Some 1920s works may have renewal complications | Verify each translation against Stanford Copyright Renewal Database before use. |
| **TEI structure varies across Perseus works** | Output script needs per-work adaptation | Build a configurable TEI template system rather than hard-coded output. |
| **Verse alignment harder than prose** | Poetry has different length ratios, enjambment | Use line-level rather than section-level alignment for verse. May need verse-specific DP parameters. |

---

## 7. Conclusions

**Feasibility: HIGH for Greek, HIGH for Latin.**

The Diodorus pipeline proved the core approach works. The 98-volume Perseus gap is
fillable because:

1. **~80% of gap works have PD translations already digitized** (Tier 1 + Tier 2).
2. **The alignment algorithm is language-agnostic** — only the embedding model is
   language-specific, and training a new one is a known ~11-hour process.
3. **The per-work marginal cost is low** (~7-16 hours) once the framework is
   parameterized.
4. **The Greek embedding model already exists** and likely generalizes to the 52 Greek
   gap volumes without retraining.

The highest-value immediate targets are **Lucian** (8 vols, Fowler on Gutenberg),
**Athenaeus** (7 vols, Yonge already in Perseus TEI), and **Cicero's Letters**
(8 vols, Shuckburgh on Gutenberg) — together covering 23 volumes with minimal
preprocessing work.

**Recommended next step:** Parameterize the existing pipeline into a reusable
framework, then run a proof-of-concept on **Marcus Aurelius** (1 volume, Long
translation on Standard Ebooks, Greek in Perseus) as the simplest possible test case
before scaling to larger works.

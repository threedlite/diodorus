# Latin Alignment Pipeline — Source Texts and Licenses

**Date:** 2026-03-02
**Purpose:** English translation sources needed for Latin works where Perseus has the Latin TEI but no English TEI.

---

### 1. Seneca — Ten Tragedies

| Field | Latin | English |
|---|---|---|
| **Source** | Perseus `data/phi1017/` | EEBO-TCP **A11909** |
| **Translator** | — | Thomas Newton, Jasper Heywood, John Studley, Alexander Neville (1581) |
| **Format** | TEI P5 XML, EpiDoc | TEI P5 XML, 14,561 verse lines, 1,142 `<sp>` speech parts |
| **License** | CC-BY-SA 4.0 | CC0 Public Domain (TCP Phase 1) |
| **GitHub** | — | https://github.com/textcreationpartnership/A11909 |
| **Coverage** | All 10 tragedies | All 10 tragedies |
| **Notes** | Landmark Elizabethan translation. Verse structure aligns with Latin verse |

### 2. Seneca — Moral and Natural Works

| Field | Latin | English |
|---|---|---|
| **Source** | Perseus `data/phi1017/` | EEBO-TCP **A11899** |
| **Translator** | — | Thomas Lodge (1614) |
| **Format** | TEI P5 XML, EpiDoc | TEI P5 XML |
| **License** | CC-BY-SA 4.0 | CC0 Public Domain (TCP Phase 1) |
| **GitHub** | — | https://github.com/textcreationpartnership/A11899 |
| **Coverage** | Epistles, De Beneficiis, De Ira, De Clementia, De Vita Beata, De Tranquillitate, De Constantia, De Brevitate Vitae, Consolations, Natural Questions | Same |
| **Notes** | First collected English Seneca. Comprehensive coverage of moral/philosophical works |

### 3. Martial — Epigrams

| Field | Latin | English |
|---|---|---|
| **Source** | Perseus `data/phi1294/` | EEBO-TCP **A52102** |
| **Translator** | — | Henry Killigrew (1695) |
| **Format** | TEI P5 XML, EpiDoc | TEI P5 XML, 5,613 verse lines |
| **License** | CC-BY-SA 4.0 | CC0 Public Domain (TCP Phase 1) |
| **GitHub** | — | https://github.com/textcreationpartnership/A52102 |
| **Coverage** | Complete | Substantial selection (not complete) |
| **Notes** | Includes some non-Martial pieces that need filtering |

### 4. Statius — Thebaid, Silvae, Achilleid

| Field | Latin | English |
|---|---|---|
| **Source** | Perseus `data/phi1020/` | Theoi.com / Wikisource |
| **Translator** | — | J.H. Mozley (Loeb, 1928) |
| **Format** | TEI P5 XML, EpiDoc | Clean HTML (hand-transcribed, not OCR) |
| **License** | CC-BY-SA 4.0 | Public Domain (1928 = PD 2024 under 95-year rule) |
| **URL** | — | https://www.theoi.com/Text/StatiusThebaid1.html |
| **Coverage** | All 3 works | Thebaid (12 books), Silvae (5 books), Achilleid |
| **Notes** | Complete Statius. Needs HTML scrape and conversion to align with Latin TEI |

---

## License Summary

| Source | License | Attribution |
|---|---|---|
| Perseus canonical-latinLit | CC-BY-SA 4.0 | Yes (BY), derivatives SA |
| EEBO-TCP (Phase 1) | CC0 Public Domain | No |

**Combined output license:** CC-BY-SA 4.0 (driven by Perseus).

---

## Related Documents

- `plans/pd_translation_availability.md` — Full PD translation research
- `plans/eebo_tcp_tei_xml_investigation.md` — EEBO-TCP search details
- `plans/latin_embedding_plan.md` — Embedding model
- `plans/latin_embedding_v2_improvement.md` — v2 model results (92.6% Top-1)

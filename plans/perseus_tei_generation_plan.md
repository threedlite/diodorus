# Plan: Generate Perseus-Compatible TEI English Translation

**Status:** Implemented
**Date:** 2026-03-01

## What was built

### `scripts/alignment/08_generate_perseus_tei.py`

Standalone script that reads existing alignment output and generates a TEI XML file
following Perseus canonical-greekLit conventions for English translations.

**Inputs** (no pipeline rerun needed):
- `output/entity_validated_alignments.json` -- 8,123 aligned Greek sections
- `output/booth_normalised.json` -- Booth's English text by book/chapter/paragraph

**Outputs:**
- `output/tlg0060.tlg001.perseus-eng80.xml` -- TEI translation (11 MB, 8,123 section divs)
- `output/__cts__eng80_fragment.xml` -- CTS catalog entry

### `scripts/alignment/run_alignment.sh`

Step 8 added at end of pipeline.

## Key decisions

- **Naming:** `perseus-eng80` (Diodorus has zero existing English translations in Perseus)
- **Long-s normalised:** All U+017F characters replaced with regular `s` for readability
- **N:1 groups:** English paragraph repeated at each Greek section for CTS completeness
- **1:M groups:** All M paragraphs placed in the single section
- **N:M groups:** Paragraphs distributed via `floor(i * M / N)`
- **Books 6-10 omitted:** No Greek or English data exists for these
- **Alignment metadata:** `ana="alignment:group=X score=Y"` on section divs
- **lxml.etree** for XML construction (handles namespaces, escaping)

## TEI structure

```
TEI > teiHeader (refsDecl with CTS XPaths) + text > body >
  div[type=translation] >
    div[type=textpart subtype=book] >
      div[type=textpart subtype=chapter] >
        div[type=textpart subtype=section] > p
```

Mirrors the Thucydides/Hobbes pattern in Perseus canonical-greekLit.

## Verification results

- 8,123 section divs matching all CTS refs in alignment data
- XML well-formed (lxml parse verification)
- Zero long-s characters in output
- 15 books present (1-5, 11-20), books 6-10 correctly absent
- 3,159 alignment groups (3,102 single-English, 57 double-English)

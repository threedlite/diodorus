# Plan: Generate Perseus-Compatible TEI English Translation

**Status:** Implemented (Booth-structured with Greek milestones, v3)
**Date:** 2026-03-01

## What was built

### `scripts/alignment/08_generate_perseus_tei.py`

Standalone script that reads existing alignment output and generates a TEI XML file
following Perseus canonical-greekLit conventions for English translations.

**Inputs** (no pipeline rerun needed):
- `output/entity_validated_alignments.json` -- 8,123 aligned Greek sections
- `output/booth_normalised.json` -- Booth's English text by book/chapter/paragraph

**Outputs:**
- `output/tlg0060.tlg001.perseus-eng80.xml` -- TEI translation (3.3 MB)
- `output/__cts__eng80_fragment.xml` -- CTS catalog entry

### `scripts/alignment/run_alignment.sh`

Step 8 added at end of pipeline.

## Key decisions

- **Naming:** `perseus-eng80` (Diodorus has zero existing English translations in Perseus)
- **Long-s normalised:** All U+017F characters replaced with regular `s` for readability
- **Booth's chapter structure:** Text is organised following Booth's own chapter divisions
  (144 chapters across 15 books), preserving his paragraph ordering exactly
- **Greek milestones:** `<milestone unit="section" n="chapter.section"/>` markers indicate
  where each Greek section begins within the Booth text (e.g., `n="1.5"`, `n="arg.0"`)
- **No text duplication:** Each of Booth's 3,216 paragraphs appears exactly once
- **No text dropped:** All paragraphs emitted in their natural position
- **Milestones on first paragraph:** For each alignment group, milestones are placed
  before the group's first Booth paragraph
- **Books 6-10 omitted:** No Greek or English data exists for these
- **lxml.etree** for XML construction (handles namespaces, escaping)

## TEI structure

```
TEI > teiHeader (refsDecl with CTS XPaths for book+chapter) + text > body >
  div[type=translation] >
    div[type=textpart subtype=book n=1] >
      div[type=textpart subtype=chapter n=1] >      <!-- Booth's chapter -->
        milestone[unit=section n="arg.0"]
        milestone[unit=section n="1.1"]
        milestone[unit=section n="1.2"]
        milestone[unit=section n="1.3"]
        milestone[unit=section n="1.4"]
        <p>Booth paragraph 1</p>
        milestone[unit=section n="1.5"]
        milestone[unit=section n="2.1"]
        ...
        <p>Booth paragraph 2</p>
        ...
```

The text follows Booth's natural order. Greek section milestones are interleaved
to indicate where each Greek section begins within the English text.

## History

### v1 (section-div based)
- Section divs with paragraph text repeated at each section for N:1 groups
- Produced 11 MB file with massive redundancy

### v2 (Greek-chapter divs with section milestones)
- Replaced section divs with milestone markers within Greek chapter divs
- Problems: cross-chapter groups caused section number collisions and
  dropped text from chapters whose sections were claimed by another chapter's group

### v3 (Booth-structured with Greek milestones) — current
- Text organised by Booth's own chapter divisions
- Greek sections marked with milestones (n="chapter.section") within Booth's text flow
- No duplication, no dropping — every paragraph in its natural position
- Cross-chapter groups are a non-issue: milestones just reference Greek chapter.section

## Alignment quality assessment

The milestone placement depends on the upstream alignment pipeline (steps 04-07).
The alignment is **usable but imperfect** — it works well in most places but is
off in specific areas.

**Overall stats (3,159 alignment groups):**
- Median score: 0.457, mean: 0.440
- 91.1% of groups score ≥ 0.2 (reasonable alignment)
- 8.9% of groups score < 0.2 (likely misaligned)
- High-scoring groups (>0.7) show strong content correspondence (e.g., named
  entities like Ptolemy, geographic descriptions of Gaul match correctly)

**Per-book variation:**
- Strongest: Books 2, 3, 5 (median ~0.5)
- Weakest: Books 13, 20 (median ~0.35), with more low-score groups

**Known issues:**
- Book 1 prooemium (Greek ch 1-2): Diodorus's philosophical preface on the value
  of history has no close match in Booth, who condensed or reordered this material.
  Group 0 scores just 0.064. The milestones are placed but point to non-corresponding
  English text.
- Booth's 1700 translation is a paraphrase, not a literal translation. He freely
  rearranges, condenses, and expands material, which limits how precisely any
  automated alignment can perform.
- Cross-chapter group boundaries (where 5 Greek sections map to 1 Booth paragraph)
  are a structural constraint of the grouping algorithm, not a content judgement.

**Bottom line:** The alignment is useful for approximate navigation — finding roughly
where a Greek section falls in Booth's text. It should not be treated as a
sentence-level correspondence. The Booth text itself is always intact and correct;
only the milestone positions may be imprecise.

## Booth text integrity guarantee

The TEI output preserves Booth's text exactly as it appears in the source, regardless
of alignment quality. All 3,216 paragraphs appear in the TEI in exact source order —
no skips, no repeats, no reordering. This was verified by comparing every `<p>` element
in document order against the Booth source paragraphs in source order: all match.

The milestone placement depends on the upstream alignment data and may be imprecise,
but the English text itself is never corrupted by the alignment process.

## Verification results

- 3,216 Booth paragraphs in exact source order (verified against booth_normalised.json)
- Zero skipped, zero repeated, zero reordered paragraphs
- 8,123 milestone markers, all Greek sections covered
- 144 Booth chapters across 15 books
- XML well-formed (lxml parse verification)
- Zero long-s characters in output
- File size: 3.3 MB

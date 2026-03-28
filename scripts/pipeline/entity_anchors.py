#!/usr/bin/env python3
"""
Generic entity anchor validation.

Uses Greek transliteration + fuzzy matching against English names.
For fable-mode works, also uses animal name matching.

Inputs:
  <output_dir>/section_alignments.json
  <output_dir>/greek_sections.json
  <output_dir>/english_sections.json

Outputs:
  <output_dir>/entity_validated_alignments.json
"""

import json
import re
import sys
from pathlib import Path
from unidecode import unidecode
from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

GREEK_SIMPLE = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z",
    "η": "e", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n",
    "ξ": "x", "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s",
    "τ": "t", "υ": "y", "φ": "ph", "χ": "kh", "ψ": "ps", "ω": "o",
    "θ": "th",
    "ά": "a", "έ": "e", "ή": "e", "ί": "i", "ό": "o", "ύ": "y",
    "ώ": "o", "ϊ": "i", "ϋ": "y", "ΐ": "i", "ΰ": "y",
}


def greek_to_latin(text):
    t = text.lower()
    for greek, latin in GREEK_SIMPLE.items():
        t = t.replace(greek, latin)
    t = re.sub(r"[^\w\s]", "", t)
    return unidecode(t).lower()


def extract_greek_names(text):
    # Match words starting with any Greek capital (basic or extended/polytonic)
    # followed by lowercase Greek letters (basic, accented, or extended)
    words = re.findall(
        r"\b[\u0391-\u03A9\u1F08-\u1F0F\u1F18-\u1F1D\u1F28-\u1F2F\u1F38-\u1F3F"
        r"\u1F48-\u1F4D\u1F59-\u1F5F\u1F68-\u1F6F\u1F88-\u1F8F\u1F98-\u1F9F"
        r"\u1FA8-\u1FAF\u1FB8-\u1FBC\u1FC8-\u1FCC\u1FD8-\u1FDB\u1FE8-\u1FEC"
        r"\u1FF8-\u1FFC]"
        r"[\u03b1-\u03c9\u03ac-\u03ce\u1F00-\u1FFF]{2,}\b", text)
    return [(w, greek_to_latin(w)) for w in words]


def extract_english_names(text):
    """Extract likely proper names from English text.

    Filters out common English words using corpus-derived stopwords
    (words appearing in >30% of sections are not distinctive names).
    """
    from lexical_overlap import EN_STOPS
    words = re.findall(r"\b[A-Z][a-z]{4,}\b", text)
    return [w.lower() for w in words if w.lower() not in EN_STOPS]


def load_config(work_name):
    config_path = PROJECT_ROOT / "scripts" / "works" / work_name / "config.json"
    with open(config_path) as f:
        return json.load(f)


def main(work_name):
    config = load_config(work_name)
    out_dir = PROJECT_ROOT / config["output_dir"]

    align_path = out_dir / "section_alignments.json"
    greek_path = out_dir / "greek_sections.json"
    english_path = out_dir / "english_sections.json"

    # Handle legacy names
    if not greek_path.exists():
        alt = out_dir / "greek_fables.json"
        if alt.exists():
            greek_path = alt
    if not english_path.exists():
        alt = out_dir / "english_fables.json"
        if alt.exists():
            english_path = alt

    for p in [align_path, greek_path, english_path]:
        if not p.exists():
            print(f"Error: {p} not found")
            raise SystemExit(1)

    with open(align_path) as f:
        alignments = json.load(f)
    with open(greek_path) as f:
        greek_data = json.load(f)
    with open(english_path) as f:
        english_data = json.load(f)

    if isinstance(greek_data, list):
        greek_data = {"sections": greek_data}
    if isinstance(english_data, list):
        english_data = {"sections": english_data}

    # Build indexes
    greek_by_ref = {s["cts_ref"]: s for s in greek_data["sections"]}
    # English may use cts_ref, fable_index, or section
    english_by_ref = {}
    for s in english_data["sections"]:
        key = s.get("cts_ref", s.get("fable_index", s.get("section", "")))
        english_by_ref[str(key)] = s

    # Build lexical table from all aligned pairs for multi-signal scoring
    from lexical_overlap import (build_lexical_table,
                                 lexical_overlap_score)
    import pickle

    # Load global cross-work lexical dictionary if available
    global_lex_path = PROJECT_ROOT / "build" / "global_lexical_table.pkl"
    if global_lex_path.exists():
        with open(global_lex_path, "rb") as f:
            global_lex = pickle.load(f)
        src2en = global_lex["src2en"]
        src_idf = global_lex["src_idf"]
        print(f"  Global lexical table: {len(src2en)} words")
    else:
        # Fall back to per-work table
        aligned_pairs = []
        for a in alignments:
            if a.get("greek_cts_ref") is None or a.get("english_cts_ref") is None:
                continue
            gr_text = greek_by_ref.get(a["greek_cts_ref"], {}).get("text", "")
            en_key = str(a.get("english_cts_ref", a.get("english_section", "")))
            en_text = english_by_ref.get(en_key, {}).get("text", "")
            if gr_text and en_text:
                aligned_pairs.append((gr_text, en_text))

        src2en, src_idf, _ = build_lexical_table(aligned_pairs) if aligned_pairs else ({}, {}, {})
        if src2en:
            print(f"  Per-work lexical table: {len(src2en)} words")

    # Compute expected char ratio for length penalty.
    # Count each section only once (avoid inflating when multiple alignments
    # share the same English section).
    total_gr = sum(len(s.get("text", "")) for s in greek_data["sections"])
    total_en = sum(len(s.get("text", "")) for s in english_data["sections"])
    expected_ratio = total_gr / total_en if total_en > 0 else 1.0

    # Build English name document frequency — names that appear in many
    # sections are common nouns (capitalized in archaic English), not
    # distinctive proper names. Exclude names appearing in >10% of sections.
    from collections import Counter
    en_name_df = Counter()
    for s in english_data["sections"]:
        for name in set(extract_english_names(s.get("text", ""))):
            en_name_df[name] += 1
    n_en_sections = len(english_data["sections"])
    common_en_names = {name for name, df in en_name_df.items()
                       if df > n_en_sections * 0.10}
    if common_en_names:
        print(f"  Filtered {len(common_en_names)} common English names "
              f"(appear in >10% of sections)")

    # Count how many Greek sections point to each English section.
    # Non-1:1 mappings should be penalized — they indicate the alignment
    # couldn't find a unique match.
    en_ref_counts = Counter()
    for a in alignments:
        en_ref = a.get("english_cts_ref")
        if en_ref is not None:
            en_ref_counts[str(en_ref)] += 1

    print("Validating alignments with entity anchors + lexical overlap...")

    import math
    import numpy as np

    # First pass: compute lexical scores to find P95 for normalization
    all_lex_scores = []
    for a in alignments:
        if a.get("match_type") == "unmatched_english" or a.get("greek_cts_ref") is None:
            continue
        gr_text = greek_by_ref.get(a["greek_cts_ref"], {}).get("text", "")
        en_key = a.get("english_cts_ref", a.get("english_section", ""))
        en_text = english_by_ref.get(str(en_key), {}).get("text", "")
        if gr_text and en_text:
            ls = lexical_overlap_score(gr_text, en_text, src2en, src_idf)
            all_lex_scores.append(ls)
    lex_p95 = float(np.percentile(all_lex_scores, 95)) if all_lex_scores else 0.25
    print(f"  Lexical score P95: {lex_p95:.3f} (used for normalization)")

    # Second pass: compute all scores
    for a in alignments:
        mt = a.get("match_type", "")
        if mt == "split_continuation":
            # Split sibling: its text was included in the parent's refinement.
            # Give it the CTS floor score since the pairing is structural.
            a["entity_overlap_score"] = 0.0
            a["entity_match_count"] = 0
            a["lexical_score"] = 0.0
            a["length_ratio_score"] = 1.0
            a["combined_score"] = 0.5
            continue
        if mt == "unmatched_english" or a.get("greek_cts_ref") is None:
            a["entity_overlap_score"] = 0.0
            a["entity_match_count"] = 0
            a["lexical_score"] = 0.0
            a["length_ratio_score"] = 0.0
            a["combined_score"] = 0.0
            continue

        gr_text = greek_by_ref.get(a["greek_cts_ref"], {}).get("text", "")
        en_key = a.get("english_cts_ref", a.get("english_section", ""))
        en_text = english_by_ref.get(str(en_key), {}).get("text", "")

        # 1. Entity overlap
        gr_names = extract_greek_names(gr_text)
        en_names = extract_english_names(en_text)

        # Filter out common English "names" (frequent nouns, not proper names)
        en_names = [n for n in en_names if n not in common_en_names]

        matches = 0
        total = max(len(gr_names), 1)
        for _, gn_lat in gr_names:
            if len(gn_lat) < 4:
                continue
            for en in en_names:
                if len(en) < 4:
                    continue
                if fuzz.partial_ratio(gn_lat, en) > 75:
                    matches += 1
                    break

        entity_score = matches / total if gr_names else 0.0
        a["entity_overlap_score"] = round(entity_score, 3)
        a["entity_match_count"] = matches

        # 2. Lexical overlap (TF-IDF weighted)
        lex_score = lexical_overlap_score(gr_text, en_text, src2en, src_idf)
        a["lexical_score"] = round(lex_score, 3)

        # 3. Speaker overlap (for dramatic works)
        gr_section = greek_by_ref.get(a["greek_cts_ref"], {})
        en_section = english_by_ref.get(str(en_key), {})
        gr_speakers = gr_section.get("speakers", [])
        en_speaker = en_section.get("speaker", "")
        speaker_score = 0.0
        has_speakers = False
        if gr_speakers and en_speaker:
            has_speakers = True
            # Check if English speaker matches any Greek speaker in this section
            en_spk_lower = en_speaker.lower().strip()
            # greek_to_latin is defined in this module
            for gs in gr_speakers:
                gs_lat = greek_to_latin(gs)
                if (gs_lat.startswith(en_spk_lower) or
                        en_spk_lower.startswith(gs_lat) or
                        fuzz.ratio(gs_lat, en_spk_lower) >= 60):
                    speaker_score = 1.0
                    break
        a["speaker_score"] = round(speaker_score, 3)

        # 4. Length ratio penalty
        # For refined sections, use the refined piece length (not the full
        # English section) since that's what's actually paired.
        gr_chars = len(gr_text)
        refined_text = a.get("english_refined_text", "")
        en_chars = len(refined_text) if refined_text else len(en_text)
        if en_chars > 0 and expected_ratio > 0:
            ratio = (gr_chars / en_chars) / expected_ratio
            length_pen = math.exp(-0.5 * (ratio - 1.0) ** 2)
        else:
            length_pen = 0.5
        a["length_ratio_score"] = round(length_pen, 3)

        # 4. Combined score — normalize each signal to 0-1 range,
        # then weighted average.
        cos_sim = min(a.get("similarity", 0), 1.0)  # clamp CTS 1.0 overrides

        # Normalize lexical score to 0-1 range using P95 computed from this work
        lex_norm = min(1.0, max(0.0, lex_score / lex_p95)) if lex_p95 > 0 else 0.0

        # Combined score.
        # Entity/lexical/speaker are the primary signals. Embedding is a
        # tiebreaker when the primary signals are ambiguous.
        # Length ratio vetoes: mismatched sizes = wrong pair.
        #
        # Entity requires ≥2 matches to be strong evidence — a single
        # common name like "Egypt" is not distinctive.

        emb_signal = max(cos_sim, 0.0)
        lex_signal = lex_norm
        ent_signal = entity_score if gr_names and matches >= 2 else entity_score * 0.3
        spk_signal = speaker_score if has_speakers else 0.0

        match_type = a.get("match_type", "")
        is_cts = "cts" in match_type

        if is_cts:
            # CTS structural match: the pairing is confirmed by section
            # numbering. Embedding is a confirmation signal, not a guess.
            # Use it at full weight and floor at 0.5.
            primary = max(ent_signal, lex_signal, spk_signal)
            content = max(primary, emb_signal)  # full embedding weight
            score = content * length_pen

            # No sharing penalty for CTS-confirmed groups — many-to-one
            # mappings are structural (e.g. Greek 1.7.1-3 → English 1.7),
            # not DP drift.

            score = max(score, 0.5)  # CTS floor: never below yellow
        else:
            # DP-only match: original scoring formula
            primary = max(ent_signal, lex_signal, spk_signal)
            if primary >= 0.3:
                content = primary
            elif primary > 0:
                content = max(primary, emb_signal * 0.5)  # embedding at half weight
            else:
                content = emb_signal  # no other signals; embedding is primary

            score = content * length_pen

            # Penalize non-1:1 mappings
            en_ref = str(a.get("english_cts_ref", ""))
            sharing = en_ref_counts.get(en_ref, 1)
            if sharing > 1 and match_type != "dp_refined":
                score *= 1.0 / math.sqrt(sharing)
                a["sharing_penalty"] = sharing

        a["combined_score"] = round(min(1.0, score), 4)

        # Mark as effectively unmatched when the length ratio is extreme
        # AND no entity evidence supports the match. Never apply to CTS
        # matches or high-similarity DP matches (cos_sim >= 0.99 means
        # the DP is very confident, even without CTS tagging).
        is_refined = match_type in ("dp_refined", "cts_refined")
        is_high_sim = cos_sim >= 0.99
        if not is_cts and not is_high_sim and length_pen < 0.1 and entity_score < 0.3 and not is_refined:
            a["combined_score"] = 0.0
            a["match_quality"] = "no_match"

    low_conf = sum(1 for a in alignments if a.get("combined_score", 0) < 0.3)
    print(f"  Total: {len(alignments)}, Low confidence: {low_conf}")

    output_path = out_dir / "entity_validated_alignments.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(alignments, f, ensure_ascii=False, indent=2)

    print(f"Saved: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/pipeline/entity_anchors.py <work_name>")
        sys.exit(1)
    main(sys.argv[1])

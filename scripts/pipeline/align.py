#!/usr/bin/env python3
"""
Generic alignment step: load extracted sections, embed, and align.

Supports two modes via config:
  - "dp": segmental dynamic programming (sequential texts)
  - "pairwise": pairwise embedding matching (non-sequential, e.g. fables)

Inputs:
  <output_dir>/greek_sections.json (or latin_sections.json)
  <output_dir>/english_sections.json

Outputs:
  <output_dir>/section_alignments.json
"""

import hashlib
import json
import sys
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from align_core import segmental_dp_align, pairwise_match

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


_model_dir_path = None  # set by load_model


def embed_with_cache(model, texts, cache_dir, label):
    """Embed texts, caching results based on content hash.

    Cache invalidates if:
    - Text content changes (different hash)
    - Model directory is newer than cached embeddings
    - Number of texts doesn't match cached array shape
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    content_hash = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()[:16]
    cache_file = cache_dir / f"emb_{label}_{content_hash}.npy"

    if cache_file.exists():
        cache_mtime = cache_file.stat().st_mtime
        # Check model hasn't been retrained since cache was written
        if _model_dir_path and _model_dir_path.exists():
            model_mtime = _model_dir_path.stat().st_mtime
            if model_mtime > cache_mtime:
                print(f"  {label}: model newer than cache, re-embedding")
                cache_file.unlink()
            else:
                embs = np.load(cache_file)
                if embs.shape[0] == len(texts):
                    print(f"  {label}: cached ({len(texts)} texts)")
                    return embs
        else:
            embs = np.load(cache_file)
            if embs.shape[0] == len(texts):
                print(f"  {label}: cached ({len(texts)} texts)")
                return embs

    embs = model.encode(texts, show_progress_bar=len(texts) > 100, batch_size=32)
    np.save(cache_file, embs)
    print(f"  {label}: embedded {len(texts)} texts")
    return embs


def split_large_sections(sections, max_chars=2000):
    """Split sections larger than max_chars into paragraph-sized chunks.

    Large sections produce blurred embeddings that align poorly. Splitting
    them into ~500-2000 char chunks gives the DP finer-grained units to
    work with, improving alignment quality.

    Splits on sentence boundaries (. ? ! ;) near the midpoint, falling back
    to any whitespace. Preserves all text — no content is lost.
    """
    import re

    result = []
    split_count = 0

    for s in sections:
        if s["char_count"] <= max_chars:
            result.append(s)
            continue

        text = s["text"]
        book = s["book"]
        base_ref = s["cts_ref"]
        edition = s.get("edition", "")
        work = s.get("work", "")

        # Split into chunks at sentence boundaries
        chunks = []
        while len(text) > max_chars:
            # Find a sentence boundary near the midpoint
            mid = max_chars
            # Look for sentence-ending punctuation followed by space
            best = -1
            for punct in ['. ', '? ', '! ', '; ', '· ']:
                idx = text.rfind(punct, max_chars // 2, mid + 200)
                if idx > best:
                    best = idx + len(punct)

            if best <= 0:
                # No sentence boundary found — split on any space
                best = text.rfind(' ', max_chars // 2, mid + 200)
                if best <= 0:
                    best = max_chars

            chunks.append(text[:best].strip())
            text = text[best:].strip()

        if text:
            chunks.append(text)

        for ci, chunk in enumerate(chunks):
            result.append({
                "book": book,
                "section": f"{s.get('section', '')}.{ci}" if len(chunks) > 1 else s.get("section", ""),
                "cts_ref": f"{base_ref}.{ci}" if len(chunks) > 1 else base_ref,
                "edition": edition,
                "text": chunk,
                "char_count": len(chunk),
                **({"work": work} if work else {}),
            })

        if len(chunks) > 1:
            split_count += 1

    if split_count > 0:
        print(f"  Split {split_count} oversized sections ({len(sections)} → {len(result)})")

    return result


def load_config(work_name):
    config_path = PROJECT_ROOT / "scripts" / "works" / work_name / "config.json"
    with open(config_path) as f:
        return json.load(f)


def load_model(source_language="greek"):
    global _model_dir_path
    custom_greek = PROJECT_ROOT / "models" / "ancient-greek-embedding"
    custom_latin = PROJECT_ROOT / "models" / "latin-embedding"
    baseline = "paraphrase-multilingual-MiniLM-L12-v2"

    if source_language == "latin" and custom_latin.exists():
        print(f"  Using custom Latin model")
        _model_dir_path = custom_latin
        return SentenceTransformer(str(custom_latin))
    elif source_language == "greek" and custom_greek.exists():
        print(f"  Using custom Ancient Greek model")
        _model_dir_path = custom_greek
        return SentenceTransformer(str(custom_greek))
    elif custom_greek.exists():
        print(f"  Using custom Ancient Greek model (fallback)")
        _model_dir_path = custom_greek
        return SentenceTransformer(str(custom_greek))
    else:
        print(f"  Using baseline: {baseline}")
        _model_dir_path = None
        return SentenceTransformer(baseline)


def run_dp_alignment(config, greek_data, english_data, model):
    """Run segmental DP alignment, book by book or work by work."""
    all_alignments = []

    # Group sections by alignment unit (work for multi_work, book otherwise)
    # Build lookup tables for both sides
    gr_by_key = {}
    en_by_key = {}

    if config.get("multi_work"):
        for s in greek_data["sections"]:
            gr_by_key.setdefault(s.get("work", ""), []).append(s)
        for s in english_data["sections"]:
            en_by_key.setdefault(s.get("work", ""), []).append(s)
    else:
        for s in greek_data["sections"]:
            gr_by_key.setdefault(s["book"], []).append(s)
        for s in english_data["sections"]:
            en_by_key.setdefault(s["book"], []).append(s)

    matched_keys = sorted(
        set(gr_by_key.keys()) & set(en_by_key.keys()),
        key=lambda x: int(x) if x.isdigit() else x
    )
    groups = [(k, gr_by_key[k], en_by_key[k]) for k in matched_keys]

    # Handle unmatched books/works — NEVER skip text
    greek_only = set(gr_by_key.keys()) - set(en_by_key.keys())
    english_only = set(en_by_key.keys()) - set(gr_by_key.keys())

    for key in sorted(greek_only, key=lambda x: int(x) if x.isdigit() else x):
        for gs in gr_by_key[key]:
            all_alignments.append({
                "book": str(key),
                "greek_cts_ref": gs["cts_ref"],
                "greek_edition": gs.get("edition", ""),
                "english_cts_ref": None,
                "english_section": "",
                "similarity": 0.0,
                "greek_preview": gs["text"][:80],
                "english_preview": "",
                "group_id": None,
                "group_size_gr": 1,
                "group_size_en": 0,
                "match_type": "unmatched_greek",
            })
        print(f"\n  {key}: {len(gr_by_key[key])} source sections (no English)")

    for key in sorted(english_only, key=lambda x: int(x) if x.isdigit() else x):
        for es in en_by_key[key]:
            all_alignments.append({
                "book": str(key),
                "greek_cts_ref": None,
                "greek_edition": None,
                "english_cts_ref": es["cts_ref"],
                "english_section": es.get("section", ""),
                "similarity": 0.0,
                "greek_preview": "",
                "english_preview": es["text"][:80],
                "group_id": None,
                "group_size_gr": 0,
                "group_size_en": 1,
                "match_type": "unmatched_english",
            })
        print(f"\n  {key}: {len(en_by_key[key])} English sections (no source)")

    cache_dir = PROJECT_ROOT / config["output_dir"] / ".embed_cache"

    for book, greek_secs, english_secs in groups:
        print(f"\n=== {book}: {len(greek_secs)} source, {len(english_secs)} target ===")

        book_label = str(book).replace(" ", "_").replace("/", "_")
        greek_embs = embed_with_cache(
            model, [s.get("text_for_embedding", s["text"]) for s in greek_secs],
            cache_dir, f"gr_{book_label}")
        english_embs = embed_with_cache(
            model, [s.get("text_for_embedding", s["text"]) for s in english_secs],
            cache_dir, f"en_{book_label}")

        greek_lens = [s["char_count"] for s in greek_secs]
        english_lens = [s["char_count"] for s in english_secs]

        total_gr = sum(greek_lens)
        total_en = sum(english_lens)
        expected_ratio = total_gr / total_en if total_en > 0 else 1.0

        # Auto-scale max_source
        gr_per_en = len(greek_secs) / max(len(english_secs), 1)
        max_source = max(5, int(gr_per_en * 2))
        print(f"  Ratio: {gr_per_en:.1f} source/target, max_source={max_source}")

        groups_result = segmental_dp_align(
            greek_embs, english_embs, greek_lens, english_lens,
            expected_ratio, max_source=max_source
        )
        print(f"  DP produced {len(groups_result)} alignment groups")

        # Build records — ensure every English section appears
        en_used = set()
        for gr_start, gr_end, en_start, en_end, score in groups_result:
            for ej in range(en_start, en_end):
                en_used.add(ej)

        en_skipped = len(english_secs) - len(en_used)

        en_to_greek = {}
        for group_id, (gr_start, gr_end, en_start, en_end, score) in enumerate(groups_result):
            for ej in range(en_start, en_end):
                if ej not in en_to_greek:
                    en_to_greek[ej] = []
                for gi in range(gr_start, gr_end):
                    gs = greek_secs[gi]
                    es = english_secs[ej]
                    en_to_greek[ej].append({
                        "book": str(book),
                        "greek_cts_ref": gs["cts_ref"],
                        "greek_edition": gs.get("edition", ""),
                        "english_cts_ref": es["cts_ref"],
                        "english_section": es.get("section", ""),
                        "similarity": round(score, 4),
                        "greek_preview": gs["text"][:80],
                        "english_preview": es["text"][:80],
                        "group_id": group_id,
                        "group_size_gr": gr_end - gr_start,
                        "group_size_en": en_end - en_start,
                        "match_type": "dp_aligned",
                    })

        for ej in range(len(english_secs)):
            if ej in en_to_greek:
                all_alignments.extend(en_to_greek[ej])
            else:
                es = english_secs[ej]
                all_alignments.append({
                    "book": str(book),
                    "greek_cts_ref": None,
                    "greek_edition": None,
                    "english_cts_ref": es["cts_ref"],
                    "english_section": es.get("section", ""),
                    "similarity": 0.0,
                    "greek_preview": "",
                    "english_preview": es["text"][:80],
                    "group_id": None,
                    "group_size_gr": 0,
                    "group_size_en": 1,
                    "match_type": "unmatched_english",
                })

        if en_skipped > 0:
            print(f"  Added {en_skipped} unmatched English sections")

    return all_alignments


def run_pairwise_alignment(config, greek_data, english_data, model):
    """Run pairwise embedding matching."""
    greek_secs = greek_data["sections"]
    english_secs = english_data["sections"]

    print(f"Source: {len(greek_secs)}, Target: {len(english_secs)}")

    cache_dir = PROJECT_ROOT / config["output_dir"] / ".embed_cache"
    greek_embs = embed_with_cache(
        model, [s.get("text_for_embedding", s["text"]) for s in greek_secs], cache_dir, "gr_pairwise")
    english_embs = embed_with_cache(
        model, [s.get("text_for_embedding", s["text"]) for s in english_secs], cache_dir, "en_pairwise")

    many_to_one = config.get("pairwise_many_to_one", False)
    matches, sim_matrix = pairwise_match(
        greek_embs, english_embs, min_similarity=0.3,
        many_to_one=many_to_one
    )

    matched = sum(1 for m in matches if m["match_type"] == "pairwise_top1")
    print(f"  Matched: {matched}, Unmatched: {len(matches) - matched}")

    alignments = []
    for m in matches:
        gs = greek_secs[m["source_idx"]]
        rec = {
            "book": gs.get("book", "fables"),
            "greek_cts_ref": gs["cts_ref"],
            "greek_edition": gs.get("edition", ""),
            "similarity": round(m["similarity"], 4),
            "greek_preview": gs["text"][:80],
            "group_id": m["source_idx"],
            "group_size_gr": 1,
            "group_size_en": 1 if m["target_idx"] is not None else 0,
            "match_type": m["match_type"],
            "runner_up_similarity": round(m["runner_up_similarity"], 4),
        }
        if m["target_idx"] is not None:
            es = english_secs[m["target_idx"]]
            rec["english_cts_ref"] = es.get("cts_ref", str(m["target_idx"]))
            rec["english_section"] = es.get("section", "")
            rec["english_preview"] = es["text"][:80]
            rec["english_title"] = es.get("title", "")
        else:
            rec["english_cts_ref"] = None
            rec["english_section"] = ""
            rec["english_preview"] = ""
            rec["english_title"] = ""
        alignments.append(rec)

    # Add unmatched English sections — NEVER skip text
    en_matched = set()
    for a in alignments:
        ref = a.get("english_cts_ref")
        if ref is not None:
            en_matched.add(str(ref))

    for es in english_secs:
        ref = str(es.get("cts_ref", es.get("fable_index", "")))
        if ref not in en_matched:
            alignments.append({
                "book": es.get("book", "fables"),
                "greek_cts_ref": None,
                "greek_edition": None,
                "english_cts_ref": ref,
                "english_section": es.get("section", ""),
                "similarity": 0.0,
                "greek_preview": "",
                "english_preview": es["text"][:80],
                "group_id": None,
                "group_size_gr": 0,
                "group_size_en": 1,
                "match_type": "unmatched_target",
            })

    en_unmatched = len(english_secs) - len(en_matched)
    if en_unmatched > 0:
        print(f"  Added {en_unmatched} unmatched English sections")

    # Save similarity matrix
    out_dir = PROJECT_ROOT / config["output_dir"]
    np.savez_compressed(out_dir / "similarity_matrix.npz", matrix=sim_matrix)

    return alignments


def main(work_name):
    config = load_config(work_name)
    out_dir = PROJECT_ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    greek_path = out_dir / "greek_sections.json"
    english_path = out_dir / "english_sections.json"

    # Also check for legacy names (greek_fables.json, english_fables.json)
    if not greek_path.exists():
        alt = out_dir / "greek_fables.json"
        if alt.exists():
            greek_path = alt
    if not english_path.exists():
        alt = out_dir / "english_fables.json"
        if alt.exists():
            english_path = alt

    for p in [greek_path, english_path]:
        if not p.exists():
            print(f"Error: {p} not found. Run extraction first.")
            raise SystemExit(1)

    with open(greek_path) as f:
        greek_data = json.load(f)
    with open(english_path) as f:
        english_data = json.load(f)

    # Handle both {"sections": [...]} and bare list formats
    if isinstance(greek_data, list):
        greek_data = {"sections": greek_data}
    if isinstance(english_data, list):
        english_data = {"sections": english_data}

    # Split sections that are extreme outliers on their own side.
    # Uses text_for_embedding length (excludes footnotes).
    # Only splits sections >4x their side's median AND >3000 chars.
    # The DP already handles moderate size differences via grouping.
    for label, data in [("source", greek_data), ("English", english_data)]:
        content_lens = sorted(len(s.get("text_for_embedding", s["text"]))
                              for s in data["sections"])
        if not content_lens:
            continue
        median = content_lens[len(content_lens) // 2]
        threshold = max(median * 4, 3000)
        oversized = sum(1 for c in content_lens if c > threshold)
        if oversized > 0:
            data["sections"] = split_large_sections(data["sections"], max_chars=threshold)
            print(f"  Split {label} outliers > {threshold} chars "
                  f"(median {median}, {oversized} oversized)")

    # Strip footnotes for embedding — keeps original text for hashing and output
    from pipeline.strip_notes import strip_notes_from_sections
    strip_notes_from_sections(greek_data["sections"])
    strip_notes_from_sections(english_data["sections"])

    # Save the post-split sections so integrity checker compares against these
    with open(greek_path, "w", encoding="utf-8") as f:
        json.dump(greek_data, f, ensure_ascii=False, indent=2)
    with open(english_path, "w", encoding="utf-8") as f:
        json.dump(english_data, f, ensure_ascii=False, indent=2)

    print("Loading embedding model...")
    source_lang = config.get("source_language", "greek")
    model = load_model(source_lang)

    mode = config.get("alignment_mode", "dp")
    if mode == "pairwise":
        alignments = run_pairwise_alignment(config, greek_data, english_data, model)
    else:
        alignments = run_dp_alignment(config, greek_data, english_data, model)

    output_path = out_dir / "section_alignments.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(alignments, f, ensure_ascii=False, indent=2)

    print(f"\nTotal alignments: {len(alignments)}")
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/pipeline/align.py <work_name>")
        sys.exit(1)
    main(sys.argv[1])

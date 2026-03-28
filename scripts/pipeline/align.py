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
import re
import sys
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from align_core import segmental_dp_align, pairwise_match
from entity_anchors import extract_greek_names, extract_english_names
from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Alignment thresholds (can be overridden in config)
MIN_PAIRWISE_SIMILARITY = 0.3
MAX_REFINE_GROUP = 8            # max Greek sections per refinement group

# Chars-per-token estimates for computing model-capacity split thresholds.
# These are empirical averages for each language in xlm-roberta tokenization.
CHARS_PER_TOKEN = {
    "greek": 3.5,   # Greek script averages ~3.5 chars per subword token
    "latin": 4.5,   # Latin/Romance text ~4.5
    "english": 5.0, # English ~5.0
}

_model_dir_path = None  # set by load_model
_model_max_seq_length = None  # set by load_model


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

    result = []
    split_count = 0

    for s in sections:
        if s["char_count"] <= max_chars:
            result.append(s)
            continue

        text = s["text"]
        embed_text = s.get("text_for_embedding", text)
        book = s["book"]
        base_ref = s["cts_ref"]
        edition = s.get("edition", "")
        work = s.get("work", "")
        notes = s.get("notes", [])

        # Split text_for_embedding at sentence boundaries (this is the clean
        # text without footnotes). Then find the corresponding ranges in the
        # full text by matching boundary words.
        def split_at_sentences(t, max_c):
            chunks = []
            while len(t) > max_c:
                mid = max_c
                best = -1
                for punct in ['. ', '? ', '! ', '; ', '· ']:
                    idx = t.rfind(punct, max_c // 2, mid + 200)
                    if idx > best:
                        best = idx + len(punct)
                if best <= 0:
                    best = t.rfind(' ', max_c // 2, mid + 200)
                    if best <= 0:
                        best = max_c
                chunks.append(t[:best].strip())
                t = t[best:].strip()
            if t:
                chunks.append(t)
            return chunks

        embed_chunks = split_at_sentences(embed_text, max_chars)

        # Map each embed chunk back to the full text by finding where
        # the first ~30 chars of each chunk appear in the remaining text.
        chunks = []
        remaining = text
        for ec in embed_chunks[:-1]:
            # Find boundary: the start of the NEXT chunk in embed_text
            # corresponds to some position in the full text
            boundary_words = ec.split()[-3:]  # last 3 words of this chunk
            boundary_str = " ".join(boundary_words)
            pos = remaining.find(boundary_str)
            if pos >= 0:
                cut = pos + len(boundary_str)
                # Advance past any trailing whitespace/footnote text to next sentence
                while cut < len(remaining) and remaining[cut] in ' \t\n':
                    cut += 1
                chunks.append(remaining[:cut].strip())
                remaining = remaining[cut:].strip()
            else:
                # Boundary not found — take proportional amount
                ratio = len(ec) / max(len(embed_text), 1)
                cut = int(ratio * len(text))
                chunks.append(remaining[:cut].strip())
                remaining = remaining[cut:].strip()
        chunks.append(remaining.strip())

        for ci, chunk in enumerate(chunks):
            is_split = len(chunks) > 1
            new_section = {
                "book": book,
                "section": f"{s.get('section', '')}.{ci}" if is_split else s.get("section", ""),
                "cts_ref": f"{base_ref}.{ci}" if is_split else base_ref,
                "edition": edition,
                "text": chunk,
                "text_for_embedding": embed_chunks[ci] if ci < len(embed_chunks) else chunk,
                "char_count": len(chunk),
            }
            if is_split:
                new_section["split_from"] = base_ref
            if work:
                new_section["work"] = work
            # Only first chunk gets the notes
            if ci == 0 and notes:
                new_section["notes"] = notes
            result.append(new_section)

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
    global _model_dir_path, _model_max_seq_length
    custom_greek = PROJECT_ROOT / "models" / "ancient-greek-embedding"
    custom_latin = PROJECT_ROOT / "models" / "latin-embedding"
    baseline = "paraphrase-multilingual-MiniLM-L12-v2"

    if source_language == "latin" and custom_latin.exists():
        print(f"  Using custom Latin model")
        _model_dir_path = custom_latin
        model = SentenceTransformer(str(custom_latin))
        _model_max_seq_length = model.max_seq_length
        return model
    elif source_language == "greek" and custom_greek.exists():
        print(f"  Using custom Ancient Greek model")
        _model_dir_path = custom_greek
        model = SentenceTransformer(str(custom_greek))
        _model_max_seq_length = model.max_seq_length
        return model
    elif custom_greek.exists():
        print(f"  Using custom Ancient Greek model (fallback)")
        _model_dir_path = custom_greek
        model = SentenceTransformer(str(custom_greek))
        _model_max_seq_length = model.max_seq_length
        return model
    else:
        print(f"  Using baseline: {baseline}")
        _model_dir_path = None
        model = SentenceTransformer(baseline)
        _model_max_seq_length = model.max_seq_length
        return model


def _entity_overlap(gr_text, en_text):
    """Fraction of Greek proper names that fuzzy-match in English text.

    Returns a float in [0, 1], or None if no Greek names were found
    (no evidence to score against).
    """
    gr_names = extract_greek_names(gr_text)
    if not gr_names:
        return None
    en_names = extract_english_names(en_text)
    if not en_names:
        return 0.0
    matches = sum(1 for _, gn_lat in gr_names
                  if any(fuzz.partial_ratio(gn_lat, en) > 75 for en in en_names))
    return matches / len(gr_names)


def _refine_group(model, en_text, n_gr, gr_embs, gr_texts=None):
    """Split English text at sentence boundaries to match Greek sections.

    Tries progressively finer splitting until enough sentences are found.
    Uses DP on sentence embeddings to find optimal partition. When Greek
    texts are provided, entity name overlap is used as an additional
    signal to keep sentences with matching names in the correct group.

    Returns list of (sub_text, similarity) tuples, or None.
    """
    if n_gr < 2 or len(en_text) < 50:
        return None

    # Split at sentence boundaries, progressively finer.
    # Keep the best split found (most sentences), even if < n_gr.
    best_sentences = None
    for pattern in [
        r'(?<=[.!?])\s+(?=[A-Z])',
        r'(?<=[.!?;])\s+(?=[A-Z])',
        r'(?<=[;])\s+(?=and\b)',
        r'(?<=[;])\s+',
    ]:
        parts = re.split(pattern, en_text)
        parts = [p.strip() for p in parts if p and p.strip()]
        # Merge tiny fragments (<60 chars) with neighbor
        merged = []
        for p in parts:
            if merged and len(p) < 60:
                merged[-1] = merged[-1] + " " + p
            else:
                merged.append(p)
        if len(merged) >= n_gr:
            best_sentences = merged
            break
        if best_sentences is None or len(merged) > len(best_sentences):
            best_sentences = merged

    if best_sentences is None or len(best_sentences) < 2:
        return None

    # Cap sentences to avoid combinatorial explosion in _optimal_split.
    # For very large English sections (30K+ chars), splitting produces 200+
    # sentences. The DP is O(sentences² × n_gr) which becomes minutes per group.
    # Cap at 80 sentences — merge excess into their neighbors proportionally.
    MAX_SENTENCES = 80
    if len(best_sentences) > MAX_SENTENCES:
        # Merge from the end to reduce to MAX_SENTENCES
        while len(best_sentences) > MAX_SENTENCES:
            # Find shortest sentence and merge with neighbor
            min_idx = min(range(1, len(best_sentences)),
                          key=lambda i: len(best_sentences[i]))
            best_sentences[min_idx - 1] += " " + best_sentences[min_idx]
            del best_sentences[min_idx]

    sentences = best_sentences

    # If fewer sentences than Greek sections, assign each sentence to exactly
    # one Greek section using order-preserving DP.  Unassigned Greek sections
    # get None, which the caller renders as arrows in the HTML.
    if len(sentences) < n_gr:
        m = len(sentences)
        sent_embs = model.encode(sentences, show_progress_bar=False, batch_size=32)
        # sim_matrix[si][gi] = cosine similarity + entity bonus
        sim_matrix = np.zeros((m, n_gr))
        for si in range(m):
            ns = np.linalg.norm(sent_embs[si])
            for gi in range(n_gr):
                ng = np.linalg.norm(gr_embs[gi])
                if ns > 1e-10 and ng > 1e-10:
                    sim_matrix[si, gi] = float(np.dot(sent_embs[si], gr_embs[gi]) / (ns * ng))
                # Entity bonus: names matching → boost
                if gr_texts:
                    ent = _entity_overlap(gr_texts[gi], sentences[si])
                    if ent is not None and ent > 0:
                        sim_matrix[si, gi] += ent
        # DP: assign m sentences to m of n_gr Greek slots, preserving order.
        # dp[si][gi] = best total similarity assigning sentences 0..si to
        # Greek slots where sentence si is assigned to Greek gi.
        NEG_INF = -1e18
        dp = np.full((m, n_gr), NEG_INF)
        parent = np.full((m, n_gr), -1, dtype=int)
        # Base case: sentence 0 can go to any Greek slot
        for gi in range(n_gr):
            dp[0][gi] = sim_matrix[0, gi]
        # Fill: sentence si goes to Greek gi, previous sentence went to < gi
        for si in range(1, m):
            best_prev = NEG_INF
            best_prev_gi = -1
            for gi in range(si, n_gr):
                # Best previous from any gi' < gi
                if gi > 0 and dp[si - 1][gi - 1] > best_prev:
                    best_prev = dp[si - 1][gi - 1]
                    best_prev_gi = gi - 1
                if best_prev > NEG_INF:
                    dp[si][gi] = best_prev + sim_matrix[si, gi]
                    parent[si][gi] = best_prev_gi
        # Backtrack: find best final assignment
        best_gi = int(np.argmax(dp[m - 1]))
        assignment = [0] * m  # assignment[si] = Greek index
        assignment[m - 1] = best_gi
        for si in range(m - 2, -1, -1):
            assignment[si] = parent[si + 1][assignment[si + 1]]
        # Build result — each assigned sentence anchors a range of Greek sections.
        # The text for each range includes ALL sentences between this anchor
        # and the next (not just the assigned sentence), so no text is lost.
        assigned = sorted((assignment[si], si) for si in range(m))
        result = [None] * n_gr
        for idx, (gi, si) in enumerate(assigned):
            start_gi = 0 if idx == 0 else gi
            next_gi = assigned[idx + 1][0] if idx + 1 < len(assigned) else n_gr
            # Include all sentences from this anchor to the next anchor
            next_si = assigned[idx + 1][1] if idx + 1 < len(assigned) else m
            first_si = 0 if idx == 0 else si
            text = " ".join(sentences[first_si:next_si])
            span = next_gi - start_gi
            if span == 1:
                result[start_gi] = (text, sim_matrix[si, gi])
            else:
                # Split text proportionally by Greek section char counts
                gr_chars = [len(gr_texts[g]) if gr_texts else 100
                            for g in range(start_gi, next_gi)]
                total_chars = sum(gr_chars)
                chunks = []
                pos = 0
                for k in range(span):
                    frac = gr_chars[k] / total_chars if total_chars > 0 else 1.0 / span
                    cut = int(frac * len(text))
                    if k < span - 1:
                        end = pos + cut
                        # Find nearest word boundary
                        while end < len(text) and text[end] != ' ':
                            end += 1
                        chunks.append(text[pos:end].strip())
                        pos = end
                    else:
                        chunks.append(text[pos:].strip())
                # Merge tiny chunks (<20 chars) with previous
                merged = []
                for c in chunks:
                    if merged and len(c) < 20:
                        merged[-1] = merged[-1] + " " + c
                    else:
                        merged.append(c)
                # Pad to span length if merging reduced count
                while len(merged) < span:
                    merged.append("")
                for k, g in enumerate(range(start_gi, next_gi)):
                    chunk = merged[k] if k < len(merged) else ""
                    result[g] = (chunk, sim_matrix[si, gi]) if chunk else ("", 0.0)
        return result

    # Encode sentences and run DP
    sent_embs = model.encode(sentences, show_progress_bar=False, batch_size=32)
    splits = _optimal_split(sentences, sent_embs, n_gr, gr_embs, gr_texts)
    if splits is None:
        return None

    # Compute similarity per piece
    dim = sent_embs.shape[1]
    prefix = np.zeros((len(sentences) + 1, dim), dtype=np.float64)
    for i in range(len(sentences)):
        prefix[i + 1] = prefix[i] + sent_embs[i]

    result = []
    idx = 0
    for i, piece in enumerate(splits):
        n = len(piece)
        mean_emb = (prefix[idx + n] - prefix[idx]) / max(n, 1)
        idx += n
        norm_p = np.linalg.norm(mean_emb)
        norm_g = np.linalg.norm(gr_embs[i])
        sim = float(np.dot(mean_emb, gr_embs[i]) / (norm_p * norm_g)) if norm_p > 1e-10 and norm_g > 1e-10 else 0.0
        result.append((" ".join(piece), sim))

    return result



def _optimal_split(sentences, sent_embs, n_gr, gr_embs, gr_texts=None):
    """Find optimal split of sentences into n_gr groups using DP.

    Uses pre-computed sentence embeddings with prefix sums for O(1) range
    similarity. When Greek texts are provided, entity name overlap is added
    as a scoring bonus — sentences containing names that match the Greek
    section are attracted to the correct group.

    DP over split positions: O(n_sents² × n_gr).
    """
    n_sents = len(sentences)
    dim = sent_embs.shape[1]

    # Prefix sums for O(1) mean embedding of any range
    prefix = np.zeros((n_sents + 1, dim), dtype=np.float64)
    for i in range(n_sents):
        prefix[i + 1] = prefix[i] + sent_embs[i]

    # Precompute norms for Greek embeddings
    gr_norms = [np.linalg.norm(gr_embs[k]) for k in range(n_gr)]

    # Precompute Greek names per section for entity matching
    gr_names_per_section = None
    if gr_texts:
        gr_names_per_section = [extract_greek_names(t) for t in gr_texts]

    def range_sim(start, end, gr_idx):
        n = end - start
        if n == 0:
            return -1e9
        mean_emb = (prefix[end] - prefix[start]) / n
        norm_m = np.linalg.norm(mean_emb)
        if norm_m < 1e-10 or gr_norms[gr_idx] < 1e-10:
            cos_sim = 0.0
        else:
            cos_sim = float(np.dot(mean_emb, gr_embs[gr_idx]) / (norm_m * gr_norms[gr_idx]))

        # Entity overlap bonus: if Greek section has proper names and the
        # English sentence range contains matching names, boost the score.
        if gr_names_per_section and gr_names_per_section[gr_idx]:
            en_text = " ".join(sentences[start:end])
            ent = _entity_overlap(gr_texts[gr_idx], en_text)
            if ent is not None and ent > 0:
                # Entity match is a strong signal — if names match, this is
                # almost certainly the right grouping. Add overlap as bonus.
                return cos_sim + ent
        return cos_sim

    # DP: dp[k][j] = best total similarity using first k Greek sections
    # covering sentences 0..j-1
    NEG_INF = -1e18
    dp = [[NEG_INF] * (n_sents + 1) for _ in range(n_gr + 1)]
    parent = [[0] * (n_sents + 1) for _ in range(n_gr + 1)]
    dp[0][0] = 0.0

    for k in range(1, n_gr + 1):
        for j in range(k, n_sents - (n_gr - k) + 1):
            # Try all possible starts for group k
            for prev_j in range(k - 1, j):
                sim = range_sim(prev_j, j, k - 1)
                total = dp[k - 1][prev_j] + sim
                if total > dp[k][j]:
                    dp[k][j] = total
                    parent[k][j] = prev_j

    # Backtrack
    bounds = [n_sents]
    j = n_sents
    for k in range(n_gr, 0, -1):
        j = parent[k][j]
        bounds.append(j)
    bounds.reverse()

    return [sentences[bounds[i]:bounds[i + 1]] for i in range(n_gr)]


def try_cts_match(greek_secs, english_secs):
    """Try to match Greek sections to English sections by CTS reference numbers.

    Tries: exact match, parent match (book.chapter.section → book.chapter),
    split variants (parent.0, parent.1), and prefix match (book.X).

    Returns dict mapping greek_sec_idx → english_sec_idx.
    """
    en_by_ref = {}
    # Also index by split_from for sections that were split by the pipeline
    en_by_split_from = {}
    for i, s in enumerate(english_secs):
        en_by_ref[s.get("cts_ref", "")] = i
        split_from = s.get("split_from")
        if split_from and split_from not in en_by_split_from:
            en_by_split_from[split_from] = i  # first split piece

    matches = {}
    for gi, gs in enumerate(greek_secs):
        ref = gs.get("cts_ref", "")
        parts = ref.split(".")

        # Exact match — if the English section was split by the pipeline,
        # redirect to the first split piece so all Greek sub-sections
        # consolidate onto one English target for refinement.
        if ref in en_by_ref:
            ei = en_by_ref[ref]
            sf = english_secs[ei].get("split_from")
            if sf and sf in en_by_split_from:
                matches[gi] = en_by_split_from[sf]
            else:
                matches[gi] = ei
            continue

        # Parent match (book.chapter.section → book.chapter)
        if len(parts) >= 3:
            parent = ".".join(parts[:-1])
            if parent in en_by_ref:
                matches[gi] = en_by_ref[parent]
                continue
            # Parent was split by pipeline — look up by split_from
            if parent in en_by_split_from:
                matches[gi] = en_by_split_from[parent]
                continue

        # Split-variant match: the full Greek ref was split
        if ref in en_by_split_from:
            matches[gi] = en_by_split_from[ref]
            continue

        # Prefix match (first two components)
        if len(parts) >= 2:
            prefix = ".".join(parts[:2])
            if prefix in en_by_ref:
                matches[gi] = en_by_ref[prefix]
                continue

        # Chapter-sibling match: for 3-part refs like 11.8.2, find all
        # English sections in the same chapter (11.8.*). If there's exactly
        # one, map to it — no ambiguity. This handles the common case where
        # Greek has sub-sections (11.8.1-5) but English has just one (11.8.1).
        if len(parts) >= 3:
            chapter_prefix = ".".join(parts[:2]) + "."
            siblings = [r for r in en_by_ref if r.startswith(chapter_prefix)]
            if len(siblings) == 1:
                matches[gi] = en_by_ref[siblings[0]]
                continue

    # Remove crossings: if Greek order and English order disagree,
    # fix the crossing by adjusting the English index to be monotonic.
    # A crossing is: gi1 < gi2 but matches[gi1] > matches[gi2].
    sorted_gi = sorted(matches.keys())
    max_en = -1
    for gi in sorted_gi:
        ei = matches[gi]
        if ei < max_en:
            # Crossing — adjust to match the previous English position
            matches[gi] = max_en
        else:
            max_en = ei

    return matches


def run_dp_alignment(config, greek_data, english_data, model):
    """Run segmental DP alignment, book by book or work by work.

    Tries CTS reference matching first, then falls back to embedding DP
    for unmatched sections. Builds a lexical overlap table from the initial
    alignment and uses it as an additional signal in a second DP pass.
    """
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

    from lexical_overlap import build_lexical_table, build_lexical_matrix

    for book, greek_secs, english_secs in groups:
        print(f"\n=== {book}: {len(greek_secs)} source, {len(english_secs)} target ===")

        # --- CTS reference matching ---
        cts_matches = try_cts_match(greek_secs, english_secs)
        if cts_matches:
            cts_pct = len(cts_matches) / len(greek_secs) * 100
            print(f"  CTS matched: {len(cts_matches)}/{len(greek_secs)} ({cts_pct:.0f}%)")

        # --- Detect unmatched prefix using entity anchors ---
        # If the first strong entity anchor is far into the Greek text,
        # the beginning is likely untranslated (preface, argument).
        prefix_gr = 0
        if (len(cts_matches) < len(greek_secs) * 0.5 and
                len(greek_secs) > 20):
            import pickle as _pkl
            _lex_path = PROJECT_ROOT / "build" / "global_lexical_table.pkl"
            if _lex_path.exists():
                with open(_lex_path, "rb") as _lf:
                    _lex = _pkl.load(_lf)
                from sentence_align import find_anchors
                _anchors = find_anchors(greek_secs, english_secs,
                                        _lex["src2en"], _lex["src_idf"])
                if _anchors and _anchors[0][0] > 5:
                    prefix_gr = _anchors[0][0]
                    print(f"  Unmatched prefix: {prefix_gr} Greek sections")

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

        # Auto-scale max_source and max_target from section count ratios
        gr_per_en = len(greek_secs) / max(len(english_secs), 1)
        en_per_gr = len(english_secs) / max(len(greek_secs), 1)
        max_source = max(5, int(gr_per_en * 2))
        max_target = max(2, int(en_per_gr * 2))
        print(f"  Ratio: {gr_per_en:.1f} source/target, max_source={max_source}, max_target={max_target}")

        # Extract speaker sequences if sections have them (drama works).
        # Normalize both sides to canonical IDs so Greek Σωσίας matches
        # English SOSIAS/Sos/SOS.
        source_speakers = None
        target_speakers = None
        if (any(s.get("speakers") for s in greek_secs) and
                any(s.get("speaker") for s in english_secs)):
            from entity_anchors import greek_to_latin

            # Collect unique Greek speakers → transliterated form
            gr_speaker_map = {}  # transliterated → canonical ID
            for s in greek_secs:
                for spk in s.get("speakers", []):
                    lat = greek_to_latin(spk)
                    if lat not in gr_speaker_map:
                        gr_speaker_map[lat] = lat

            # Map English speakers to canonical IDs by prefix or fuzzy matching
            en_speaker_map = {}  # english_lower → canonical ID
            for s in english_secs:
                en_spk = s.get("speaker", "").lower().strip()
                if not en_spk or en_spk in en_speaker_map:
                    continue
                # Find best Greek match: prefix or fuzzy
                best = None
                best_score = 0
                for gr_lat in gr_speaker_map:
                    # Prefix match (handles abbreviations: sos→sosias)
                    if gr_lat.startswith(en_spk) or en_spk.startswith(gr_lat):
                        best = gr_lat
                        break
                    # Fuzzy match (handles transliteration: bdelycleon→bdelykleon)
                    score = fuzz.ratio(en_spk, gr_lat)
                    if score > best_score and score >= 60:
                        best_score = score
                        best = gr_lat
                en_speaker_map[en_spk] = best if best else en_spk

            source_speakers = [
                [gr_speaker_map.get(greek_to_latin(spk), greek_to_latin(spk))
                 for spk in s.get("speakers", [])]
                for s in greek_secs
            ]
            target_speakers = [
                en_speaker_map.get(s.get("speaker", "").lower().strip(), "")
                for s in english_secs
            ]

            # Report mapping
            mapped = {v for v in en_speaker_map.values() if v in gr_speaker_map}
            print(f"  Speaker mapping: {len(mapped)} English→Greek matches")

        # Compute entity overlap matrix
        n_g, n_e = len(greek_secs), len(english_secs)
        gr_names = [extract_greek_names(s.get("text_for_embedding", s["text"]))
                     for s in greek_secs]
        en_names = [extract_english_names(s.get("text_for_embedding", s["text"]))
                     for s in english_secs]
        entity_matrix = np.zeros((n_g, n_e), dtype=np.float32)
        for si in range(n_g):
            if not gr_names[si]:
                continue
            for tj in range(n_e):
                if not en_names[tj]:
                    continue
                matches = sum(1 for _, gn_lat in gr_names[si]
                              if any(fuzz.partial_ratio(gn_lat, en) > 75
                                     for en in en_names[tj]))
                if matches > 0:
                    entity_matrix[si][tj] = matches / len(gr_names[si])

        # --- First DP pass ---
        groups_result = segmental_dp_align(
            greek_embs, english_embs, greek_lens, english_lens,
            expected_ratio, max_source=max_source, max_target=max_target,
            source_speakers=source_speakers, target_speakers=target_speakers,
            entity_matrix=entity_matrix,
        )
        print(f"  DP pass 1: {len(groups_result)} groups")

        # --- Build lexical table from first-pass alignment ---
        # Use CTS matches (high confidence) + DP results
        aligned_pairs = []
        # From CTS matches
        for gi, ei in cts_matches.items():
            aligned_pairs.append((
                greek_secs[gi].get("text_for_embedding", greek_secs[gi]["text"]),
                english_secs[ei].get("text_for_embedding", english_secs[ei]["text"]),
            ))
        # From DP groups
        for gs, ge, es, ee, score in groups_result:
            gr_text = " ".join(greek_secs[i].get("text_for_embedding", greek_secs[i]["text"])
                               for i in range(gs, ge))
            en_text = " ".join(english_secs[j].get("text_for_embedding", english_secs[j]["text"])
                               for j in range(es, ee))
            aligned_pairs.append((gr_text, en_text))

        if aligned_pairs:
            src2en, src_idf, _ = build_lexical_table(aligned_pairs)
            if src2en:
                print(f"  Lexical table: {len(src2en)} words")
                # Build lexical matrix
                gr_texts = [s.get("text_for_embedding", s["text"]) for s in greek_secs]
                en_texts = [s.get("text_for_embedding", s["text"]) for s in english_secs]
                lexical_matrix = build_lexical_matrix(gr_texts, en_texts, src2en, src_idf,
                                                     bandwidth=max(30, n_e // 3))

                # Combine entity + lexical (take max — they complement each other)
                combined_matrix = np.maximum(entity_matrix, lexical_matrix)

                # --- Second DP pass with combined matrix ---
                groups_result = segmental_dp_align(
                    greek_embs, english_embs, greek_lens, english_lens,
                    expected_ratio, max_source=max_source, max_target=max_target,
                    source_speakers=source_speakers, target_speakers=target_speakers,
                    entity_matrix=combined_matrix,
                )
                print(f"  DP pass 2: {len(groups_result)} groups")

        # CTS-first alignment: when CTS covers >50% of Greek sections,
        # use CTS matches as the base and run DP only on gaps between
        # CTS anchors. This replaces the old 100%-only override.
        cts_pct = len(cts_matches) / max(len(greek_secs), 1)
        trailing_en_indices = set()  # English sections beyond last Greek, per book
        if cts_pct > 0.5:
            sorted_gi = sorted(cts_matches.keys())

            # Build CTS groups: consolidate consecutive Greek sections that
            # map to the same English section (for refinement later)
            cts_groups = []
            prev_ei = None
            group_gs = sorted_gi[0]
            for gi in sorted_gi:
                ei = cts_matches[gi]
                if prev_ei is not None and ei != prev_ei:
                    cts_groups.append((group_gs, gi, prev_ei, prev_ei + 1, 1.0))
                    group_gs = gi
                prev_ei = ei
            if prev_ei is not None:
                cts_groups.append((group_gs, sorted_gi[-1] + 1, prev_ei,
                                   prev_ei + 1, 1.0))

            # Identify gaps: Greek sections between CTS anchors with no match
            gaps = []
            # Gap before first CTS match — include as prefix group even if
            # there's no English before the first CTS anchor. The gap DP
            # will match these to the nearest English, or they'll be unmatched.
            if sorted_gi[0] > 0:
                en_bound = max(cts_matches[sorted_gi[0]], 1)  # at least en[0:1]
                gaps.append((0, sorted_gi[0], 0, en_bound))
            # Gaps between consecutive CTS matches
            for i in range(len(sorted_gi) - 1):
                gi1, gi2 = sorted_gi[i], sorted_gi[i + 1]
                ei1, ei2 = cts_matches[gi1], cts_matches[gi2]
                if gi2 - gi1 > 1 and ei2 - ei1 > 0:
                    gaps.append((gi1 + 1, gi2, ei1 + 1, ei2))
            # Gap after last CTS match
            last_gi = sorted_gi[-1]
            last_ei = cts_matches[last_gi]
            trailing_gr = len(greek_secs) - (last_gi + 1)
            trailing_en = len(english_secs) - (last_ei + 1)
            if trailing_gr > 0 or trailing_en > 0:
                en_start = min(last_ei + 1, len(english_secs))
                en_end = len(english_secs)
                gr_start = last_gi + 1
                gr_end = len(greek_secs)
                if trailing_gr > 0 and trailing_en > 0:
                    gaps.append((gr_start, gr_end, en_start, en_end))
                elif trailing_gr > 0:
                    # Trailing Greek, no trailing English — force-match
                    gaps.append((gr_start, gr_end,
                                 max(0, len(english_secs) - 1), len(english_secs)))
                elif trailing_en > 0:
                    # Trailing English, no trailing Greek — these English
                    # sections are finer subdivisions beyond the last Greek
                    # section. Track them to suppress unmatched emission later.
                    trailing_en_indices = set(range(en_start, en_end))

            # Run DP on each gap to fill in un-CTS-matched sections.
            # Small gaps (≤3 Greek sections) are assigned to the nearest
            # English section as a single group — DP on tiny sub-problems
            # produces degenerate results with no context.
            gap_groups = []
            for gs, ge, es, ee in gaps:
                g_len = ge - gs
                e_len = ee - es
                if g_len == 0 or e_len == 0:
                    continue
                if g_len <= 3 or e_len <= 1:
                    # Small gap: assign all Greek sections to first English
                    gap_groups.append((gs, ge, es, min(es + 1, ee), 0.5))
                else:
                    # Large gap: run DP (cap max_source to avoid explosion)
                    gap_max_source = min(max(max_source, g_len), 20)
                    p_ratio = (sum(greek_lens[gs:ge]) /
                               max(sum(english_lens[es:ee]), 1))
                    p_spk_src = source_speakers[gs:ge] if source_speakers else None
                    p_spk_tgt = target_speakers[es:ee] if target_speakers else None
                    p_ent = entity_matrix[gs:ge, es:ee] if entity_matrix is not None else None
                    sub = segmental_dp_align(
                        greek_embs[gs:ge], english_embs[es:ee],
                        greek_lens[gs:ge], english_lens[es:ee],
                        p_ratio, max_source=gap_max_source, max_target=max_target,
                        source_speakers=p_spk_src, target_speakers=p_spk_tgt,
                        entity_matrix=p_ent,
                    )
                    for s_s, s_e, t_s, t_e, sc in sub:
                        gap_groups.append((s_s + gs, s_e + gs,
                                           t_s + es, t_e + es, sc))

            # Merge CTS groups + gap DP results, sorted by Greek position
            groups_result = sorted(cts_groups + gap_groups)
            n_gap_gr = sum(ge - gs for gs, ge, _, _, _ in gap_groups)
            print(f"  CTS-first: {len(cts_groups)} CTS groups + "
                  f"{len(gap_groups)} gap groups ({len(gaps)} gaps, "
                  f"{n_gap_gr} Greek sections in gaps)")

        print(f"  Final: {len(groups_result)} alignment groups")

        # Override prefix sections as unmatched (detected earlier)
        if prefix_gr > 0:
            new_groups = []
            # First group: all prefix Greek → first English (unmatched)
            new_groups.append((0, prefix_gr, 0, 1, 0.0))
            # Keep only DP groups that start after the prefix
            for gs, ge, es, ee, sc in groups_result:
                if gs >= prefix_gr:
                    new_groups.append((gs, ge, es, ee, sc))
                elif ge > prefix_gr:
                    # Overlapping — trim to start at prefix_gr
                    new_groups.append((prefix_gr, ge, es, ee, sc))
            groups_result = new_groups

        # Build records — ensure every English section appears
        en_used = set(trailing_en_indices)  # trailing English beyond last Greek
        for gr_start, gr_end, en_start, en_end, score in groups_result:
            for ej in range(en_start, en_end):
                en_used.add(ej)
                # If this English section was split, mark all siblings as used
                # (their text is included in the refinement via concatenation)
                sf = english_secs[ej].get("split_from")
                if sf:
                    for other_ej, other_es in enumerate(english_secs):
                        if other_es.get("split_from") == sf:
                            en_used.add(other_ej)

        en_skipped = len(english_secs) - len(en_used)

        # Build CTS lookup: for each Greek index, which English index did CTS assign?
        # Used to tag match_type as "cts_aligned" / "cts_refined" when the DP
        # result agrees with CTS structural matching.
        cts_en_for_gr = {}  # greek_idx → english_idx from CTS
        for gi, ei in cts_matches.items():
            cts_en_for_gr[gi] = ei

        en_to_greek = {}
        refined_count = 0
        for group_id, (gr_start, gr_end, en_start, en_end, score) in enumerate(groups_result):
            n_gr = gr_end - gr_start
            n_en = en_end - en_start

            # Refinement: when multiple Greek sections map to 1 English section,
            # split the English at sentence boundaries and match each piece to a
            # Greek section using embedding similarity.
            if n_gr > 1 and n_en == 1 and score > 0:
                ej = en_start
                es = english_secs[ej]
                en_text = es.get("text_for_embedding", es["text"])
                # If this English section was split by the pipeline, concatenate
                # all split siblings' text so refinement sees the full content.
                sf = es.get("split_from")
                if sf:
                    sibling_texts = []
                    for other_es in english_secs:
                        if other_es.get("split_from") == sf:
                            sibling_texts.append(
                                other_es.get("text_for_embedding", other_es["text"]))
                    if sibling_texts:
                        en_text = " ".join(sibling_texts)
                gr_emb_group = greek_embs[gr_start:gr_end]

                gr_texts_group = [greek_secs[gi].get("text_for_embedding",
                                    greek_secs[gi]["text"])
                                  for gi in range(gr_start, gr_end)]
                refined = _refine_group(model, en_text, n_gr, gr_emb_group,
                                        gr_texts=gr_texts_group)

                if refined and any(r is not None for r in refined):
                    refined_count += 1
                    if ej not in en_to_greek:
                        en_to_greek[ej] = []
                    for gi_offset, entry in enumerate(refined):
                        gi_abs = gr_start + gi_offset
                        gs = greek_secs[gi_abs]
                        is_cts_match = (gi_abs in cts_en_for_gr and
                                        cts_en_for_gr[gi_abs] == ej)
                        if entry is not None:
                            sub_text, sub_sim = entry
                            en_to_greek[ej].append({
                                "book": str(book),
                                "greek_cts_ref": gs["cts_ref"],
                                "greek_edition": gs.get("edition", ""),
                                "english_cts_ref": es["cts_ref"],
                                "english_section": es.get("section", ""),
                                "similarity": round(sub_sim, 4),
                                "greek_preview": gs["text"][:80],
                                "english_preview": sub_text[:80],
                                "english_refined_text": sub_text,
                                "group_id": group_id,
                                "group_size_gr": 1,
                                "group_size_en": 1,
                                "match_type": "cts_refined" if is_cts_match else "dp_refined",
                                "refined_part": gi_offset,
                            })
                        else:
                            # No refined text for this Greek section — show arrow
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
                                "group_size_gr": n_gr,
                                "group_size_en": 1,
                                "match_type": "cts_aligned" if is_cts_match else "dp_aligned",
                            })
                    continue

            # Default: no refinement — all Greek sections point to same English
            for ej in range(en_start, en_end):
                if ej not in en_to_greek:
                    en_to_greek[ej] = []
                for gi in range(gr_start, gr_end):
                    gs = greek_secs[gi]
                    es = english_secs[ej]
                    is_cts_match = (gi in cts_en_for_gr and
                                    cts_en_for_gr[gi] == ej)
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
                        "match_type": "cts_aligned" if is_cts_match else "dp_aligned",
                    })

        if refined_count > 0:
            print(f"  Refined {refined_count} groups (split English to match Greek)")

        # Link split siblings: if en[15] (1.16.0) is in en_to_greek but
        # en[16] (1.16.1, same split_from) is not, add en[16] pointing to
        # the last Greek section in en[15]'s group. This ensures the sibling
        # appears in the alignment output (integrity requires all English present).
        split_linked = 0
        for ej in list(en_to_greek.keys()):
            sf = english_secs[ej].get("split_from")
            if not sf:
                continue
            for other_ej, other_es in enumerate(english_secs):
                if other_ej != ej and other_es.get("split_from") == sf and other_ej not in en_to_greek:
                    # Link sibling: emit as a continuation of its split parent.
                    # Use greek_cts_ref=None so it's not subject to dedup, and
                    # match_type="split_continuation" so scoring can handle it.
                    last_rec = en_to_greek[ej][-1]
                    en_to_greek[other_ej] = [{
                        "book": str(book),
                        "greek_cts_ref": None,
                        "greek_edition": None,
                        "english_cts_ref": other_es["cts_ref"],
                        "english_section": other_es.get("section", ""),
                        "similarity": last_rec.get("similarity", 0),
                        "greek_preview": "",
                        "english_preview": other_es["text"][:80],
                        "group_id": last_rec.get("group_id"),
                        "group_size_gr": 0,
                        "group_size_en": 1,
                        "match_type": "split_continuation",
                    }]
                    split_linked += 1
        if split_linked > 0:
            print(f"  Linked {split_linked} split siblings")

        emitted_gr = set()
        for ej in range(len(english_secs)):
            emitted_any = False
            if ej in en_to_greek:
                for rec in en_to_greek[ej]:
                    gr_ref = rec.get("greek_cts_ref")
                    if gr_ref:
                        if gr_ref in emitted_gr:
                            continue  # skip duplicate Greek section
                        emitted_gr.add(gr_ref)
                    all_alignments.append(rec)
                    emitted_any = True
            if not emitted_any:
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

    # Verify order: the loop above already emits in English order (which
    # preserves Greek order for matched sections since the DP is monotonic).
    # Don't re-sort — it would break the interleaving of unmatched English
    # sections with their neighbors.

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
        greek_embs, english_embs, min_similarity=MIN_PAIRWISE_SIMILARITY,
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

    # Merge heading/non-content sections into the next section.
    # Headings (is_heading=True) and sections with empty text_for_embedding
    # are editorial content (chapter summaries, footnotes) that shouldn't
    # take up DP slots. Merge them into the next real section so all text
    # is preserved but the DP only sees translation content.
    for data in [greek_data, english_data]:
        merged = []
        pending_text = ""
        for s in data["sections"]:
            is_non_content = (s.get("is_heading") or
                              s.get("text_for_embedding", None) == "")
            if is_non_content:
                pending_text += " " + s["text"] if pending_text else s["text"]
            else:
                if pending_text:
                    s["heading_text"] = pending_text.strip()
                    s["text"] = pending_text + " " + s["text"]
                    s["char_count"] = len(s["text"])
                    pending_text = ""
                merged.append(s)
        # If trailing pending text, append to last section
        if pending_text and merged:
            merged[-1]["text"] += " " + pending_text
            merged[-1]["char_count"] = len(merged[-1]["text"])
        elif pending_text:
            # Edge case: all sections are headings — keep them
            merged = data["sections"]
        data["sections"] = merged

    # Split oversized sections that would produce blurred embeddings.
    # Two thresholds combined (take the more conservative):
    # - Outlier detection: median * 4 (only split sections much larger than peers)
    # - Model capacity: 2x the model's effective char capacity (sections losing
    #   >50% content to truncation)
    # The outlier threshold prevents fragmenting works where all sections are
    # uniformly large (e.g. long treatise chapters). The model capacity threshold
    # prevents splitting sections that already fit the model even if they look
    # like outliers relative to very short peers.
    source_lang = config.get("source_language", "greek")
    for label, data, lang in [("source", greek_data, source_lang),
                              ("English", english_data, "english")]:
        cpt = CHARS_PER_TOKEN.get(lang, 4.5)
        max_tokens = _model_max_seq_length or 512
        model_capacity = int(max_tokens * cpt * 0.9)
        content_lens = sorted(len(s.get("text_for_embedding", s["text"]))
                              for s in data["sections"])
        if not content_lens:
            continue
        median = content_lens[len(content_lens) // 2]
        threshold = max(median * 4, model_capacity * 2)
        oversized = sum(1 for c in content_lens if c > threshold)
        if oversized > 0:
            data["sections"] = split_large_sections(data["sections"], max_chars=threshold)
            print(f"  Split {label} outliers > {threshold} chars "
                  f"(median {median}, model cap {model_capacity}, {oversized} oversized)")

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

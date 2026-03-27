#!/usr/bin/env python3
"""
Sentence-level alignment using entity and lexical anchors.

Strategy:
1. Find entity-based anchors (Greek sections with strong entity matches
   to English sections, in order-preserving sequence)
2. Between anchors, run local sentence-level DP using entity + lexical
   similarity (no embeddings needed)
3. Sections before the first anchor are likely untranslated preface material

This replaces the embedding-based global DP for works where entity/lexical
signals are available.
"""

import math
import re
import numpy as np

from entity_anchors import extract_greek_names, extract_english_names, greek_to_latin
from lexical_overlap import extract_gr_words, extract_en_words
from rapidfuzz import fuzz

# Sentence splitting
GR_SENT_RE = re.compile(r'(?<=[.;·!?])\s+')
EN_SENT_RE = re.compile(r'(?<=[.!?;])\s+')
MIN_SENT_CHARS = 20


def split_sentences(text, pattern):
    """Split text into sentences, merging tiny fragments."""
    raw = pattern.split(text.strip())
    raw = [s.strip() for s in raw if s.strip()]
    merged = []
    for s in raw:
        if merged and len(s) < MIN_SENT_CHARS:
            merged[-1] = merged[-1] + " " + s
        else:
            merged.append(s)
    return merged


def entity_match_count(gr_text, en_text):
    """Count how many Greek proper names fuzzy-match English names."""
    gr_names = extract_greek_names(gr_text)
    if not gr_names:
        return 0
    en_names = extract_english_names(en_text)
    if not en_names:
        return 0
    return sum(1 for _, gn_lat in gr_names
               if any(fuzz.partial_ratio(gn_lat, en) > 75 for en in en_names))


def find_anchors(greek_secs, english_secs, src2en=None, src_idf=None,
                 min_entity_matches=2, min_lexical_score=0.25):
    """Find order-preserving anchor pairs using entities AND lexical overlap.

    Uses inverted index for fast matching — no pairwise scan.
    For each Greek section, finds candidate English sections that share
    entity names or lexical words, then picks the best.

    Returns list of (gr_idx, en_idx, score).
    """
    from collections import defaultdict

    # Pre-extract entity names
    gr_entities = []
    for gs in greek_secs:
        if 'arg' in gs.get('cts_ref', ''):
            gr_entities.append(set())
            continue
        text = gs.get('text_for_embedding', gs['text'])
        names = extract_greek_names(text)
        gr_entities.append(set(lat for _, lat in names))

    en_entity_names = []
    for es in english_secs:
        text = es.get('text_for_embedding', es['text'])
        en_entity_names.append(set(extract_english_names(text)))

    # Pre-extract lexical words using the PMI lexicon
    gr_lex_words = []
    en_lex_words = []
    for gs in greek_secs:
        text = gs.get('text_for_embedding', gs['text'])
        gr_words = extract_gr_words(text)
        # Map Greek words to possible English translations via lexicon
        possible_en = set()
        if src2en:
            for gw in gr_words:
                if gw in src2en:
                    possible_en.update(src2en[gw].keys())
        gr_lex_words.append(possible_en)

    for es in english_secs:
        text = es.get('text_for_embedding', es['text'])
        en_lex_words.append(extract_en_words(text))

    # Build inverted index: name/word → set of English section indices
    en_entity_index = defaultdict(set)
    for ei, names in enumerate(en_entity_names):
        for name in names:
            en_entity_index[name].add(ei)

    en_word_index = defaultdict(set)
    for ei, words in enumerate(en_lex_words):
        for word in words:
            en_word_index[word].add(ei)

    # For each Greek section, find best English match via index lookup
    best_match = {}
    for gi in range(len(greek_secs)):
        if not gr_entities[gi] and not gr_lex_words[gi]:
            continue
        if len(greek_secs[gi].get('text', '')) < 30:
            continue

        candidates = defaultdict(float)

        # Entity matches via index
        for gn in gr_entities[gi]:
            for en_name in en_entity_index:
                if (gn[:4] == en_name[:4] or
                        en_name.startswith(gn) or gn.startswith(en_name)):
                    for ei in en_entity_index[en_name]:
                        candidates[ei] += 2.0

        # Lexical matches via index
        for possible_en_word in gr_lex_words[gi]:
            if possible_en_word in en_word_index:
                for ei in en_word_index[possible_en_word]:
                    candidates[ei] += 0.5

        if candidates:
            best_ei = max(candidates, key=candidates.get)
            if candidates[best_ei] >= 2.0:
                best_match[gi] = (best_ei, candidates[best_ei])

    if not best_match:
        return []

    # Longest increasing subsequence on English indices (weighted by score)
    pairs = sorted(best_match.items())  # sorted by gi
    n = len(pairs)
    dp_lis = [0.0] * n
    parent_lis = [-1] * n

    for i in range(n):
        dp_lis[i] = pairs[i][1][1]  # weight = score
        for j in range(i):
            if pairs[j][1][0] < pairs[i][1][0]:  # ei strictly increasing
                if dp_lis[j] + pairs[i][1][1] > dp_lis[i]:
                    dp_lis[i] = dp_lis[j] + pairs[i][1][1]
                    parent_lis[i] = j

    # Backtrack
    best_i = max(range(n), key=lambda i: dp_lis[i])
    lis = []
    i = best_i
    while i >= 0:
        gi, (ei, score) = pairs[i]
        lis.append((gi, ei, score))
        i = parent_lis[i]
    lis.reverse()

    return lis


def sentence_similarity(gr_sent, en_sent, src2en, src_idf):
    """Score a Greek/English sentence pair using entities + lexical overlap."""
    score = 0.0

    # Entity matches (strong signal)
    gr_names = extract_greek_names(gr_sent)
    en_names = extract_english_names(en_sent)
    if gr_names and en_names:
        for _, gn_lat in gr_names:
            for en in en_names:
                if fuzz.partial_ratio(gn_lat, en) > 75:
                    score += 2.0
                    break

    # Lexical matches (PMI weighted)
    gr_words = extract_gr_words(gr_sent)
    en_words = extract_en_words(en_sent)
    if gr_words and en_words and src2en:
        for gw in gr_words:
            idf = src_idf.get(gw, 0)
            if idf <= 0 or gw not in src2en:
                continue
            for ew, tw in src2en[gw].items():
                if ew in en_words:
                    score += idf * tw
                    break

    return score


def local_sentence_dp(gr_sents, en_sents, src2en, src_idf,
                      max_source=5, max_target=3):
    """Run sentence-level DP alignment on a small local segment.

    No bandwidth constraint — segments are small enough for full search.
    """
    n_gr = len(gr_sents)
    n_en = len(en_sents)

    if n_gr == 0 or n_en == 0:
        return []

    # Build similarity matrix (full — segments are small)
    sim = np.zeros((n_gr, n_en), dtype=np.float32)
    for i in range(n_gr):
        for j in range(n_en):
            sim[i][j] = sentence_similarity(
                gr_sents[i], en_sents[j], src2en, src_idf)

    # Length-based expected ratio
    gr_lens = [len(s) for s in gr_sents]
    en_lens = [len(s) for s in en_sents]
    total_gr = sum(gr_lens)
    total_en = sum(en_lens)
    expected_ratio = total_gr / total_en if total_en > 0 else 1.0

    prefix_gr = np.zeros(n_gr + 1)
    prefix_en = np.zeros(n_en + 1)
    for i in range(n_gr):
        prefix_gr[i + 1] = prefix_gr[i] + gr_lens[i]
    for j in range(n_en):
        prefix_en[j + 1] = prefix_en[j] + en_lens[j]

    # DP — no bandwidth constraint
    NEG_INF = -1e18
    dp = np.full((n_gr + 1, n_en + 1), NEG_INF, dtype=np.float64)
    dp[0][0] = 0.0
    parent = [[None] * (n_en + 1) for _ in range(n_gr + 1)]

    for i in range(n_gr + 1):
        for j in range(n_en + 1):
            if dp[i][j] == NEG_INF:
                continue
            for g in range(1, min(max_source + 1, n_gr - i + 1)):
                for e in range(1, min(max_target + 1, n_en - j + 1)):
                    group_sim = 0.0
                    for gi in range(i, i + g):
                        for ej in range(j, j + e):
                            group_sim += sim[gi][ej]

                    # Length ratio bonus
                    gc = prefix_gr[i + g] - prefix_gr[i]
                    ec = prefix_en[j + e] - prefix_en[j]
                    if ec > 0 and expected_ratio > 0:
                        ratio = (gc / ec) / expected_ratio
                        length_bonus = math.exp(-0.5 * (ratio - 1.0) ** 2) * 0.5
                    else:
                        length_bonus = 0.0

                    new_score = dp[i][j] + group_sim + length_bonus
                    if new_score > dp[i + g][j + e]:
                        dp[i + g][j + e] = new_score
                        parent[i + g][j + e] = (i, j, g, e)

    # Backtrack
    ci, cj = n_gr, n_en
    if dp[ci][cj] == NEG_INF:
        best = NEG_INF
        for i in range(n_gr + 1):
            for j in range(n_en + 1):
                if dp[i][j] > best:
                    best = dp[i][j]
                    ci, cj = i, j

    groups = []
    while ci > 0 and cj > 0 and parent[ci][cj] is not None:
        pi, pj, g, e = parent[ci][cj]
        group_sim = sum(sim[gi][ej]
                        for gi in range(pi, ci) for ej in range(pj, cj))
        groups.append((pi, ci, pj, cj, group_sim))
        ci, cj = pi, pj
    groups.reverse()
    return groups


def align_book_by_anchors(greek_secs, english_secs, src2en, src_idf):
    """Align Greek and English sections within a book using entity anchors.

    1. Find entity-based anchors (order-preserving)
    2. Between each pair of consecutive anchors, run local sentence DP
    3. Return section-level alignment groups

    Returns list of (gr_start, gr_end, en_start, en_end, score).
    """
    # Find anchors using entities + lexical overlap
    anchors = find_anchors(greek_secs, english_secs, src2en, src_idf)
    if not anchors:
        return []

    print(f"    Entity anchors: {len(anchors)}")

    # Build anchor points. Do NOT force (0,0) as a start — sections
    # before the first real anchor are unmatched (e.g. untranslated preface).
    anchor_points = []
    for gi, ei, nm in anchors:
        anchor_points.append((gi, ei))
    anchor_points.append((len(greek_secs), len(english_secs)))

    # Deduplicate and sort
    seen = set()
    unique = []
    for p in anchor_points:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    anchor_points = sorted(unique)

    # Emit unmatched Greek sections before the first anchor
    all_groups = []
    first_gr = anchor_points[0][0] if anchor_points else len(greek_secs)
    first_en = anchor_points[0][1] if anchor_points else len(english_secs)
    if first_gr > 0:
        # Greek sections 0..first_gr have no English counterpart.
        # Map them to the first English section (score 0 = unmatched)
        # so they appear in the output without losing any text.
        en_target = min(first_en, len(english_secs) - 1)
        all_groups.append((0, first_gr, en_target, en_target + 1, 0.0))
        print(f"    Unmatched prefix: {first_gr} Greek sections")

    # Between each pair of anchor points, run local sentence DP
    for ai in range(len(anchor_points) - 1):
        gs, es = anchor_points[ai]
        ge, ee = anchor_points[ai + 1]

        if gs >= ge:
            continue

        seg_gr = greek_secs[gs:ge]
        seg_en = english_secs[es:ee] if es < ee else []

        if not seg_en:
            # No English for this range — all unmatched
            # Still need to emit groups for the pipeline
            all_groups.append((gs, ge, max(es - 1, 0), max(es, 1), 0.0))
            continue

        # Split into sentences
        gr_sents = []
        gr_sent_sec = []
        for si, sec in enumerate(seg_gr):
            text = sec.get('text_for_embedding', sec['text'])
            for sent in split_sentences(text, GR_SENT_RE):
                gr_sents.append(sent)
                gr_sent_sec.append(si)

        en_sents = []
        en_sent_sec = []
        for si, sec in enumerate(seg_en):
            text = sec.get('text_for_embedding', sec['text'])
            for sent in split_sentences(text, EN_SENT_RE):
                en_sents.append(sent)
                en_sent_sec.append(si)

        if not gr_sents or not en_sents:
            all_groups.append((gs, ge, es, ee, 0.0))
            continue

        # Run local DP
        sent_groups = local_sentence_dp(gr_sents, en_sents, src2en, src_idf)

        # Map sentence groups back to section groups
        sec_map = {}
        for sgs, sge, ses, see, score in sent_groups:
            for sgi in range(sgs, sge):
                gr_sec = gr_sent_sec[sgi] + gs  # global index
                for sei in range(ses, see):
                    en_sec = en_sent_sec[sei] + es  # global index
                    if gr_sec not in sec_map:
                        sec_map[gr_sec] = {}
                    if en_sec not in sec_map[gr_sec]:
                        sec_map[gr_sec][en_sec] = 0.0
                    sec_map[gr_sec][en_sec] += score

        # Build section groups
        prev_en = -1
        group_start = gs
        group_en = es
        for gi in range(gs, ge):
            if gi in sec_map:
                best_en = max(sec_map[gi], key=sec_map[gi].get)
            else:
                best_en = group_en

            if prev_en >= 0 and best_en != group_en:
                all_groups.append((group_start, gi, group_en, group_en + 1, 0.0))
                group_start = gi
            group_en = best_en
            prev_en = best_en

        if group_start < ge:
            all_groups.append((group_start, ge, group_en, group_en + 1, 0.0))

    print(f"    Section groups: {len(all_groups)}")
    return all_groups

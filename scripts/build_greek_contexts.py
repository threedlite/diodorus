#!/usr/bin/env python3
"""
Build Greek distributional context vectors from the corpus.

For each Greek content word, records which other Greek words appear within
a ±N word window. Applies PPMI weighting and optional SVD dimensionality
reduction.

Outputs: build/greek_contexts.pkl

Usage:
    python scripts/build_greek_contexts.py
"""

import json
import math
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import svds

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "pipeline"))

from lexical_overlap import GR_WORD_RE, GR_STOPS

TEI_NS = "{http://www.tei-c.org/ns/1.0}"

WINDOW = 5          # context window ±N words
MIN_WORD_FREQ = 5   # minimum word frequency to include
SVD_DIMS = 200      # dimensionality after SVD reduction


def extract_greek_texts_from_perseus():
    """Extract all Greek text from Perseus XML files."""
    from lxml import etree

    texts = []
    perseus_dir = PROJECT_ROOT / "data-sources" / "perseus" / "canonical-greekLit" / "data"
    if not perseus_dir.exists():
        return texts

    count = 0
    for author_dir in sorted(perseus_dir.iterdir()):
        if not author_dir.is_dir():
            continue
        for work_dir in sorted(author_dir.iterdir()):
            if not work_dir.is_dir():
                continue
            grc_files = [f for f in work_dir.glob("*grc*.xml") if f.name != "__cts__.xml"]
            for grc in grc_files:
                try:
                    tree = etree.parse(str(grc))
                    root = tree.getroot()
                    for div in root.iter(f"{TEI_NS}div"):
                        subtype = div.get("subtype", "")
                        if subtype in ("chapter", "section", "card"):
                            text = " ".join(div.itertext()).strip()
                            if len(text) > 30:
                                texts.append(text)
                                count += 1
                except Exception:
                    continue

    print(f"  Perseus: {count} sections")
    return texts


def extract_greek_texts_from_first1k():
    """Extract all Greek text from First1KGreek XML files."""
    from lxml import etree

    texts = []
    f1k_dir = PROJECT_ROOT / "data-sources" / "greek_corpus" / "First1KGreek" / "data"
    if not f1k_dir.exists():
        return texts

    count = 0
    for author_dir in sorted(f1k_dir.iterdir()):
        if not author_dir.is_dir():
            continue
        for work_dir in sorted(author_dir.iterdir()):
            if not work_dir.is_dir():
                continue
            grc_files = [f for f in work_dir.glob("*grc*.xml") if f.name != "__cts__.xml"]
            for grc in grc_files:
                try:
                    tree = etree.parse(str(grc))
                    root = tree.getroot()
                    for div in root.iter(f"{TEI_NS}div"):
                        subtype = div.get("subtype", "")
                        if subtype in ("chapter", "section", "card"):
                            text = " ".join(div.itertext()).strip()
                            if len(text) > 30:
                                texts.append(text)
                                count += 1
                except Exception:
                    continue

    print(f"  First1KGreek: {count} sections")
    return texts


def extract_greek_texts_from_aligned():
    """Extract Greek text from our aligned works."""
    works_dir = PROJECT_ROOT / "scripts" / "works"
    texts = []
    count = 0

    for config_path in sorted(works_dir.glob("*/config.json")):
        with open(config_path) as f:
            cfg = json.load(f)
        gr_path = PROJECT_ROOT / cfg["output_dir"] / "greek_sections.json"
        if not gr_path.exists():
            continue
        with open(gr_path) as f:
            gr_data = json.load(f)
        gr_secs = gr_data["sections"] if isinstance(gr_data, dict) else gr_data
        for s in gr_secs:
            text = s.get("text", "")
            if len(text) > 30:
                texts.append(text)
                count += 1

    print(f"  Aligned works: {count} sections")
    return texts


def tokenize(text):
    """Extract Greek content words from text, preserving order."""
    words = []
    for w in GR_WORD_RE.findall(text):
        if len(w) <= 2:
            continue
        wl = w.lower()
        if wl in GR_STOPS:
            continue
        words.append(wl)
    return words


def build_context_vectors(texts, window=WINDOW, min_freq=MIN_WORD_FREQ):
    """Build word co-occurrence matrix from Greek texts.

    Returns:
        cooccur: sparse CSR matrix (n_words × n_words)
        word2idx: dict mapping word → index
        idx2word: dict mapping index → word
        word_freq: dict mapping word → corpus frequency
    """
    # First pass: count word frequencies
    print("  Pass 1: counting word frequencies...")
    word_freq = Counter()
    for text in texts:
        for w in tokenize(text):
            word_freq[w] += 1

    # Filter to words above min_freq
    vocab = {w for w, f in word_freq.items() if f >= min_freq}
    word2idx = {w: i for i, w in enumerate(sorted(vocab))}
    idx2word = {i: w for w, i in word2idx.items()}
    n_vocab = len(word2idx)
    print(f"  Vocabulary: {n_vocab} words (freq >= {min_freq})")

    # Second pass: count co-occurrences within window
    print(f"  Pass 2: counting co-occurrences (window ±{window})...")
    cooccur_counts = Counter()
    total_windows = 0

    for text in texts:
        words = tokenize(text)
        for i, w in enumerate(words):
            if w not in word2idx:
                continue
            wi = word2idx[w]
            for j in range(max(0, i - window), min(len(words), i + window + 1)):
                if i == j:
                    continue
                cw = words[j]
                if cw not in word2idx:
                    continue
                cj = word2idx[cw]
                cooccur_counts[(wi, cj)] += 1
            total_windows += 1

    print(f"  Total windows: {total_windows:,}")
    print(f"  Non-zero co-occurrences: {len(cooccur_counts):,}")

    # Build sparse matrix
    rows, cols, vals = [], [], []
    for (i, j), count in cooccur_counts.items():
        rows.append(i)
        cols.append(j)
        vals.append(count)

    cooccur = sparse.csr_matrix((vals, (rows, cols)), shape=(n_vocab, n_vocab),
                                dtype=np.float32)

    return cooccur, word2idx, idx2word, dict(word_freq)


def apply_ppmi(cooccur, word2idx, word_freq):
    """Apply Positive Pointwise Mutual Information weighting.

    PPMI(w, c) = max(0, log(P(w,c) / (P(w) × P(c))))
    """
    print("  Applying PPMI weighting...")
    n_vocab = len(word2idx)

    # Total count
    total = cooccur.sum()
    if total == 0:
        return cooccur

    # Row and column marginals
    row_sums = np.array(cooccur.sum(axis=1)).flatten()
    col_sums = np.array(cooccur.sum(axis=0)).flatten()

    # Convert to COO for element-wise operations
    coo = cooccur.tocoo()
    new_vals = np.zeros(len(coo.data), dtype=np.float32)

    for idx in range(len(coo.data)):
        i, j, count = coo.row[idx], coo.col[idx], coo.data[idx]
        if count <= 0 or row_sums[i] <= 0 or col_sums[j] <= 0:
            continue
        pmi = math.log(count * total / (row_sums[i] * col_sums[j]))
        new_vals[idx] = max(0, pmi)

    ppmi = sparse.csr_matrix((new_vals, (coo.row, coo.col)),
                             shape=(n_vocab, n_vocab), dtype=np.float32)
    # Remove zeros
    ppmi.eliminate_zeros()
    nnz = ppmi.nnz
    print(f"  PPMI matrix: {nnz:,} non-zero entries")
    return ppmi


def reduce_dims(ppmi_matrix, n_dims=SVD_DIMS):
    """Reduce dimensionality with truncated SVD."""
    print(f"  SVD reduction to {n_dims} dimensions...")
    n_vocab = ppmi_matrix.shape[0]
    n_dims = min(n_dims, n_vocab - 1)

    U, S, Vt = svds(ppmi_matrix.astype(np.float32), k=n_dims)

    # Weight by sqrt(S) — standard practice for word vectors
    embeddings = U * np.sqrt(S)

    # Normalize rows to unit length
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms

    print(f"  Embeddings shape: {embeddings.shape}")
    return embeddings


def main():
    print("Building Greek distributional context vectors...\n")

    # Collect all Greek text
    print("Collecting Greek text...")
    texts = []
    texts.extend(extract_greek_texts_from_perseus())
    texts.extend(extract_greek_texts_from_first1k())
    texts.extend(extract_greek_texts_from_aligned())
    print(f"Total: {len(texts)} sections\n")

    # Build co-occurrence matrix
    print("Building co-occurrence matrix...")
    cooccur, word2idx, idx2word, word_freq = build_context_vectors(texts)

    # Apply PPMI
    ppmi = apply_ppmi(cooccur, word2idx, word_freq)

    # Reduce dimensions with SVD
    embeddings = reduce_dims(ppmi)

    # Save
    out_path = PROJECT_ROOT / "build" / "greek_contexts.pkl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump({
            "embeddings": embeddings,
            "word2idx": word2idx,
            "idx2word": idx2word,
            "word_freq": word_freq,
            "window": WINDOW,
            "min_freq": MIN_WORD_FREQ,
            "svd_dims": SVD_DIMS,
        }, f)
    print(f"\nSaved: {out_path}")
    print(f"  {len(word2idx)} words, {embeddings.shape[1]} dimensions")

    # Quick sanity check: find nearest neighbors for a few test words
    print("\nNearest neighbors (sanity check):")
    test_words = ["θάνατος", "πόλεμος", "βασιλεύς", "ἀγαπῶν", "ἠγάπησεν",
                  "ἀγάπη", "φιλία", "πόλις", "στρατηγός"]
    for tw in test_words:
        if tw not in word2idx:
            print(f"  {tw}: NOT IN VOCAB")
            continue
        ti = word2idx[tw]
        tv = embeddings[ti]
        # Cosine similarity to all others
        sims = embeddings @ tv
        top_idx = np.argsort(-sims)[1:8]  # skip self
        neighbors = [(idx2word[i], f"{sims[i]:.3f}") for i in top_idx]
        nb_str = ", ".join(f"{w}({s})" for w, s in neighbors)
        print(f"  {tw}: {nb_str}")


if __name__ == "__main__":
    main()

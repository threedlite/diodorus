#!/usr/bin/env python3
"""
Extend xlm-roberta-base tokenizer with frequent Ancient Greek subwords.

Only run this if s03_check_tokenizer.py reports fragmentation > 2.5x.

Strategy: Find Greek words and subwords that the base tokenizer
over-fragments, and add the most frequent ones as new tokens.
This uses corpus frequency analysis rather than a byte-level BPE
(which produces tokens incompatible with SentencePiece).

Input:
  - data-sources/greek_corpus/ancient_greek_all.txt

Output:
  - models/xlm-r-greek-extended/ (tokenizer + resized model)
"""

import re
from collections import Counter
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForMaskedLM

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_NAME = "xlm-roberta-base"
CORPUS = PROJECT_ROOT / "data-sources" / "greek_corpus" / "ancient_greek_all.txt"
EXTENDED_DIR = PROJECT_ROOT / "models" / "xlm-r-greek-extended"

if not CORPUS.exists():
    print(f"Error: corpus not found at {CORPUS}")
    print("Run s01_build_greek_corpus.py first.")
    raise SystemExit(1)

print(f"Loading {MODEL_NAME} tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
existing_vocab = set(tokenizer.get_vocab().keys())

# Read corpus and find frequently-occurring Greek words that get over-fragmented
print("Analyzing corpus for over-fragmented Greek words...")
word_freq = Counter()
with open(CORPUS, encoding="utf-8") as f:
    for line in f:
        words = line.strip().split()
        for w in words:
            # Only consider words with Greek characters
            if any("\u0370" <= c <= "\u03FF" or "\u1F00" <= c <= "\u1FFF" for c in w):
                word_freq[w] += 1

print(f"Unique Greek words: {len(word_freq)}")

# Find words that the tokenizer fragments into 3+ tokens (over-fragmented)
# and that occur frequently enough to be worth adding
candidates = []
for word, freq in word_freq.most_common(50000):
    if freq < 5:
        break
    # Tokenize with the SentencePiece prefix
    tokens = tokenizer.tokenize(word)
    if len(tokens) >= 3:
        # Add the full word with SentencePiece prefix
        sp_word = "\u2581" + word  # SentencePiece uses ▁ prefix
        if sp_word not in existing_vocab:
            candidates.append((sp_word, freq, len(tokens)))

    # Also try common subwords: if the word fragments into many pieces,
    # the intermediate multi-char pieces might be useful
    if len(tokens) >= 4:
        for tok in tokens:
            clean = tok.replace("\u2581", "")
            if len(clean) >= 3 and any("\u0370" <= c <= "\u03FF" or "\u1F00" <= c <= "\u1FFF" for c in clean):
                if tok not in existing_vocab:
                    candidates.append((tok, freq, 1))

# Deduplicate and take top 2000 by frequency
seen = set()
unique_candidates = []
for token, freq, n_toks in candidates:
    if token not in seen:
        seen.add(token)
        unique_candidates.append((token, freq))

# Sort by frequency, take top 2000
unique_candidates.sort(key=lambda x: -x[1])
new_tokens = [t for t, _ in unique_candidates[:2000]]

print(f"Adding {len(new_tokens)} new Greek tokens to tokenizer")
num_added = tokenizer.add_tokens(new_tokens)
print(f"Actually added: {num_added} (some may have already existed)")

# Resize model embeddings
print(f"Loading {MODEL_NAME} model and resizing embeddings...")
model = AutoModelForMaskedLM.from_pretrained(MODEL_NAME)
model.resize_token_embeddings(len(tokenizer))

# Save
EXTENDED_DIR.mkdir(parents=True, exist_ok=True)
tokenizer.save_pretrained(EXTENDED_DIR)
model.save_pretrained(EXTENDED_DIR)
print(f"Saved extended model+tokenizer to {EXTENDED_DIR}")

# Verify on test sentences
test_sentences = [
    "Τοῖς τὰς κοινὰς ἱστορίας πραγματευσαμένοις δίκαιον ἀπονέμειν",
    "ὁ δὲ Ἡρακλῆς τὴν μὲν Ἰόλην ἔλαβε",
    "τῶν δ᾽ Ἀθηναίων ἡ ἐκκλησία συνελέγη",
    "πρῶτον μὲν οὖν περὶ τῆς Αἰγύπτου διέξιμεν",
]

base_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
total_before = 0
total_after = 0
for sent in test_sentences:
    before = base_tokenizer.tokenize(sent)
    after = tokenizer.tokenize(sent)
    total_before += len(before)
    total_after += len(after)
    print(f"  '{sent[:50]}...' {len(before)} -> {len(after)} tokens")

words_total = sum(len(s.split()) for s in test_sentences)
print(f"\nOverall: {total_before} -> {total_after} tokens ({total_before - total_after} fewer)")
print(f"Fragmentation: {total_before/words_total:.2f}x -> {total_after/words_total:.2f}x")

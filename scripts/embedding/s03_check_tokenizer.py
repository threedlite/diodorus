#!/usr/bin/env python3
"""
Check xlm-roberta-base tokenization quality on Ancient Greek text.
Measures fragmentation ratio (tokens per word).

If ratio > 2.5, recommends running s03b_extend_tokenizer.py.
If ratio <= 2.5, proceed directly to s04_continued_pretraining.py.

Output: prints analysis to stdout; exits with code 1 if extension recommended.
"""

from transformers import AutoTokenizer

MODEL_NAME = "xlm-roberta-base"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

# Test on Ancient Greek (opening of Diodorus Siculus, Library of History)
test = "Τοῖς τὰς κοινὰς ἱστορίας πραγματευσαμένοις δίκαιον ἀπονέμειν"
tokens = tokenizer.tokenize(test)
print(f"Test text: {test}")
print(f"Tokens ({len(tokens)}): {tokens}")

# Check how many Greek-specific tokens exist
vocab = tokenizer.get_vocab()
greek_tokens = [t for t in vocab if any("\u0370" <= c <= "\u03FF" for c in t)]
polytonic = [t for t in vocab if any("\u1F00" <= c <= "\u1FFF" for c in t)]
print(f"\nGreek tokens in vocab: {len(greek_tokens)}")
print(f"Polytonic tokens: {len(polytonic)}")
print(f"Total vocab size: {len(vocab)}")

# Measure fragmentation
words = test.split()
fragmentation = len(tokens) / len(words)
print(f"\nFragmentation ratio: {fragmentation:.2f}x (1.0 = perfect, >2.5 = problematic)")

# Additional test samples
additional_tests = [
    "ὁ δὲ Ἡρακλῆς τὴν μὲν Ἰόλην ἔλαβε",
    "τῶν δ᾽ Ἀθηναίων ἡ ἐκκλησία συνελέγη",
    "πρῶτον μὲν οὖν περὶ τῆς Αἰγύπτου διέξιμεν",
]

total_tokens = len(tokens)
total_words = len(words)
for t in additional_tests:
    toks = tokenizer.tokenize(t)
    ws = t.split()
    total_tokens += len(toks)
    total_words += len(ws)
    print(f"  '{t[:50]}...' -> {len(toks)} tokens / {len(ws)} words = {len(toks)/len(ws):.2f}x")

avg_frag = total_tokens / total_words
print(f"\nAverage fragmentation across all samples: {avg_frag:.2f}x")

if avg_frag > 2.5:
    print("\nRECOMMENDATION: High fragmentation detected.")
    print("Run s03b_extend_tokenizer.py to add Greek subwords before continuing.")
    raise SystemExit(1)
else:
    print("\nRECOMMENDATION: Tokenization acceptable.")
    print("Proceed to s04_continued_pretraining.py without extension.")
    raise SystemExit(0)

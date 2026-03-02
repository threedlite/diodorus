#!/usr/bin/env python3
"""
Check xlm-roberta-base tokenization quality on Latin text.
Measures fragmentation ratio (tokens per word).

Latin should fragment less than Ancient Greek since XLM-R's training
included more Latin-script text.

Output: prints analysis to stdout; exits with code 1 if extension recommended.
"""

from transformers import AutoTokenizer

MODEL_NAME = "xlm-roberta-base"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

# Test on Latin (opening of Caesar, Gallic War)
test = "Gallia est omnis divisa in partes tres quarum unam incolunt Belgae"
tokens = tokenizer.tokenize(test)
print(f"Test text: {test}")
print(f"Tokens ({len(tokens)}): {tokens}")

# Check Latin-relevant tokens
vocab = tokenizer.get_vocab()
# Count tokens that are pure ASCII Latin (no special chars)
latin_word_tokens = [t for t in vocab if t.isalpha() and all("a" <= c <= "z" for c in t.lower())]
print(f"\nPure Latin-letter tokens in vocab: {len(latin_word_tokens)}")
print(f"Total vocab size: {len(vocab)}")

# Measure fragmentation
words = test.split()
fragmentation = len(tokens) / len(words)
print(f"\nFragmentation ratio: {fragmentation:.2f}x (1.0 = perfect, >2.5 = problematic)")

# Additional test samples covering different Latin authors/styles
additional_tests = [
    "Arma virumque cano Troiae qui primus ab oris",  # Virgil
    "Quousque tandem abutere Catilina patientia nostra",  # Cicero
    "Ab urbe condita libros monumenta rerum gestarum",  # Livy
    "Quidquid id est timeo Danaos et dona ferentes",  # Virgil
    "Omnia vincit amor et nos cedamus amori",  # Virgil
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
    print("MLM pre-training will help compensate (tokenizer extension is not effective for SentencePiece).")
    raise SystemExit(1)
else:
    print("\nRECOMMENDATION: Tokenization acceptable for Latin.")
    print("Proceed to MLM pre-training.")
    raise SystemExit(0)

#!/usr/bin/env python3
"""
Bilingual lexical overlap scoring using TF-IDF weighted word correspondences.

Learns a Greek→English translation table from aligned text pairs, then
scores new pairs by checking how many Greek content words have their
expected English correspondences present.

Usage:
    from pipeline.lexical_overlap import build_lexical_table, lexical_overlap_score
"""

import math
import pickle
import re
from collections import Counter, defaultdict
from pathlib import Path

# Word extraction patterns
GR_WORD_RE = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]+', re.UNICODE)
EN_WORD_RE = re.compile(r'[a-zA-Z]+')

# Stopwords — loaded from cached corpus frequency data if available,
# otherwise falls back to a minimal bootstrap set.
# The full sets are computed by build_lexicon.py from corpus word frequencies.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_STOPWORDS_PATH = _PROJECT_ROOT / "build" / "stopwords.pkl"

def _load_stopwords():
    if _STOPWORDS_PATH.exists():
        with open(_STOPWORDS_PATH, "rb") as f:
            data = pickle.load(f)
            return frozenset(data.get("greek", set())), frozenset(data.get("english", set()))
    # Bootstrap fallback — minimal function words to get started
    return _BOOTSTRAP_GR_STOPS, _BOOTSTRAP_EN_STOPS

# Minimal bootstrap sets — only the most basic function words.
# The full corpus-derived sets are in build/stopwords.pkl.
_BOOTSTRAP_GR_STOPS = frozenset({
    # articles
    'ὁ', 'ἡ', 'τό', 'τὸ', 'τοῦ', 'τῆς', 'τῷ', 'τῇ', 'τόν', 'τὸν',
    'τήν', 'τὴν', 'τῶν', 'τοῖς', 'ταῖς', 'τούς', 'τοὺς', 'τάς', 'τὰς',
    'οἱ', 'αἱ', 'τά', 'τὰ',
    # particles and conjunctions
    'καί', 'καὶ', 'δέ', 'δὲ', 'τε', 'μέν', 'μὲν', 'γάρ', 'γὰρ',
    'ἀλλά', 'ἀλλὰ', 'ἀλλ', 'ὅτι', 'ὡς', 'ὥστε', 'ὅτε', 'ἐπεί',
    'ἐπεὶ', 'ἐπειδή', 'ἐπειδὴ', 'εἰ', 'ἐάν', 'ἐὰν', 'ἄν', 'ἂν',
    'ἤ', 'ἢ', 'οὔτε', 'μήτε', 'οὐδέ', 'οὐδὲ', 'μηδέ', 'μηδὲ',
    'ἵνα', 'ὅπως', 'ἕως', 'πρίν', 'πρὶν',
    # negation
    'οὐ', 'οὐκ', 'οὐχ', 'μή', 'μὴ', 'οὐδέν', 'οὐδὲν', 'μηδέν', 'μηδὲν',
    # prepositions
    'ἐν', 'εἰς', 'ἐκ', 'ἐξ', 'πρός', 'πρὸς', 'ἀπό', 'ἀπὸ', 'κατά',
    'κατὰ', 'κατ', 'περί', 'περὶ', 'διά', 'διὰ', 'ὑπό', 'ὑπὸ', 'μετά',
    'μετὰ', 'ἐπί', 'ἐπὶ', 'ἐπ', 'παρά', 'παρὰ', 'παρ', 'ὑπέρ', 'ὑπὲρ',
    'πρό', 'πρὸ', 'ἀντί', 'ἀντὶ', 'σύν', 'σὺν',
    # pronouns
    'αὐτός', 'αὐτὸς', 'αὐτόν', 'αὐτὸν', 'αὐτοῦ', 'αὐτῷ', 'αὐτήν',
    'αὐτὴν', 'αὐτῆς', 'αὐτῇ', 'αὐτῶν', 'αὐτοῖς', 'αὐτοὺς', 'αὐτάς',
    'αὐτὰς', 'αὐταῖς',
    'ἐγώ', 'ἐγὼ', 'ἐμοῦ', 'μου', 'ἐμοί', 'μοι', 'ἐμέ', 'με',
    'σύ', 'σὺ', 'σοῦ', 'σου', 'σοί', 'σοι', 'σέ', 'σε',
    'ἡμεῖς', 'ἡμῶν', 'ἡμῖν', 'ἡμᾶς',
    'ὑμεῖς', 'ὑμῶν', 'ὑμῖν', 'ὑμᾶς',
    'ὅς', 'ἥ', 'ὅ', 'οὗ', 'ᾧ', 'ὅν', 'ἥν', 'ἣν', 'ὧν', 'οἷς', 'αἷς',
    'οὕς', 'ἅς', 'ἃς',
    'οὗτος', 'αὕτη', 'τοῦτο', 'τούτου', 'τούτῳ', 'τοῦτον', 'ταύτην',
    'τούτων', 'τούτοις', 'ταύταις', 'τούτους', 'ταύτας',
    'ταῦτα', 'τοιοῦτος', 'τοιαύτη', 'τοιοῦτο', 'τοιοῦτον',
    'ἐκεῖνος', 'ἐκείνη', 'ἐκεῖνο', 'ἐκείνου', 'ἐκείνῳ', 'ἐκεῖνον',
    'ἐκείνην', 'ἐκείνων', 'ἐκείνοις',
    'τις', 'τι', 'τινά', 'τινὰ', 'τινός', 'τινὸς', 'τινί', 'τινὶ',
    'τινές', 'τινὲς', 'τινῶν', 'τινάς', 'τινὰς',
    # forms of εἰμί
    'ἐστι', 'ἐστιν', 'ἐστί', 'ἐστίν', 'εἶναι', 'ἦν', 'ἐστ', 'ὤν',
    'ὢν', 'οὖσα', 'ὄν', 'ὄντος', 'ὄντα', 'εἰσί', 'εἰσίν', 'ἔστι',
    'ἔσται', 'ἦσαν', 'εἴη',
    # common adverbs and particles
    'οὖν', 'δή', 'δὴ', 'ἤδη', 'ἔτι', 'νῦν', 'τότε', 'πάλιν',
    'μόνον', 'μᾶλλον', 'ὅμως', 'πάντα', 'πάντων', 'πᾶσι', 'πᾶν',
    'ἅμα', 'ὥσπερ', 'μάλιστα', 'οὕτω', 'οὕτως', 'ὧδε', 'ἄλλ',
    'ἄλλα', 'ἄλλο', 'ἄλλον', 'ἄλλων', 'ἄλλοις', 'ἄλλους', 'ἄλλας',
    'ἄλλη', 'ἄλλης', 'ἄλλῃ',
    # common verbs
    'ἔχει', 'ἔχειν', 'ἔχων', 'ἔχοντα', 'εἶχε', 'εἶχεν',
    'ποιεῖ', 'ποιεῖν', 'λέγει', 'λέγειν', 'φησί', 'φησὶ', 'φησιν',
    'δεῖ', 'ἔφη',
})

_BOOTSTRAP_EN_STOPS = frozenset({
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
    'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'shall', 'should', 'may', 'might', 'can', 'could',
    'not', 'no', 'nor', 'it', 'its', 'he', 'him', 'his', 'she', 'her',
    'they', 'them', 'their', 'we', 'us', 'our', 'you', 'your', 'i',
    'my', 'me', 'this', 'that', 'these', 'those', 'which', 'who',
    'whom', 'what', 'so', 'as', 'if', 'than',
})

# Load corpus-derived stopwords (or fall back to bootstrap)
GR_STOPS, EN_STOPS = _load_stopwords()


def extract_gr_words(text):
    """Extract Greek content words from text."""
    words = set()
    for w in GR_WORD_RE.findall(text):
        if len(w) <= 2:
            continue
        wl = w.lower()
        if wl in GR_STOPS:
            continue
        words.add(wl)
    return words


def extract_en_words(text):
    """Extract English content words from text."""
    words = set()
    for w in EN_WORD_RE.findall(text):
        if len(w) <= 2:
            continue
        wl = w.lower()
        if wl in EN_STOPS:
            continue
        words.add(wl)
    return words


def build_lexical_table(aligned_pairs, min_cooccur=2, max_translations=10,
                        min_weight=0.01, idf_cap_percentile=90):
    """Build a source→English word translation table from aligned text pairs.

    Args:
        aligned_pairs: list of (source_text, english_text) tuples
        min_cooccur: minimum co-occurrence count to keep a pair
        max_translations: max translations to keep per source word
        min_weight: minimum normalized weight to keep a translation
        idf_cap_percentile: cap IDF at this percentile to prevent
            rare-word dominance

    Returns:
        src2en: dict mapping source_word → {english_word: normalized_weight}
        src_idf: dict mapping source_word → idf_weight
        en_idf: dict mapping english_word → idf_weight
        cooccur: Counter mapping (source_word, english_word) → raw count
    """
    cooccur = Counter()
    src_df = Counter()
    en_df = Counter()
    n_pairs = len(aligned_pairs)

    for src_text, en_text in aligned_pairs:
        src_words = extract_gr_words(src_text)
        en_words = extract_en_words(en_text)

        for sw in src_words:
            src_df[sw] += 1
            for ew in en_words:
                cooccur[(sw, ew)] += 1
        for ew in en_words:
            en_df[ew] += 1

    # Compute IDF with cap
    raw_src_idf = {w: math.log(n_pairs / max(df, 1))
                   for w, df in src_df.items()}
    raw_en_idf = {w: math.log(n_pairs / max(df, 1))
                  for w, df in en_df.items()}

    # Cap IDF at percentile to prevent rare-word noise
    if raw_src_idf:
        import numpy as np
        idf_vals = list(raw_src_idf.values())
        cap = float(np.percentile(idf_vals, idf_cap_percentile))
        src_idf = {w: min(v, cap) for w, v in raw_src_idf.items()}
    else:
        src_idf = raw_src_idf

    if raw_en_idf:
        import numpy as np
        idf_vals = list(raw_en_idf.values())
        cap = float(np.percentile(idf_vals, idf_cap_percentile))
        en_idf = {w: min(v, cap) for w, v in raw_en_idf.items()}
    else:
        en_idf = raw_en_idf

    # Build translation table weighted by PMI (pointwise mutual information).
    # PMI = log(P(sw,ew) / (P(sw) × P(ew)))
    # This correctly handles common words: θάνατος co-occurring with "death"
    # more often than chance is a strong signal regardless of how common
    # θάνατος is overall.
    src2en_raw = defaultdict(dict)
    for (sw, ew), count in cooccur.items():
        if count < min_cooccur:
            continue
        # PMI: log(P(sw,ew) / (P(sw) * P(ew)))
        # P(sw,ew) ≈ count / n_pairs
        # P(sw) ≈ src_df[sw] / n_pairs
        # P(ew) ≈ en_df[ew] / n_pairs
        p_joint = count / n_pairs
        p_src = src_df[sw] / n_pairs
        p_en = en_df[ew] / n_pairs
        if p_src <= 0 or p_en <= 0:
            continue
        pmi = math.log(p_joint / (p_src * p_en))
        if pmi <= 0:
            continue  # negative PMI = co-occur less than chance
        # Weight by count × PMI (frequent + surprising = best signal)
        weight = count * pmi
        src2en_raw[sw][ew] = weight

    # Normalize per source word, prune, and keep top-K
    src2en = {}
    for sw, translations in src2en_raw.items():
        total = sum(translations.values())
        if total <= 0:
            continue

        # Normalize
        normed = {ew: w / total for ew, w in translations.items()}

        # Prune below min_weight
        normed = {ew: w for ew, w in normed.items() if w >= min_weight}

        # Keep top-K
        if len(normed) > max_translations:
            top = sorted(normed.items(), key=lambda x: -x[1])[:max_translations]
            normed = dict(top)

        # Re-normalize after pruning
        total2 = sum(normed.values())
        if total2 > 0:
            normed = {ew: w / total2 for ew, w in normed.items()}
            src2en[sw] = normed

    return src2en, src_idf, en_idf, cooccur


def lexical_overlap_score(src_text, en_text, src2en, src_idf):
    """Score a source/English text pair by IDF-weighted bilingual word overlap.

    For each source content word, check if any of its known English
    correspondences appear in the English text. Weight matches by
    the source word's IDF (rarer = more informative).

    Returns float in [0, 1].
    """
    src_words = extract_gr_words(src_text)
    en_words = extract_en_words(en_text)

    if not src_words or not en_words or not src2en:
        return 0.0

    weighted_matches = 0.0
    total_weight = 0.0

    for sw in src_words:
        idf = src_idf.get(sw, 0)
        if idf <= 0 or sw not in src2en:
            continue
        total_weight += idf
        for ew, trans_weight in src2en[sw].items():
            if ew in en_words:
                weighted_matches += idf * trans_weight
                break

    if total_weight == 0:
        return 0.0
    return weighted_matches / total_weight


def build_lexical_matrix(src_sents, en_sents, src2en, src_idf, bandwidth=30):
    """Build a sentence-level lexical overlap matrix for the DP.

    Only computes within a diagonal bandwidth to keep it tractable.

    Returns numpy array of shape (n_src, n_en).
    """
    import numpy as np

    n_src = len(src_sents)
    n_en = len(en_sents)
    matrix = np.zeros((n_src, n_en), dtype=np.float32)

    for i in range(n_src):
        src_words = extract_gr_words(src_sents[i])
        if not src_words:
            continue

        # Precompute IDF-weighted translations for this sentence's words
        word_data = []
        for sw in src_words:
            idf = src_idf.get(sw, 0)
            if idf <= 0 or sw not in src2en:
                continue
            word_data.append((idf, src2en[sw]))

        if not word_data:
            continue

        total_weight = sum(idf for idf, _ in word_data)
        if total_weight == 0:
            continue

        j_center = int(i * n_en / n_src) if n_src > 0 else 0
        j_lo = max(0, j_center - bandwidth)
        j_hi = min(n_en, j_center + bandwidth)

        for j in range(j_lo, j_hi):
            en_words = extract_en_words(en_sents[j])
            if not en_words:
                continue

            wm = 0.0
            for idf, translations in word_data:
                for ew, tw in translations.items():
                    if ew in en_words:
                        wm += idf * tw
                        break

            if wm > 0:
                matrix[i][j] = wm / total_weight

    return matrix

# Synthetic Lemma Grouping

## Problem

The concordance treats every inflected surface form as a separate entry.
θάνατος, θανάτου, θανάτον, θανάτῳ, θανάτων each have their own translation
vectors. This scatters evidence across forms and makes the concordance harder
to use as a reference — you have to know which inflection to look up.

We want to group inflected forms into synthetic lemma clusters using only the
data we already have (translation vectors + character similarity), without
external morphological models or dictionaries.

## Exploration results

### Character similarity metrics compared

Tested four metrics for measuring character-level relatedness between Greek
word pairs (10,000 sampled pairs: 5,000 prefix-sharing + 5,000 random):

| Metric | Catches inflections (high char + high trans) | False look-alikes (high char + low trans) | Missed inflections (low char + high trans) |
|--------|---:|---:|---:|
| Trigram Jaccard | 833 | 1,878 | 195 |
| Longest common substring ratio | 1,026 | 4,276 | 2 |
| Edit distance ratio | 1,026 | 4,141 | 2 |
| Longest common subsequence ratio | 1,026 | 5,682 | 2 |

**Trigram Jaccard is unsuitable** — it misses 195 true inflectional pairs
(e.g., φθονεῖν/φθονήσαντες, ἰουδαίους/ἰουδαϊκῶν) because a single character
change breaks multiple trigrams.

**Longest common substring ratio** is best — it misses only 2 pairs (both
false positives), has the best ratio of true catches to false look-alikes,
and is linguistically meaningful ("do these words share a stem?").

### Combining character and translation similarity

Neither metric alone separates inflections from unrelated pairs. Tested
nonlinear combinations of longest common substring ratio (LCS) and
translation vector cosine (TC):

| Combination | Notes |
|---|---|
| Product (LCS × TC) | Most aggressive separation; zeros if either axis is zero. Histogram shows a dip around 0.15–0.20. |
| Geometric mean | Very similar rankings to harmonic mean. |
| Harmonic mean | Slightly more forgiving than product. Top pairs identical to geometric. |
| Min(LCS, TC) | Sharpest elbow in sorted-score curve at ~rank 500–700. |

**Key finding:** All combinations agree on the top ~500–700 pairs — these
are unambiguously inflections (σόλων/σόλωνος, ἀλήθειαν/ἀλήθεια,
πέρσαι/πέρσαις, σωκράτης/σωκράτην, etc.). Below that, quality degrades.

**Product** shows the most bimodal histogram with a dip around 0.15–0.20,
suggesting a natural threshold zone. The elbow in the sorted-score curve
is around rank 500–700 out of 2,129 non-zero pairs.

### Why there is no clean gap

The translation vectors are noisy. Many words appear in only 3–5 aligned
sections (the minimum co-occurrence threshold), so their translation profiles
are dominated by context rather than meaning. Two inflected forms of the
same lemma can have very different translation vectors simply because they
appeared in different passages.

This noise is irreducible at the current corpus size. More aligned pairs
would improve translation vector quality and make the gap clearer.

## Algorithm

Given the exploration results, the English-pivot approach (grouping by
top translation) is unreliable — top translations are often wrong or
context-dependent (θάνατος → "penalty" as rank 1).

### Step 1: Compute pairwise scores

For all pairs of Greek words sharing ≥4 characters in their longest common
substring:
```
score = lc_substring_ratio(w1, w2) × translation_cosine(w1, w2)
```

The LCS ≥4 filter limits the candidate space (most unrelated pairs have
LCS < 4 characters) while allowing augmented/reduplicated verb forms through.
An additional early filter of LCS ratio ≥ 0.5 is applied before computing
the translation cosine, reducing the candidate space from 3.4M to ~265K pairs.

### Step 2: Find the threshold from the data

Sort all non-zero scores. Compute the second derivative of the sorted
curve to find the elbow — the point where score drops off sharply. Pairs
above the elbow are high-confidence lemma pairs. The threshold is clamped
to the range [0.10, 0.30].

Current data: elbow at 0.300, yielding 57,269 pairs above threshold.

### Step 3: Build clusters with pairwise requirement

A node joins a cluster only if it has a qualifying score with **every
existing member** of that cluster. This prevents chain-merging where A–B
and B–C would link unrelated A and C through a bridging word.

This replaced the original connected-components approach which suffered
from chain merges (e.g., νόμους → ἀγορανόμος → ἀγορά linking "laws" to
"market" via the compound "market-inspector").

Comparison:

| | Connected components | Pairwise requirement |
|---|---|---|
| Words grouped | 25,747 | 19,574 |
| Lemma groups | 9,505 | 11,221 |
| Mean cluster size | 3.7 | 2.7 |
| Chain merges | Yes (problematic) | No |

Cluster size is capped at 20 forms per lemma.

### Step 4: Pick representative

Representative: the most frequent form (highest total co-occurrence count
across all English translations). This is the form the corpus uses most
and is the most recognizable.

### Edge cases

1. **Verbs with augments** — ἔλυσα vs λύω may not cluster because LCS is
   short and translation vectors diverge. Acceptable — verb paradigms are
   large and tense/aspect distinctions are meaningful.

2. **Proper nouns** — many top pairs are proper nouns (σόλων/σόλωνος,
   σωκράτης/σωκράτην). These cluster well and are valid lemma groups.

3. **Compound words** — the pairwise requirement prevents compounds from
   bridging unrelated stems. ἀγορανόμος shares a stem with both ἀγορά
   and νόμος but those two don't share a stem with each other, so they
   stay in separate clusters.

## Current results

From 86,969 Greek words:
- **11,221 multi-form lemma groups** (19,574 words grouped, 22%)
- Median cluster size: 2, mean: 2.7, max: 20

Example groups:
- ἀργυρίου (silver): 20 forms — ἀργυρᾶ, ἀργυραῖ, ἀργυρᾶν, ἄργυρον, ...
- φιλοσοφίαν (philosophy): 13 forms — φιλοσοφεῖ, φιλοσοφία, φιλοσοφίας, ...
- ἑλληνικῶν (Greek): 16 forms — ἕλληνα, ἑλληνικὴν, ἑλληνικῆς, ...
- βασιλείαν (kingdom): 20 forms — βασιλεύειν, βασιλεύς, βασιλεῦσι, ...
- γυμνὸν (naked): 14 forms — γυμνή, γυμνοί, γυμνός, ...

## Output

### Concordance CSV columns

Two columns added to the concordance:

```csv
greek,english,weight,rank,cooccur_count,greek_idf,synthetic_lemma,synthetic_lemma_confidence
θάνατος,death,0.51,1,847,4.21,θάνατος,0.92
θανάτου,death,0.48,1,612,4.55,θάνατος,0.85
θανάτῳ,death,0.45,1,301,4.55,θάνατος,0.78
κολάσεως,death,0.30,1,45,6.80,κολάσεως,
```

- `synthetic_lemma` — the representative form (most frequent member of the
  group), or the word itself if ungrouped
- `synthetic_lemma_confidence` — the product score (LCS × cosine) of this
  word's best link into the lemma group. High (>0.5) means strong evidence.
  Low (~0.30) means borderline. Blank for ungrouped singletons.

### Separate lemma index

`build/synthetic_lemmas.csv`:

```csv
lemma,forms,form_count,top_english,top_weight
θάνατος,"θάνατος|θανάτου|θανάτῳ|θανάτων|θάνατον",5,death,0.51
```

## Scripts

- `scripts/build_synthetic_lemmas.py` — builds lemma groups, outputs
  `build/synthetic_lemmas.csv` and `build/synthetic_lemmas.pkl`
- `scripts/export_concordance.py` — reads the lemma pickle and adds the
  two columns to the concordance CSV
- `scripts/explore_lemma_pairs.py` — exploration: samples pairs, computes
  4 character metrics vs translation cosine, generates scatter plots
- `scripts/explore_lemma_combinations.py` — exploration: tests product,
  geometric mean, harmonic mean, min; generates histograms and elbow plots

Exploration outputs in `build/`:
- `lemma_pair_exploration.csv` — 10K sampled pairs with all metrics
- `lemma_pair_scatter_4metrics.png` — 4-panel scatter plots
- `lemma_combined_histograms.png` — distribution of combined scores
- `lemma_combined_elbows.png` — sorted score curves

## Open questions

1. Should lemma groups feed back into alignment scoring? A lemmatized lexical
   table would give stronger overlap scores. Worth testing separately.

2. Should we weight the two axes differently in the product? Current data
   suggests equal weighting works, but a slight bias toward character
   similarity (e.g., LCS^1.2 × TC^0.8) might reduce false merges from
   noisy translation vectors.

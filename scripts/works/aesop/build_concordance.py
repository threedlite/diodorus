#!/usr/bin/env python3
"""
Build a concordance between Chambry Greek fable numbers and Townsend English
fable indices using title-based subject matching.

Greek titles contain animal/character names in Greek (e.g., "Ἀετὸς καὶ Ἀλώπηξ").
English titles contain the same in English (e.g., "The Eagle and the Fox").

Strategy:
1. Map Greek animal/character names to English equivalents
2. Extract subject sets from both Greek and English titles
3. Match fables by subject-set overlap
4. Disambiguate ties using embedding similarity from the existing sim matrix

Output: concordance.json — maps Greek fable section → English fable section
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BUILD_DIR = PROJECT_ROOT / "build" / "aesop"

# ── Greek → English subject dictionary ──────────────────────────────────
# Built from the most common Greek title words in the Chambry edition.
# Covers all animals/characters appearing 2+ times in titles.
GREEK_TO_ENGLISH = {
    # Animals
    "Ἀλώπηξ": "Fox", "Ἀλωπεκῶν": "Fox", "Ἀλωπεκῆ": "Fox", "Ἀλώπεκος": "Fox",
    "Λέων": "Lion", "Λεόντων": "Lion",
    "Λύκος": "Wolf", "Λύκοι": "Wolf",
    "Ὄνος": "Ass", "Ὄνοι": "Ass",
    "Κύων": "Dog", "Κύνες": "Dog",
    "Ἵππος": "Horse", "Ἵπποι": "Horse",
    "Ὄφις": "Serpent", "Ὄφεις": "Serpent",
    "Πίθηκος": "Monkey", "Πίθηκοι": "Monkey",
    "Κόραξ": "Crow", "Κόρακες": "Crow",
    "Κάμηλος": "Camel",
    "Γαλῆ": "Weasel", "Γαλέη": "Weasel",
    "Ἔλαφος": "Stag", "Ἐλάφη": "Stag",
    "Κολοιὸς": "Jackdaw", "Κολοιός": "Jackdaw",
    "Χελιδών": "Swallow",
    "Βάτραχοι": "Frog", "Βάτραχος": "Frog",
    "Μῦς": "Mouse", "Μύες": "Mouse", "Μῦες": "Mouse",
    "Ἀετός": "Eagle", "Ἀετὸς": "Eagle",
    "Βοῦς": "Ox", "Βόες": "Ox",
    "Κορώνη": "Raven", "Κορῶναι": "Raven",
    "Ταῦρος": "Bull", "Ταῦροι": "Bull",
    "Αἴλουρος": "Cat",
    "Ὄρνις": "Hen", "Ὄρνιθες": "Hen",
    "Βάτραχος": "Frog",
    "Θάλασσα": "Sea",
    "Ἔχις": "Viper",
    "Πρόβατα": "Sheep", "Πρόβατον": "Sheep",
    "Ψύλλα": "Flea",
    "Ἀλεκτρυών": "Cock", "Ἀλέκτορες": "Cock", "Ἀλεκτρυόνες": "Cock",
    "Πέρδιξ": "Partridge",
    "Ἁλιεύς": "Fisherman", "Ἀλιεῖς": "Fisherman", "Ἁλιεῖς": "Fisherman",
    "Τράγος": "Goat",
    "Τέττιξ": "Grasshopper", "Τέττιγες": "Grasshopper",
    "Ἄρκτος": "Bear",
    "Χελώνη": "Tortoise",
    "Ὁδοιπόρος": "Traveler", "Ὁδοιπόροι": "Traveler",
    "Ἱέραξ": "Hawk",
    "Δελφίς": "Dolphin", "Δελφῖνες": "Dolphin",
    "Ἰατρός": "Physician",
    "Λαγωός": "Hare", "Λαγωοὶ": "Hare", "Λαγωοί": "Hare",
    "Νυκτερίς": "Bat",
    "Ὗς": "Sow", "Σῦς": "Sow",
    "Κάνθαρος": "Beetle",
    "Ἀράχνη": "Spider",
    "Μέλισσαι": "Bee", "Μέλισσα": "Bee",
    "Κριός": "Ram",
    "Ἔριφος": "Kid",
    "Αἴξ": "Goat", "Αἶγες": "Goat",
    "Λύρα": "Lyre",
    "Δρῦς": "Oak",
    "Κάλαμος": "Reed",
    "Λεοντῆ": "Lion",
    "Μυρμήκες": "Ant", "Μύρμηξ": "Ant",
    "Ὕαινα": "Hyena",
    "Γέρανος": "Crane", "Γέρανοι": "Crane",
    "Χήν": "Goose",
    "Ταώς": "Peacock",
    "Κοχλίας": "Snail",
    "Ἀσπάλαξ": "Mole",
    "Λαμπὰς": "Lamp",
    "Γαστὴρ": "Belly",
    "Λάρναξ": "Box",
    "Τοξότης": "Archer",
    "Ναυαγός": "Shipwrecked",
    "Κηπουρός": "Gardener",
    "Μάντις": "Prophet",
    "Ἡρακλῆς": "Hercules",
    "Ἑρμῆς": "Mercury", "Ἑρμοῦ": "Mercury",
    "Ζεύς": "Jupiter", "Ζεὺς": "Jupiter",
    "Ἀθηνᾶ": "Minerva",
    "Ἀφροδίτη": "Venus",
    "Προμηθεὺς": "Prometheus", "Προμηθεύς": "Prometheus",
    "Βορέας": "North Wind",
    "Ἥλιος": "Sun",
    # People / roles
    "Ἄνθρωπος": "Man", "Ἀνὴρ": "Man", "Ἀνήρ": "Man",
    "Γεωργὸς": "Farmer", "Γεωργός": "Farmer", "Γωργὸς": "Farmer",
    "Ποιμὴν": "Shepherd", "Ποιμήν": "Shepherd",
    "Παῖς": "Boy", "Παῖδες": "Boy",
    "Μήτηρ": "Mother",
    "Πατὴρ": "Father", "Πατήρ": "Father",
    "Γυνὴ": "Woman", "Γυνή": "Woman",
    "Γέρων": "Old Man",
    "Γραῦς": "Old Woman",
    "Τύχη": "Fortune",
    "Ὁρνιθοθήρας": "Fowler", "Ὀρνιθοθήρας": "Fowler",
    "Αἰπόλος": "Goatherd", "Αἰγοβοσκὸς": "Goatherd",
    "Ἀλεκτοροπώλης": "Cock-Seller",
    "Ἀγαλματοπώλης": "Seller of Images",
    "Κιθαρῳδός": "Harper",
    "Ξυλεύς": "Woodcutter", "Ξυλοκόπος": "Woodcutter",
    "Δρυτόμος": "Woodcutter",
    # Abstract/other
    "Αἰθίοψ": "Ethiopian",
    "Αἴσωπος": "Aesop",
    "Ἀηδών": "Nightingale", "Ἀηδὼν": "Nightingale",
    "Ἰχθύες": "Fish", "Ἰχθῦς": "Fish",
    "Ὄρος": "Mountain",
    "Ἐλαία": "Olive",
    "Νεανίσκοι": "Young Men",
    "Κέδρος": "Cedar",
    "Σφῆκες": "Wasps", "Σφήξ": "Wasp",
    "Λέαινα": "Lioness",
    "Ἡμίονος": "Mule",
    "Ἐχῖνος": "Hedgehog",
    "Ἀστρολόγος": "Astronomer",
    "Ὀνηλάτης": "Ass-Driver",
    "Κολοιοὶ": "Jackdaw",
    "Λάμπρος": "Lamp",
    "Πέτρα": "Rock",
    "Ῥόδον": "Rose",
    "Δαμάλη": "Heifer",
    "Κάρκινος": "Crab",
    "Χελιδὼν": "Swallow",
    "Νυκτερὶς": "Bat",
    "Κώνωψ": "Gnat", "Κώνωπες": "Gnat",
    "Μυῖα": "Fly", "Μυῖαι": "Fly",
    "Ὄρτυξ": "Quail",
    "Κόλαξ": "Flatterer",
    "Πελαργός": "Stork",
    "Λύχνος": "Lamp",
    "Περιστερὰ": "Dove", "Περιστερά": "Dove",
    "Δᾳδίον": "Torch",
    "Λεοπάρδαλις": "Leopard",
    "Πάρδαλις": "Leopard",
}

# Also map some English title words to normalized forms
ENGLISH_NORMALIZE = {
    "Hound": "Dog",
    "Housedog": "Dog",
    "Mastiff": "Dog",
    "Serpent": "Serpent",
    "Snake": "Serpent",
    "Viper": "Viper",
    "Dove": "Dove",
    "Pigeon": "Dove",
    "Sow": "Sow",
    "Boar": "Sow",
    "Donkey": "Ass",
    "Mule": "Mule",
    "Hares": "Hare",
    "Foxes": "Fox",
    "Dogs": "Dog",
    "Ants": "Ant",
    "Frogs": "Frog",
    "Flies": "Fly",
    "Mice": "Mouse",
    "Bees": "Bee",
    "Cocks": "Cock",
    "Wolves": "Wolf",
    "Lions": "Lion",
    "Oxen": "Ox",
    "Bulls": "Bull",
    "Asses": "Ass",
    "Wasps": "Wasp",
    "Heifer": "Heifer",
    "Geese": "Goose",
    "Stork": "Stork",
    "Cranes": "Crane",
    "Trees": "Tree",
    "Roosters": "Cock",
    "Leopard": "Leopard",
}


def extract_greek_subjects(head: str) -> set[str]:
    """Extract English subject names from a Greek fable header."""
    # Remove parenthetical references
    title = re.split(r"\s*\(", head, maxsplit=1)[0]
    # Remove leading number
    title = re.sub(r"^\d+[a-z]*\.\s*", "", title)
    # Remove "Ἄλλως." prefix (variant indicator)
    title = re.sub(r"Ἄλλως\.?\s*", "", title)
    title = title.strip().rstrip(".")

    subjects = set()
    # Try to match each word against our dictionary
    for word in title.replace(",", "").replace(".", "").split():
        if word in GREEK_TO_ENGLISH:
            subjects.add(GREEK_TO_ENGLISH[word])
    return subjects


def extract_english_subjects(title: str) -> set[str]:
    """Extract normalized subject names from an English fable title."""
    # Remove common articles/prepositions
    clean = title
    for remove in ["The ", "the ", "A ", "a ", "An ", "an ",
                    "and ", "And ", "of ", "his ", "His ",
                    "her ", "Her ", "its ", "Their ", "their ",
                    "Who ", "who ", "with ", "With "]:
        clean = clean.replace(remove, " ")
    clean = clean.strip()

    subjects = set()
    # Split on spaces, hyphens
    words = re.split(r"[\s,\-]+", clean)
    for word in words:
        word = word.strip()
        if not word:
            continue
        # Check normalization map first
        if word in ENGLISH_NORMALIZE:
            subjects.add(ENGLISH_NORMALIZE[word])
        # Check if it's already a known subject
        elif word in set(GREEK_TO_ENGLISH.values()):
            subjects.add(word)
    return subjects


def load_similarity_matrix():
    """Load precomputed similarity matrix if available."""
    npz_path = BUILD_DIR / "similarity_matrix.npz"
    if npz_path.exists():
        data = np.load(str(npz_path))
        # Try common key names
        for key in ["sim_matrix", "matrix", "similarity"]:
            if key in data.files:
                return data[key]
        # Fall back to first key
        if data.files:
            return data[data.files[0]]
        return None
    return None


def main():
    # Load sections
    with open(BUILD_DIR / "greek_sections.json") as f:
        greek_secs = json.load(f)["sections"]
    with open(BUILD_DIR / "english_sections.json") as f:
        english_secs = json.load(f)["sections"]

    print(f"Greek fables: {len(greek_secs)}")
    print(f"English fables: {len(english_secs)}")

    # Extract subjects from titles
    greek_subjects = []
    for s in greek_secs:
        subj = extract_greek_subjects(s.get("head", ""))
        greek_subjects.append(subj)

    english_subjects = []
    for s in english_secs:
        subj = extract_english_subjects(s.get("title", ""))
        english_subjects.append(subj)

    # Build index: subject-set → list of English indices
    from collections import defaultdict
    en_by_subjects = defaultdict(list)
    for j, subj in enumerate(english_subjects):
        key = frozenset(subj) if subj else None
        if key:
            en_by_subjects[key].append(j)

    # Also build a more flexible index: English sections by individual subject
    en_by_subject_word = defaultdict(set)
    for j, subj in enumerate(english_subjects):
        for s in subj:
            en_by_subject_word[s].add(j)

    # Load similarity matrix for disambiguation
    sim_matrix = load_similarity_matrix()
    if sim_matrix is not None:
        print(f"Similarity matrix: {sim_matrix.shape}")
    else:
        print("WARNING: No similarity matrix found; disambiguation will be limited")

    # Match Greek → English
    concordance = {}  # greek_section → english_section
    match_details = []  # for reporting
    en_used = set()  # track used English indices

    # Pass 1: Exact subject-set matches
    for i, (g_sec, g_subj) in enumerate(zip(greek_secs, greek_subjects)):
        if not g_subj:
            continue
        key = frozenset(g_subj)
        candidates = en_by_subjects.get(key, [])
        if not candidates:
            continue

        if len(candidates) == 1:
            j = candidates[0]
            concordance[g_sec["section"]] = english_secs[j]["section"]
            en_used.add(j)
            match_details.append({
                "greek_section": g_sec["section"],
                "greek_head": g_sec.get("head", "")[:60],
                "english_section": english_secs[j]["section"],
                "english_title": english_secs[j]["title"],
                "match_method": "exact_subjects",
                "subjects": sorted(g_subj),
            })
        elif sim_matrix is not None:
            # Multiple candidates — use embedding similarity to pick best
            sims = [(j, float(sim_matrix[i, j])) for j in candidates]
            sims.sort(key=lambda x: x[1], reverse=True)
            best_j, best_sim = sims[0]
            concordance[g_sec["section"]] = english_secs[best_j]["section"]
            en_used.add(best_j)
            match_details.append({
                "greek_section": g_sec["section"],
                "greek_head": g_sec.get("head", "")[:60],
                "english_section": english_secs[best_j]["section"],
                "english_title": english_secs[best_j]["title"],
                "match_method": "exact_subjects_disambig",
                "subjects": sorted(g_subj),
                "sim": best_sim,
                "n_candidates": len(candidates),
            })

    exact_count = len(concordance)
    print(f"\nPass 1 (exact subject-set match): {exact_count} matches")

    # Pass 2: Partial subject overlap (for Greek fables with 2+ subjects,
    # find English fables that share the most subjects)
    for i, (g_sec, g_subj) in enumerate(zip(greek_secs, greek_subjects)):
        if g_sec["section"] in concordance:
            continue
        if not g_subj or len(g_subj) < 1:
            continue

        # Find English candidates that share at least one subject
        candidate_scores = defaultdict(int)
        for subj_word in g_subj:
            for j in en_by_subject_word.get(subj_word, set()):
                candidate_scores[j] += 1

        if not candidate_scores:
            continue

        # Require at least 50% subject overlap in BOTH directions
        best_candidates = []
        for j, overlap_count in candidate_scores.items():
            en_subj = english_subjects[j]
            if not en_subj:
                continue
            # Jaccard-like: overlap / union
            union = len(g_subj | en_subj)
            jaccard = overlap_count / union if union else 0
            # Also check: what fraction of Greek subjects are matched?
            greek_coverage = overlap_count / len(g_subj)
            # And English coverage
            en_coverage = overlap_count / len(en_subj)
            if greek_coverage >= 0.5 and en_coverage >= 0.5:
                score = jaccard
                if sim_matrix is not None:
                    score = jaccard * 0.5 + float(sim_matrix[i, j]) * 0.5
                best_candidates.append((j, score, jaccard))

        if not best_candidates:
            continue

        best_candidates.sort(key=lambda x: x[1], reverse=True)
        best_j, best_score, best_jaccard = best_candidates[0]

        # Only accept if the match is reasonably good
        if best_jaccard >= 0.3:
            concordance[g_sec["section"]] = english_secs[best_j]["section"]
            en_used.add(best_j)
            match_details.append({
                "greek_section": g_sec["section"],
                "greek_head": g_sec.get("head", "")[:60],
                "english_section": english_secs[best_j]["section"],
                "english_title": english_secs[best_j]["title"],
                "match_method": "partial_subjects",
                "greek_subjects": sorted(g_subj),
                "english_subjects": sorted(english_subjects[best_j]),
                "jaccard": best_jaccard,
            })

    partial_count = len(concordance) - exact_count
    print(f"Pass 2 (partial subject overlap): {partial_count} additional matches")

    # Pass 3: For remaining unmatched Greek fables with subjects, try
    # single-subject match where there's only one English candidate
    for i, (g_sec, g_subj) in enumerate(zip(greek_secs, greek_subjects)):
        if g_sec["section"] in concordance:
            continue
        if not g_subj:
            continue
        if len(g_subj) != 1:
            continue

        subj_word = list(g_subj)[0]
        candidates = [j for j in en_by_subject_word.get(subj_word, set())
                       if j not in en_used]

        if len(candidates) == 1:
            j = candidates[0]
            concordance[g_sec["section"]] = english_secs[j]["section"]
            en_used.add(j)
            match_details.append({
                "greek_section": g_sec["section"],
                "greek_head": g_sec.get("head", "")[:60],
                "english_section": english_secs[j]["section"],
                "english_title": english_secs[j]["title"],
                "match_method": "single_remaining",
                "subjects": sorted(g_subj),
            })
        elif len(candidates) > 1 and sim_matrix is not None:
            # Use embedding similarity to pick among remaining candidates
            sims = [(j, float(sim_matrix[i, j])) for j in candidates]
            sims.sort(key=lambda x: x[1], reverse=True)
            best_j, best_sim = sims[0]
            if best_sim >= 0.5:  # only accept decent similarity
                concordance[g_sec["section"]] = english_secs[best_j]["section"]
                en_used.add(best_j)
                match_details.append({
                    "greek_section": g_sec["section"],
                    "greek_head": g_sec.get("head", "")[:60],
                    "english_section": english_secs[best_j]["section"],
                    "english_title": english_secs[best_j]["title"],
                    "match_method": "single_subject_sim",
                    "subjects": sorted(g_subj),
                    "sim": best_sim,
                })

    single_count = len(concordance) - exact_count - partial_count
    print(f"Pass 3 (single-subject + sim): {single_count} additional matches")

    total = len(concordance)
    print(f"\nTotal concordance entries: {total} / {len(greek_secs)} Greek fables")
    print(f"Unmatched Greek: {len(greek_secs) - total}")
    print(f"Unmatched English: {len(english_secs) - len(en_used)}")

    # Report match methods
    from collections import Counter
    methods = Counter(d["match_method"] for d in match_details)
    for method, count in methods.most_common():
        print(f"  {method}: {count}")

    # Save concordance
    output_path = Path(__file__).parent / "concordance.json"
    with open(output_path, "w") as f:
        json.dump(concordance, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {output_path}")

    # Save detailed report
    report_path = BUILD_DIR / "concordance_report.json"
    with open(report_path, "w") as f:
        json.dump(match_details, f, indent=2, ensure_ascii=False)
    print(f"Saved: {report_path}")

    # Show some sample matches
    print("\n── Sample matches ──")
    for d in match_details[:20]:
        method = d["match_method"]
        print(f"  G#{d['greek_section']} → E#{d['english_section']}  "
              f"[{method}] {d['english_title']}")

    # Show unmatched Greek fables
    unmatched_greek = [s for s in greek_secs if s["section"] not in concordance]
    if unmatched_greek:
        print(f"\n── Unmatched Greek fables (first 20) ──")
        for s in unmatched_greek[:20]:
            head = s.get("head", "")[:70]
            subj = extract_greek_subjects(s.get("head", ""))
            print(f"  G#{s['section']}: {head}  subjects={subj or '∅'}")

    # Verify no English section is mapped to by contradictory Greek fables
    # (many-to-one is OK for variants like 4/4b)
    en_to_greek = defaultdict(list)
    for g_sec, e_sec in concordance.items():
        en_to_greek[e_sec].append(g_sec)
    multi = {e: gs for e, gs in en_to_greek.items() if len(gs) > 1}
    if multi:
        print(f"\n── English fables matched by multiple Greek fables ({len(multi)}) ──")
        for e_sec, g_secs in sorted(multi.items(), key=lambda x: int(re.sub(r'[^0-9]', '', x[0]) or 0)):
            e_title = next(s["title"] for s in english_secs if s["section"] == e_sec)
            print(f"  E#{e_sec} '{e_title}' ← G#{', G#'.join(g_secs)}")


if __name__ == "__main__":
    main()

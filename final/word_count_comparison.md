# Greek vs English Word Count Comparison

Ranked by how close the source and English word counts are per work (ratio = min/max words).

| Rank | Work | Author | Source Words | English Words | Ratio | % Diff |
|------|------|--------|------------:|-------------:|------:|-------:|
| 1 | History of the Wars | Procopius | 234,112 | 248,226 | 0.943 | 5.9% |
| 2 | Ecclesiazusae | Aristophanes | 7,679 | 8,515 | 0.902 | 10.3% |
| 3 | Secret History (Anecdota) | Procopius | 32,419 | 39,091 | 0.829 | 18.7% |
| 4 | Frogs (Ranae) | Aristophanes | 9,478 | 11,620 | 0.816 | 20.3% |
| 5 | Epigrams | Theocritus | 1,750 | 1,398 | 0.799 | 22.4% |
| 6 | Cynegeticus | Arrian | 5,985 | 7,622 | 0.785 | 24.1% |
| 7 | Fabulae | Aesop | 44,243 | 33,894 | 0.766 | 26.5% |
| 8 | Aethiopica | Heliodorus | 76,368 | 99,986 | 0.764 | 26.8% |
| 9 | Refutatio Omnium Haeresium (Philosophumena) | Hippolytus | 122,986 | 93,626 | 0.761 | 27.1% |
| 10 | Peace (Pax) | Aristophanes | 8,353 | 6,342 | 0.759 | 27.4% |
| 11 | Bibliotheca Historica | Diodorus Siculus | 388,036 | 518,722 | 0.748 | 28.8% |
| 12 | Anabasis of Alexander | Arrian | 78,837 | 107,570 | 0.733 | 30.8% |
| 13 | Roman Antiquities | Dionysius of Halicarnassus | 285,290 | 401,780 | 0.710 | 33.9% |
| 14 | Enneads | Plotinus | 232,695 | 337,348 | 0.690 | 36.7% |
| 15 | Characters | Theophrastus | 6,721 | 9,899 | 0.679 | 38.2% |
| 16 | Hymn to the Mother of the Gods | Julian | 5,752 | 8,641 | 0.666 | 40.1% |
| 17 | Constitution of the Athenians | Aristotle | 16,180 | 24,700 | 0.655 | 41.7% |
| 18 | Leucippe and Clitophon | Achilles Tatius | 41,690 | 63,686 | 0.655 | 41.7% |
| 19 | Daphnis and Chloe | Longus | 19,780 | 30,299 | 0.653 | 42.0% |
| 20 | Idylls * | Bion of Phlossa | 1,800 | 2,769 | 0.650 | 42.4% |
| 21 | Hymn to King Helios | Julian | 7,449 | 11,492 | 0.648 | 42.7% |
| 22 | Argonautica | Apollonius Rhodius | 42,949 | 66,298 | 0.648 | 42.7% |
| 23 | Meditations (Ad Se Ipsum) | Marcus Aurelius | 29,269 | 45,629 | 0.641 | 43.7% |
| 24 | Acharnians | Aristophanes | 22,191 | 12,187 | 0.549 | 58.2% |
| 25 | Epistulae | Alciphron | 50,995 | 27,896 | 0.547 | 58.6% |
| 26 | Idylls | Theocritus | 19,437 | 35,770 | 0.543 | 59.2% |
| 27 | Thesmophoriazusae | Aristophanes | 23,995 | 12,853 | 0.536 | 60.5% |
| 28 | Knights | Aristophanes | 28,710 | 15,197 | 0.529 | 61.6% |
| 29 | Wasps (Vespae) | Aristophanes | 20,760 | 10,507 | 0.506 | 65.6% |
| 30 | Lysistrata | Aristophanes | 27,614 | 13,747 | 0.498 | 67.1% |
| 31 | Plutus | Aristophanes | 31,214 | 13,408 | 0.430 | 79.8% |
| 32 | De Compositione Verborum | Dionysius of Halicarnassus | 20,943 | 77,840 | 0.269 | 115.2% |
| 33 | Idylls * | Moschus | 3,599 | 32,764 | 0.110 | 160.4% |
| — | De Vita Pythagorica / De Mysteriis | Iamblichus | 0 | 0 | N/A | N/A |
| — | Thebaid / Achilleid | Statius | 0 | 0 | N/A | N/A |

## Notes

- **Ratio** = min(source, english) / max(source, english). 1.0 = perfect match.
- **% Diff** = absolute difference / average of the two counts.
- Word counts are raw whitespace-split tokens from the HTML parallel text columns.
- English translations are typically wordier than Greek, so English > Greek is expected for well-aligned works.
- Works marked with * have notes:
  - **Idylls** (Bion of Phlossa): 3 files but only 1 unique
  - **Idylls** (Moschus): 5 files but only 1 unique
- Works with no parallel text: De Vita Pythagorica / De Mysteriis (Iamblichus): HTML files exist but contain no parallel text; Thebaid / Achilleid (Statius): HTML files exist but contain no parallel text
- Works where source >> English may have alignment issues or source text that includes apparatus/scholia.

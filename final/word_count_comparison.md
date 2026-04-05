# Greek vs English Word Count Comparison

Ranked by how close the source and English word counts are per work (ratio = min/max words).

| Rank | Work | Author | Source Words | English Words | Ratio | % Diff |
|------|------|--------|------------:|-------------:|------:|-------:|
| 1 | Fabulae | Aesop | 50,382 | 46,995 | 0.933 | 7.0% |
| 2 | Daphnis and Chloe | Longus | 21,951 | 23,617 | 0.929 | 7.3% |
| 3 | Leucippe and Clitophon | Achilles Tatius | 47,173 | 54,085 | 0.872 | 13.7% |
| 4 | Thesmophoriazusae | Aristophanes | 7,632 | 6,655 | 0.872 | 13.7% |
| 5 | Acharnians | Aristophanes | 7,753 | 6,353 | 0.819 | 19.8% |
| 6 | Enneads | Plotinus | 234,864 | 287,289 | 0.818 | 20.1% |
| 7 | Aethiopica | Heliodorus | 84,953 | 104,688 | 0.811 | 20.8% |
| 8 | Cynegeticus | Arrian | 6,620 | 8,382 | 0.790 | 23.5% |
| 9 | Epigrams | Theocritus | 1,935 | 1,508 | 0.779 | 24.8% |
| 10 | Anabasis of Alexander | Arrian | 85,636 | 114,611 | 0.747 | 28.9% |
| 11 | Roman Antiquities | Dionysius of Halicarnassus | 310,725 | 421,218 | 0.738 | 30.2% |
| 12 | Lysistrata | Aristophanes | 8,520 | 6,211 | 0.729 | 31.3% |
| 13 | Knights | Aristophanes | 9,684 | 6,988 | 0.722 | 32.3% |
| 14 | Characters | Theophrastus | 7,372 | 10,243 | 0.720 | 32.6% |
| 15 | Hymn to the Mother of the Gods | Julian | 6,299 | 9,085 | 0.693 | 36.2% |
| 16 | Constitution of the Athenians | Aristotle | 18,032 | 26,141 | 0.690 | 36.7% |
| 17 | Meditations (Ad Se Ipsum) | Marcus Aurelius | 32,406 | 47,792 | 0.678 | 38.4% |
| 18 | Hymn to King Helios | Julian | 8,158 | 12,273 | 0.665 | 40.3% |
| 19 | Argonautica | Apollonius Rhodius | 43,391 | 65,837 | 0.659 | 41.1% |
| 20 | Bibliotheca Historica | Diodorus Siculus | 417,026 | 633,644 | 0.658 | 41.2% |
| 21 | Refutatio Omnium Haeresium (Philosophumena) | Hippolytus | 129,601 | 80,275 | 0.619 | 47.0% |
| 22 | Plutus | Aristophanes | 8,530 | 4,998 | 0.586 | 52.2% |
| 23 | Thebaid / Achilleid | Statius | 70,111 | 120,941 | 0.580 | 53.2% |
| 24 | Peace (Pax) | Aristophanes | 8,630 | 15,368 | 0.562 | 56.2% |
| 25 | Ecclesiazusae | Aristophanes | 7,859 | 14,393 | 0.546 | 58.7% |
| 26 | Wasps (Vespae) | Aristophanes | 10,571 | 5,736 | 0.543 | 59.3% |
| 27 | Epistulae | Alciphron | 47,629 | 21,599 | 0.453 | 75.2% |
| 28 | Frogs (Ranae) | Aristophanes | 9,522 | 21,906 | 0.435 | 78.8% |
| 29 | Idylls * | Moschus | 3,795 | 9,091 | 0.417 | 82.2% |
| 30 | Secret History (Anecdota) | Procopius | 34,865 | 85,055 | 0.410 | 83.7% |
| 31 | De Compositione Verborum | Dionysius of Halicarnassus | 22,782 | 69,807 | 0.326 | 101.6% |
| 32 | History of the Wars | Procopius | 244,944 | 867,204 | 0.282 | 111.9% |
| 33 | Idylls * | Bion of Phlossa | 2,011 | 11,313 | 0.178 | 139.6% |
| 34 | De Vita Pythagorica / De Mysteriis | Iamblichus | 80,914 | 459,158 | 0.176 | 140.1% |
| 35 | Idylls | Theocritus | 21,649 | 158,073 | 0.137 | 151.8% |

## Notes

- **Ratio** = min(source, english) / max(source, english). 1.0 = perfect match.
- **% Diff** = absolute difference / average of the two counts.
- Word counts are raw whitespace-split tokens from the HTML parallel text columns.
- English translations are typically wordier than Greek, so English > Greek is expected for well-aligned works.
- Works marked with * have notes:
  - **Idylls** (Moschus): 5 files but only 1 unique
  - **Idylls** (Bion of Phlossa): 3 files but only 1 unique
- Works where source >> English may have alignment issues or source text that includes apparatus/scholia.

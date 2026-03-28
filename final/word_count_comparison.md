# Greek vs English Word Count Comparison

Ranked by how close the source and English word counts are per work (ratio = min/max words).

| Rank | Work | Author | Source Words | English Words | Ratio | % Diff |
|------|------|--------|------------:|-------------:|------:|-------:|
| 1 | Daphnis and Chloe | Longus | 22,066 | 23,755 | 0.929 | 7.4% |
| 2 | Fabulae | Aesop | 50,894 | 47,097 | 0.925 | 7.7% |
| 3 | Leucippe and Clitophon | Achilles Tatius | 47,339 | 53,833 | 0.879 | 12.8% |
| 4 | Thesmophoriazusae | Aristophanes | 7,709 | 6,655 | 0.863 | 14.7% |
| 5 | Enneads | Plotinus | 237,109 | 285,963 | 0.829 | 18.7% |
| 6 | Cynegeticus | Arrian | 6,669 | 8,379 | 0.796 | 22.7% |
| 7 | Acharnians | Aristophanes | 7,835 | 6,163 | 0.787 | 23.9% |
| 8 | Epigrams | Theocritus | 1,947 | 1,503 | 0.772 | 25.7% |
| 9 | Anabasis of Alexander | Arrian | 86,097 | 114,932 | 0.749 | 28.7% |
| 10 | Roman Antiquities | Dionysius of Halicarnassus | 312,704 | 420,726 | 0.743 | 29.5% |
| 11 | Characters | Theophrastus | 7,438 | 10,220 | 0.728 | 31.5% |
| 12 | Lysistrata | Aristophanes | 8,634 | 6,202 | 0.718 | 32.8% |
| 13 | Knights | Aristophanes | 9,767 | 6,948 | 0.711 | 33.7% |
| 14 | Constitution of the Athenians | Aristotle | 18,186 | 26,109 | 0.697 | 35.8% |
| 15 | Hymn to the Mother of the Gods | Julian | 6,323 | 9,095 | 0.695 | 36.0% |
| 16 | Meditations (Ad Se Ipsum) | Marcus Aurelius | 32,627 | 47,641 | 0.685 | 37.4% |
| 17 | Hymn to King Helios | Julian | 8,204 | 12,250 | 0.670 | 39.6% |
| 18 | Argonautica | Apollonius Rhodius | 43,564 | 65,693 | 0.663 | 40.5% |
| 19 | Bibliotheca Historica | Diodorus Siculus | 419,242 | 633,238 | 0.662 | 40.7% |
| 20 | Refutatio Omnium Haeresium (Philosophumena) | Hippolytus | 129,199 | 79,839 | 0.618 | 47.2% |
| 21 | Thebaid / Achilleid | Statius | 70,111 | 120,941 | 0.580 | 53.2% |
| 22 | Plutus | Aristophanes | 8,641 | 4,986 | 0.577 | 53.6% |
| 23 | Peace (Pax) | Aristophanes | 8,746 | 15,361 | 0.569 | 54.9% |
| 24 | Wasps (Vespae) | Aristophanes | 10,730 | 5,776 | 0.538 | 60.0% |
| 25 | Aethiopica | Heliodorus | 85,005 | 44,328 | 0.521 | 62.9% |
| 26 | Ecclesiazusae | Aristophanes | 7,937 | 15,812 | 0.502 | 66.3% |
| 27 | Secret History (Anecdota) | Procopius | 35,151 | 76,782 | 0.458 | 74.4% |
| 28 | History of the Wars | Procopius | 246,635 | 542,683 | 0.454 | 75.0% |
| 29 | Frogs (Ranae) | Aristophanes | 9,638 | 21,898 | 0.440 | 77.8% |
| 30 | Epistulae | Alciphron | 47,775 | 16,269 | 0.341 | 98.4% |
| 31 | De Compositione Verborum | Dionysius of Halicarnassus | 22,891 | 69,647 | 0.329 | 101.1% |
| 32 | De Vita Pythagorica / De Mysteriis | Iamblichus | 81,370 | 453,587 | 0.179 | 139.2% |
| 33 | Idylls * | Bion of Phlossa | 2,022 | 11,301 | 0.179 | 139.3% |
| 34 | Idylls | Theocritus | 21,796 | 157,945 | 0.138 | 151.5% |
| 35 | Idylls * | Moschus | 3,794 | 90,022 | 0.042 | 183.8% |

## Notes

- **Ratio** = min(source, english) / max(source, english). 1.0 = perfect match.
- **% Diff** = absolute difference / average of the two counts.
- Word counts are raw whitespace-split tokens from the HTML parallel text columns.
- English translations are typically wordier than Greek, so English > Greek is expected for well-aligned works.
- Works marked with * have notes:
  - **Idylls** (Bion of Phlossa): 3 files but only 1 unique
  - **Idylls** (Moschus): 5 files but only 1 unique
- Works where source >> English may have alignment issues or source text that includes apparatus/scholia.

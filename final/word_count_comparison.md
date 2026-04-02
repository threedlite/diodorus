# Greek vs English Word Count Comparison

Ranked by how close the source and English word counts are per work (ratio = min/max words).

| Rank | Work | Author | Source Words | English Words | Ratio | % Diff |
|------|------|--------|------------:|-------------:|------:|-------:|
| 1 | Daphnis and Chloe | Longus | 22,066 | 23,755 | 0.929 | 7.4% |
| 2 | Fabulae | Aesop | 50,894 | 46,456 | 0.913 | 9.1% |
| 3 | Leucippe and Clitophon | Achilles Tatius | 47,339 | 53,833 | 0.879 | 12.8% |
| 4 | Thesmophoriazusae | Aristophanes | 7,709 | 6,648 | 0.862 | 14.8% |
| 5 | Enneads | Plotinus | 237,109 | 285,963 | 0.829 | 18.7% |
| 6 | Aethiopica | Heliodorus | 85,005 | 103,772 | 0.819 | 19.9% |
| 7 | Cynegeticus | Arrian | 6,669 | 8,379 | 0.796 | 22.7% |
| 8 | Acharnians | Aristophanes | 7,835 | 6,197 | 0.791 | 23.3% |
| 9 | Epigrams | Theocritus | 1,947 | 1,503 | 0.772 | 25.7% |
| 10 | Anabasis of Alexander | Arrian | 86,097 | 114,932 | 0.749 | 28.7% |
| 11 | Roman Antiquities | Dionysius of Halicarnassus | 312,704 | 420,726 | 0.743 | 29.5% |
| 12 | Characters | Theophrastus | 7,438 | 10,220 | 0.728 | 31.5% |
| 13 | Lysistrata | Aristophanes | 8,634 | 6,202 | 0.718 | 32.8% |
| 14 | Knights | Aristophanes | 9,767 | 6,948 | 0.711 | 33.7% |
| 15 | Constitution of the Athenians | Aristotle | 18,186 | 26,109 | 0.697 | 35.8% |
| 16 | Hymn to the Mother of the Gods | Julian | 6,323 | 9,095 | 0.695 | 36.0% |
| 17 | Meditations (Ad Se Ipsum) | Marcus Aurelius | 32,627 | 47,641 | 0.685 | 37.4% |
| 18 | Hymn to King Helios | Julian | 8,204 | 12,250 | 0.670 | 39.6% |
| 19 | Argonautica | Apollonius Rhodius | 43,564 | 65,688 | 0.663 | 40.5% |
| 20 | Bibliotheca Historica | Diodorus Siculus | 419,242 | 632,890 | 0.662 | 40.6% |
| 21 | Refutatio Omnium Haeresium (Philosophumena) | Hippolytus | 129,199 | 79,839 | 0.618 | 47.2% |
| 22 | Thebaid / Achilleid | Statius | 70,111 | 120,941 | 0.580 | 53.2% |
| 23 | Plutus | Aristophanes | 8,641 | 4,986 | 0.577 | 53.6% |
| 24 | Peace (Pax) | Aristophanes | 8,746 | 15,361 | 0.569 | 54.9% |
| 25 | Wasps (Vespae) | Aristophanes | 10,730 | 5,764 | 0.537 | 60.2% |
| 26 | Ecclesiazusae | Aristophanes | 7,937 | 15,798 | 0.502 | 66.2% |
| 27 | Secret History (Anecdota) | Procopius | 35,151 | 77,012 | 0.456 | 74.6% |
| 28 | Epistulae | Alciphron | 47,775 | 21,410 | 0.448 | 76.2% |
| 29 | Frogs (Ranae) | Aristophanes | 9,638 | 21,898 | 0.440 | 77.8% |
| 30 | De Compositione Verborum | Dionysius of Halicarnassus | 22,891 | 69,647 | 0.329 | 101.1% |
| 31 | History of the Wars | Procopius | 246,635 | 861,734 | 0.286 | 111.0% |
| 32 | De Vita Pythagorica / De Mysteriis | Iamblichus | 81,370 | 453,587 | 0.179 | 139.2% |
| 33 | Idylls * | Bion of Phlossa | 2,022 | 11,301 | 0.179 | 139.3% |
| 34 | Idylls | Theocritus | 21,796 | 157,945 | 0.138 | 151.5% |
| 35 | Idylls * | Moschus | 3,794 | 89,673 | 0.042 | 183.8% |

## Notes

- **Ratio** = min(source, english) / max(source, english). 1.0 = perfect match.
- **% Diff** = absolute difference / average of the two counts.
- Word counts are raw whitespace-split tokens from the HTML parallel text columns.
- English translations are typically wordier than Greek, so English > Greek is expected for well-aligned works.
- Works marked with * have notes:
  - **Idylls** (Bion of Phlossa): 3 files but only 1 unique
  - **Idylls** (Moschus): 5 files but only 1 unique
- Works where source >> English may have alignment issues or source text that includes apparatus/scholia.

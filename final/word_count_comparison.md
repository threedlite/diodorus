# Greek vs English Word Count Comparison

Ranked by how close the source and English word counts are per work (ratio = min/max words).

| Rank | Work | Author | Source Words | English Words | Ratio | % Diff |
|------|------|--------|------------:|-------------:|------:|-------:|
| 1 | Wasps (Vespae) | Aristophanes | 10,730 | 11,008 | 0.975 | 2.6% |
| 2 | History of the Wars | Procopius | 246,635 | 258,981 | 0.952 | 4.9% |
| 3 | Ecclesiazusae | Aristophanes | 7,937 | 8,787 | 0.903 | 10.2% |
| 4 | Aethiopica | Heliodorus | 85,005 | 102,981 | 0.825 | 19.1% |
| 5 | Frogs (Ranae) | Aristophanes | 9,638 | 11,910 | 0.809 | 21.1% |
| 6 | Epigrams | Theocritus | 1,947 | 1,525 | 0.783 | 24.3% |
| 7 | Secret History (Anecdota) | Procopius | 35,151 | 44,940 | 0.782 | 24.4% |
| 8 | Refutatio Omnium Haeresium (Philosophumena) | Hippolytus | 129,199 | 96,868 | 0.750 | 28.6% |
| 9 | Anabasis of Alexander | Arrian | 86,097 | 114,892 | 0.749 | 28.7% |
| 10 | Peace (Pax) | Aristophanes | 8,746 | 6,530 | 0.747 | 29.0% |
| 11 | Bibliotheca Historica | Diodorus Siculus | 419,242 | 563,751 | 0.744 | 29.4% |
| 12 | Roman Antiquities | Dionysius of Halicarnassus | 312,704 | 421,412 | 0.742 | 29.6% |
| 13 | Hymn to the Mother of the Gods | Julian | 6,323 | 9,002 | 0.702 | 35.0% |
| 14 | Hymn to King Helios | Julian | 8,204 | 11,928 | 0.688 | 37.0% |
| 15 | Fabulae | Aesop | 50,894 | 34,811 | 0.684 | 37.5% |
| 16 | Enneads | Plotinus | 237,109 | 356,926 | 0.664 | 40.3% |
| 17 | Argonautica | Apollonius Rhodius | 43,564 | 68,602 | 0.635 | 44.6% |
| 18 | Plutus | Aristophanes | 8,641 | 13,969 | 0.619 | 47.1% |
| 19 | Knights | Aristophanes | 9,767 | 15,874 | 0.615 | 47.6% |
| 20 | Acharnians | Aristophanes | 7,835 | 12,805 | 0.612 | 48.2% |
| 21 | Lysistrata | Aristophanes | 8,634 | 14,298 | 0.604 | 49.4% |
| 22 | Epistulae | Alciphron | 47,775 | 28,794 | 0.603 | 49.6% |
| 23 | Daphnis and Chloe | Longus | 22,066 | 36,863 | 0.599 | 50.2% |
| 24 | Leucippe and Clitophon | Achilles Tatius | 47,339 | 81,445 | 0.581 | 53.0% |
| 25 | Thesmophoriazusae | Aristophanes | 7,709 | 13,374 | 0.576 | 53.7% |
| 26 | Idylls * | Bion of Phlossa | 1,622 | 2,852 | 0.569 | 55.0% |
| 27 | Meditations (Ad Se Ipsum) | Marcus Aurelius | 32,627 | 60,794 | 0.537 | 60.3% |
| 28 | Cynegeticus | Arrian | 6,669 | 15,340 | 0.435 | 78.8% |
| 29 | Characters | Theophrastus | 7,438 | 19,570 | 0.380 | 89.8% |
| 30 | Constitution of the Athenians | Aristotle | 18,186 | 50,791 | 0.358 | 94.5% |
| 31 | Idylls | Theocritus | 21,796 | 72,223 | 0.302 | 107.3% |
| 32 | De Compositione Verborum | Dionysius of Halicarnassus | 22,891 | 81,637 | 0.280 | 112.4% |
| 33 | Idylls * | Moschus | 3,794 | 29,468 | 0.129 | 154.4% |
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

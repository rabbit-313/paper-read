# Notes

- Source PDF: `_local_artifacts/1904.06813.pdf`
- Paper: Personalized Re-ranking for Recommendation, RecSys 2019.
- Translation source: `../translation/paper.ja.md`
- The PDF extraction was text-based, but the two-column layout caused section-order noise in `extraction/raw.md`; slide content was checked against page previews.
- Figures and tables used in slides were cropped from rendered PDF pages for readability.
- Evaluation caveat: Seq2Slate and GlobalRerank are discussed but not used as online baselines because the paper treats their decoder latency as unacceptable for the target online system.

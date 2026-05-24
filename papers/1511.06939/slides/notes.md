# Notes

- Source paper: arXiv:1511.06939, "Session-based Recommendations with Recurrent Neural Networks".
- This is the original GRU4Rec paper, published at ICLR 2016.
- Figures used:
  - `arch.png`: network architecture.
  - `mini-batch.png`: session-parallel mini-batch.
- Main evaluation facts:
  - RSC15: 7,966,257 train sessions, 31,637,239 clicks, 37,483 items.
  - VIDEO: about 3 million train sessions, about 13 million watch events, 330k videos.
  - Metrics: Recall@20 and MRR@20.
  - Best baseline: Item-KNN.
  - Best reported gains are roughly 20-30% over Item-KNN depending on dataset/metric/loss.
- Caveat:
  - This is an early RNN-based session recommendation paper; later attention, graph, and transformer methods should be considered for modern baselines.

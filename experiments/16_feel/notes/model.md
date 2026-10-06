# A trained feeler: reading the feeling with a small CTC model (2026-10-06)

**Question.** feel.py reads each piece of ink blind by matching it against remembered letters (nearest
neighbour, evenly stretched): ~44% of pieces read as Azure reads them, and long joined pieces fail. Can a
small *trained* model — the "online handwriting recognition" route — read the same feeling better, and give
letter cuts from the same pass? And does training on several typefaces together help?

**Method.** Files: `model_lib.py` (features, model, decoder), `methods/model_ctc*.py`.

- *Input — the feeling only, no picture.* Per pen-path position (`model_lib.raw`, 18 channels): feel.feeling's
  six (pen height, ink above, ink below, heading dy/dx, ink mass); the stick's walk up the branches at that
  position (highest point, lowest point, branch length); the dots as taps above/below; the cutter's geometric
  facts (ascender, tall, descender, deep, thin, connector); candidate cut places. Laid out in reading order
  (right end first) and pooled to 20 frames per rise, so that four typefaces at four scan sizes feel alike.
- *Model.* LayerNorm → two 1-D convolutions (96 ch, width 5) → 2-layer BiLSTM (128 per direction) → per
  frame: a letter-form (base + init/med/fin/iso, 103–~130 classes) or blank, trained with CTC on Azure's
  letters; and a boundary score, trained (BCE) on the letter cutter's cuts where the train record has them.
  714k parameters. Augmentation: ±15% stretch along the path, ±10% height scale, small noise.
- *Reading.* CTC prefix beam search (beam 8) that only keeps chains the script's grammar allows
  (init med* fin, or iso, runs may touch). *Cuts:* Viterbi alignment gives each letter's emission frame;
  between two letters, the frame the boundary head likes best, snapped to the nearest candidate cut place.
- *Training sets.* Per document (its train pages only), joint (train pages of all four documents, 10.9k
  pieces), and joint then fine-tuned on the document's own train pages (10 passes, lr 5e-4). No dev or test
  page is ever trained on.

## Every logged run (dev; mean per-document piece accuracy is the headline)

| method | what | mean/doc pieces | letters | 0582 | 0618 | 1036 | 0772 |
|---|---|---|---|---|---|---|---|
| feel_v1 | baseline (two rows merged: 0582 alone, then the rest) | 44.1% | ~54% | 43.1 | 35.9 | 42.2 | 54.3 |
| model_ctc_doc | per document, 40 passes, seed 0 (0582 row + 3-doc row) | 73.0% | 81.2% | 72.1 | 69.5 | 71.3 | 79.1 |
| model_ctc_doc_s1 | same, seed 1, 0582 only | — | 75.4% | 68.8 | | | |
| model_ctc | joint, 20 passes | 75.6% | 83.9% | 77.8 | 72.8 | 71.8 | 80.0 |
| **model_ctc_ft** | joint + 10-pass fine-tune per document | **77.0%** | **85.2%** | 81.6 | 73.5 | 72.4 | 80.6 |
| model_ctc_ft_s1 | same, fine-tune seed 1 | 76.8% | 85.1% | 81.8 | 73.2 | 72.7 | 79.4 |
| model_ctc_ft_cand | model_ctc_ft, cuts chosen among the candidates instead | 77.0% | 85.2% | (cuts worse: 60–74% within a stroke) | | | |

By length (model_ctc_ft, all four documents' dev pages): one letter 887/946 (94%), two 433/556 (78%), three
227/363 (63%), four 126/260 (48%), five or more 41/142 (29%). feel_v1 on 0582: 65% / 27% / 29% / 16% / 0%.

Cuts within one stroke of the cutter's own, on pieces read right: 71–82% per document for model_ctc_ft
(242–561 cuts per document), against feel_v1's 95% on 0582 (79 cuts — far fewer, easier pieces).

## What helped, what did not

- **Training a reader at all**: 43% → 72% on 0582 with a per-document model and nothing tuned. The nearest-
  neighbour chain search has no tolerance for a letter written longer here and shorter there; the BiLSTM
  learns it, and CTC never needs the cuts to learn the letters, so every train piece counts (feel_v1 can only
  remember the joined pieces the cutter managed to cut).
- **Several typefaces together**: joint beats per-document on every document (+2.6 points mean; +5.7 on
  0582, the smallest train set). Fine-tuning on the document's own pages adds ~1.4 more (77.0 vs 75.6); two
  fine-tune seeds agree within 0.3 points, so the gain over joint is small but probably real; the gain over
  per-document is well beyond the seed noise.
- **Run-to-run noise**: per-document training on 0582 moved 72.1 → 68.8 with another seed (±3 points: a small
  document's train set is small). The fine-tuned joint model is much steadier (77.0 / 76.8).
- **Did not help**: picking the cut among the candidate places between two letters by the boundary score
  (same reading, cuts 5–10 points further from the cutter's). The frame-then-snap rule stays.

**Choices tuned on dev: two** (fine-tuning on/off, cut rule frame/candidate). Everything else (20 frames per
rise, model size, 40/20/10 passes, learning rates, augmentation, beam 8, boundary weight 0.5) was set once
by guess and never varied, so dev is close to an honest estimate. Test pages were never read.

## Open risks and next steps

- **Cuts** are the weak half: ~75% within a stroke of the cutter's, below the 95% feel_v1 has on the few
  pieces it reads. CTC emits spikes, not spans; the boundary head is trained on only the half of train pieces
  the cutter cut. A next try: once the letters are read, cut with feel.py's chain search (or the cutter
  itself, `penpath.plan`) *constrained to the model's reading* — reading from the model, cuts from geometry.
- **Long pieces** still fail (5+ letters: 29%). A word list from the document (the `taps_lex` direction) as a
  prior in the beam would likely add several points; the beam already supports adding a score per prefix.
- "Right" is Azure's reading, unchecked; on dev pages the model may learn Azure's own habits.
- Joint training here covers the four bench documents' train pages; on a new document the fine-tune needs
  that document's own Azure-labelled pages, as feel_v1 does. Without them, the joint model alone (75.6%
  here) is what one gets — untested on an unseen typeface.
- Speed: joint training ~28 min on 4 CPU threads (with two other researchers' jobs alongside), fine-tune
  2–6 min per document, reading ~5 ms per piece; peak memory < 0.9 GB.

Environment: `out/torchenv` (CPU torch 2.14.1 + the repo, editable). Models are cached in `out/models/`.

# Scaling the trained feeler to many books (2026-10-06)

**Question.** `model_ctc_ft` (the CTC BiLSTM reader of the pen path, 714k parameters) was trained on the TRAIN
pages of only the four benchmark books and reads 77.0% of dev pieces as Azure does. Does training on many more
scanned books — many more typefaces — make it better on the benchmark, and how does accuracy grow with the
number of books?

**Short answer.** More books help, but only once the reader is allowed to grow. With the reader kept at its
size and a fixed training budget, the benchmark stayed flat (77.3 → 77.2 → 76.8 → 76.9 → 78.1 for 0, 15, 30,
60, 93 extra books), while the same models read *books they had never seen* much better (61 → 72 → 72 → 74%).
A reader twice as wide (1.5M parameters) trained on all 93 extra books reads **80.8%** of dev pieces
(81.3% with a longer fine-tune), up from 77.0, on every one of the four books, and long pieces gain most
(five letters or more 29 → 38%). It is the books and the width together: the same wide reader on the four
bench books alone reads 76.3% (it overfits: training loss 0.25), and the narrow one on all 93 books 78.1%.

## Books

Files: `scale_lib.py` (extraction, trainer, probe), `methods/model_scale*.py`, `methods/hybrid_scale.py`.
Data under `out/books/` (gitignored): `raw/` the fetched documents, `screen.jsonl` the screening, `feats/`
the extracted pieces, `run_*.log` every run's log, `probe.jsonl` the unseen-book probe.

- 160 random documents from `s3://mandumah-source-docs`, **one per journal** (4650 journals in the bucket;
  one per journal so that each book is likely a different typeface). The benchmark journals 0582, 0618,
  1036, 0772 and the gold-set journals 0005, 1110 excluded whole.
- Kept if scanned (the PDF's only font is `Dummy`: 114 of 160) and mostly Arabic (Arabic letters > 80% of
  Azure's letters: **93 books**).
- Up to 8 pages per book whose Azure page angle is within 5° of upright and which carry ≥ 40 words (page 1
  only if fewer than 8 others: covers). 71 books gave 8 pages; the smallest gave 2.
- Pieces extracted exactly as `bench.build_cache` does for TRAIN pages (`reader.pieces_of`, `reader.blind`,
  the cutter's cuts via `penpath.plan` + `solve` with each book's own atlas), stored straight away as
  `model_lib.raw` features (float16). **317,412 pieces** (median ~3,400 per book; 52% carry cutter cuts),
  against 10,693 in the four bench books' train pages. ~2.5 min per book, peak 1.0–3.5 GB per process, 3 at a
  time (OpenCV limited to 2 threads: with its default 16 per process the CPU thrashed).
- The order of the books is a fixed random shuffle (`scale_lib.book_order`); "N books" means the first N.
  The list, in order, with pages and pieces: `python scale_lib.py stats`.

The bench books contribute only their TRAIN pages (`model_lib.doc_train_raw`); no dev or test page is ever
trained on. Every run below is on dev, logged in `out/results.jsonl`.

## Method

The reader, features, decoder and fine-tune are model_ctc_ft's (`model_lib`), unchanged. Two changes in
the trainer (`scale_lib.train`), needed for 30× the data on a CPU:

- training length in optimiser **steps** instead of passes (12k steps of 32 pieces for every curve point, so
  that each point costs the same; model_ctc_ft's joint step was ~6.8k steps);
- **length-bucketed batches** (64 batches' worth of pieces sorted by length, cut into batches, the batches
  shuffled): 2.3× faster per step on CPU, no change in accuracy at 4 books (77.3 vs 77.0).
- Letter-forms seen fewer than 20 times in the training set are dropped with their pieces (Latin letters,
  stray marks): 90 forms at 4 books, 113 at 15, 125 at 93.

Then the per-book fine-tune exactly as model_ctc_ft: the book's own train pages, 10 passes, lr 5e-4, batches of 32.

## The growth curve (dev, mean per-document piece accuracy)

Same reader (714k parameters), 12k steps of 32, then the 10-pass fine-tune per bench book.

| extra books | pieces trained on | **bench, fine-tuned** | 0582 | 0618 | 1036 | 0772 | bench, joint only (no fine-tune) | **unseen books** (probe) |
|---|---|---|---|---|---|---|---|---|
| 0 (model_ctc_ft, 6.8k steps) | 10.9k | 77.0 | 81.6 | 73.5 | 72.4 | 80.6 | 75.6 | — |
| 0 | 10.7k | 77.3 | 79.6 | 75.1 | 74.0 | 80.6 | 75.4 | 60.9 |
| 15 | 65k | 77.2 | 81.8 | 73.9 | 72.9 | 80.0 | 73.1 | 72.0 |
| 30 | 110k | 76.8 | 78.8 | 73.5 | 74.0 | 81.0 | 72.2 | 72.4 |
| 60 | 219k | 76.9 | 79.3 | 74.5 | 73.4 | 80.3 | 71.8 | 73.9 |
| 93 | 328k | 78.1 | 80.8 | 75.0 | 74.6 | 81.9 | 73.1 | (seen) |
| **93, reader grown** (1.5M, 14k steps of 64) | 328k | **80.8** | 84.0 | 77.8 | 77.1 | 84.4 | | (seen) |
| 0, reader grown (control, 7k steps of 64) | 10.7k | 76.3 | 80.0 | 72.1 | 73.8 | 79.4 | | |

*Unseen books* (`scale_lib.probe`): the last 10 books in the order (never trained on by any model up to 60
books), 300 random pieces each, the joint model alone (no fine-tune: there are no labels for a new book),
letters only; mean per-book piece accuracy against Azure. Per book at 0 → 60: 61→75, 73→87, 69→81, 41→52,
59→67, 66→80, 62→77, 60→72, 54→75, 63→74 — every book climbs.

Dev has 2,267 pieces: one standard error of the mean is ~0.9 points, so the four small-reader points
(76.8–78.1) are indistinguishable; the grown reader's +3.8 is well outside it (and holds on every book).

**Reading the curve.**

- *For a book never seen*, typefaces are what counts: 4 books → 15 books is +11 points; 15 → 60 is +2 more,
  still rising slowly with the small reader.
- *For the benchmark books*, which already have their own train pages, the small reader gains nothing: the joint
  model gets *worse* on them as other books crowd them out (75.4 → 71.8 before fine-tuning — they are 16% of
  the data at 15 books, 3% at 93), and the fine-tune wins back the difference and no more. Its training loss
  rose with the data (0.33 at 4 books, 0.65 at 15, 0.73 at 30): the 714k reader was full.
- Growing the reader (LSTM 192 per direction, convolutions 128, 1.5M parameters) and giving it 2.3× the
  samples turned the extra books into accuracy: 80.8%.

## Every run (dev)

| method | what | mean/doc pieces | letters | 0582 | 0618 | 1036 | 0772 | train time | peak |
|---|---|---|---|---|---|---|---|---|---|
| model_scale_n0 | 0 extra books, 12k×32, ft 10 | 77.32 | 85.00 | 79.55 | 75.11 | 74.00 | 80.63 | 35 min joint | 0.9 GB |
| model_scale_n0_joint | same, no fine-tune | 75.35 | 83.81 | 77.56 | 73.06 | 71.11 | 79.68 | | |
| model_scale_n15 | 15 books | 77.15 | 85.29 | 81.80 | 73.92 | 72.87 | 80.00 | 37 min | 0.9 GB |
| model_scale_n15_joint | no fine-tune | 73.14 | 82.18 | 76.56 | 71.12 | 69.02 | 75.87 | | |
| model_scale_n30 | 30 books | 76.81 | 85.05 | 78.80 | 73.49 | 74.00 | 80.95 | 42 min | 1.0 GB |
| model_scale_n30_joint | no fine-tune | 72.22 | 81.60 | 73.32 | 71.12 | 69.50 | 74.92 | | |
| model_scale_n60 | 60 books | 76.86 | 85.19 | 79.30 | 74.46 | 73.35 | 80.32 | 41 min | 1.3 GB |
| model_scale_n60_joint | no fine-tune | 71.83 | 81.57 | 71.57 | 70.37 | 67.90 | 77.46 | | |
| model_scale_n60_ft20 | 60 books, fine-tune 20 passes | 77.81 | 86.02 | 80.30 | 74.57 | 75.12 | 81.27 | | |
| model_scale_n93 | 93 books | 78.09 | 86.27 | 80.80 | 75.00 | 74.64 | 81.90 | 79 min | 1.6 GB |
| model_scale_n93_joint | no fine-tune | 73.08 | 82.60 | 72.82 | 70.15 | 69.34 | 80.00 | | |
| model_scale_n93_ft20 | 93 books, fine-tune 20 passes | 78.50 | 86.63 | 81.80 | 74.35 | 76.24 | 81.59 | | |
| **model_scale_big** (= model_scale) | 93 books, 1.5M reader, 14k×64, ft 10 | **80.83** | **87.74** | 84.04 | 77.80 | 77.05 | 84.44 | 175 min | 1.9 GB |
| model_scale_big_ft20 | same, fine-tune 20 passes | 81.28 | 87.93 | 84.29 | 78.23 | 77.85 | 84.76 | | |
| hybrid_scale | model_scale's letters, cuts re-chosen by the feeling | 80.83 | 87.74 | 84.04 | 77.80 | 77.05 | 84.44 | | |
| model_scale_big_n0 | control: 1.5M reader, 0 extra books, 7k×64, ft 10 | 76.34 | 84.67 | 80.05 | 72.09 | 73.84 | 79.37 | 95 min | 1.0 GB |

Train times are wall clock with two to four trainings and another agent's jobs sharing the 16 CPUs, 4 torch
threads each (an uncontended step is ~0.15 s for the small reader with buckets, ~0.5 s for the grown one).
Fine-tunes: 3–15 min per book. Peak memory per process ≤ 1.9 GB (the 93-book run holds all 328k pieces).

**By length** (all four books' dev pages), model_ctc_ft → model_scale_big: one letter 94 → 96%, two 78 → 81%,
three 63 → 67%, four 48 → 58%, five or more 29 → 38%. Letters 85.2 → 87.7%.

**Cuts** (within one stroke of the cutter's, pieces read right): model_scale_big's own cuts 88 / 79 / 81 / 76%
(0582 / 0618 / 1036 / 0772), better than model_ctc_ft's 82 / 73 / 72 / 71 — the boundary head also learned from
the 165k pieces the cutter cut in the new books. Re-choosing them from the geometry (hybrid_scale) now helps
only on 0582 (91%) and loses on 0618 (73) and 1036 (78): the hybrid is no longer worth it with this reader.

## What helped, what did not

- **Growing the reader with the data**: +3.8 points over model_ctc_ft, +2.7 over the same 93 books in the small
  reader; every book, every length. The one thing that turned books into benchmark accuracy. Width alone does
  not do it: the wide reader on the four bench books only is 76.3% (−1.0 against the narrow one).
- **More typefaces, for a book the reader has never seen**: +11 points from 4 to 19 books, +13 at 64 —
  the strongest effect measured here, and the one that matters for the archive (no per-book labels there).
- **More books for the benchmark books, small reader**: nothing (flat within noise up to 60 books, +0.8 at 93).
- **Longer fine-tune** (20 passes instead of 10): +1.0 (n60), +0.4 (n93), +0.45 (grown) — within noise each time,
  consistently positive. Not adopted for model_scale (would be a choice tuned on dev); noted.
- **Length buckets**: 2.3× faster training, accuracy unchanged. Needed for any of this to fit in an afternoon.
- **Choices tuned on dev**: the reader size was chosen once, before seeing any scale result, and run once;
  fine-tune 10 vs 20 was measured but not adopted. Dev remains close to an honest estimate.

## Is it still climbing?

On unseen books, yes, slowly (72.0 → 72.4 → 73.9 from 19 to 64 books with the small reader, which is full).
On the benchmark, the grown reader is one point at 97 books; the curve for it (grown reader at 15, 30, 60)
was not measured for time. The likely next gains, in order: the grown reader trained longer (its loss was
still falling: 0.60 → 0.58 over the last 2k steps); a still wider reader; more pages per book rather than
more books (8 pages already give ~3,400 pieces each); then the curve of the grown reader.

## Open risks

- "Right" is Azure's reading, unchecked, in the new books as in the bench. The new books bring their own Azure
  mistakes and their own binding errors (Azure's words bound to the wrong ink); the reader learns them too.
- The unseen-book probe uses the books' own pieces (no split by page needed: those books were not trained on),
  without the cutter's candidate cuts (letters only), and is not the benchmark's dev set.
- One seed per run. The 0582 dev page is small (401 pieces: ±2 points per run).

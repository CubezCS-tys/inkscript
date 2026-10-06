# 16 · Read a word by feeling it: the pen path alone, never the picture

**Question.** The owner's picture (2026-10-05): someone writes a word on your
back with a stick; without looking you track it, know the word, and know where
each letter starts and ends. Can a machine that never sees the image — only
what a stick on the back would give — read a piece of ink and cut it into
letters in one pass, better than reading the picture blind (experiment 10)?

**Method.** `feel.py`. Every connected piece is unrolled along its pen path as
the letter cutter does (`penpath.unroll`). What the feeler receives:

- **the stick's walk**: from the first letter's join on the baseline to the
  last letter, going up every branch it meets (an alef's stem, a loop, a tail)
  and back down before moving on — heading and height at every step;
- **along the trunk**: how far the ink reaches above and below, how much ink
  hangs there (a bowl, a loop);
- **the dots afterwards, as taps** at a place along the word — the word first,
  then the dots, the way the owner's father writes. Kept apart because a dot
  is a separate stroke in time and carries most of a letter's identity but
  none of its shape: the body matches on shape, the taps break the tie.

It remembers every letter the cutter cut on pages 1–4 of the reference
document (Azure's text as the label), as individual feelings, not averages
(experiment 10: examples beat mean pictures). On page 5 it reads each piece
blind: the cheapest chain of remembered letters along the path, under the
script's grammar (initial, medials, final, or one isolated letter), with each
letter paying for its mismatch along its stretch, its taps and its unusual
length. Reading and cuts come out of the same pass. The three constants were
chosen on pages 1–3 → 4 (`--dev`), then fixed.

```
python feel.py <azure.json> <scan.pdf> 1,2,3,4 5 out        # writes out/feel.json, prints the scores
python make_page.py out/feel.json out/feel.html               # the live page: the pen on the ink, the feeling, the reading
```

## Result (2026-10-05, reference document `0582-004-009-012`, page 5)

| | Feeling the path | Reading the picture (exp. 10) |
|---|---|---|
| pieces read as Azure reads them | **295 / 582 (50.7%)** | 41% (of 570) |
| isolated letters | 209 / 276 (76%) | 67% |
| two-letter pieces | 55 / 137 (40%) | ~20% (joined) |
| three letters | 25 / 100 (25%) | |
| four | 6 / 48 (12.5%) | |
| five or more | 0 / 21 | 0 / 23 |
| letters right | 58.5% | |

Cuts, where a joined piece was read right: 96% within one stroke of the
cutter's own cuts (median 0.31 strokes, 108 cuts). The cutter is not ground
truth; this says the feeler cuts where the cutter does when it reads right.

Experiment 10 counted 570 pieces on the same page before the cutter fixes of
2026-09-22; this run finds 582. "Right" means "the same as Azure", unchecked.

**On the way.** With the letters' true cuts handed to it, the feeler first
named only 40% of letters: sampling the feeling at points stepped over every
ascender (a tall stroke hangs from one position of the path), and the trunk
alone said nothing about loops. Pooling per stretch and adding the stick's
full walk (up each branch and back) took that to 53%, and the blind reading
from ~33% to ~47% on the development page. Most remaining confusions are
tooth letters (`ب`/`ي`, `ن`/`ت`) and `و`/`ر` — told apart by dots this face
often prints as one blob, or by a small loop.

## What it means

The feel of the path carries more than the picture did, read the same crude
way: the first evidence for the owner's back-writing idea. It is far from a
reader — long pieces fail, because the evenly stretched match has no tolerance
for a letter written a little longer here and shorter there, and the chain
knows no words. The obvious next steps, in order of likely gain: stretch-
tolerant matching (dynamic time warping) instead of even stretching; a small
sequence model trained on the archive's paths with Azure's text (the trained
version of this); and a word list from the document itself. Ideas:
[docs/ideas.md](../../docs/ideas.md), "Read the word by feeling it".

## The research round (2026-10-05/06): a benchmark, four directions, one held-out test

`bench.py` fixes four scanned books in four typefaces (0582, 0618, 1036, 0772), each split into train pages
(what a method may remember), dev pages (what it may be tuned on) and test pages (read once, at the end).
Three agents worked on dev only, each in its own files (`methods/`, `notes/`); a fourth combined two of them.
Every run is in `out/results.jsonl`. The truth is Azure's reading.

**Held-out test, read once (2026-10-06), pieces read as Azure reads them, mean of the four books:**

| method | 0582 | 0618 | 1036 | 0772 | mean | letters |
|---|---|---|---|---|---|---|
| `feel_v1` — the first feeler | 47.8 | 47.2 | 43.5 | 55.8 | **48.6** | 58.1 |
| `warp_gate` — every example remembered, walk DTW, a neighbour vote | 54.1 | 56.1 | 56.2 | 59.2 | **56.4** | 64.1 |
| `taps_prior` — dots felt by size and shape, letter-trigram prior | 62.4 | 61.9 | 56.0 | 68.9 | **62.3** | 68.2 |
| `combo_best` — both of those | 63.6 | 67.4 | 61.0 | 69.3 | **65.3** | 71.9 |
| `model_ctc_ft` — small trained reader (CTC BiLSTM, 714k parameters), all four books then each | 79.4 | 80.9 | 77.3 | 78.3 | **79.0** | 86.1 |
| `hybrid_ctc_geo` — that reader's letters, cuts re-chosen by the feeling | 79.4 | 80.9 | 77.3 | 78.3 | **79.0** | 86.1 |

The hybrid reads the same as the trained reader by construction and moves its cuts nearer the cutter's
(within one stroke: 0582 80→91%, 1036 63→73%, 0772 60→75%, 0618 72→77%). Best feeler by length: one letter
96%, two 80%, three 63%, four 58%, five or more 36%. Notes per direction: `notes/warp.md`, `notes/taps.md`,
`notes/model.md`, `notes/combo.md`.

**What it means.** The pen path alone, never the picture, reads four pieces in five the way Azure does, in four
typefaces, on unseen pages — a small trained reader beat every hand-built method by 14 points. Learning all four
books together, then each book's own pages, beat learning each alone. Long joined pieces remain the weakness.
Not measured yet: whether the feeler is right where Azure is wrong (needs the gold pages, experiment 12).

The visual report: `python make_report.py out/means.json combo_best` → `out/report.html` (with
`report_data.py` and `make_live.py` → `out/feel_best.html`, both run with `out/torchenv/bin/python`).


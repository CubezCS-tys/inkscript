# 18 · Does each letter's highlight sit on its letter? (milestone 2, measured)

**Question.** Coverage says ~98% of words have a box for every letter; nothing has said whether the boxes sit on
the right letters. STATUS carried "by eye about 85–90%" as a guess, and experiment 15 was abandoned because a
picture for a human reader was a poor instrument. Here a calibrated Gemini judge looks at the scan, and three
ways of placing the boxes are compared on the same words:

- **cutter** — today's PDFs, read back (`pdf/inspect.py`): each glyph's advance in scan pixels, i.e. its cell
  (D10); a glyph still carrying several letters is sliced equally, as Chrome does;
- **feeler** — experiment 16's `hybrid_ctc_geo` cuts on the pen path, turned into cells by the cutter's own rule
  (`penpath.letter_blobs`), only on words where it reads every joined piece as Azure does;
- **equal slices** — the free baseline (D7): the word's span divided by its letters.

## Method

1. `collect.py` (torchenv, one process, peak 0.81 GB, 12 min). Pages: the bench books' pages no method trained,
   tuned or tested on (experiment 17's list: 0618 p1,16; 1036 p1,10; 0772 p6,14,16,18,20,23,25,27) and the
   fixture 0582 p1–5 (cutter and equal only). PDFs: `experiments/14_vs_azure/out/tryout_2026-10-05/{fixture_r2l,
   native_r2l,native}` (the geometry code has not changed since 2026-09-20). PDF words are matched to Azure's
   words (same letters, overlapping x). Words of 2–7 letters, no vowel marks, no lam-alef. Unseen pages: 1,174
   such words, **608 (52%) with feeler boxes** (the rest: a piece read differently, 607 of 1,276 before the
   length filter; a few with no pen path).
2. `judge18.py`. The crop is the word in its line from the 300-dpi scan, ink untouched (experiment 17's lesson):
   the word's paper pale yellow, the paper inside the box, over the word's height, light blue. Two questions per
   box, asked separately: **graded** — the word with the target letter in brackets, "does the band cover it
   EXACT / MOSTLY / PARTLY / OTHER"; **blind** — no target given, "rewrite the word bracketing every letter more
   than half inside the band; is it clean". **Right = graded EXACT and blind brackets exactly that letter.**
   Item ids name the word, letter and pixel box, never the method; identical boxes from two methods are one item;
   items of all methods shuffled together. Temperature 0, thinking low, 8 crops a request.
3. `calibrate.py` on fixture words (not the sample): 60 boxes right by construction (a letter that is its own
   piece of ink), the same boxes moved by a whole letter onto the neighbour (30 + 30 inside joined pieces), moved
   by half the letter's width (30 + 30).
4. `run18.py`: sample A 130 unseen words with feeler boxes (cutter, feeler, equal); B 50 unseen words without
   (cutter, equal); C 50 fixture words (cutter, equal). 2,485 boxes, 2,170 distinct items, 2 questions each.
5. `analyze.py` → `out/summary.json` (95% intervals: bootstrap over words). `make_report.py` → `out/report.html`.

```
experiments/16_feel/out/torchenv/bin/python collect.py
.venv/bin/python calibrate.py gemini-3.8-flash [--blind]
.venv/bin/python run18.py A 130 B 50 C 50 [--mode=graded|blind --part=i/n]
.venv/bin/python analyze.py && .venv/bin/python make_report.py
```

## Calibration (2026-10-06)

| | right box accepted | whole-letter-off refused | half-letter-off refused |
|---|---|---|---|
| first question ("which numbered letters are inside"), Flash | 54/60 | 57/60 | 41/60 |
| same, Pro | 51/60 | 55/60 | 40/60 |
| graded alone, Flash | 56/60 | 58/60 | 44/60 |
| graded alone, **Pro** | 60/60 | 47/60 | 24/60 |
| blind alone, Flash | 50/60 | 57/60 | 37/60 |
| **graded AND blind, Flash (used)** | **49/60** | **60/60** | **52/60** |

The first question failed on counting: both models swapped the alef and lam of ال. Pro under the graded question
said EXACT to almost anything with the named letter in it (it accepted 13 of 60 whole-letter-off boxes): it was
dropped. The two Flash questions err on different boxes, so requiring both gives a strict judge: it never accepted
a box a whole letter off and accepted 8 of 60 half a letter off, but refused 11 of 60 right boxes (mostly the ا
of ال again). It can tell right from wrong; it understates every method alike. An eye check by the agent of 30
random cutter verdicts agreed with the clear cases and found the misses to be mostly narrow boxes on thin letters.
(A tatweel in the judge's bracketed answer, «[يـ]», was first parsed as a letter; fixed and re-parsed from the
cache.)

## Result

**Sample A — the same 130 words (523 letters), unseen pages:**

| | letters right | words right (every letter) | letters in joined pieces |
|---|---|---|---|
| cutter | **70.2%** (65.6–74.6) | 36.9% (28.5–45.4) | 64.8% |
| feeler | **74.6%** (70.7–78.1) | 35.4% (26.9–43.8) | 70.3% |
| equal slices | **53.9%** (48.0–59.8) | 24.6% (16.9–31.5) | 53.2% |

Paired, same words: the cutter alone right on 31 words, equal slices alone on 15 (letters 148 vs 63); the feeler
against the cutter 7 vs 9 words, 45 vs 22 letters. Corrected roughly for the judge's strictness (sensitivity 49/60,
false acceptance 0–8/60), letters right: **cutter ~83–86%, feeler ~90–91%, equal ~59–66%.**

**Sample B — 50 unseen words the feeler misread:** cutter 66.9% (59.8–73.9) letters, 26% words; equal 46.3%
(39.4–53.4), 12%.

**Sample C — 50 fixture words (0582):** cutter 56.2% (49.5–63.0), 16% words; equal **58.2%** (50.3–66.1), 26%.
On the reference document the cutter does **not** beat equal slicing.

By book (A): 0772 cutter 74% / equal 50%; 1036 61% / 57%; 0618 55% / 58%. The cutter's win comes mostly from
0772; on 0618, 1036 and 0582 it is level with the baseline.

**Where each fails** (all samples, rule "both"):
- cutter: 329 of 981 boxes wrong; joined letters 38% wrong, separate pieces 14%. **A joined alef** (the final
  ا of كان, منها, أسباب) is right in 5 of 56: it hangs from one point of the pen path, so its stretch of the
  baseline — its box — is a sliver at its foot. Equal slices get 27 of 56. One letter in fifteen, about a sixth
  of the cutter's wrong boxes. Then م (35/68 wrong), ى, ن, د.
- feeler: same rule for boxes, so the same alef sliver (4 of 33 right); otherwise its cuts are a little better
  than the cutter's on joined letters (70% vs 65%).
- equal slices: fails on wide and narrow letters alike — ى 24/31 wrong, ن, ك, ق, ل, and separate pieces (72 of 174
  wrong vs the cutter's 24), where the word's gaps are not where an equal slice falls.

**Spend: $7.63** (cap $10): 659 requests, 6.0 M tokens in, 0.21 M out; calibration $1.82 (of which Pro $1.07),
measurement $5.81 at Flash ($1/$5 per M, rounded up).

## What it means

- The guess of 85–90% is about right for the cutter's letters *after allowing for a strict judge* (~83–86% on
  unseen pages); measured strictly, 70% of letters and 37% of words have every highlight on the right letter.
- The cutter beats the free baseline on unseen books (70 vs 54%, words 37 vs 25%, paired 31:15), so by D7's rule
  it earns its place there — but **not on the fixture 0582** (56 vs 58%), nor clearly on 0618 or 1036. Its win is
  concentrated in one typeface.
- The feeler's cuts are slightly better than the cutter's (+4 points letters, interval overlapping; words level),
  only on the half of words it reads right. Not worth switching for on this evidence.
- The cheapest real gain: the **joined alef's box**. Giving a letter's cell the width of the ink hanging from its
  stretch (not only its stretch of the trunk) would turn ~50 of the cutter's 329 wrong boxes in this sample. That
  is a change to `penpath.letter_blobs` and should be measured with this same judge before and after.
- Limits: words of 2–7 letters without vowels or lam-alef; the judge is Gemini, not the owner; its calibration
  used separate letters, which are easier than joined ones; "right" demands the whole letter and nothing of a
  neighbour, stricter than what a reader notices when dragging.

Not done: `docs/` and `experiments/README.md` not edited (rule of this task). Suggested index line:
`| 18 | Do the letter boxes sit on the right letters? | strict Gemini judge: cutter 70% letters / 37% words, feeler 75/35, equal slices 54/25 on unseen pages; level with equal slices on 0582; joined alef boxes are slivers | milestone 2 measured |`

# 21 · Better letter boxes: a final alef gets its whole stem

**Question.** Experiment 18 measured where the cutter's letter highlights fall: right on 70% of letters on unseen
pages, but level with equal slicing on the fixture 0582, and a joined final alef (كان، منها، كتاب) got a sliver of a
box at its foot. Can the cutter place boxes better? Proved with 18's judge, same words, before and after.

## What was wrong (seen, not guessed)

`out/draw.png` (before) / `out/draw_new.png` (after): each piece's ink coloured by letter, the pen path in black,
the cuts in red, the cells below. The pen path's left end was the **leftmost point of the centre line**. A final
alef's stem usually leans so its top is leftmost (and on a perfectly upright stem `argmin` picks the topmost of the
tied points), so the path *started at the top of the alef and ran down its stem*. The alef's stretch of the path was
the top of its stem; the cut fell part-way down; the letter before it took the stem's lower half and foot (in منها
the ه took most of the alef). The alef's cell — its stretch of the path in page x — ran from the stem's left edge to
its centre line: median **5 px** wide on the fixture, against an ink width of 9–13 px; 53 of 290 final alefs had a
box narrower than half their ink.

## The change (one; `patch.py`, as a diff to src: `penpath.patch`)

`penpath.unroll`: the path now **ends where the last letter meets the baseline**. New helper `stem_foot`: if, from
its left end, the path climbs down a tall (≥ 0.6 × the line's rise), nearly vertical stroke to the row the rest of
the path runs along, the path is cut there; the stem then hangs from its foot like any other tall stroke (as a lam's
or kaf's already does). Nothing else changed: cells are still each letter's stretch of the path, so neighbours still
tile the piece without overlap and a drag still passes every letter in order.

What the highlight looks like now: the alef's band covers its whole stem plus the start of the joining stroke
(median 13 px on the fixture; 4 of 290 still narrower than half the ink), and the letter before it no longer
reaches into the stem. On the fixture the rule fired on 276 pieces ending in ا/أ and 18 others (ى ر ن د ي ل …, a
tail tip climbing down); 220 more pieces moved a cut because the document's atlas (pictures of letters learned from
its own cuts) now sees the letters before an alef without half a stem.

## Method

- `build.py orig|new DOC…`: builds a document exactly as `inkscript native … --vector --verify` (calls `cli.main`
  in this process), with the patch applied to the imported `penpath` for `new`; keeps the sample pages' plans. src/
  was not edited. The unpatched rebuild reproduced 18's cutter boxes to the pixel on 0582 and 1036 and on 109 of
  110 words with 0618 (one 0618 word, المرجع, sits 10–18 px off in 18's PDF; kept as 18 had it). (The unpatched
  0772 build was stopped to free CPU; not needed.)
- `boxes.py`: the patched PDFs read back as 18 did (`collect.pdf_words`), matched to 18's sample words: 230/230.
- `judge21.py`: 18's judge (Gemini 3.8 Flash, same crop, the graded and the blind question, right = both). A box
  that did not move has the same crop, so it keeps 18's verdict (18's cache copied into `out/judge_cache.jsonl`). The
  221 moved boxes were asked shuffled together with **120 of 18's boxes asked again** (cutter and equal) as a
  control. `analyze21.py` → `out/summary21.json` (95% intervals: bootstrap over words; the paired difference
  bootstrapped too). `make_report21.py` → `out/report.html`. `look18.py`, `look21.py`, `cells.py`: the contact
  sheets and piece drawings used to find the cause.

## Result (2026-10-06, rule "both")

| sample | | before | after | equal slices | after − before, letters |
|---|---|---|---|---|---|
| A · 130 unseen words | letters | 70.2% (65.6–74.6) | **76.7%** (72.7–80.5) | 53.9% | +3.5 to +9.5 |
| | words | 36.9% (28.5–45.4) | **43.8%** (35.4–52.3) | 24.6% | 13 vs 4 words |
| B · 50 unseen, feeler misread | letters | 66.9% (59.8–73.9) | 68.9% (61.5–76.2) | 46.3% | −0.4 to +4.9 |
| | words | 26% (14–38) | 32% (20–44) | 12% | 3 vs 0 |
| C · 50 fixture words | letters | 56.2% (49.5–63.0) | **62.2%** (54.6–69.6) | 58.2% | +1.4 to +11.4 |
| | words | 16% (8–26) | **26%** (14–38) | 26% | 5 vs 0 |

- Joined final alef (ا/أ after a joined letter), all samples: right **4 → 39 of 54** (equal slices 26). The 6 still
  "wrong" on the fixture look right by eye (`out/look21_cutter_new_bad_alef.png`): all graded EXACT, failing only the blind question.
- Wrong boxes, all samples: 329 → **278** of 981 (equal slices 463).
- By book (A): 0618 59 → **68%** (equal 61), 1036 62 → **68%** (57), 0772 75 → 81% (52). The cutter now beats
  equal slicing in every book, and on the fixture is level-to-ahead (62 vs 58%, intervals overlapping) instead of
  behind.
- Judge noise (control): 92 of 120 boxes asked twice got the same verdict; 14 flipped each way. Unbiased, but noisy
  box by box: trust the paired counts and intervals, not single verdicts.

**Nothing that worked broke** (patched builds): fixture words intact 1,246/1,246, lines in order 113/113, letter
coverage 1,062/1,104 (96.2%) — all identical to the unpatched build. 1036 2,677/2,677, 238/238, coverage
2,618/2,645 (same); 0618 3,929/3,929, 363/363, coverage 3,381 → 3,384/3,420; 0772 6,321/6,324, 497/509 (same), order
inversions 4 → 3, coverage 4,151 → 4,149/4,318.

**Spend: $0.94** (cap $10): 221 moved boxes + 120 control, both questions, Flash. Log: `out/spend.jsonl`.

## What is left (looked at, not fixed)

- م and ل are now the most-missed letters. On 0618/0772 most misses are naskh's stacked joins (م sitting on top of
  the next letter in لمـ، مح، من): one stretch of the baseline cannot hold two letters stacked vertically. A
  baseline-cell rule cannot fix that; it would need highlight boxes that are not full-height columns.
- Many remaining "wrong" fixture boxes look right by eye and fail only the blind question (e.g. the ا of ال), the
  judge's known weakness from 18.

## What it means

- The alef sliver was one bug in where the pen path ends, not a problem with cells: fixing it moved the cutter from
  70 to 77% of letters on unseen pages and from below to above equal slicing on the fixture, with no cost to the
  text or coverage. Recommended for src: `git apply experiments/21_better_boxes/penpath.patch` (when no set run is
  going), then rebuild.
- The feeler (75% in 18) turns its cuts into boxes on the same path, so it would probably gain the same way (not measured).

Not done (rule of this task): `docs/`, `src/` and `experiments/README.md` not edited. Suggested index line:
`| 21 | Better letter boxes | the pen path ended at the top of a final alef: ending it at the stem's foot takes the cutter from 70→77% letters right on unseen pages, 56→62% on 0582 (equal slices 54/58); joined alefs 4→39 of 54; text checks and coverage unchanged | milestone 2 |`

```
../../.venv/bin/python build.py orig 0582 1036 0618 0772     # and: build.py new …   (≈3 min the fixture, ≈1 h 0772)
../../.venv/bin/python boxes.py new && ../../.venv/bin/python judge21.py && ../../.venv/bin/python analyze21.py
../../.venv/bin/python fixture_stats.py && ../../.venv/bin/python make_report21.py
```

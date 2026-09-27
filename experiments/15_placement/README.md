# 15 · Milestone 2: do the letter boxes sit on the right letters?

**Question.** Letter coverage says 97.8% of words have a box for every letter.
It says nothing about whether the boxes sit *right* — STATUS has carried "by eye
about 85–90%" since 2026-09-20, which is not a measurement. And the proxy
attempt ([09_pen_path/vs_equal.py](../09_pen_path/vs_equal.py)) tied with equal
slicing overall, winning only where letter widths differ. That is the test D7
demands, and it could not settle it.

So ask a reader, and ask the question that matters: **is the pen path better
than the free baseline?**

**Method, second attempt — the real PDFs.** The first sheet (`make_sheet.py`)
drew the cells as tinted bands on an upscaled crop. The owner's objection, which
was right: *a picture of a selection is a worse instrument than the selection*.
Blurred by upscaling and washed out by the tint, it is harder to see where a
letter starts than in the document itself.

So `build_baseline.py` rebuilds the document with `native.LETTERS = False` —
every word one glyph again, which is precisely D7's baseline, since the viewer
then slices the word evenly by itself. No simulation. `ab.py` puts that PDF
beside the letter-cut one in the browser's own viewer, as **A** and **B** by a
coin flip (recorded in `mapping.json`, not on screen), with a word list that
sends both panes to the same word at the same zoom. Drag across the word in
each, see the real highlight, judge.

`make_sheet.py` is kept: it is quicker to scan, it labels each band with the
letter it claims, and it is useful for finding badly cut words. It is not the
instrument for the verdict.

**Method (the first sheet).** Each row is the same word twice, with every letter's selection cell
tinted band by band — what a drag-select would cover. One is cut along the pen
path, one into equal parts. Which is which is a coin flip per word and is never
shown; the identity lives only in the exported file. One keypress a word: left
better, right better, the same, both wrong.

```
python make_sheet.py <built_dir> <stem> [--page N] [--limit 120]
python tally.py out/*_placement.json
```

Blind, because the judgement is subtle and knowing which is "ours" would decide
it. Paired, because both cuts are of the same ink on the same word, so the
comparison is not confounded by which words are easy.

`tally.py` reports the split and a sign test. The bar is **50%**, not 0% —
equal slicing is free, and D7 retired a cutter for merely matching it.
**both wrong** is counted apart: it is the share of words where letter selection
does not work at all whichever method cut them, which is the honest ceiling on
what letter-level highlighting delivers today.

## Result

**Abandoned unjudged, 2026-09-27.** Two instruments were built and neither was
good enough to spend a reader's time on.

1. `make_sheet.py` draws each letter's cell as a tinted band on an upscaled
   crop. The owner's objection: a picture of a selection is a worse instrument
   than the selection. Correct — upscaling blurs the ink and the tint flattens
   the contrast, so the edge of a band is harder to place than in the document.
2. `ab.py` puts the two real PDFs side by side and drives both to the same word.
   The jump needed a cache-busting query before Chrome's viewer would honour
   `#page`/`#zoom` at all, and even then the target word is not marked;
   `#search=` was added to highlight it and did not work either.

**So milestone 2 is still unmeasured, and STATUS still carries "by eye about
85–90%" as a guess.** That is the honest position.

What is worth keeping from the attempt:

- `build_baseline.py` — the baseline as a *real* PDF (`native.LETTERS = False`,
  every word one glyph, the viewer slices it itself). Whatever instrument comes
  next should compare against this rather than simulate equal slicing.
- `make_sheet.py` is still useful for *finding* bad cuts, because it labels each
  band with the letter it claims. It found `ونيودلهى`, where the `ن` takes 39.8%
  of the word and the final `ى` 2.2% — a real failure of the kind D8's second
  path start was meant to catch.

If this is picked up again, the thing to fix is not the rendering but the
**driving**: a viewer whose selection can be controlled and read back
(pdf.js with its own API, rather than Chrome's plugin behind an iframe).

## What it decides

Whether the pen path — the single largest piece of work in this repo — earns its
place by the repo's own rule. A result near 50% says it does not, and that the
letter cutter should be judged on what it uniquely does (a kaf keeping the arm
it throws over its neighbour) rather than on average accuracy. A clear win says
the proxy measurement was the wrong instrument, not the method.

Either answer is worth having, and only a reader can give it.

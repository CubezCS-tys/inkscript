# Letters: how a joined word becomes one glyph per letter

Arabic joins its letters, so the ink of a word is a few connected blobs, not
letters. A website never has this problem — it places one glyph per letter and
knows every box because it put it there. We go the other way: from finished
ink back to the boxes. This page is the narrative; the rules and their
measurements are in [pdf-writing-rules.md](pdf-writing-rules.md) → "Letters";
the code is `src/inkscript/geometry/penpath.py` (cutting) and
`geometry/layout.py` (words → pieces).

## 1. Word → pieces (`layout.split_word`)

A word's text is split where the script cannot join (after `ا د ذ ر ز و`…):
`المعجم` → `ا` + `لمعجم`. Its ink is grouped into blobs with their dots. If
blobs and text pieces pair off one to one, each piece gets its blob. If not —
two runs touch in the ink, a letter's ink is broken, punctuation is attached —
the two sequences are aligned by width (one-to-one, one-to-many,
many-to-one), and a touching group goes on as one piece.

## 2. Piece → pen path (`penpath.unroll`)

The blob is thinned to a one-pixel centre line. The **trunk** runs from where
the first letter meets the baseline (rightmost ink on or just above the
baseline) to the piece's leftmost point. Everything else — an arm, a tall
stroke, the far side of a loop, a tail sweeping back — belongs to the trunk
point it hangs from. The piece is thereby unrolled into a strip indexed by
distance along the path. Broken ink is bridged *for the path only*.

If a hard fact fails with that start (next section), the path is tried again
from the first letter's body above the baseline, and the start the facts
prefer is kept: some faces print `في` with the ya's flat tail running back to
the right along the baseline, and the tail's tip is then the rightmost ink.

## 3. Where to cut (`penpath.best_cuts`, `solve`)

Candidate cut points are the thin places along the path. Which of them to use
is decided by two witnesses:

- **Hard facts** (`_facts`): a letter's dots, hamza, tall stroke and bowl lie
  in its own stretch; no letter is a bare connecting stroke. A fact is only
  enforced for a letter-form if 85% of its occurrences in this document show it.
- **The document's atlas** (`build_atlas`): the mean picture of every
  letter-form — (letter, initial/medial/final) — built from the cut letters
  themselves. Cuts are re-chosen so each letter looks like its picture; the
  pictures are rebuilt; four damped rounds. Learned from the document's first
  1,500 pieces, then applied to the rest (`apply`).

No typeface is ever configured. Each document teaches its own alphabet.

## 4. Letter → glyph (`penpath.letter_blobs`, `pdf/type3.py`)

A letter's **ink** is everything hanging from its stretch of the path, with
its marks; its **cell** is its stretch of the baseline. The glyph's origin and
advance come from the cell, so Chrome highlights the cell; the ink may
overhang (a kaf's arm), as in a typeset font. Where the path doubles back the
cells share the piece's width in proportion to the path. Neighbouring letters
overlap by one pixel at the seam so that no ink is lost; cut and uncut pages
differ only in edge shading (1.2% of ink pixels slightly, 0.03% by more than
half tone).

Every piece that gets cuts is cut (`native.CUT_ALL`); the witnesses' verdict
goes in the build report as `letters_why`.

## Measuring and debugging

| Question | Tool |
|---|---|
| What share of words has a box for every letter? | `experiments/09_pen_path/coverage.py <vector.pdf>` (add `--list` for the missed words) |
| The same over a built set, with text checks and doubt reasons | `experiments/09_pen_path/summary.py <out>/w*` |
| Why is *this* word not cut? | `experiments/09_pen_path/why_word.py <azure.json> <scan.pdf> <page> <word,word>` |
| Why do pieces of this document get no letters, ranked? | `experiments/09_pen_path/nopath.py <azure.json> <scan.pdf> <pages>` |
| Are the cuts any good? (coloured sheets of accepted / doubted pieces) | `experiments/09_pen_path/diagnose.py <azure.json> <scan.pdf>` |
| Is a letter-form cut systematically wrong in this book? | build its font, look at the glyph: `experiments/11_typeface/peek.py`, `peek_pieces.py` |

The honest gaps: coverage counts boxes, not whether they sit right
(milestone 2); vowelled words are never cut; underlined words cut badly.

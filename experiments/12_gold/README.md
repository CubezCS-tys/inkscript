# 12 · The gold set: is the reading right, and what kind of wrong is it?

**Question.** The PDFs carry Azure's reading. "99.99% of words intact" says we
preserved it, not that it is right — and nothing in the repo measures whether
it *is* right. Two milestones wait on that number:
[roadmap.md](../../docs/roadmap.md) item 1 (a checker built from the book's own
letters) and the baseline rule that any checker must beat *changing nothing*.

So: over a page of every face type, **is each word's reading right, and when it
is not, what class of error is it?**

The class is the part that decides what gets built. A checker can only test a
hypothesis it can pose — `ه` against `ة`, one dot against two. If most of the
errors are look-alike substitutions, milestone 1 is the right build. If most
are dropped, merged or invented words, a checker cannot see them at all and the
right build is a coverage test instead: every word's ink accounted for, every
piece of ink claimed by a word.

**Method.** `mark.py` makes one self-contained page per document page: every
word of that page as its own ink beside the reading the PDF carries, in reading
order, a class to pick and a field for what the ink really says. Every row
starts at *correct*, so only the wrong ones cost a click. The readings and
boxes come from `<stem>.shapes.json` (what the PDF actually carries, page-1
Gemini text included), the ink from the scan rendered exactly as the build saw
it. `tally.py` turns the marked pages into the taxonomy.

```
python mark.py <stem> --page 3 [--built DIR] [--azure DIR]     # one page to mark
python tally.py out/*.gold.json                                # the numbers
```

It prints a command to serve the page over http: Chrome gives a `file://` page
an opaque origin and may refuse it localStorage, which is what keeps a
half-finished page of marks.

Nothing here writes to a built set, so it is safe to run while a set builds.

## Most "contradictions" are not reading errors (2026-09-22)

The owner opened the candidate sheet and asked why a row showed the ink `على`
beside the reading `وعلى`. The reading was right; the *crop* was wrong — and the
reason matters for the whole pool.

A contradiction is "same ink, different text", where the ink is a word's blob
signature. A word whose leading run was never attached to it has a signature of
only part of itself, and then two genuinely different words match on a fragment:
`وعلى` "conflicts" with `على` because only the `على` blob was signed. Counting
suspects whose text has more runs than the signature has blobs:

| kind | suspects | signature covers only part of the word |
|---|---|---|
| extension | 1,428 | **872 (61%)** |
| substitution | 649 | 86 (13%) |
| marks-or-punctuation | 8 | 0 |

So the 1,399 contradictions are not 1,399 errors. `extension` conflicts are
mostly an artefact of incomplete blob attachment; `substitution` conflicts are
the trustworthy pool. `candidates.py` now defaults to `--kinds substitution`,
drops any suspect whose signature covers only part of its word, and crops the
whole **Azure word box** rather than the box the signature matched. The pool
drops from 1,833 rows to 330, and every row is a word beside a rival reading of
the same word.

*(That incomplete attachment is itself worth a look — a word whose ink is only
partly assigned is a layout bug, not a reading one. Noted, not chased.)*

## Some conflicts are BOXING errors, not reading errors (2026-09-27)

The owner queried a row showing a single stroke beside the reading `١٩`. The
reading is right; **Azure's own word box for `١٩` is 14 px wide and 85 px tall**
— it covers the `١` only. The conflict pool surfaces boxing faults dressed as
reading faults, and the sheet had no way to say so.

Two changes. A suspect whose box cannot hold its reading is dropped, using the
repo's own plausibility rule (`pdf-writing-rules.md`, "Pieces": 0.12–1.4 line
heights per letter; that box is 0.08). And a class, **`ink isn't this word`**,
for the ones that get through — the reading is fine, the box is not. `tally.py`
counts it apart from reading errors, because it is not one.

Only 2 of 120 rows were dropped by the width rule, so the pool is intact; but
the class matters, because without it a boxing fault gets marked "wrong word"
and quietly inflates the error taxonomy that decides milestone 1.

## The classes

`correct` · `dots` (ب ت ث ن ي, ج ح خ) · `hamza` (أ ا إ) · `ة/ه` · `ى/ي` ·
`other look-alike` · `wrong word` · `merged` · `split` · `invented` ·
**`the book's style`** · `unsure`.

`the book's style` is the one that is not an error. Many printings of this
corpus never dot a final ya and never write the hamza on an initial alef. A
checker that "corrects" those is not fixing thousands of errors, it is quietly
rewriting a 1950s journal into modern orthography. So the class is marked
separately, and the rule it implies is the same one the atlas already follows:
**the document is the witness** — flag a departure from *the book's own
practice*, never from standard Arabic.

Words with ink but no reading cannot appear as a row (nothing read them), so
the page opens with the whole scan, every reading boxed in red: unboxed ink is
a dropped word, counted by hand into one field.

## Result

**Two pages marked (2026-09-21), 427 words, 5 doubtful.**

| page | reader | face | result |
|---|---|---|---|
| `0005-032-001-001` p2 (body) | Azure | heavy, clean | 277 / 277 right |
| `1110-000-001-001` p1 (front page) | **Gemini** | the set's weakest document | 146 / 150 — one dot error, three the eye could not settle |
| `1110-000-001-001` p1, the same ink | **Azure** (the reading Gemini replaces) | the same page | **149 / 150** — one doubtful word |

The same page was then scored against **Azure's own reading**, which the build
replaces with Gemini's on page 1 (`--reader azure`: no API call, the text is in
the JSON). Same ink, same boxes, only the reader changed — and Azure won,
149/150 against 146/150. All three of Gemini's extra problems are in body text;
the title and author words are identical and correct in both. D1 was kept
unchanged all the same ([decisions.md](../../docs/decisions.md), D16): the
evidence is one page, and an editorial front page is not the cover D1 was made
for. The test that would settle it is a **real cover** scored both ways —
`0670-006-001-003` (13 words on page 1), `1075-001-001-001` (13),
`0565-000-002-001` (17).

`بما` was the one word marked doubtful in *both* passes, forty minutes apart and
at different indices: ambiguous ink rather than reader error, and a sign the
marking itself is reproducible.

**Azure on a difficult face is still unmeasured** — both weak-document pages so
far are front pages. A body page of a weak document is the open one
(`0845-000-001-001` p2, `0920-004-009-001` p2, both generated).

Three of the five doubtful words were marked *unsure*: the ink itself does not
settle them. A checker scoring geometry will not settle them either, so the
error pool a checker could actually address is smaller than the error rate
looks — on these two pages, one word in 427.

**The first page killed the method (2026-09-21).** `0005-032-001-001` p2, a
heavy 1950s face, hand-marked in full: **277 words, 0 errors, 1 unsure** —
Azure's reading was right on every word. At an error rate that low, collecting
the 30–50 errors a taxonomy needs would take ten to fifteen thousand
hand-marked words. Marking pages in order cannot answer the question.

So the question splits in two, and only one half needs an unbiased sample:

* **How often is the reading wrong?** Needs whole pages, and one page of a
  clean face already says: rarely. The number that matters now is whether the
  *difficult* faces are as good — one page of the worst document in the set
  (`1110-000-001-001`, 78% letter coverage) answers it, and `--sample 150`
  makes that 150 words instead of 462.
* **When it IS wrong, what kind of wrong?** Needs errors, not words, and does
  not care how they were found. `candidates.py` draws them from the pools the
  repo already has: 1,399 contradictions (same ink read two ways, so one
  reading is certainly wrong) and 50,007 numbers. Biased pools — a
  contradiction needs the same ink twice, which favours look-alikes — so the
  look-alike share they report is an over-estimate, and the result is a bound,
  not a rate.

## What it changes

Decides the shape of milestone 1 before any of it is written, and gives
milestone 2 (placement) and any future checker the ground truth they are
currently missing. The acceptance criterion it implies is precision-first: a
false correction corrupts the archive, a missed one merely leaves it as it was.

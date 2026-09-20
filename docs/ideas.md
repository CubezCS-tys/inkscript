# Ideas

Every idea that has come up, whoever had it, with what became of it and where
to pick it up. Newest thinking first inside each group. Add to this file the
moment an idea is voiced — not when it is built.

Status words: **built** (in the package), **experiment** (measured, not in the
build), **parked** (agreed worth doing, not started), **dropped** (tried; the
reason is recorded), **open** (voiced, not yet judged).

## Trusting the text (the biggest gap)

- **A second opinion on Azure from the book's own letters — as a checker, not
  a reader.** *parked, milestone 1.* Cut a word by its known reading (we do
  that well), then ask whether the ink fits a look-alike reading better:
  one dot or two, `ة`/`ه`, `ى`/`ي`, `أ`/`ا`. Feeds the review-and-correct
  loop. Pick up from `experiments/10_atlas_reader/` (it has the per-letter
  scoring against stored examples) and `verify/second.py`.
- **Reading blind with the atlas** (owner, 2026-09-20: "trace the letters,
  record the history of the strokes and match against our database of letter
  strokes"). *experiment 10.* A held-out page read with no text: 41% of pieces
  agree with Azure; isolated letters 67%; joined pieces ~20% (you must cut
  before you can match and match before you can cut; tooth letters). Matching
  individual stored examples beat mean pictures by far (27% → 41%) — the
  "database" instinct was right. Not a replacement for Azure/Gemini; see the
  checker above.
- **Gemini labels the alphabet's glyphs instead of reading whole pages**
  (owner, 2026-09-19). *open.* Would give labels per shape, but does not solve
  where one letter ends (a geometry problem). Could label the restored
  typeface's glyphs cheaply as a cross-check.
- **Gemini re-reads only what is doubtful.** *built:* numbers
  (`inkscript numbers`) and contradictions — same ink, different text
  (`inkscript check`, `inkscript second`); two readings against one become a
  proposed correction. Corrections are written into a finished PDF by
  `inkscript correct`.
- **Geometry as a better medium for LLMs** (owner's founding idea). *open.*
  Give a model the outlines/alphabet ids rather than pixels. Untested.

## Letters

- **Follow the pen** (owner, 2026-09-19/20: "a human can do OCR with their
  eyes closed… feel the strokes"). *built* — `geometry/penpath.py`,
  [letters.md](letters.md). 96.8% letter coverage at scale.
- **An atlas of pen paths rather than pictures.** *open.* Store each
  letter-form's typical centre line and match line against line; would
  tolerate stretching and slant where pictures do not. The data exists (every
  cut letter has its stretch of path).
- **Stroke-order animations as a reference** (owner offered to find some).
  *open.* Not needed so far: a loop lies inside one letter, so which way round
  it was drawn does not change the cut.
- **Cut at the join point, not a column.** *built* — it is what the pen path
  does; the vertical-column cutter (`geometry/letters.py`) is kept for its
  shared pieces. Columns were no better than Chrome's equal slices.
- **Vowelled words.** *parked.* Never cut, because pdfium reorders the pieces
  of a split vowelled word. Up to 6% of some documents. Needs an experiment on
  how to store marks with letter glyphs.
- **Underlines.** *parked.* Remove the rule from the ink before cutting; the
  rule-separation in `geometry/trace.py` only catches long rules.
- **Measure placement, not just coverage.** *parked, milestone 2.* A
  hand-checked sheet of a few hundred pieces, then every change measured
  against it and against equal slicing.
- **The owner's hand-marked line** (word → letters selectable yes/no).
  *method, keep using.* One line found four bugs.

## The typeface and restoration

- **Type with a book's font** (owner, 2026-09-20). *experiment 11* —
  `experiments/11_typeface/make_font.py` builds an installable TTF with
  joining forms and lam-alef; [typeface.md](typeface.md).
- **Restore the letters from many printings** (owner: "enhancing the font to
  make up for the broken pieces"). *experiment 11.* Body voted from up to 15
  best printings, marks from the best one, joins on the document's band.
- **A restored edition of the page.** *parked.* Third output beside the
  faithful PDFs: same layout, damaged letters (low atlas score, bridged ink)
  redrawn from the restored font. Never replaces the faithful PDF.
- **The font as a debugger.** *method.* A wrong glyph means a systematic wrong
  cut in that book (found the swapped `في` and the unsplit alefs).
- Open font work: final `و` of 0565; forms a short document never prints
  (borrowed from relatives — could borrow from a *similar book's* font);
  digits and punctuation; mark positioning (GPOS); kerning of `فى`.
- **Sharp display atlas.** *parked.* The atlas at full resolution, examples
  aligned before the median — the readable form of "the document's alphabet".

## The PDF and other viewers

- **Shared alphabet across occurrences** (2026-09-17). *dropped for drawing,
  kept as knowledge.* Drawing one occurrence with another's ink costs a median
  15% of its pixels, six times the tracing error; so the alphabet labels the
  ink (`/InkShapes`, `<stem>.shapes.json`) and never replaces an outline.
- **"What if I don't care about size?"** (owner). Scale-normalised matching:
  the alphabet saturates within a document and resets between type weights —
  different weights are different alphabets (`experiments/03`).
- **Firefox / pdf.js.** *decided: 8 pt stays.* A larger nominal size fixes half
  the lines there and costs pdfium 0.1% (`experiments/06`).
- **Junk-encoded typeset fonts → rebuild their ToUnicode from Azure**
  (`pdf/fontfix.py`). *built, switched off* until coverage ≥ 99.5%; meanwhile
  such text is neutralised with `/ActualText`.
- **Tables.** *parked.* Cells that pdfium joins across rows.
- Apple Preview: untested.

## Showing the work

- **Animation for the owner's father** ("the liquid thing, then the
  geometry"). *built* — `docs/demo/ink_to_text.html`.
- **Interactive storyboard as documentation** (owner, 2026-09-18; "a lot more
  visual so me and others can really understand", 2026-09-20). *built* —
  `docs/storyboard/` (`build.py` + `letters_data.py` + `template.html`,
  `rebuild.sh`). Fifteen chapters, every picture from real outputs: the idea,
  a real page, **follow the pen** (eight-step stepper on seven real words),
  **the atlas** sharpening round by round, **the swapped في**, how Chrome
  reads, the rules, **every document as a dot** (two runs), **type live in
  two books' fonts**, reading blind, what it does not do. Still open: a
  walk-through of one whole page being built, a restored-edition panel once it
  exists, and phone-width polish.

## Scale

- **Run the corpus.** *in progress.* 227 journals done twice; next a rerun
  with the post-run fixes and a per-document before/after of the boxes; then
  the 451 sample; the corpus is ~100,000 documents. See
  [operations.md](operations.md) for memory and resuming.
- **Speed.** About 7.6 s a page single-threaded, most of it the letter
  cutter's Python loops. Untouched: vectorising `best_cuts`, caching page
  geometry between the two passes.

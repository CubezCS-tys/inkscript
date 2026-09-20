# Roadmap

**This file has one live list — the next section.** Numbers and gaps are in
[STATUS.md](STATUS.md); every idea and its fate in [ideas.md](ideas.md).
Everything under "History" is kept for the record and is done or superseded.

## The live list (owner's order, 2026-09-20)

1. **Make the text trustworthy.** The PDFs carry Azure's reading; "words
   intact" means we preserved it, not that it is right. A second opinion
   from the book's own letters: not reading blind (experiment 10: 41% of
   pieces, the cut-before-read problem) but CHECKING — cut by the known
   word, then ask whether the ink fits a look-alike reading better (dot
   counts, small marks, `ة`/`ه`). Feed the review-and-correct loop.
2. **A measure of highlight placement**, from a hand-checked sample: 96%
   of words have a box per letter, but how many boxes sit right is not
   measured.
3. **The typeface export** (experiment 11), and a sharp display atlas.
4. Known gaps: vowelled words never cut; underlined words; fine slanted
   faces; tables; Firefox word order; corrections shorter than the glyph
   count.
5. **Rerun the 227 journals with the fixes made after the run** (swapped
   `في`, thin alefs, hamza, dots under a swept-back tail) and compare every
   document's letter boxes before and after:
   `experiments/09_pen_path/compare_boxes.py OLD_DIR NEW_DIR`. Cheap, runs in
   the background ([operations.md](operations.md)). Then the 451 sample.
6. **Typeface polish, then a restored edition** ([typeface.md](typeface.md)).

## Standing rules

- Every glyph is the printed occurrence's own outline, stored in scan
  pixels. No substitution, no simplification.
- No rule about the text layer is adopted on reasoning alone; each is
  measured against pdfium, MuPDF and poppler and recorded in
  `docs/pdf-writing-rules.md` with the number that justified it.
- The word stays one glyph whenever splitting would require a guess.

## History

### The list of 2026-09-18 (items 2, 3, 4 and 6 done or started since; 1 and 5 carried into the live list or decided)


1. **Corpus sample at real scale.** 500–1,000 documents drawn evenly
   across journals, built and checked unattended; read the per-page
   report for anything under 97% or with inversions. Every failure mode
   so far was found this way, not by reasoning. Cost: ~$0.005 per document
   for Gemini page 1.
2. **Make the review list useful.** Done 2026-09-18: `check --html` shows
   each reading editable beside its ink and exports the changes;
   `inkscript correct` writes them into the PDF's ToUnicode without a
   rebuild (`pdf/correct.py`, `pdf/inspect.py`).
3. **Second reading for numbers and contradictions only.** Send just those
   crops to Gemini (a few per page) and accept a correction only when the
   two readings agree. Cheap, and it targets the errors that matter.
4. **Letter-level selection inside a connected run.** *(Pieces, not words: a different count from the letter coverage in STATUS.md.)* In the build
   along the pen path (2026-09-20, `geometry/penpath.py`, the user's
   idea of following the strokes): cuts are points on the ink's centre
   line, chosen by hard facts plus the document's own letter atlas; 69%
   of multi-letter pieces on the fixture, 2,132 letter glyphs, Chrome
   unchanged. Next: the fine slanted face of `0690…` (big kaf pieces
   still start on the arm; 230 of 532 pieces get no path), a sharp
   display atlas (the seed of the typeface), then rebuild the sets.
5. **Other viewers.** Firefox (pdf.js) measured (`experiments/06`): words
   come back intact (95%) but lines copy out word-reversed at the 8 pt
   nominal size, because pdf.js splits a line into items at any pen jump
   over 0.6 × size and keeps items in stream order; a 16–24 pt nominal
   size fixes about half the lines with no effect on Chrome. Decide
   whether to adopt it after the other half is understood. Apple Preview
   untested.
6. **The typeface.** Export the document alphabet as an installable font
   (OpenType via fontTools) once letter-level pieces exist; until then the
   SVG specimen is the honest form.

### Todo (2026-09-18, morning)

Parked by the user to carry on with the roadmap; pick up in this order.

- [x] Went through the weakest pages of the 227-journal sample. Found
      and fixed: the line-order reference (Azure's word order is wrong on
      verse and tables — now by position; number-only lines not judged);
      pdfium dropping a whole run as a fake-bold duplicate when a nearby
      run had the same codes (`0005`); a kerned pair losing its space
      (`0385`); Latin-majority lines needing the left-to-right storage;
      the ornate ﴾﴿ wrongly mirrored; typeset pages with junk-encoded
      fonts (`0470`, inversions come from that text, left out of the
      check). Remaining: table cells pdfium joins across rows, math
      tokens (`i=1,2,K,N)xi`).
- [x] Firefox: the other half is tight word gaps (merged) and words
      written as pieces (split into items); every larger nominal size
      costs pdfium 0.1%. Decision: 8 pt stays (`experiments/06`).
- [x] Refused cover pages: the top half is tried, then a title-and-author
      extraction (5 of 6 read); and the real cause on most — Gemini was
      handed a thumbnail instead of the scan (10 of 227 documents) — fixed
      by rendering pages whose single image is under 150 dpi.
- [x] Comparison against ocrmypdf (Tesseract) and Azure's own searchable
      PDF on three documents (`experiments/07`): lines in reading order
      in Chrome 98–100% vs 34–75% (Azure) vs 2–16% (ocrmypdf). ABBYY not
      available here.
- [x] Interactive storyboard (`docs/storyboard/`, built from real outputs;
      published as an artifact 2026-09-18). Rebuild it after each
      corpus run so its numbers stay true.
- [x] Typeset PDFs with junk-encoded fonts: their text objects are now
      neutralised with an `/ActualText` span (our layer is the only text;
      `0470` 40 → 1 inversions, `1370` 43 → 23). `pdf/fontfix.py` also
      rebuilds such fonts' ToUnicode from Azure's words (93–98% of glyphs
      on `0470`), but at that coverage the fixed fonts read back worse
      than our layer, so the switch to them waits for ≥99.5% coverage
      (ligature-aware alignment would get there).
- [x] Push the repo when the user asks (pushed 2026-09-18 to github.com/CubezCS-tys/inkscript; pushed after every milestone since).

# Decisions

Choices between alternatives, with the evidence. Newest last. If you are about
to undo one of these, the reason it was made is here; if the evidence has
changed, add a new entry rather than editing the old one.

**D1 · Gemini reads page 1 only; Azure reads the rest (2026-09-14).** The team
wanted Gemini only for the front page: title and author are what Azure gets
wrong and what Gemini gets right. Gemini's text is fitted into Azure's boxes
with order-tolerant matching (`ocr/align.py`). Covers refused by Gemini
(`RECITATION`) fall back to the top half, then to a title-and-author prompt.

**D2 · The glyph is the word's own ink, as a Type 3 font in scan pixels
(2026-09-17).** Glyph space is pixels at 300 dpi (FontMatrix does the
scaling), so outlines are stored unchanged; decimal 1/1000 units cost 19% more
bytes for nothing. Invisible over the scan (`.pdf`), visible alone
(`_vector.pdf`).

**D3 · Never draw one occurrence with another's ink (2026-09-17).** Measured:
a median 15% of pixels differ, six times the tracing error. The shape alphabet
is kept as knowledge (`/InkShapes`, `shapes.json`), not as a drawing shortcut.

**D4 · Chrome's engine is the verification target (2026-09-17/18).** MuPDF and
poppler are measured too but disagree with it on vowelled text. Chrome's line
reconstruction was read from pdfium's source and emulated
(`text.chrome_reads`); stored text is its exact inverse (`text.visual`).

**D5 · pypdfium2 pinned to 5.12.1 (2026-09-18).** 5.13 bundles pdfium 7999,
which had automatic line direction off; verifying against it produced a day of
wrong rules. The "words intact" metric ignores order, so "lines in order" and
"inversions" were added at the same time.

**D6 · 8 pt nominal size stays (2026-09-18).** Larger sizes help pdf.js
(Firefox) on half its lines and cost pdfium 0.1% of words. Chrome wins.

**D7 · Letters: cut only on real joins; then cut along the pen path
(2026-09-19/20).** A free column alignment put 90.9% of cuts within a stroke of
the join; Chrome's equal slices of an uncut glyph: 91.6%. So an unconstrained
cut bought nothing. Cuts were restricted to thin joins (D7a), then replaced by
points on the ink's centre line (D7b), which also handles a kaf whose arm
overhangs its neighbour. Every selection method is compared with equal slicing.

**D8 · Two witnesses choose the cuts: hard facts and the document's own atlas
(2026-09-20).** The atlas alone let big letters swallow small neighbours; the
facts alone leave plain letters undecided. Pictures are compared softened
(2 px) or a fine face's atlas is empty. The atlas update is damped (a full swap
flip-flopped). The atlas can confirm its own mistake (395 swapped `في`), so
facts from outside it must be able to overrule: a failed fact triggers a
second path start.

**D9 · Cut every piece that gets cuts; the witnesses' verdict is reported, not
enforced (2026-09-20, `CUT_ALL`).** About two thirds of rejected cuts were
right, and a wrong cut costs what an uncut piece costs (a highlight slightly
off). Coverage on the reference document went 63% → 95% of words. The verdict
counts are in each build report (`letters_why`).

**D10 · A letter's selection box is its stretch of the baseline; its ink may
overhang (2026-09-20).** As in a typeset font. Origin and advance come from
the cell, so Chrome highlights the cell while the kaf keeps its arm.

**D11 · The atlas is learned from a document's first 1,500 pieces; later pieces
are cut against it and reduced to outlines at once (2026-09-20).** Whole-canvas
pictures for every candidate cut reached 5.7 GB in one process and froze the
machine. Peak is now ~0.85 GB (5 pages) to ~1.6 GB (81 pages).

**D12 · Blobs and text pieces are aligned by width when they do not pair off
(2026-09-20).** Touching runs, broken letters, attached punctuation. The exact
count match keeps its old behaviour; the alignment only runs on a mismatch.
Alef counts as a narrow letter, or a light face's alefs pull in their
neighbours' blobs.

**D13 · Corrections are dealt out over a word's glyphs; a shorter correction
is declined (2026-09-20).** A word is now several glyphs. A glyph cannot be
given no text: pdfium reads an empty ToUnicode entry back as the char code.

**D14 · Restoration never touches the faithful PDF (2026-09-20).** The owner
wants the vector PDF as "the original font as the text" and absolute accuracy.
Restored letters live in the typeface and, later, a separate restored edition.

**D15 · Outputs live in the repo's `out/` folders, gitignored (2026-09-20).**
The owner's Desktop had filled up; and relative paths were hard to find, so
paths given to the owner are absolute.

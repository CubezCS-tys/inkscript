# Glossary

**Azure word / box** — one word of Azure Document Intelligence's reading with
its polygon on the page. The unit everything is matched to.

**Blob** — one connected component of ink, traced as outline polygons with
holes (`geometry/trace.py`). Dots and hamzas are their own blobs.

**Rule** — a long straight line (table border, underline) separated from the
ink before blobs are formed; never glyph ink.

**Run** — a stretch of letters the script joins: `المعجم` is two runs, `ا` and
`لمعجم`, because alef never joins the letter after it.

**Piece** — the ink of one run (or of several runs that touch in the ink),
with its text. The unit the letter cutter works on. One glyph unless it is cut.

**Letter-form** — a letter in one of its four shapes: isolated, initial,
medial, final. The atlas and the font are keyed by (letter, form). Lam-alef
(`لا`) is one unit.

**Pen path / trunk** — the centre line of a piece from its first letter's foot
on the baseline to its left end. Everything else hangs from a trunk point.
**Strip** — the piece unrolled along the trunk; a cut is a position on it.

**Candidate** — a thin place on the path where a cut is allowed.

**Facts** — what must be true of a letter's stretch whatever the typeface:
its dots and hamza, a tall stroke, a bowl below the baseline, not being a bare
connector. **Reliable** — a fact is enforced for a letter-form only if 85% of
its occurrences in this document show it.

**Atlas** — the document's own mean picture of every letter-form, learned from
its cut letters. **Likeness** — overlap of a letter with its atlas picture
(0–1, softened). **Rounds** — cut, rebuild the atlas, cut again.

**Verdict** — why the witnesses doubt a cut (`letters_why` in the build
report). Reported, not enforced (`CUT_ALL`).

**Cell** — a letter's stretch of the baseline in page x: its selection box.
Its **ink** may overhang the cell.

**Letter coverage** — share of Arabic words (2+ letters, no vowel marks) in
which every letter has its own box in pdfium. Says boxes exist, not that they
sit right.

**Equal slicing** — what Chrome does with an uncut glyph: the box divided
evenly among its characters. The baseline every cutter must beat.

**Words intact / lines in order / inversions** — the `--verify` numbers: a
word copies out from pdfium exactly; a line's words come out in reading order;
adjacent lines of a column swapped. Words intact ignores order.

**Stored (visual) form** — text written into ToUnicode so that pdfium's line
reconstruction gives the logical reading back (`text.visual`, inverse of
`text.chrome_reads`).

**Faithful PDF / vector PDF** — `<stem>.pdf`: the scan with invisible ink
glyphs over it. `<stem>_vector.pdf`: the glyphs alone, visible — "the original
font as the text".

**Born-digital page** — a page that already has real text; left alone. **Junk
font** — a typeset font whose encoding gives nonsense; its text is neutralised
with `/ActualText`.

**Shape alphabet** — shapes recurring across a document (`shapes.json`,
`/InkShapes`). Knowledge about the ink; never used to draw.

**Restored glyph / restored edition** — a letter voted from many printings
(exists, in the font); a page redrawn with such letters (an idea).

**Fixture / reference document** — `tests/fixtures/0582-004-009-012`, five
pages of a heavy old face; the document most things were tuned on, so its
numbers flatter.

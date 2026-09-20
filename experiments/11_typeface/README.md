# 11 — A book's letters as a font

**Question.** Can the letters cut from a document become an installable font —
type new Arabic text in a 1950s journal's face — and can many printings of a
letter give a better glyph than any one of them?

**Method and use.** See `docs/typeface.md`. `make_font.py` builds the TTF
(needs `fonttools`), `specimen.py` typesets test sentences through LibreOffice,
`peek.py` and `peek_pieces.py` show the printings behind a letter-form.

**Results.** Two books typeset new sentences with joined letters
(`out/two_books.png`). Restoration: both cell edges aligned, body voted from up
to 15 printings with a few pixels' tolerance, marks from the best printing,
joins on the document's band.

**The surprise.** The font is the best debugger of the letter cutter so far. A
blank initial `ف` in the second book's font was 395 copies of `في` with their
two letters swapped (the ya's tail runs back along the baseline); a bloated
isolated `ا` was words never split at a thin alef. Both were fixed in the
package; neither was visible in the coverage number.

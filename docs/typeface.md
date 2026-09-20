# The typeface: a book's letters as a font you can type with

`experiments/11_typeface/` (not yet part of the package). Needs `fonttools`
in the venv (`.venv/bin/pip install fonttools`).

```
.venv/bin/python experiments/11_typeface/make_font.py <azure.json> <scan.pdf> "Family Name" out.ttf
cp out.ttf ~/.local/share/fonts/ && fc-cache -f          # install for this user; delete the file to uninstall
.venv/bin/python experiments/11_typeface/specimen.py out.png "Family A" "Family B"   # typeset test sentences via LibreOffice
```

## What the font is

For every letter-form the document prints — (letter, isolated / initial /
medial / final), plus lam-alef — one glyph:

1. **Printings.** The letters cut by the pen path ([letters.md](letters.md)),
   ranked by likeness to the document's atlas; only body-size lines and
   usual-width printings (a kashida-stretched one is not the form's usual
   shape). Up to 15 per form.
2. **Restoration.** Each printing is drawn on a common canvas with *both* of
   its cell edges on fixed columns (aligned on one edge only, the other end of
   the connecting stroke smeared and left gaps between typed letters). The
   **body** is the ink at least half the printings agree on — a break in one
   fills in, a blot in one goes — voted with a tolerance of a few pixels, or a
   fine face's strokes never coincide and the letter vanishes. **Marks** (dots,
   hamza: small components clear of the baseline) are not voted: they sit
   somewhere slightly different every time and a vote erases them; they come
   from the best printing, and marks the letter does not carry are dropped.
3. **Joins.** Where a form joins a neighbour, its connecting stroke ends on the
   document's usual join band (median top and bottom of the ink at cut edges),
   two pixels past the cell, so typed letters meet and overlap.
4. **OpenType.** `init`/`medi`/`fina` substitutions and an `rlig` lam-alef, so
   any shaping application (LibreOffice, browsers) joins the text. A form the
   document never printed borrows its nearest relative.

Forms with fewer than four printings use the single best one.

## What it has shown

- It works: new sentences typeset in a 1950s-looking heavy face
  (`0582-004-009-012`) and in a light modern face (`0565-000-002-001`).
- It is a **debugger for the letter cutter**: a wrong glyph means that form is
  cut wrong throughout that book. The blank initial `ف` of 0565 was 395 copies
  of `في` with their letters swapped; its wide isolated `ا` was words not
  split at the alef.

## Known faults

Final `و` of 0565 looks like `ر`; a five-page document lacks some forms
(final `ص` of 0582 is borrowed); uneven gaps (`فى`); no digits, punctuation,
vowel-mark positioning or kerning.

## The line not to cross

The faithful PDFs are never repaired ([decisions.md](decisions.md), D14). A
**restored edition** — same page, damaged letters redrawn from this font — is
an open idea ([ideas.md](ideas.md)); it would be a third output.

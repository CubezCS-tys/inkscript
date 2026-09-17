# How the text layer is written, and why

Everything here was found by writing a PDF, extracting its text with three
engines — pdfium (Chrome), MuPDF and poppler — and comparing with what a
LibreOffice-typeset Arabic PDF gives the same engines. "Native" means: no
worse than that reference. Where an engine's behaviour surprised us, the
rule records the experiment, not a theory.

## Glyphs

- **One Type 3 font per line, one glyph per word.** A glyph's drawing
  commands are the word's traced ink polygons (holes filled even-odd), its
  advance is the ink width, its ToUnicode entry is the word's text.
- **Text stored in visual order.** Extractors take a glyph's characters as
  laid out and run bidi over them; Arabic stored logically extracted
  backwards (`تاسارد`). Arabic letters are stored reversed; **digit runs are
  not** (native PDFs store `379هـ)` as `)ـه379`; reversing digits gave `973`).
- **Punctuation rides on its word** when Azure boxed it separately and the
  ink touches; a box holding several tokens is split into one glyph per
  token when its ink splits the same way. A glyph whose text *starts* with
  a neutral (`: ةيمجعم`) made MuPDF read the line left-to-right.
- **Page furniture is not glyph ink.** Rules and dashes are drawn as plain
  paths. Inside a glyph they made it declare a box reaching into another
  line.

## Lines

- **One text run per line, words in visual order**, a real space glyph
  between words, never wider than the smallest gap on the line (poppler
  drops a space glyph that overlaps a word). A space *character* inside each
  word's ToUnicode instead confused every engine.
- **One nominal size (8 pt) for every line**, glyphs scaled to true size.
  pdfium judges "same line" against the font size; a 40 pt title swallowed
  the author line beneath it.
- **Each run starts and ends with the narrow space glyph.** pdfium decides
  new-line-or-not from the vertical jump measured against the *width of the
  last glyph of one run and the first of the next*. Word-wide glyphs made a
  15 pt pitch look like one line, and pdfium then sorted equal-x justified
  lines among themselves: body lines swapped in pairs (25 inversions over 12
  pages → 0).
- **Declared glyph boxes are clipped at the neighbouring lines' ink with a
  gap (30% of line height)**, never to empty (keep ≥30% of the glyph's
  height). Boxes that merely touched (<1 pt) were read as one line; an
  inverted box made pdfium drop the glyph.
- **Superscript footnote markers** that Azure returns as their own line are
  folded into the body line beside them; as separate objects they overlapped
  both neighbours.
- **Invisible over the scan = zero opacity (ExtGState ca 0)**, not render
  mode 3, which does not apply to Type 3 glyphs.

## Exactness

- **Glyph space is in scan pixels.** The FontMatrix scales one glyph unit to
  one pixel at the nominal size, so the traced integer outlines are stored
  as they are: no scaling, no decimal rounding, lines placed on a whole
  pixel. Every glyph's absolute coordinates agree with the previous
  (decimal 1/1000-unit) writer to 0.02 px — the previous writer's rounding.
  The space glyph's advance is a whole pixel too; the pen adjustments must
  use the same rounded value or words drift along the line.
- **Every occurrence keeps its own outline.** A document alphabet labels
  each glyph (`/InkShapes [ids]` on the glyph stream, right to left) but
  never substitutes a shared outline: drawing one occurrence with
  another's ink changes a median 15% of its pixels (max 43%), six times the
  tracing error. The alphabet is exported beside the PDF instead
  (`<stem>.shapes.json`, `<stem>.alphabet.svg`, `<stem>.alphabet.png`).

## Known ceiling

Words whose ink physically touches cannot be split by any layer. Brackets
mirror as they do in native Arabic PDFs. Selection is per word.

## Numbers (30 documents, 115 pages, pdfium)

98.5% of words copy out intact with vowel marks; 0 reading-order inversions.

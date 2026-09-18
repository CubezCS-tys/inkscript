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
- **Text stored the way pdfium inverts it.** pdfium (Chrome) rebuilds a
  line that has right-to-left text by reversing the *order* of its bidi
  segments and then reversing each Arabic segment (and a neutral one that
  follows it) in place; Latin, digit, vowel-mark and separator segments
  (`, . / - : + %`) keep their internal order (`CPDF_TextPage::CloseTempLine`
  with `CFX_BidiString`'s automatic direction — branches 7559 = Chrome 144,
  7665–7947, and main). The stored form is the inverse: the word reversed
  as a whole, with every run of order-keeping characters put back the way
  it was, and brackets pdfium will read right-to-left are pre-mirrored,
  since it mirrors them (`AddCharInfoByRLDirection`) — `362` stays `362`,
  `كِتابُ` is stored `ُباتِك`, `379هـ)` becomes `(ـه379`, `(2)` stays `(2)`.
  Tokens without Arabic in an Arabic line get the same treatment, since
  pdfium reads the whole line in one pass. `text.chrome_reads` is that
  pdfium routine in Python and the tests check
  `chrome_reads(visual(line)) == line`. Known limit: `(Kose) في` comes
  back `(Kose )في`, the space glyph and the bracket forming one neutral
  segment that pdfium keeps forward after Latin text.
  *History:* the first rule here ("reverse each run of letters between
  vowel marks in place, word order as stored") was measured against
  pypdfium2 5.13, whose pdfium build 7999 had switched the automatic
  direction off; it passed the words-intact check because that check
  ignores order, while Chrome itself read every line's words backwards
  only in that build and vowelled words backwards in ours. pypdfium2 is
  now pinned to 5.12.1 (build 7947, reads like Chrome) and `--verify`
  also reports **lines in order**. A multi-word Latin phrase inside an
  Arabic line still comes back with its words swapped in Chrome — pdfium
  reverses every segment's position — and that is left as it is, because
  swapping the glyphs' texts would break the ink↔text mapping.
  There is no native reference to follow — Chrome's own PDF of the same
  line extracts wrongly in every engine — and MuPDF and poppler disagree
  with pdfium on vowelled text, so Chrome's engine is the target and the
  others are measured, not matched.
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
- **No two nearby runs may share their char-code sequence.** pdfium drops
  a text object as a fake-bold duplicate (`IsSameTextObject`) when one of
  the five objects before it has the same item count with the same codes
  and sits within a fraction of a line. Codes here are positional, so two
  runs with the same word count were identical, and a whole body line
  vanished from `0005` page 4 (727 → 733 of 733 words). The closing space
  glyph's code is now shifted by the line number modulo 6.
- **A kerned pair moves the pen back before its space glyph**, not after:
  a backwards adjustment right after the space lost it in pdfium (`سبأ لم`
  → `سبألم`; `0385`: 10,717 → 10,734 of 10,736).
- **Runs sharing a band go left to right** (see "Source pages"): pdfium
  joins text objects whose boxes overlap vertically whatever the gap, then
  reverses the whole line's segments.
- **A line whose Latin segments outnumber its Arabic ones is stored the
  left-to-right way**: pdfium keeps its segment order and reverses only
  the Arabic segments (and neutrals after them) in place, so those are
  stored reversed and pre-mirrored while the words stay in stream order
  (`text.visual(..., ltr_line=True)`, `text.latin_majority`).

## Source pages

- **The corpus PDFs are Azure's own searchable PDFs.** Every `BT…ET` text
  object is cut out of their content streams before the layer is added
  (the image and line art untouched, checked pixel-identical). Redaction
  was not enough: MuPDF left 19 of 34 runs it could not measure, and every
  engine then read two layers — lines merged, thousands of order inversions.
- **Gemini's page-1 read is stripped of Markdown** (`# …`, `---`, `**…**`)
  before alignment; it decorates some pages despite the prompt.
- **Born-digital pages are left untouched.** A page whose text is set in
  real embedded fonts (a modern journal typeset in InDesign) already is
  native text; stripping "the text layer" there erased the page's words.
  Azure's scans carry exactly one font, `Dummy`; anything else is real.
  A typeset page may also carry Azure's layer on top (the corpus has
  journals that went through OCR anyway): it is still native when the real
  fonts hold at least half as many words as the `Dummy` layer, and then
  only the `Dummy` layer is stripped (`0500`: 0 → 724 inversions when its
  16 typeset pages got a third layer). A real font whose text extracts as
  symbol junk (`ΔϴϤϨΘϟ`, no usable encoding, or a ToUnicode yielding
  under 90% letters) counts as no text: the page gets our layer, and its
  junk text objects are wrapped in a marked-content span whose
  `/ActualText` is a single space. The glyphs still draw — on such a page
  they ARE the visible ink; stripping them blanked 41 pages of `0470` —
  but pdfium, MuPDF and poppler extract the span's text instead, so our
  layer is the only text (`0470`: 40 → 1 inversions, `1370`: 43 → 23).
  `pdf/fontfix.py` can also build the fonts a real ToUnicode from Azure's
  words (glyphs aligned to word boxes, letters by vote); on `0470` it
  covers 93–98% of glyphs but reads back at 88% of words against our
  layer's 100%, so a page trusts its own fixed fonts only above 99.5%
  coverage (`FIX_COVERAGE`), which no document has reached yet.
- **Gemini sees the page at scan resolution.** The embedded image is
  handed over verbatim only when it is at least 150 dpi for the page; 10
  of 227 night documents carried a thumbnail (17 × 27 px once) or a 75 dpi
  copy as their single image, and Gemini read little or nothing from it.
  Otherwise the page is rendered at 300 dpi.
- **Refused cover pages.** When the strict transcription comes back empty
  twice, the top half of the page is tried, then a title-and-author
  extraction, which the recitation filter allows where a verbatim page is
  refused (`FinishReason.RECITATION`). Five of six refused covers in the
  night sample read this way; the sixth is an editorial with a heading
  only.
- **Sideways pages** (tables printed landscape; Azure's page angle ≈ ±90°)
  are laid out in a turned frame and written with a rotated text matrix, so
  the glyphs land on the ink and pdfium reads the lines as lines (65–76% →
  100% of words intact on such pages).
- **Runs are written in Azure's line order**, which is reading order: on a
  two-column page Azure gives the right column's lines, then the left's,
  band by band. Sorting by baseline interleaved the columns. Vertical
  neighbours for box clipping still come from page order.
- **Superscript-line folding is limited to a small line right beside a
  larger one**; without the size and distance limits, a short line in the
  other column of a two-column page was folded into it, chain-merging 87
  lines into 8.

## Not handled yet

- Reading order on two-column pages is only as good as Azure's line order.
- MuPDF- and poppler-based viewers get vowelled words wrong where Chrome
  gets them right; the engines contradict each other on this and Chrome is
  the target.

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

## Pieces (selection inside a word)

A viewer decides which characters of a multi-character glyph a drag-select
covers by slicing the glyph's width equally, so a drag that starts a few
pixels inside `362` yields `62`. The finer the glyphs, the more exact the
selection. Glyphs are therefore one *piece* of ink where that is certain:

- **Text side:** Arabic breaks after `ا د ذ ر ز و ة ى` and hamza (letters
  that never join leftward); marks stay on their letter; any non-Arabic run
  (`126/4`, `(1)`) is one piece.
- **Ink side:** base strokes (height ≥ 0.3 of the line) with their dots and
  marks attached by horizontal overlap.
- **Split only when the counts agree** and every Arabic piece's ink width is
  plausible for its letter count (0.12–1.4 line heights per letter): a
  detached stroke (the bar of ك) can make the count match by accident.
  Otherwise the word stays one glyph. Never guess.
- **A word carrying vowel marks stays one glyph.** pdfium never reorders
  glyphs inside a word; an unvowelled word survives because its letter-run
  reversal spans all its pieces, but a mark cuts the run and split pieces
  come out in the wrong order whatever is stored (no invisible separator
  changes it — every one leaks into the text).
- **Tokens that share one Azure box are separate words for spacing**, or
  they copy out fused (`مكةتاريخ`).
- **Within a word, pieces are written in text order** (reversed for the
  right-to-left run), not by ink position: a و whose tail sweeps under the
  next letter starts further left than that letter.
- **A piece's advance runs to the next piece**, so no pen adjustment sits
  inside a word: pdfium turns a kerning adjustment after a narrow glyph into
  a generated space (`ا لحكم`, `3 6 2`).

Measured on the 30 documents: 24% of words split (1.34 glyphs per word),
words intact in pdfium unchanged at 98.5%, and pieces sharing the same
strict ink shape carry the same text 99.74% of the time — the check that
catches a wrong assignment.

## Known ceiling

Words whose ink physically touches cannot be split by any layer. Brackets
mirror as they do in native Arabic PDFs. Selection is per piece; cutting
inside a connected run of letters is not done.

## Numbers (30 documents, 115 pages, pdfium)

98.5% of words copy out intact with vowel marks; 0 reading-order inversions.

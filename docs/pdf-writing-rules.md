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

## Letters (selection inside a connected run)

*Since 2026-09-20 the build cuts letters along the pen path
(`geometry/penpath.py`, experiment 09); the column method below it is
kept as `geometry/letters.py` and supplies the shared pieces (letter
signatures, line geometry, piece masks).*

- **A cut is a point on the pen path, not a column of the page.** The
  piece's ink is thinned to its centre line; the trunk runs from where
  the first letter meets the baseline to the piece's left end, and every
  other bit of ink — an arm, an ascender, the far side of a loop, a tail
  sweeping back — belongs to the trunk point it hangs from. A kaf keeps
  the arm it throws over its neighbour, which no vertical cut can do.
  (The start is the rightmost point *near the baseline*: started at the
  rightmost ink, the path ran down a kaf's arm and cuts fell along it.)
- **Two witnesses choose the cuts.** The hard facts — a letter's dots,
  tall stroke and bowl lie in its own stretch of the path — and the
  document's own alphabet: the mean picture of each letter-form, built
  from the cut letters, the cuts re-chosen to match it, rebuilt, four
  rounds, damped (a full swap flip-flopped on a fine typeface). The
  pictures alone let a large letter swallow a small neighbour; the facts
  alone leave featureless runs undecided. Pictures are compared
  softened (2 px): as hard masks a fine typeface's strokes never
  coincide and its atlas came out empty.
- **On the strip a hanging tall stroke occupies one position**, however
  wide it is on the page, so "has an ascender" is one position, not two
  columns (the two-column rule rejected 61% of pieces). A fact is
  enforced for a letter-form only if 85% of its occurrences show it.
- **A letter glyph = the ink hanging from its stretch + a cell that is
  its stretch of the baseline.** Origin and advance come from the cell;
  the ink may reach outside it, as a typeset kaf's arm overhangs the
  next glyph's box. Chrome highlights the cell.
- **Seams and holes.** Outlines run through pixel centres, so letters
  traced apart left a one-pixel seam of missing ink (1.1% of a page's
  ink): each letter takes one pixel of its neighbour at the seam, inside
  the piece's ink only. Rebuilding a piece's mask from its outlines
  erased the ink around holes (every `ه` a pixel wider): the hole's
  outline is drawn back. Cut letters are traced without simplification.
  Fixture, cut against uncut at 300 dpi: 1.2% of ink pixels differ in
  edge shading (>64 levels), 0.03% by more than half tone.
- **Every piece that gets cuts is cut** (`CUT_ALL`); the witnesses' verdict
  is reported (`letters_why`), not enforced: two thirds of rejected cuts
  were right, and a wrong cut costs what an uncut piece costs. Broken ink
  is bridged for the path only; blobs and text pieces that do not pair off
  are aligned by width; where the path doubles back the cells share the
  width in proportion to the path.
- **When a fact fails, the path is tried again from the first letter's
  body**, and the start the facts prefer is kept: a face that prints `في`
  with the ya's tail running back along the baseline had both letters
  swapped in all 395 copies, the atlas agreeing with itself. Marks go to the
  nearest point of the whole centre line. No letter is a bare connector.
- Numbers (2026-09-20): reference document 96.2% of words with a box for
  every letter, 1,246/1,246 words, 113/113 lines; 227 journals 96.8%, text
  unchanged. Kept current in `docs/STATUS.md`; narrative in `docs/letters.md`.

### The column method (before the pen path)

- **A piece's letters are aligned to its ink, not detected.** The letters
  are known (the OCR's text, split where the script cannot join), and
  each has signatures visible in any typeface: dots above or below and
  how many, an ascender (`ا ل ك ط`), a descending bowl (`ج ح خ`; `ن ي س ص
  ق ل م` when the piece ends there), a width class. A dynamic programme
  gives each letter one interval of the piece's width, scoring the
  interval against its letter (`geometry/letters.py`).
- **A cut falls only on a join.** The geometry offers the places — columns
  where the ink is nothing but the connecting stroke (`joins`; along a
  kashida or a flat final `ب`, places a stroke apart) — and the letters'
  signatures choose among them. A piece with fewer joins than cuts stays
  whole. Left free over every column the programme was no nearer the
  joins than equal slices of the width are, which is what Chrome shows
  for an uncut glyph: 90.9% against 91.6% of cuts within a stroke of the
  join (its median error was smaller, 3 px against 4, its worst cuts
  worse). So an unconstrained cut bought nothing over not cutting.
- **Tall and deep are measured against the line, not the piece.** A
  threshold from a two-letter piece's own ink missed about half of the
  real ascenders (`ل` initial showed its ascender 48% of the time, final
  `ا` 59%); against the line's baseline and its usual rise and drop (60th
  percentile of its blobs, so a bracket does not inflate it) they show
  85% and 86%. Presence is a count of columns, not a share: an alef is
  three pixels of ink in an interval that may be thirty wide.
- **The document is the witness.** No signature table is trusted on its
  own: what each letter-form actually shows in this document is learned
  by majority over all its aligned occurrences (at least five), feature
  by feature; a feature that holds for under 85% of a form's occurrences
  says nothing about that form and cannot veto. A piece's cuts are
  accepted only when every letter shows every reliable feature and at
  least one is positive (a tall stroke, a bowl, a dot). Fixture: 654 of
  912 plans accepted (1,122 pieces of two or more letters); 1,747 letter
  glyphs; Chrome unchanged at 1,246/1,246 words, 113/113 lines. A wrong
  cut can only move a highlight: the letters' texts concatenate to the
  word.
- **A letter glyph's ink is the piece's ink cut at the column**, the main
  run divided at the cut and each dot going with the interval that holds
  its centre; the union of a piece's letter glyphs is exactly the piece's
  ink. Vowelled words are not cut (marks would break the run order in
  pdfium); lam-alef is one glyph; a kashida rides on the letter before it.
- **Vertical neighbours for box clipping are the nearest runs on other
  bands.** Two runs on one baseline are not each other's neighbour; taken
  as one, they clipped a whole line's boxes to a sliver. The clip itself
  still stops at the neighbour's ink plus the gap even when neighbours
  overlap (a sliver there is the price): stopping at the midpoint of the
  overlap made pdfium read neighbouring lines as one (113 → 7 lines on a
  page), so `--verify` now warns when pdfium returns far fewer lines than
  were written.

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
mirror as they do in native Arabic PDFs. Selection is per letter where a
piece was cut along its pen path (96.8% of words at scale, see "Letters"
above and `docs/STATUS.md`), per piece otherwise; words carrying vowel marks
are never cut. *(Until 2026-09-19 this section read "cutting inside a
connected run of letters is not done".)*

## Numbers (30 documents, 115 pages, pdfium)

98.5% of words copy out intact with vowel marks; 0 reading-order inversions.

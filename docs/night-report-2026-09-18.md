# Night report — 2026-09-18

What happened overnight and in the morning that followed, what to look at
first, and what I'd do next. Everything below is committed on `main` in
`~/Desktop/inkscript` (not pushed). All sets were rebuilt at 09:19 by one
code state.

## Look at these first

1. `~/Desktop/native_pdfs/` — the 30-document test set, final build.
2. `~/Desktop/s3_native/` — the 47 corpus documents: PDFs, `vector/`,
   `alphabet/`, `review/<doc>.review.html` (a word's ink beside its readings,
   then every number).
3. `~/Desktop/OCR_gem_json/output/s3_night/` — one document from each of
   227 journals (4,440 pages): `native/`, `review/`, `native_final.log`
   (one line per document), `check_final.log`, `numbers_final.log`.
4. `experiments/07_engine_comparison/` — the same pages as Azure's own
   searchable PDF and as ocrmypdf output, read by Chrome's engine.

## Verified numbers (Chrome's engine, final build)

| set | words intact | lines in reading order | in-column inversions | pages without their image |
|---|---|---|---|---|
| 30-document test set, 115 pages | 34,958 / 34,959 (**100.0%**) | 3,866 / 3,868 (99.9%) | 3 | 0 |
| 47 corpus documents, 1,007 pages (43 born-digital, 14 sideways) | 237,695 / 237,741 (**100.0%**; was 99.1% yesterday) | 20,213 / 20,224 (99.9%) | 103 (was 2,208) | 0 |
| 227-journal sample, 4,440 pages (903 born-digital, 16 sideways) | 912,551 / 912,800 (**99.97%**; was 98.02% at 01:00) | 84,117 / 84,186 (99.9%), 5 reversed | 535 (was 1,299) | 0 (was 98 documents with at least one) |

"Lines in reading order" is new: a line's Arabic words come back contiguous
and in order inside one line of Chrome's text, the reference being the words
by ink position. 51 lines where Latin words outnumber Arabic ones are counted
apart (pdfium reads those left to right by its majority rule; a natively
typeset PDF gets the same). Most remaining inversions are typeset pages whose
fonts have no usable encoding (`0470`, `1370`: their own junk text interleaves
with our layer) and table pages.

Consistency check over the sample: 959,667 words, 1,399 contradictions
(same ink, different text), 2,085 words to review, 50,007 numbers. Numbers
re-read trial (Gemini reads each number from its own crop): 308 numbers over
eight documents, 269 agree (87%), 39 to review, $0.26.

Same pages, three text layers, one reader (`experiments/07`): lines in
reading order in Chrome — ours 98–100%, Azure's own searchable PDF 34–75%,
ocrmypdf/Tesseract 2–15%; words intact 99.9–100% / 96–99% / 62–85% (the
last mixes recognition with layer structure; see the README's caveats).

## What was wrong, and how it was found

The first night run's numbers (98.0%, 1,299 inversions, two documents at
11% and 3%) led to defects that none of the existing checks could see.

1. **Pages lost their scan image.** A page that inherits `/Resources` from
   the Pages tree got a fresh Resources dictionary for the fonts, which
   shadowed the inherited one; the image XObject vanished and the page
   rendered blank. 98 of 224 night documents, 17 of the 47, 12 of the 30
   had such pages — including copies on the Desktop. Found through MuPDF's
   "cannot find XObject resource 'Im0'" while cropping numbers. Fixed;
   `--verify` renders every page and reports any that lost its ink.
2. **Every word mirrored.** Some scanner content ends with an unbalanced
   `cm` (a flipped 0.75 scale); the layer inherited it and Chrome read the
   words backwards (`1105` 11%, `1185` 3%, both now 99%+). Fixed by
   wrapping the scanner content in `q … Q`.
3. **The verifier was not reading like Chrome.** Yesterday's rule for
   vowelled text was measured against pypdfium2 5.13, whose pdfium build
   7999 has automatic right-to-left detection off. Chrome 144 (build 7559),
   every build to 7947, and pdfium's main branch reverse the ORDER of a
   line's bidi segments and each Arabic segment in place, mirroring
   brackets. So in real Chrome our vowelled words came out backwards, and
   in the verifier every line's words did — which the words-intact check
   ignores. Read from pdfium's source and confirmed with builds 7947 and
   7999. `text.visual()` is now the exact inverse of Chrome's routine,
   `text.chrome_reads()` emulates it, tests round-trip lines, pypdfium2 is
   pinned to 5.12.1 (build 7947), and `--verify` reports lines in order.
4. **A whole body line dropped by pdfium.** pdfium treats a text object as
   a fake-bold duplicate of one of the five before it when item counts and
   char codes match and it sits within a fraction of a line; our codes were
   positional, so two runs with the same word count were identical, and a
   line vanished from `0005` page 4. The closing space glyph's code now
   varies by line (727 → 733 of 733).
5. **Gemini was handed thumbnails.** The "single embedded image" of a page
   was taken as the scan; on 10 of 227 documents it was a thumbnail (17 × 27
   px once) or a 75 dpi copy, and Gemini read little or nothing. Pages are
   rendered unless the image is at least 150 dpi. Seven documents' page-1
   reads grew from a few dozen to thousands of characters.

Smaller fixes, each measured:

- **Ruled lines are cut out of the ink** before letters are traced: a
  header's underline had fused with a word into one glyph spanning the
  page (running heads came back with their halves swapped; table borders
  no longer fuse with cell text).
- **Runs on the same baseline are written left to right**: pdfium joins
  text objects that overlap vertically whatever the gap, then reverses
  the whole line.
- **Kerned word pairs move the pen back before the space glyph**, not
  after; the space was lost (`0385`: 10,717 → 10,734 of 10,736).
- **Latin-majority lines** stored the left-to-right way; the ornate
  Quranic brackets ﴾﴿ are not mirrored by pdfium and no longer by us.
- **Typeset pages** under an Azure layer are born-digital (the redundant
  Azure layer stripped); pages whose fonts extract as symbol junk keep
  that text (it is their visible ink) and get our layer; presentation-form
  Arabic counts as readable.
- **Refused cover pages**: the top half is tried, then a title-and-author
  extraction, which the recitation filter allows (5 of 6 read).
- **The line-order reference** is by ink position: Azure's word order is
  wrong on vowelled verse and table rows, and the first version of the
  metric blamed the writer for it.

## Firefox (pdf.js), measured and decided

pdf.js infers word spaces from the pen's jumps relative to the font size
and emits its items in stream order, so at the 8 pt nominal size an Arabic
line copies out with its words reversed (words intact, 95%). A 16–24 pt
nominal size brings half the lines to Chrome's reading; the other half are
tight word gaps (merged) and words written as pieces (split), and every
larger size costs pdfium 0.1% of words. Decision: 8 pt stays.
`experiments/06_pdfjs_nominal_size/`.

## Open, in the order I'd take them

1. Typeset PDFs with junk-encoded fonts (`0470`, `1370`): give those fonts
   a correct ToUnicode from Azure's words — the born-digital variant of
   this project; it would also remove their inversions.
2. Table pages: cells pdfium joins across rows; Azure's line order there.
3. Math tokens in mixed lines (`i=1,2,K,N)xi`) — 14 words on `1245`.
4. Letter-level selection inside a connected run (roadmap item 4).
5. A larger unattended sample (500–1,000 documents) with the same checks.

## Honest note on "pioneering"

The parts exist elsewhere: JBIG2/DjVu symbol dictionaries, invisible OCR
layers, Type 3 fonts. What I have not seen elsewhere is the combination —
the page's own ink as the font, every glyph the printed occurrence's
outline, the text layer's every rule measured against the viewer engine
rather than assumed (this night showed why: the engine's own builds
disagree), and the alphabet used as a witness against the OCR — applied
to Arabic print, where the engines get vowelled text wrong even in
natively typeset PDFs. The measured numbers are the claim; the comparison
in `experiments/07` is the first outside reference point.

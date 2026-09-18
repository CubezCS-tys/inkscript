# Night report — 2026-09-18

What happened while you slept, what to look at first, and what I'd do next.
Everything below is committed on `main` in `~/Desktop/inkscript` (not pushed).

## Look at these first

1. `~/Desktop/native_pdfs/` — the 30-document test set, final build.
2. `~/Desktop/s3_native/` — the 47 corpus documents: PDFs, `vector/`,
   `alphabet/`, `review/<doc>.review.html` (a word's ink beside its readings,
   then every number). Both Desktop folders were rebuilt at 04:00 with the
   final writer; earlier copies had blank pages (see below).
3. `~/Desktop/OCR_gem_json/output/s3_night/` — one document from each of
   227 journals (4,440 pages): `native/`, `review/`, `native_final.log`
   (one line per document), `check_final.log`, `numbers_final.log`.

## Verified numbers (Chrome's engine, final build)

| set | words intact | lines in reading order | in-column inversions | pages without their image |
|---|---|---|---|---|
| 30-document test set, 115 pages | 34,952 / 34,955 (**99.99%**) | 3,861 / 3,879 (99.5%) | 3 | 0 |
| 47 corpus documents, 1,007 pages (43 born-digital, 14 sideways) | 237,564 / 237,696 (**99.94%**; was 99.1%) | 20,167 / 20,499 (98.4%) | 105 (was 2,208) | 0 |
| 227-journal sample, 4,440 pages (1,043 born-digital, 16 sideways) | 874,190 / 874,663 (**99.95%**; was 98.02%) | 81,221 / 82,180 (98.8%) | 422 (was 1,299) | 0 (was 98 documents with at least one) |

"Lines in reading order" is new: a line's Arabic words come back contiguous
and in order inside one line of Chrome's text. 42 lines in the night sample
come back reversed; 71 lines where Latin words outnumber Arabic ones are
counted apart, because pdfium reads those left to right by its own majority
rule (a natively typeset PDF gets the same).

Weakest documents in the night sample: `0005-032-001-001` 727/733,
`0385-012-019-001` 10,654/10,736, `1245-001-004-001` 2,188/2,203. Most
inversions: `0470-000-001-003` (71), `0140-000-062-001` (25) — table and
multi-column pages, Azure's line order.

Consistency check over the sample: 920,307 words, 1,217 contradictions
(same ink, different text), 1,799 words to review, 48,631 numbers.
Numbers re-read trial (Gemini reads each number from its own crop): 165
numbers over three documents, 141 agree (85%), 24 to review, $0.14.

## What was wrong, and how it was found

The morning numbers of the first night run (98.0%, 1,299 inversions, two
documents at 11% and 3%) led to two writer defects that none of the
existing checks could see:

1. **Pages lost their scan image.** A page that inherits `/Resources` from
   the Pages tree got a fresh Resources dictionary for the fonts, which
   shadowed the inherited one; the page's image XObject was no longer
   visible and the page rendered blank. **98 of 224 night documents, 17 of
   the 47, 12 of the 30** had at least one such page. Found through MuPDF's
   "cannot find XObject resource 'Im0'" while cropping numbers. Fixed
   (inherited dictionary copied onto the page); `--verify` now renders
   every page and reports any that lost its ink.
2. **Every word mirrored.** Some scanner content ends with an unbalanced
   `cm` (a flipped 0.75 scale). The text layer inherited it and Chrome read
   the words backwards: `1105` at 11%, `1185` at 3%. Fixed by wrapping the
   scanner content in `q … Q`. Both documents are at 99%.

Then the one that matters most:

3. **The verifier was not reading like Chrome.** Yesterday's rule for
   vowelled text ("reverse letter runs between marks, keep word order")
   was measured against pypdfium2 5.13, whose pdfium build 7999 has the
   automatic right-to-left detection switched off. Chrome 144 (build 7559),
   every build up to 7947, and pdfium's main branch reverse the ORDER of a
   line's bidi segments and each Arabic segment in place, mirroring
   brackets. So in real Chrome our vowelled words came out backwards, and
   in the verifier every line's words came out backwards — which the
   words-intact check ignores. Read from pdfium's source
   (`CPDF_TextPage::CloseTempLine`, `CFX_BidiString`), confirmed by
   reading the same PDF with builds 7947 and 7999. Now `text.visual()` is
   the exact inverse of Chrome's routine, `text.chrome_reads()` emulates
   it, the tests round-trip lines through it, pypdfium2 is pinned to
   5.12.1 (build 7947), and `--verify` reports lines in order.

Smaller fixes from the same pass, each measured:

- **Ruled lines are cut out of the ink** before letters are traced: a
  header's underline had fused with the word it touched into one glyph
  spanning the page, and pdfium sorted the line by it (running heads came
  back with their halves swapped). Table borders no longer fuse with cell
  text either (`1380`: +21 words).
- **Runs on the same baseline are written left to right**: pdfium joins
  text objects that overlap vertically whatever the horizontal gap, then
  reverses the whole line, so the stream order must be visual.
- **Typeset pages under an Azure layer** (real fonts carrying at least half
  as many words as the `Dummy` layer) are born-digital: left as they are,
  with Azure's redundant layer stripped. `0500` had gone from 0 to 724
  inversions when its 16 typeset pages received a third text layer.
- **Indirect `/Font` and `/ExtGState` dictionaries** (a consequence of the
  inherited-Resources fix) aborted a 47-document run; handled.
- Numbers re-read: robust answer parsing, unread crops counted.

## Firefox (pdf.js), measured

pdf.js infers word spaces from the pen's jumps relative to the font size
(0.102–0.6 × size) and emits its text items in stream order, so at the 8 pt
nominal size an Arabic line copies out with its words reversed (words
themselves intact, 95%). A 16–24 pt nominal size brings 48% of lines to
Chrome's reading with no effect on pdfium; the other half is not yet
explained. Recorded in `experiments/06_pdfjs_nominal_size/`, not adopted.

## Open, in the order I'd take them

1. The 42 reversed and ~900 out-of-order lines in the night sample: list
   them per page (the metric is there) and look at the pages; most will be
   tables and running heads.
2. Firefox: separate the unexplained half of the lines; decide on the
   nominal size.
3. The recitation-filter cover pages (Gemini refuses some title pages).
4. Letter-level selection inside a connected run (roadmap item 4).
5. A comparison against ABBYY / ocrmypdf output on the same pages, for
   the "pioneering" claim — an afternoon's work, and the honest way to say
   it.

## Honest note on "pioneering"

The parts exist elsewhere: JBIG2/DjVu symbol dictionaries, invisible OCR
layers, Type 3 fonts. What I have not seen elsewhere is the combination —
the page's own ink as the font, every glyph the printed occurrence's
outline, the text layer's every rule measured against the viewer engine
rather than assumed (last night showed why: the engine's own builds
disagree), and the alphabet used as a witness against the OCR — applied
to Arabic print, where the engines get vowelled text wrong even in
natively typeset PDFs. The measured numbers are the claim.

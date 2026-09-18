# Night report — 2026-09-18

What happened while you slept, what to look at first, and what I'd do next.
Everything below is committed on `main` in `~/Desktop/inkscript`.

## Look at these first

1. `~/Desktop/s3_native/` — the 47 corpus documents from yesterday's scale
   test, rebuilt with every fix: PDFs, `vector/`, `alphabet/`, and
   `review/<doc>.review.html` (the word's ink beside its readings, then every
   number). Open `review/0450-000-022-001.review.html` for a page with real
   candidates (`صد`/`ضد`, `٣٩`/`٣٢`).
2. `~/Desktop/OCR_gem_json/output/s3_night/` — the overnight sample: one
   document from each of 227 journals (4,440 pages). `pipeline.log` has the
   totals; `native/`, `review/` as above. (See "Night sample" below for the
   numbers, or `pipeline.log` if the build was still running when you read
   this.)
3. `~/Desktop/native_pdfs/` — the 30-document test set, current build.

## Verified numbers

| set | words intact in Chrome's engine | in-column order inversions |
|---|---|---|
| 30-document test set (115 pages) | 34,919 / 34,945 (**99.9%**) | 3 |
| 47 corpus documents (1,007 pages; 43 born-digital pages left as they are, 14 sideways) | 235,576 / 237,596 (**99.1%**) | remaining ones are table pages and Azure's own line order |
| 227-journal night sample | see `s3_night/pipeline.log` | |

## What the corpus taught the pipeline (each fixed, tested, documented)

- **The corpus PDFs are Azure's searchable PDFs**, not raw scans: their text
  layer is now cut out before ours goes in (redaction missed half of it, and
  every engine read two layers).
- **Born-digital journals exist** (InDesign-typeset, real fonts). They are
  detected by their fonts and left untouched — they already are native text.
- **Fully vowelled text**: Chrome's engine restores a glyph's string by
  reversing letter runs *between* marks; storing that same transformation
  took a vowelled poem from 6% to 100% of words intact. Vowelled words are
  never split into pieces (Chrome never reorders glyphs within a word).
  MuPDF and poppler disagree with Chrome here; Chrome is the target.
- **Sideways pages** (tables printed landscape): laid out in a turned frame,
  written with a rotated text matrix: 65–76% → 100%.
- **Gemini**: Markdown decorations stripped; rotated scans sent upright;
  empty answers retried and never cached (13 empty front pages → 9; the 9
  are the recitation filter refusing cover pages, left on Azure's text).
- **Line order**: runs written in Azure's order (column-aware); superscript
  folding limited to adjacent small lines (it had chain-merged 87 lines
  into 8 on a two-column page); isolated out-of-place lines moved to their
  height. Tokens sharing one Azure box get a space glyph between them.
- **Memory**: shape-alphabet prototypes stored packed; per-page ink
  released; `native --resume` and `--only`. An 81-page document peaks at
  843 MB (it had been killing the machine).

## New tools

- `inkscript fetch` — pull documents from the corpus bucket.
- `inkscript check --html` — contradictions (same ink, different text),
  classified as *substitution* (worth a look: `يحكم`/`بحكم`, `٧٠`/`٧٦`),
  *marks/punctuation*, or *extension* (`وهو` beside `هو`: Azure's box
  covering only the shared ligature, a box artefact). Plus every number.
  47 documents: 99 substitutions across 248,714 words.
- `inkscript numbers` — a second reading of every number from its own ink,
  twelve crops per Gemini request; disagreements to review. Trial 36/36.

## Open, in the order I'd take them

1. Read the night sample's per-document lines for anything under 98% and
   look at those pages; that is how every fix above was found.
2. The recitation-filter cover pages: try a different prompt framing or a
   crop of the title area only.
3. Azure's line order on table pages (the remaining inversions).
4. Firefox (pdf.js) on vowelled pages — unknown; Chrome is verified.
5. Letter-level selection inside a connected run (roadmap item 4).

## Honest note on "pioneering"

The parts exist elsewhere: JBIG2/DjVu symbol dictionaries, invisible OCR
layers, Type 3 fonts. What I have not seen elsewhere is the combination —
the page's own ink as the font, every glyph the printed occurrence's
outline, the text layer's every rule measured against the viewer engine
rather than assumed, and the alphabet used as a witness against the OCR —
applied to Arabic print, where the engines themselves get vowelled text
wrong even in natively typeset PDFs. The measured numbers are the claim;
the words "pioneering" or "novel" should wait for a comparison against
ABBYY / Tesseract-PDF / ocrmypdf output on the same pages, which would be a
worthwhile afternoon.

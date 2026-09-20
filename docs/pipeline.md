# The two halves

```
 scan.pdf ─┬─► OCR (Azure words+boxes; Gemini re-reads page 1) ──► what each word SAYS
           │                                                            │
           └─► GEOMETRY (binarise → ink blobs → outline polygons) ──► what each mark IS and WHERE
                                                                        │
                                   pdf/  (blobs → word boxes → Type 3 glyphs → text runs)
                                                                        ▼
                                        <stem>.pdf  scan + selectable ink glyphs
                                        <stem>_vector.pdf  the glyphs alone
```

| part | package | reads | writes |
|---|---|---|---|
| OCR | `inkscript.ocr` | Azure JSON, scans, Gemini | page-1 text per box, searchable PDF (older path) |
| Geometry | `inkscript.geometry` | scans | outline polygons, shape alphabet, blob→word layout |
| Meeting point | `inkscript.pdf` | both | ink-glyph PDFs |
| Checks | `inkscript.verify` | PDFs | pdfium/MuPDF/poppler numbers |
| Review | `inkscript.viewer` | outputs | static HTML bundles |

## Letters

Since 2026-09-20 `inkscript native` makes two passes over a document: the first
cuts every joined piece into letters along its pen path and learns the
document's letter atlas; the second writes the PDF, one glyph per letter where
a piece was cut. How, and the tools for looking inside it: [letters.md](letters.md).

## Typical run

```
inkscript frontpage --azure-dir DATA/azure --scan-dir DATA/input --out OUT/frontpage --verify
inkscript native    --azure-dir DATA/azure --scan-dir DATA/input --frontpage-dir OUT/frontpage --out OUT/native --vector --verify
inkscript compare   --frontpage-dir OUT/frontpage --azure-dir DATA/azure --out OUT/review --zip
inkscript trace     --pdf DATA/input/<stem>.pdf --page 1 --out OUT/trace
inkscript alphabet  DATA/input/*.pdf --pages 5 --out OUT/alphabet.json
```

`DATA/azure/<stem>/<stem>.json` + `<stem>.pdf` are Azure prebuilt-read outputs;
`DATA/input/<stem>.pdf` the image-only scans. Data never lives in the repo.

## The alphabet beside the PDF

`inkscript native` builds one shape alphabet per document and writes:

- `<stem>.shapes.json` — every shape's prototype outline and count, and every
  glyph's placement (page, text, box, the shape ids it is made of);
- `<stem>.alphabet.svg` — one `<symbol id="s<id>">` per shape and a specimen
  sheet by frequency; `<stem>.alphabet.png` — the same sheet as an image.

Inside the PDF each glyph stream carries `/InkShapes [ids]`. The alphabet is
knowledge about the ink; the page always draws each occurrence's own outline
(see pdf-writing-rules.md, "Exactness"). Different type weights are different
alphabets; that is correct, not a defect.

## Checking a document against itself

`inkscript check OUT/native` reads each `<stem>.shapes.json` and lists
*contradictions*: words whose ink signature (shape ids right to left, small
blobs tagged above/on/below) matches another word's but whose text differs —
one of the readings is wrong. It also lists every word containing a digit,
since a wrong date is the error that hurts most and shows least. `--out`
writes `<stem>.review.json` per document.

`inkscript numbers OUT/review OUT/native` reads every number again from its
own ink (crops, twelve per Gemini request, sideways pages turned upright)
and writes `<stem>.numbers.json`; a number whose digits the two readings
disagree on goes to review, one they agree on is very likely right. Nothing
is corrected automatically. Trial: 36 of 36 agreed on a footnote-heavy
document, $0.03.

## Correcting a reading without a rebuild

The review page (`check --html`) shows each reading in an editable field
beside its ink. Change the wrong ones, press **Show corrections**, and the
page lists them as `[{page, box, text}]` (also copied to the clipboard). Then

```
inkscript correct OUT/native/<stem>.pdf --file corrections.json
```

finds the glyph whose declared box lies in each Azure box, stores the new
text the way that line is stored (the inverse of Chrome's reading, right-
or left-to-right by the line's majority), rewrites only that ToUnicode
entry (incremental save; the ink is untouched), marks the placement in
`<stem>.shapes.json` and appends to `<stem>.corrections.json`. A single
word: `--page 3 --box 535,2709,550,2744 --text "..."`.
`inkscript.pdf.inspect.page_glyphs` is the reader behind it (and behind the
storyboard's glyph explorer): every glyph of a page back out of its font.

## Checking against the viewer

`inkscript native --verify` opens every finished PDF in pdfium — Chrome's
engine, pinned to the build that reads like Chrome (pypdfium2 5.12.1,
pdfium 7947; 5.13's 7999 does not, see pdf-writing-rules.md "History") —
and reports per document:

- **words intact**: each word placed in the layer comes back whole (marks
  included, edge punctuation ignored);
- **lines in order**: each line's Arabic words come back contiguous and in
  reading order inside one pdfium line (lines of three or more words);
  the count of lines that come back *reversed* is shown when non-zero;
- **order inversions**: consecutive pdfium lines in the same column whose
  baseline jumps back up the page (sideways and born-digital pages skipped);
- **pages that lost their image**: the output page renders with less than
  half the scan page's ink.

`inkscript.text.chrome_reads` is pdfium's line reconstruction in Python;
the tests round-trip `visual()` through it.

## What the geometry does not do yet

- Letter-level glyphs (Arabic joins letters; a blob is a sub-word).
- Read on its own: labels come from the OCR half. See
  `experiments/04_label_once_purity.py` for the measurement that frames it:
  strict shape groups are 99.8% consistent, but two-thirds of a page's
  words are shapes that appear once.

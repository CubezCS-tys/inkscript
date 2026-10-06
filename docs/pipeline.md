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
| What we know beyond the ink | `inkscript.enrich` | Azure JSON, scan, build outputs | JATS + ALTO XML, trust marks, Quran links, `_trust.pdf` |
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

## The document as data: `--xml` and `--trust` (since 2026-10-06)

`inkscript native ... --xml` writes two files beside the PDFs (D20):

- `<stem>.jats.xml` — the article as publishers keep it (JATS 1.4, Journal
  Archiving and Interchange DTD): front matter, body in reading order with
  sections, footnotes linked from their markers, references, every Quran
  quotation linked to its verse.
- `<stem>.alto.xml` — every page, line and word with its box as libraries keep
  OCR (ALTO 4.4): Azure's confidence, the trust mark and its reasons, the
  other reader's text, ids that link each word to its JATS element (through
  its block) and to its glyphs (the same id in `shapes.json` placements, as
  `"word"`).

`--trust` writes `<stem>_trust.pdf` (and `<stem>_vector_trust.pdf` with
`--vector`): the faithful PDF with one amber highlight per flagged word, in a
layer "Uncertain words" that a viewer can hide, appended as an incremental
update so the original bytes come first, unchanged (pdf-writing-rules.md,
"The trust copy").

Every word gets one trust mark (experiment 22's default rule,
`enrich/trust.py`): **verified** (a Quran verse or Gemini's page-1 reading
agrees), **flagged** with reasons (Azure confidence < 0.8, speck, ornament or
display type, Latin on an Arabic page, Persian letter left in the text, differs
from the Quran verse, Gemini reads it differently), or **agreed** (no signal).
Quran quotations are found and checked word for word against the Tanzil text
that ships in `src/inkscript/data/quran/` (CC BY 3.0, `NOTICE.md`).

With `--verify`, both XML files are validated against the official schemas
(fetched once into `~/.cache/inkscript/schemas`; without network the build
says "not validated" and carries on) and each trust PDF is checked against its
faithful PDF in pdfium (same bytes first, same text and character boxes on
every page). Neither flag changes anything else: without them the outputs are
as before. The extra time is small (a few seconds on the fixture's ~35 s build:
rendering each scan page once for the ink signal, the Quran index ~1 s).

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
pdfium 7947; 5.13's 7999 does not, see pdf-writing-rules.md, the *History* note under "Glyphs", and decisions.md D5) —
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

- Letters of words carrying vowel marks (never cut); see [letters.md](letters.md) for what is cut.
- Read on its own: labels come from the OCR half. See
  `experiments/04_label_once_purity.py` for the measurement that frames it:
  strict shape groups are 99.8% consistent, but two-thirds of a page's
  words are shapes that appear once.

## The code, file by file

| File | What it does |
|---|---|
| `src/inkscript/cli.py` | the ten subcommands (table below) |
| `src/inkscript/text.py` | Arabic text rules: runs/pieces, marks, `visual` (how text is stored) and `chrome_reads` (pdfium's line reconstruction, emulated) |
| `src/inkscript/ocr/azure.py`, `align.py`, `gemini.py`, `frontpage.py` | load Azure's JSON; fit Gemini's page-1 text into Azure's boxes; the Gemini calls and fallbacks; the older searchable-PDF path |
| `src/inkscript/geometry/trace.py` | page → ink blobs as outline polygons; rules separated |
| `src/inkscript/geometry/layout.py` | blobs → words → lines; `split_word`: a word's ink into pieces (and into letters when plans exist) |
| `src/inkscript/geometry/penpath.py` | the letter cutter: pen path, facts, atlas, cells ([letters.md](letters.md)) |
| `src/inkscript/geometry/letters.py` | the earlier column cutter; still supplies letter signatures, line geometry, piece masks |
| `src/inkscript/geometry/alphabet.py` | the document's shape alphabet (knowledge, never drawing) |
| `src/inkscript/pdf/native.py` | `build_document`: born-digital detection, the letters pass, the PDF pass, the report |
| `src/inkscript/pdf/type3.py` | writes the Type 3 fonts and text runs — every rule in pdf-writing-rules.md lives here |
| `src/inkscript/pdf/inspect.py`, `correct.py`, `fontfix.py` | read glyphs back from a PDF; write a corrected reading in place; rebuild junk fonts' ToUnicode (off) |
| `src/inkscript/verify/engines.py` | what `--verify` measures in pdfium |
| `src/inkscript/verify/consistency.py`, `numbers.py`, `second.py`, `review_html.py` | same-ink-different-text contradictions; Gemini second readings; the editable review page |
| `src/inkscript/viewer/frontpage_compare.py` | static review bundle for front pages |
| `src/inkscript/enrich/__init__.py` | `enrich()`: run after a build by `--xml`/`--trust`; `verify()`: schemas and trust-PDF checks |
| `src/inkscript/enrich/document.py` | Azure's reading as the enrich step sees it: words with ids (`p<page>w<n>`), boxes in scan pixels, the text the PDF carries, lines, paragraphs and their position roles; text-element offsets converted |
| `src/inkscript/enrich/quran.py` | Quran quotations found, linked to sura:verse, checked word for word (experiment 20); the Tanzil text in `src/inkscript/data/quran/` |
| `src/inkscript/enrich/trust.py` | one mark per word: verified / agreed / flagged with reasons (experiment 22's default rule) |
| `src/inkscript/enrich/jats.py`, `alto.py` | `<stem>.jats.xml` (JATS 1.4 Archiving) and `<stem>.alto.xml` (ALTO 4.4) |
| `src/inkscript/enrich/trustpdf.py` | `<stem>_trust.pdf`: highlights in an optional-content layer, incremental update; its check |
| `src/inkscript/enrich/schemas.py` | fetches and caches the official schemas; validates |

| Command | Needs | Gives |
|---|---|---|
| `inkscript fetch --id-file ids.txt --out DIR` | the `aws` CLI with credentials that can read `s3://mandumah-source-docs` (the owner's AWS profile; not in the repo) | `DIR/<id>/<id>.{pdf,json}` |
| `inkscript frontpage --azure-dir … --out …` | `GEMINI_API_KEY` in `.env` | page-1 reading per document (`<stem>.gemini.p1.md`) |
| `inkscript native --azure-dir … [--scan-dir …] --frontpage-dir … --out … [--vector] [--verify] [--xml] [--trust] [--resume] [--only ID]` | — | `<stem>.pdf`, `<stem>_vector.pdf`, `shapes.json`, alphabet, `native_pdf_report.json`; `--xml`: `<stem>.jats.xml`, `<stem>.alto.xml`; `--trust`: `<stem>_trust.pdf`, `<stem>_vector_trust.pdf` |
| `inkscript check OUT --out REVIEW [--html]` | — | contradictions and every number, as a review list |
| `inkscript numbers`, `inkscript second` | Gemini | second readings; `--apply` writes agreed corrections |
| `inkscript correct PDF corrections.json` | — | readings rewritten in place, logged in `<stem>.corrections.json` |
| `inkscript compare`, `trace`, `alphabet` | — | front-page review bundle; one page's outlines; alphabet saturation |

Without the bucket or keys, everything still runs on the bundled document
(`tests/fixtures/0582-004-009-012`). One test: `.venv/bin/pytest -q tests/test_pieces.py`;
the documentation checks alone: `.venv/bin/pytest -q tests/test_docs.py` (instant).

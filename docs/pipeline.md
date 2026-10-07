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
| Review | `inkscript.viewer` | outputs | `inkscript view` (the XML files in a browser, linked to the scan); static HTML bundles |

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
  quotation linked to its verse. The structure is read by `enrich/structure.py`
  (experiment 26, D22): page furniture by repetition and place (kept out of the
  text); notes as the small lines at the foot of a page that open with a number,
  each linked from its marker in that page's text (glued "عاصم(٢).", alone
  "(٢)", or raised) — endnotes in order through the text; headings by size,
  bold ink (stroke width measured on the scan), numbering, colon and space, a
  run of short numbered lines being a list; title and authors from Gemini's
  title file when `<stem>.gemini.title.json` sits beside the Azure JSON or in
  `--frontpage-dir` (aligned to Azure's words, whose ids the JATS lists), else
  from page 1's layout; volume/issue from the id (000 = none, `041,042` =
  41-42, 999 = special).
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

## Looking at the outputs: `inkscript view` (since 2026-10-07)

```
inkscript view OUT                         # http://127.0.0.1:8765/ — every document under OUT (any depth)
inkscript view OUT --doc ID --open         # straight to one document, in the browser
inkscript view OUT --host 0.0.0.0          # to read it on a phone on the same network
inkscript view OUT --static DIR --doc ID   # a folder that opens from disk (index.html), no server
```

A small web app (Python's own `http.server`, no library, nothing sent
anywhere; experiment 31) over the files `--xml` writes:

- **the list** of documents: title, authors, journal, year, pages, flagged and
  corrected words, Quran quotations; filter and sort;
- **Page**: the scan (rendered from `<stem>.pdf` — the faithful PDF, whose
  background is the scan — with pymupdf, cached in `~/.cache/inkscript/view`)
  with every ALTO word as a box. Pointing at a word shows its text, Azure's
  confidence, its trust mark and reasons, the other reading or the correction
  (the ALTERNATIVE), its Quran verse, its ids and its glyph in `shapes.json`.
  Switches tint flagged / corrected / verified words and draw lines, blocks or
  block roles (title, author, heading, footnote, page furniture);
- **Article**: the JATS as a right-to-left article — title, authors, rubric,
  facts, headings, paragraphs, note markers linked to the notes (and back),
  quotations with their sura:verse, references, the custom-meta;
- **Both**: the two side by side and linked. A click on a word of the article
  puts its box in the middle of the page and lights it; a click on a box puts
  the article's word in the middle. JATS has no word ids, so the viewer matches
  each block's words in reading order to the ALTO words of that block (the
  block ids link the two files, D20): 99.85% of the article's words on
  experiment 28's 205 documents, every non-furniture block placed;
- **XML**: both files as written, folded, with "go to id" (a word's card opens
  its `<String>` or its JATS element).

It is fast on long documents: a page and its words are drawn only when they
come near the view (48 pages: open 0.9 s, jump to page 40 in 0.2 s).

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

**From exact sources, judged on the ink (`inkscript fix`, experiment 27, D21).**

```
inkscript fix OUT/<stem> --azure-dir AZ [--scan-dir SCANS] --apply      # or OUT for every document in it
```

1. *Propose* (`enrich/corrections.propose`): each word of a Quran quotation
   that differs from its verse word by dots or letters gets the verse's word
   (its short vowels too when Azure's reading was vowelled; the word's
   punctuation kept). Not proposed: the author's wording, the print's
   spelling, quotation edges, splits (see D21). A merge (إلاماشاء) is proposed
   as one word's text with spaces (إلا ما شاء).
2. *Judge* (`enrich/judge.py`): Gemini 3.8 Flash sees the word's line on the
   300-dpi scan (paper behind the word tinted, nothing on the ink) and the
   printed reading and the proposal as A and B, blind; if it picks the
   proposal, Gemini 3.1 Pro is asked the same; both must agree. Answers are
   cached, every request's cost logged, nothing sent past `--cap`.
3. *Apply* (`--apply`): the accepted text goes into `<stem>.pdf` and
   `<stem>_vector.pdf` as above (the glyphs must read the printed reading
   first, or the correction is declined), the pages are rendered before and
   after and compared pixel for pixel, then `enrich` rewrites the ALTO (CONTENT
   corrected, the earlier reading an `ALTERNATIVE PURPOSE="azure-reading"`,
   `TAGREFS trust.corrected`, a Processing step), the JATS text and the trust
   PDFs (a green highlight in a "Corrected words" layer).

Statuses in `<stem>.corrections.json`: proposed → candidate → accepted →
applied, or rejected (the first judge kept the printed reading, saw neither,
or could not tell), disputed (Pro disagreed), declined (the PDF cannot take
it, D13). A rerun judges nothing twice and writes nothing twice; a rebuild
followed by `--xml`/`--trust` writes the applied corrections in again.

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
| `src/inkscript/cli.py` | the twelve subcommands (table below) |
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
| `src/inkscript/viewer/outputs.py`, `serve.py`, `app/` | `inkscript view`: reads a build's ALTO/JATS/PDF (pages, words, the article as HTML with each word linked to its ALTO id); the local server and `--static` bundle; the app (one HTML, one JS, one CSS, no library) |
| `src/inkscript/enrich/__init__.py` | `enrich()`: run after a build by `--xml`/`--trust`; `verify()`: schemas and trust-PDF checks |
| `src/inkscript/enrich/document.py` | Azure's reading as the enrich step sees it: words with ids (`p<page>w<n>`), boxes in scan pixels, the text the PDF carries, lines, paragraphs and their position roles; text-element offsets converted |
| `src/inkscript/enrich/quran.py` | Quran quotations found, linked to sura:verse, checked word for word (experiment 20); the Tanzil text in `src/inkscript/data/quran/` |
| `src/inkscript/enrich/trust.py` | one mark per word: verified / agreed / flagged with reasons (experiment 22's default rule; a common word at confidence ≥ 0.6 is not flagged for its confidence alone, experiment 27, list in `src/inkscript/data/lexicon/`) / corrected |
| `src/inkscript/enrich/corrections.py` | `inkscript fix`: corrections proposed from Quran verses, judged, applied; `<stem>.corrections.json`; `overlay` puts applied ones into the reading the XML is written from (experiment 27, D21) |
| `src/inkscript/enrich/judge.py` | the ink judge: Gemini, blind A/B on the scan's crop (experiment 17's marking), cached, spend-capped |
| `src/inkscript/enrich/structure.py` | the article's structure: furniture, title/authors (Gemini's title file aligned to the ink, or page 1's layout), headings, notes and their markers, journal name and year; `read_meta`, `id_parts` |
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
| `inkscript fix OUT/<stem>\|OUT --azure-dir … [--judge gemini\|none] [--apply] [--cap 1.0]` | `GEMINI_API_KEY` (unless `--judge none`) | `<stem>.corrections.json` (every proposal, verdict and write); with `--apply` the accepted ones in both PDFs' text, the ALTO, JATS and trust PDFs |
| `inkscript view OUT [--doc ID] [--port N] [--static DIR]` | — | the outputs in a browser: scan with every ALTO word, the JATS as an article, linked; both XML files |
| `inkscript compare`, `trace`, `alphabet` | — | front-page review bundle; one page's outlines; alphabet saturation |

Without the bucket or keys, everything still runs on the bundled document
(`tests/fixtures/0582-004-009-012`). One test: `.venv/bin/pytest -q tests/test_pieces.py`;
the documentation checks alone: `.venv/bin/pytest -q tests/test_docs.py` (instant).

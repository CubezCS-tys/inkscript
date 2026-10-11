# 35 · Every edition from the master files

**Question.** From the master files alone (JATS + ALTO; the scan only for pictures), can we generate every
derived edition an Arabic article needs — a reading web page for phones, an EPUB, a new print PDF that keeps the
page's layout, a one-column research-paper PDF, Markdown and a dataset record — and how close is the rebuilt print
page to the original? (Owner's new branch of the vision, 2026-10-11: any Arabic page rebuilt as a native digital
publication, like an English research paper.)

**Answer: yes, all six, for all 205 documents, and the rebuilt page keeps the original's blocks.** `inkscript
edition` ran on experiment 29's 205 masters (3,254 pages, 1932–2025) with 0 failures in 18 minutes on 2 workers
(peak 0.63 GB a worker; 513 MB of output, 300 MB of it the scan pictures). Read back from the finished files —
the PDFs through pdfium 5.12.1, as Chrome reads them:

| edition | printed words found | body words lost | printed twice | words in reading order |
|---|---|---|---|---|
| reading HTML | 880,523 / 880,617 (99.99%) | 28 | 67 | — |
| EPUB 3 | 880,523 / 880,617 (99.99%) | 28 | 67 | — |
| Markdown | 880,521 / 880,617 (99.99%) | 29 | 35 | — |
| dataset record (JSONL) | 880,511 / 880,617 (99.99%) | 33 | 33 | — |
| layout-faithful PDF (every ALTO word, furniture too) | 901,480 / 901,794 (99.97%) | 312 | 81 | 96.1% (median document 99.3%) |
| one-column PDF (digits left out: it renumbers notes and pages) | 824,855 / 825,314 (99.94%) | 387 | 166 | 93.6% (median document 99.0%) |

The rest of "found" are title and author words: the reading editions take the title from the catalogue (D25),
which sometimes words it differently from the page (66 words). Words out of order in the PDFs are almost all Latin
lines (English references) inside Arabic documents: they copy word-reversed, the price of marking the PDF right to
left (D18) that the faithful PDF pays too. EPUB: 21 of 21 checked (every tenth, plus fork B's 12) pass W3C
epubcheck 5.2.1 with no error or warning.

**The judge** (Gemini 3.1 Pro, the scan beside the layout-faithful rebuild; $0.39 of the $5 cap) on 36 stratified
archive pages: same blocks yes 33, mostly 3; same order yes 36; headings right 34, partly 2; overall 4/5 on 33
pages, 3 on 2, 2 on 1 (a landscape table printed sideways — see below). It never gave a 5. Calibrated on 9 rebuilt
pages with a fault put in on purpose: a paragraph left out caught 3/3, two paragraphs' texts swapped caught 3/3,
a heading set as body text caught 0/2 (plus one on a page it failed anyway). So its "missing" and "moved" are
evidence; its "headings right" is not.

Report with pictures: `out/report.html` (six archive articles side by side — scan, layout rebuild, one-column page,
phone — the judge's answers and what it caught, the hand-made table and maths tests, the engine bake-off).

## Method

`src/inkscript/edition/` (the command `inkscript edition MASTERS --out OUT [--doc ID] [--only …] [--workers 2]`):

| file | what |
|---|---|
| `model.py` | one article read from its JATS + ALTO into the shape every writer uses: front matter, body nodes in reading order (headings, paragraphs, tables, formulas), notes, references, verses; ALTO pages and blocks; each node tied to its blocks (`regions()` = where its ink is on the scan) and each block told what the JATS made of it |
| `html.py`, `scan.py` | the reading page: right to left, phone first, light/dark, bundled OFL fonts (Noto Naskh Arabic text, Markazi Text titles, subset WOFF), catalogue front matter, notes linked both ways, Quran quotations with their verse, tables `dir="rtl"`, MathML; every paragraph, heading, note and reference has a "view the original" button that shows its ink cut from the page picture by an SVG viewBox (one 120-dpi grey JPEG a page, loaded on click); Google Scholar `citation_*` and schema.org data |
| `epub.py` | EPUB 3 from the same renderer (XHTML), `page-progression-direction="rtl"`, notes as EPUB footnotes, MathML, fonts embedded, no scan pictures (230–300 KB) |
| `printpdf.py`, `pdftext.py`, `fonts.py` | both print PDFs with LuaLaTeX (below); `pdftext` rewrites the PDF's text layer so pdfium reads it in logical order |
| `data.py` | Markdown (YAML header, `[^note]`, ﴿…﴾ + tanzil link, HTML tables, `$…$` LaTeX) and the record (text exact and folded for search, metadata, sections, notes, references, Quran, tables, formulas, scan regions per paragraph, provenance: readers, trust counts, file hashes) |
| `check.py`, `build.py` | the checks on the finished files; the command |

**Layout-faithful PDF.** The faithful PDF's page size; every ALTO line set at its own place and width in its
block's size (from the line heights, so headings keep their relative size), bold for titles and headings, grey
for running heads and page numbers, justified where the print is, centred where it is; tables get rules from the
cell boxes; formulas typeset, or the scan crop. Line for line beat re-flowing each block: ink correlation with the
scan 0.58–0.88 against 0.27–0.71. Lines printed sideways (a landscape table on a portrait page: 9 pages of the
set) are turned — found by the judge, which had seen them as crumbs.

**Engine (D27).** LuaLaTeX (LuaHBTeX 1.17, HarfBuzz, babel's Arabic with kashida justification) for both PDFs,
against Chromium 153 (HTML → PDF), on 8 archive documents and the 2 test masters (`bakeoff.py`,
`out/bakeoff.json`): words found in pdfium, median, LuaLaTeX 99.9–100% vs Chromium 41–69% (its lam-alef comes
back as ال, spaces vanish, brackets turn); 1.5–6 s a document, 0.3–0.6 GB. Per-word /ActualText made pdfium run
lines together (80% in order) and was dropped; instead `pdftext.py` stores each line as the faithful PDF does
(glyphs left to right, a real space glyph at each gap, ligature mappings reversed, marks as outlines), and lines
sharing a band are written left to right (table rows). A document mostly in Latin script is not marked right to
left (3 English articles: 23% → 99.9% in order).

**Checks** (`check.py`, on the files as a user gets them): every ALTO word the master places in the article must
come out of each edition exactly once (tokens folded as for search; the layout PDF must carry every ALTO word,
furniture included; allowed extras are the text an edition adds — catalogue front matter, verses, labels); reading
order = share of the expected word sequence that comes out in order (LCS) plus inversions of neighbouring blocks.

**Judge** (`judge.py`, `sample.py`, `planted.py`): 36 pages drawn by stratum (first pages, footnotes, two
columns, table grids, Quran, headings, plain; seeded), plus the 3 hand-made pages and 9 planted faults; scan and
rebuild at 1,600 px, one JSON answer per page, temperature 0, cached by a hash of both pictures, spend logged
(`out/judge_spend.jsonl`).

**Hand-made test masters** (`tests/fixtures/edition/`, made by `testdocs/make_testdocs.py`). **Not archive
pages.** The 205 masters have no structured tables or equations; two small articles were written by hand in the
format of `32_open_stack/research/02_formats.md` — an XHTML table (header rows, merged cells, cells stored right
column first), display formulas as MathML `dir="rtl"` with `<tex-math>` and a scan crop in `<alternatives>`, an
inline formula — with a matching ALTO (tables as `ComposedBlock`, formulas as `Illustration`) and a "scan"
typeset in another font in Chromium and roughened. Both validate (JATS 1.4 DTD, ALTO 4.4 XSD). Every edition
renders them: tables right to left with merged cells, maths as MathML (HTML, EPUB), LaTeX-typeset (PDFs) or
`$…$` (Markdown); 148/148 and 177/177 words, formulas 3/3 and 1/1. Two corrections to 02_formats: `<processing-meta>`
goes before `<front>`, and JATS's XHTML `<table>` takes no `dir` (the direction comes from `xml:lang`).

```
PYTHONPATH=src .venv/bin/inkscript edition experiments/29_catalogue/out/merged --out experiments/35_edition/out/editions --workers 2
PYTHONPATH=src .venv/bin/python experiments/35_edition/summarise.py          # out/numbers.json
PYTHONPATH=src .venv/bin/python experiments/35_edition/sample.py; …/planted.py; …/judge.py [--go]
<playwright python> experiments/35_edition/shots.py out/report/shots out/editions ID:top …
PYTHONPATH=src .venv/bin/python experiments/35_edition/make_report.py       # out/report.html
```

## What is wrong

- Latin lines inside Arabic documents copy word-reversed from both PDFs (D18's price); Latin words with f-ligatures
  in the one-column PDF copy with two letters swapped (alhatif → alhatfi).
- Few kashidas (1–14 a document): lines are justified mostly by spacing; 15–25% of lines are squeezed by up to 4%.
- The judge does not see heading size or weight (0/2 planted).
- Archive tables are only boxes of words in the masters: no rules in the rebuild, short paragraphs in the reading
  editions. Pictures, rules and ornaments are not redrawn; a logo's lettering comes out as text.
- Inline formulas copy out of the PDFs jumbled; a tanween before a colon moves after it; Chromium does not mirror ∑
  in right-to-left MathML.
- Master quirks the editions show: note numbers glued to words, table numbers read as footnotes (0562, 2025),
  catalogue titles worded differently from the page.

## What it changed

`inkscript edition` (`src/inkscript/edition/`), D27 (LuaLaTeX, line for line, the text layer rewritten for
pdfium), a rule in `docs/pdf-writing-rules.md` (a Latin-script document is not marked R2L), STATUS and ideas
updated. Tests: `tests/test_edition_data.py`, `test_edition_html.py`, `test_edition_print.py`.

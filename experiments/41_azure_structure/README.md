# Experiment 41 — Azure's text, Gemini's structure, on whole articles; Argon or Flash?

**Question (owner-approved 2026-10-15).** Experiment 40's approach B — Gemini returns a page's structure as Azure line
ids and never retypes the text; strict fix rule v5 — was the most faithful on 11 pages. Does it hold up on ~50 whole
articles across decades and journals, and is `gemini-3.8-flash` as good as `gemini-4-argon` at it (about a third of the
price; the brief said half)? Can the outputs serve as training labels for our own specialists (layout, reading order, tables, footnote links,
whole-document metadata)?

**Status.** Done 2026-10-15. Gemini spend **$10.72 of the $20 cap** (160 calls, `out/gemini_spend.jsonl`): pilot $1.26,
Argon $6.00, Flash $2.32, repeat calls $1.14. Owner's report: `out/report.html` (`report.py`; not published by the
experiment). Hand-check pages: `out/handcheck/<stem>.html` (five articles).

**Answer.** The format holds up. On 399 pages (43 whole articles of 1–24 pages, 12 windows of long articles; 1932–2025,
54 journals) neither model lost a chunk, broke its JSON or ran out of tokens; of 17,137 Azure lines Argon dropped 1 and
Flash 4, none was used twice (but Argon threw 28 lines with words away as "noise", 26 of them the top half of one page;
Flash 17 short table cells). The text is Azure's, so nothing is invented; with Argon's fixes it is more faithful than
Azure alone: **1.55% of words wrong vs Azure's 1.80%** on 34 truth pages (owner gold 20 pages: 1.04% vs 1.36%;
born-digital 14: 2.19% vs 2.36%); Flash 1.77% (gold 1.32%). The two models build almost the same structure: line types
agree on 94.7% of 16,903 lines, reading order 99.5% of line pairs, tables TEDS 0.91 — Argon against itself on a repeat
call: 96.4% and 99.99%. **Argon for the edition** (fixes judged right by eye 34/40 vs Flash 27/40; on truth pages 41
closer / 18 further vs 13 / 10; better titles 37/41 vs 34/41 near-exact; on the three pages where the orders differ most,
Argon is right each time). **Flash for structure labels** at $0.0058 a page vs Argon's $0.0151, with its fixes not applied.

## Method

* **Sample** (`inventory.py` → `out/inventory.json`, all 931 local documents with PDF + Azure JSON; `choose_sample.py` →
  `out/sample.json`, the reason for each). Every experiment-40 sample document (whole if ≤ 24 pages, else a window of the
  sample page ± 2 with page 1 as context), every document with an owner gold page marked done (all 20 pages), five more
  born-digital documents (14 truth pages in all), more experiment-39 referee pages (29 of 44 inside), and fill for French,
  English, equations, tables, two columns, heavy footnotes. 41 of 55 have a catalogue master
  (`experiments/29_catalogue/out/merged/<stem>.jats.xml`).
* **Pipeline** (`structure.py`). Chunks of ≤ 10 pages (24-page articles in 3 chunks). Input: each page image (2400 px,
  media resolution high) and Azure's lines as `page:line [x0,y0,x1,y1 in 0-1000] text`. A later chunk also gets page 1's
  image, the outline so far and the last block of the previous chunk; a window gets page 1's image and lines (for the
  metadata). Output JSON: per page, blocks in reading order (title, heading + level, byline, abstract, keywords,
  paragraph, list item, reference, footnote + marker + id, verse with half-lines, quote, table rows/cells/spans,
  equation + LaTeX, caption, figure + box + description, header/footer, other), `continued` across page breaks, `calls`
  linking markers to footnote ids, `splits`, `noise`, `fixes` (Azure misreadings, strict v5 rule, applied and logged),
  `sic` (printed misprints, D30 `span.sic`, never applied), `math`, `missed` (`data-added`), metadata (strings copied from
  Azure; abstracts as line ids). Same prompt for both models, thinking low. Every answer saved on arrival (resumable).
  Assembly writes `out/<run>/docs/<stem>.html` (FORMAT.md, one section per page), `article/` (flowing view), `book/`
  (bookkeeping), `labels/` (training labels: every line with box, text, block, type, coarse label, level, order, verse
  half, table row/col/span; blocks with continuations, footnote ids, calls; metadata).
* **One change after the pilot** (5 articles, both models): a firmer footnote-call rule (Flash had linked none of 76
  footnotes on the poem); pilot outputs kept in `out/pilot_v1/`. **One deterministic step** added after scoring: table
  cells are ordered right to left (Latin tables left to right) from Azure's boxes, because both models gave the same
  table in either direction from one identical call to the next (TEDS 0.3 between repeats; 1.0 after).
* **Flash thinking medium** (pilot, 2 articles): no gain on the poem (still no footnote calls, +40% cost); on the 1930s
  ledger it thought 26,000 tokens and was truncated. Low it is. Thinking low used 0 thinking tokens on both models.
* **Scoring** (`score41.py` → `out/scores.json`): words wrong = 1 − F1 of word multisets vs the truth (exp 40's measure),
  text = every Azure line in the run's order with fixes (the edition text, with LaTeX in place of formula characters, is
  also reported: Argon 1.93%, because two born-digital linear-programming pages became LaTeX); reading-order CER; line
  bookkeeping; line types vs experiment 39's Pro referee (lines matched by box and text) and between runs; Kendall
  concordance of line orders; tables paired by lines, TEDS; footnote calls; continuations; metadata vs JATS; fix verdicts
  on truth pages. **By eye** (`sheets.py` → `out/sheets/*.png`, verdicts `out/judged.json`): 40 random fixes per model and
  40 of Argon's 176 / all 25 of Flash's misprint flags, each beside its printed line. **Noise**: five articles (52 pages)
  sent again identically to each model (`argon_r2`, `flash_r2`). **Pictures**: `render41.py` (headless Chromium, exp 40's
  venv) → `out/side/<stem>_pNNN.jpg` (scan | each model's blocks | each model rendered).

## Results (399 pages, same pages for both)

| | Argon | Flash | note |
|---|---|---|---|
| chunks failed (bad JSON / truncated / refused) | 0 of 67 | 0 of 67 | |
| Azure lines dropped / duplicated | 1 / 0 | 4 / 0 | of 17,137 |
| lines with words called noise | 28 | 17 | Argon: 26 on 0656 p4 (top half of the page) |
| words wrong, 34 truth pages (Azure 1.80%) | **1.55%** | 1.77% | gold 1.04 / 1.32 (Azure 1.36); born-digital 2.19 / 2.33 (2.36) |
| fixes applied; by eye right / wrong / unsure (40) | 1,134; 34 / 4 / 2 | 421; 27 / 9 / 4 | wrong = repairing printed misprints (المتعمون, لأساوب, ٨930 → 1930) |
| misprint flags; by eye right / wrong / unsure | 176; 30 / 5 / 5 (40) | 25; 20 / 4 / 1 | Flash flags some Azure misreadings instead of fixing them |
| line types vs Pro referee (29 pages, 1,245 lines) | 91.4% | 92.7% | without endnotes the referee calls references: 97.0% / 95.5% |
| footnote calls linked | 369 / 467 | 364 / 436 | most of the rest point to endnotes typed list/references |
| continued across page breaks | 188 | 190 | 172 first lines marked by both |
| metadata: title near-exact / authors found | 37/41, 38/43 | 34/41, 36/43 | vs catalogue masters |
| $ / page, s / page | $0.0151, 9.9 s | $0.0058, 6.2 s | $0.109 / $0.042 per article |

Between the models: types 94.7%, segmentation 98.2%, order 99.5% (112 multi-column pages 99.3%), 46 tables paired,
TEDS 0.91. Repeat calls: Argon vs itself types 96.4% (62 body lines became list items), Flash vs itself 98.9%. The
models disagree mostly on numbered paragraphs (list or body) and endnotes (footnote, list or references) — questions
of definition the prompt leaves open.

**Archive scale** (15.9 pages a document): Argon $15k per million pages, **$239k per million documents** Standard,
$120k Batch, doubling from 1 Dec 2026; Flash $5.8k / **$92k** Standard, $46k Batch, doubling from 1 Jan 2027. Prices
checked 2026-10-15 on ai.google.dev: Flash is $0.75 / $3.75 per million tokens (not $1 / $5), `common.py` corrected.

## Honest limits

34 truth pages; the referee is also a Gemini; fixes and flags judged by one reader from crops; repeats only on 5
articles; one run per model, so gaps under a point or two are noise. Windows are not whole articles; articles over 24
pages were not run whole.

## What it changed

* Approach B scales: whole articles, chunked, with metadata, footnote links and page-break joins, no failures, nothing
  lost but a page Argon wrongly called noise. Azure stays the text; Gemini only arranges it, and Argon's fixes make it
  better than Azure alone.
* Argon is the reader for the edition; Flash is good enough (and 2.6× cheaper) as the labeller for our own layout,
  order, table and footnote specialists, with fixes off. Before labelling at scale: define list vs body and endnotes in
  the prompt; reject any answer that calls a line with words "noise"; keep the box-based table cell order.
* Owner's hand check (2026-10-16): 0747 marked block by block, 183/183 right, no notes (`out/handcheck/marks/`);
  the other four (2382, 0877, 0924, 1140) checked by eye, no faults found (not marked block by block). Five articles
  is a small sample; the known gaps above were not hit by them.

## Formats to download (2026-10-16, no model calls)

**What.** Each of the 55 articles in seven files, linked under it on `out/views/index.html` with their sizes
(`out/views/formats/<stem>/`): **Scan PDF** (`inkscript native`, not vector: the scan itself, each word its own ink,
text selectable and searchable), **Layout PDF** and **One-column PDF**, **Web page**, **Markdown** and **JSON**
(`inkscript edition`), and the **JATS XML** master. No EPUB, no Word (owner). `masters.py` turns Argon's structure
and Azure's lines into the JATS 1.4 + ALTO 4.4 masters `inkscript edition` reads (mapping in its docstring): front
matter from the catalogue master when there is one (41 of 55), title and authors as printed; abstracts and keywords
stay where printed, as paragraphs; footnotes with linked calls (355); references; verse as `verse-group` with one
`verse-line` per half (338 halves in 226 verses); 47 tables cell by cell (1,305 cells; ALTO ComposedBlocks); 68
equations as MathML + LaTeX + scan crop and 82 inline formulas; 49 figures cropped from the 300 dpi pages; D30 flags
as `named-content content-type="sic"` with the proposed correction in `xlink:title` (174 placed), the printed word
kept; Argon's 1,134 fixes applied, each listed in `back/notes`, and Azure's reading kept as ALTO `ALTERNATIVE` where a
fix maps word for word. Lines Argon left out stay in the ALTO only, as `role.noise` (grey in the layout PDF): 172
noise lines, 41 of them with words (232 words; 26 lines are the top of 0656 p4) and 1 dropped line (20 words).
A window of a long article is cut to its pages and numbered from 1 in its masters and scan PDF. The scan PDF gets
Argon's fixes written into Azure's words where they map word for word (961 of 1,134).

    .venv/bin/python masters.py prep            # out/native_in/: Azure JSON + PDF per article (windows cut), 11 s
    out/native/run_all.sh                       # inkscript native --verify, 3 at a time, 4 threads each
    .venv/bin/python masters.py build           # out/masters/: JATS, ALTO, crops; 36 s
    .venv/bin/inkscript edition out/masters --out out/views/formats --only html,layout,onecol,md,jsonl --workers 2
    .venv/bin/python masters.py link            # scan PDF + JATS beside the editions; formats/formats.json
    .venv/bin/python masters.py check           # out/formats_check.json (+ formats_check/<stem>.json)
    .venv/bin/python views.py --index-only      # index.html with the download row

**Checks** (all 55; PDFs read back with pdfium 5.12.1). Edition's own `check.py` (every ALTO word the master places
in the article, once):

| format | printed words found | lost | twice | words in reading order |
|---|---|---|---|---|
| Web page | 131,218 / 131,218 | 0 | 52 | — |
| Markdown | 131,218 / 131,218 | 0 | 272 (figure captions repeated as picture alt text) | — |
| JSON | 131,218 / 131,218 | 0 | 3 | — |
| Layout PDF (every ALTO word) | 134,890 / 135,551 (99.5%) | 661 | 119 | 96.9% |
| One-column PDF (digits not compared) | 124,950 / 124,987 (99.97%) | 37 | 9 | 92.6% |

Of the layout PDF's 661, 466 are words the master keeps but the page shows as a picture (Azure's words of typeset
equations, words inside figures); most of the rest are table cells pdfium runs together (0924) and Latin maths.
The one-column order is lower because footnotes sit at each page's foot while the check expects them at the end
(0747, 76 notes in 8 pages: 63%). Formulas in the web page: 140 of 153 as MathML; 13 LaTeX strings latex2mathml
could not convert show as LaTeX code.
Against Argon's block text (our own count, `masters.py check`): JATS, web page, Markdown and JSON 0 words missing
of 131,231 (JATS 1: a checker artefact, the web page made from the same JATS has it); one-column PDF 37 of 124,994;
layout PDF 670 of 135,247 (as above). **Scan PDF**: on the 44 articles with scanned pages only, 329 of 107,251
words differ from Argon's text (0.3%: fixes that do not map word for word); `--verify`: 112,469 / 112,480 Azure words
intact, lines in order 11,160 / 11,161, every page keeps its image. **But** on the 11 articles with born-digital
pages, `inkscript native` keeps the publisher's own text layer there (its rule), and those layers are broken
(املفتاحية for المفتاحية, reversed English): 5,618 of 27,996 words (20%) do not come back.
JATS: 55/55 valid against the JATS 1.4 Archiving MathML3 DTD; ALTO: 55/55 valid against ALTO 4.4 XSD.
Spot checks rendered (0747, 2382, 0877, 0924, 1140): blocks, verse, footnotes, tables, equations and the figure all
in place.

**Faults found and fixed in `src/inkscript/edition/`** (`pytest -q`: 102 passed): figure and formula crops printed
as their file path in both PDFs when the masters folder was given as a relative path (LuaLaTeX runs in a temporary
folder; `model.load` now resolves it); the one-column PDF dropped printed front-matter lines that are not an author
(now printed, as the web page does); Latin headings were set right to left there and French words hyphenated so they
did not copy whole (no hyphenation in the one-column PDF now). Added: JATS `verse-line` read as a paragraph of class
"verse" (centred in the web page and the one-column PDF).

**Limits.** Abstracts and keywords are not in the JATS front matter (printing them in both places would double them
in every edition). Misprint flags are in the JATS but the editions show the printed word only. The one-column PDF
floats tables to the next page top. A byline that holds more than an author name (0747's "ضبطها وشرحها …") shows
twice in the web page header (as the author and as the printed line). Window articles count pages from 1.
Time: native 38 min for 399 pages (3 workers, peak 1.2 GB each, 4 threads); edition 5 min (2 workers, peak 0.49 GB).
Disk: `out/views/formats/` 295 MB, `out/masters/` 22 MB, `out/native/` 165 MB beyond the hard links (its
`*.alphabet.svg` and `*.shapes.json` are not used by the views), `out/native_in/` 48 MB.

## Files

`common.py` (exp 40's client: CAP $20, prices corrected) · `inventory.py` · `choose_sample.py` · `structure.py` ·
`score41.py` · `render41.py` · `sheets.py` · `handcheck.py` · `report.py` · `reader.py` (the owner's reading
edition of Argon's 55 articles, no model calls: `out/reader/index.html` library, `out/reader/<stem>.html` with metadata
header, page-break joins, KaTeX, figure crops, footnote popovers, misprint flags, a fixes toggle and scans beside the
text; 82 MB with 399 page scans). `masters.py` (the downloadable formats, above). `views.py` (the owner wanted the original beside ours instead, 2026-10-15; no model calls):
`out/views/index.html`; `out/views/pages/<stem>.html` page by page (scan left, our rebuild of exactly that page right,
footnotes at its foot; stacked on a phone); `out/views/mirror/<stem>.html` a born-digital twin (every Azure line set in
Scheherazade New at its own box, fitted to the box width; figures, KaTeX equations and table cells at their boxes;
"Blocks" outlines block types, "Overlay" lays the twin on the scan with an opacity slider); JPEGs hard-linked from
`out/reader/`; 89 MB. Outputs under `out/` (gitignored):
`sample.json`, `inventory.json`, `pages/` (300 dpi renders), `argon/`, `flash/`, `argon_r2/`, `flash_r2/`,
`pilot_v1/` (the pilot's argon, flash and flash_med outputs, prompt v1), `side/`, `reader/`, `sheets/`, `handcheck/`, `scores.json`, `judged.json`, `report.html`, logs.

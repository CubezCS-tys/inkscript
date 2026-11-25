# Experiment 99 — LiteParse against the extraction exam (a free baseline)

**Status:** done (2026-11-24). Free and local: no paid API, no GPU; no parse made a network connection.

## Question

The owner (2026-11-23, "go ahead and test it"): LiteParse (LlamaIndex, Apache-2.0, Rust core, Python package
`liteparse`) reads a PDF's own text layer with PDFium, runs OCR only where there is no text (bundled Tesseract, or its
own small "ocria-nano" models), and builds structure (headings, paragraphs, list items, tables) by rules. What does it
give, for free, on our extraction exam (experiment 97: 60 locked articles, 214 pages, settled answer keys)?
Pre-registered: **Q1** structure (P1 labels, P2 grouping, P3 order, P7 tables, P9 reference boundaries); **Q2** reading
for (a) the PDF's text layer, (b) Tesseract on the page image, (c) ocria-nano on the page image; **Q3** right-to-left
order; **Q4** cost; **Q5** 10 born-digital PDFs made from publishers' Word files.

## Headline (all 214 exam pages; n under each measure)

| Measure | LiteParse: text layer | text layer, Apache-only | Tesseract on image | ocria-nano on image | Baseline v1 (Azure + Gemini) | Key A vs key B | Pass mark |
|---|---|---|---|---|---|---|---|
| P1 label per line, all roles (n=10,124 lines) | 48.1% | 49.5% | 32.2% | 54.5% | 95.7% | 99.2% | ≥ 97% |
| P1, only roles LiteParse can name (n=6,786) | 71.6% | 73.6% | 47.7% | 81.0% | – | – | (diagnostic) |
| key text lines in no LiteParse block | 11.8% | 6.4% | 6.9% | 5.3% | 0.1% | 0.0% | ≤ 0.5% |
| P2 grouping, same-piece F1 | 67.9% | 75.4% | 17.4% | 76.4% | 99.6% | 99.9% | ≥ 95% |
| P3 order, one column (~850–895 pairs) | 99.3% | 97.6% | 96.4% | 99.8% | 99.1% | 100% | ≥ 98% |
| P3 order, two columns (~390–410 pairs) | 93.8% | 92.4% | 92.5% | 93.4% | 100% | 100% | ≥ 95% |
| P7 tables found (n=43) | 62.8% | 95.3% | 51.2% | 90.7% | 100% | 100% | ≥ 98% |
| P7 shape right, of found | 33.3% (27) | 43.9% (41) | 4.5% (22) | 48.7% (39) | 100% | 100% | ≥ 95% |
| P7 cells exact / folded (n≈1,000–1,600 cells) | 4.3% / 4.4% | 22.1% / 24.3% | 1.2% / 1.2% | 26.7% / 28.7% | 90.1% / 98.5% | 99.7% / 99.8% | ≥ 99.5% |
| P9 reference boundaries from list items (n=517) | 0.2% | 7.3% | 1.6% | 0.0% | 99.2% | 99.3% | ≥ 98% |
| P9 boundaries, list items + paragraphs (diagnostic) | 24.2% | 13.5% | 12.4% | 19.7% | 99.2% | 99.3% | – |
| R1 letters / words wrong, exact, as returned (584 lines) | 39.5% / 51.4% | (same text) | 54.7% / 72.0% | 11.2% / 35.6% | Azure 0.8% / 4.3%; t91 1.3% / 5.5% | – | ≤ 0.5% / ≤ 2% |
| R1 folded, punctuation ignored, as returned | 37.4% / 44.7% | (same) | 54.0% / 70.1% | 8.9% / 26.5% | Azure 0.6% / 2.3%; t91 0.7% / 2.6% | – | ≤ 0.5% / ≤ 2% |
| R1 same, after we put LiteParse's pieces right to left | 31.1% / 37.7% | (same) | 20.2% / 29.7% | 6.4% / 24.4% | – | – | – |
| Q4 pages / second; peak memory | 5.7; 1.2 GB | 16.7; 87 MB | 0.10; 0.7 GB | 0.58; 2.0 GB | – | – | – |

Every LiteParse mode misses every pass mark except one-column order (text layer 99.3%, ocria-nano 99.8%).
Full tables (per role, confusion, Q3, Q4): `out/scores/liteparse_scorecard.md`; every miss: `out/scores/misses_<mode>_<PART>.jsonl`;
line readings: `out/scores/r1_lines_<mode>.jsonl`; split by PDF origin: `out/scores/breakdown.json`.

## Method

- **Versions.** LiteParse 2.21.1 (pip, 2026-11-23) in its own venv `out/venv`, home, model and tessdata folders under
  `out/`; scripts in `scripts/`, run from `out/runs/`. Tesseract data: tessdata_best `ara` + `eng` (Apache-2.0) in
  `out/tessdata`. ocria-nano 1.0.0 + ONNX Runtime 1.31.1 (`lit models pull`, 58 MB, `out/models`). LiteParse's PDFium
  carries no version string; its API is a superset of our pinned PDFium 7947 (445 vs 425 `FPDF*` symbols, 20 newer,
  none missing: `out/logs/sym_*.txt`), so it is a **newer build than our pin**.
- **Options** were fixed before the exam run, from the docs and 5 dev articles outside the exam (`OPTIONS.md`,
  `DEV_STEMS.json`): text modes `ocr_enabled=False, extract_blocks=True, emit_word_boxes=True, num_workers=4`;
  Tesseract `ara+eng`, 150 dpi; ocria-nano 250 dpi (both defaults were best on dev). "Apache-only" = the same text
  run with the model folder empty (no LayoutNet table model, which otherwise runs whenever ocria-nano is installed).
  The exam was run once per mode (`scripts/run_lit.py`, one JSON per article in `out/runs/exam_<mode>/`).
- **Inputs.** All 60 source PDFs were already local (`experiments/96_layout3/out/gpu/pdflinks` → fetch folders of
  exps 43/52/70/74/33/34); nothing was pulled from S3. 147 exam pages are born digital (Word, InDesign, Distiller), 67
  are scans whose PDF carries an OCR text layer (ScanToPDF, Image2PDF …): every exam page has a text layer
  (`out/inventory.json`). OCR modes read the 300-dpi page JPEGs (`43_rehearsal/out/pages`), i.e. no text layer.
- **Lines matched.** Each LiteParse word box (72-dpi units, top-left origin) is scaled by the packet's width_px / page
  width (4.1667, checked by drawing both on 2 dev + 2 exam pages: `out/pictures/box_check/`) and given to the Azure line
  it overlaps most (≥ 30% of the smaller box); an Azure line takes the block holding most of its matched word area.
  Items listed in no block (LiteParse leaves table cells' `text_item_indices` empty) take the smallest block whose box
  holds them. **Found on the way:** 78 of 214 pages (the ScanToPDF files) have a crop box inside the media box, and
  their invisible OCR text sits offset from the ink by the crop origin (LiteParse reports the layer where it is;
  the layer itself is misplaced). For those pages only, the converter tries 7 shifts (0, ± the crop origin per axis)
  and keeps the one with most overlap with Azure's lines (`scripts/cropboxes.py`, `convert99.py`); before this, text-layer
  reading looked 51% wrong instead of 39%.
- **Scoring.** LiteParse is converted into the key formats (`convert99.py`) and scored with experiment 97's own
  `score97.run_part` → `compare_page` / `compare_tab` / `compare_refs` (imported, not copied or edited), exactly as key
  A is scored against key B. Pieces = blocks in LiteParse's order (its reading order). Tables: `header` (one row) +
  `rows`, cell direction from the cells' x. References: LiteParse has no notion of a reference, so P9 is boundaries
  only, from `list_item` blocks (pre-registered), and as a diagnostic from list items + paragraphs. R1: the truth is
  built exactly as `score97.score_r1` does (blind readers A = B, else third reader C; folded-only truths for folded
  scores; order-only and unreadable lines left out); the 365 lines where all three witnesses agreed take Azure's text
  as truth (the 60 blind-read controls had none wrong). Counted directly over 584 lines (Azure through this count:
  0.8% / 3.8%, t91 1.2% / 5.0%, matching exp 97's estimate). "As returned": a line's LiteParse items in LiteParse's own
  order (= its page text); "pieces right to left": the same items sorted right to left by us.
- **Role mapping** (LiteParse kind → key role): `heading`→heading, `paragraph`→paragraph, `list_item`→list-item,
  `table` / `merged_table` / `grid_fallback`→table, `figure`→figure, `code`→other, `page_header` / `page_footer`→running-head,
  `rule`→not text; no block → (no-block). **LiteParse cannot name**: title, translated title, byline, affiliation,
  abstract, keywords, front matter, quote, verse, footnote, endnote, reference, caption, equation, page number — 3,338 of
  the 10,124 key lines (33%) carry such a role, hence P1 is also given over the 6 roles it can name. No captions,
  table numbers, continuation flags, note calls or reference fields exist in its output (P6, P4 and P9 fields not scored).
- **Network.** No network namespace is allowed on this box (`unshare -n`/`-rn` refused). Instead: proxies pointed at a
  closed local port, `HF_HUB_OFFLINE`, `ORT_DISABLE_TELEMETRY=1`, no OCR server URL, and every run under
  `strace -f -e trace=connect` (positive control logged its connect). **Zero connect() calls** in all 17 runs (dev,
  exam, legacy): `out/logs/net_*.log`. The only downloads were the deliberate ones (pip, tessdata, `lit models pull`).
  LiteParse documents no telemetry; its binary holds download URLs only for tessdata (GitHub), ONNX Runtime (NuGet)
  and the models (HuggingFace).

## Result

**Q1 structure: far below the pipeline.** Best mode (ocria-nano) labels 54.5% of lines right (81.0% on the roles it
can name), groups at F1 76.4%, finds 90.7% of tables but gets only 48.7% of their shapes and 28.7% of cells (folded).
What goes wrong, in the order of lines lost (`liteparse_scorecard.md`, confusion): references are paragraphs (1,300–1,570
lines; LiteParse does cut them one paragraph per reference on clean pages, see the reference picture, but never
calls them references), abstracts are paragraphs, list items are paragraphs (list-item right 3.5–15%), page numbers
and some running heads fall in no block or into the footer, headings are found 26–44%. Order is fine on one column
(99.3–99.8%) and misses on two columns (92–94% against 95%). The Apache-only rules find more tables (95.3%) than the
run with LayoutNet (62.8%), and split them less wrongly; the model mainly helps running heads (0% → 56%). With
Tesseract the structure collapses (each word is an item; P2 17%).

**Q2 reading: only ocria-nano is near usable, and it is 10× worse than Azure.** Letters / words wrong, folded and
punctuation ignored: text layer 37.4% / 44.7%, Tesseract 54.0% / 70.1% as returned (20.2% / 29.7% once we reorder
its words), ocria-nano 8.9% / 26.5%; Azure 0.6% / 2.3%, our t91 0.7% / 2.6%. The text layer is bad for reasons of the
PDFs, not only of LiteParse: on born-digital pages 81 of 389 lines come back **twice** (the PDF holds the text twice; our
pinned PDFium 7947 returns both copies too), Word/InDesign Arabic fonts map lam-alef and ligatures wrongly
(«الكلامت املفتاحية»), one Distiller font returns garbage («ʽʰʡعة»); on scans the layer is someone else's OCR
(26% letters wrong) and 19 lines have none. Born-digital lines: 41.9% letters wrong as returned; scans: 26.1%.

**Q3 right-to-left order.** Inside one text item LiteParse returns logical order (no line was right only after reversing
its characters, in any mode). But a line made of several items comes back **left to right, i.e. visually reversed**:
137 of 170 such Arabic lines in the text layer, 359 of 362 with Tesseract (whose items are words: 79% of lines with all
words right have them in the wrong order; 54 lines are right only after reversing the word order), 45 of 47 with
ocria-nano (whose items are mostly whole lines, so it is hit least: 7 of 115). Word boxes inside an item are also listed
left to right. Putting the pieces right to left ourselves cuts letter errors from 37.4% to 31.1% (text layer) and
54.0% to 20.2% (Tesseract). This is the behaviour our PDFium pin exists to avoid; LiteParse bundles a newer PDFium and
assembles lines itself.

**Q4 cost** (nice 19, ≤ 4 workers): text layer 16.7 pages/s and 87 MB peak without the model, 5.7 pages/s and 1.2 GB
with LayoutNet; ocria-nano 0.58 pages/s, 2.0 GB peak, ~3 cores; Tesseract `ara+eng` 0.10 pages/s on one core (a page
image is one page, so the 4 page workers had nothing to share).

**Q5 legacy Word-made PDFs** (10 local `legacy/` PDFs from exp 53, seed 99, 328 pages, 29 s): text comes out (they are
LibreOffice PDFs with a good layer), but 1.0% of Arabic words carry junk letters where kashida glyphs stood
(«يمثflflل», 840 of 84,329 words; PDFium 7947 gives the clean word), multi-piece Arabic lines again come left to right
(1,976 lines left to right, 10 right to left), block text keeps control characters (\x1f), running heads are often
footers, and 90 tables are reported, many as `merged_table` fragments with split cells («مية الأغوار ال جنوبي»). Usable as raw
text after our own clean-up; not usable as structure.

**Licence of ocria-nano.** "OCRia-nano-1 Model License" (modified OpenRAIL-M, `out/models/ocria-nano/LICENSE`):
§1(n)(ii) "evaluating or benchmarking the Model, by any person or organization, including publishing the results" is
a permitted Research Purpose, so this test was allowed and was done. Production use is not: Attachment A 2(a)/(b)
needs a commercial licence above $2M revenue or $2M funding, and 2(c) forbids use "as part of, a Competing Service"
(document parsing / OCR / extraction competing with LlamaParse) "whatever Your revenue or funding". LiteParse itself
(and Tesseract's data) are Apache-2.0.

**What could not be done or verified.** No network namespace (strace observed, did not block). PDFium build number
unknown (only "newer than 7947"). R1 text-layer numbers include some line-matching error where one LiteParse item spans
two Azure lines (hanging-indent references) and on the 78 shifted ScanToPDF pages; P2/P1 for Tesseract are dominated by
word-sized items. Per-mode memory includes Python and the JSON copies, not LiteParse alone.

## Pictures (looked at; `out/pictures/`)

- `pages_<stem>_pNNN.png`, 8 pages (2 body, 2 two-column, 2 table, 1 references, 1 front; seed 99): key | Azure + Gemini
  | LiteParse text layer, lines filled by role, red frames where the key's role is not accepted. Seen: on the reference
  page every reference is its own LiteParse block, all called paragraph (31 red lines); on the two-column page with
  numbered items every list item is a paragraph, and the heading «فقه ابن تيمية» is in no block; on the front page of a
  scan the title is a paragraph and the Quran-verse quotes and many first lines are "figure"; on one table page the
  table is right as a table but its caption and the chart's caption are paragraphs and two chart tick labels are
  missed; the page number is never a page number.
- `lines_strip_1.png`, `lines_strip_2.png`, 12 exam lines: crop, truth, Azure, t91, LiteParse text layer, Tesseract,
  ocria-nano. Seen: Tesseract lines come back in reversed word order («من إليه كل أشارت ما وهذا ...»); the text layer
  shows the lam-alef swap («المقرر» → «املقرر») and split words («الديموج ارفية»); ocria-nano is closest but drops or
  changes letters («خلال» → «عخلال», «فترة» → «فز») and misses a digit («٣,٥٠» → «٢,٥٠»).
- `box_check/`: Azure boxes (green) and LiteParse word boxes (red) on 2 dev and 2 exam pages; the ScanToPDF exam page
  shows the text layer sitting low against the ink (the crop-box offset above).

## What it changed

Nothing in the pipeline. LiteParse is **not** a replacement for any stage on our Arabic journals: no role it lacks can be
recovered from it, its Arabic line order needs our own fix, and its best reader (ocria-nano) is 10× worse than Azure
and cannot be used in production under its licence. One finding carries over: 78 of the exam's 214 pages (all
ScanToPDF files) have an OCR text layer offset from the ink by the crop box, so any use of those PDFs' text layer
(selection, search, a "text layer first" route) must register it first.

## Files

- `OPTIONS.md`, `DEV_STEMS.json` — options and how they were chosen (dev only).
- `scripts/litrun.sh` (sandbox wrapper), `run_lit.py` (runner, LiteParse venv), `inventory.py`, `cropboxes.py` (repo
  venv, pinned PDFium), `convert99.py` (LiteParse → key formats), `score99.py` (scorer: `liteparse_scorecard.json/.md`),
  `analysis99.py` (`breakdown.json`), `pictures99.py` (Desk venv PIL + raqm), `check_boxes.py`, `dev_options.py`,
  `peek99.py`.
- `out/` (gitignored): `runs/`, `scores/`, `pictures/`, `logs/` (time, strace), `venv/`, `models/`, `tessdata/`.

Re-run: `scripts/litrun.sh exam_<mode> --py $PWD/scripts/run_lit.py --mode <mode> --set exam` (resumable), then
`nice -n 19 ionice -c3 /home/appuser/inkscript/.venv/bin/python scripts/score99.py`.

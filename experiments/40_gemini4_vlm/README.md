# Experiment 40 — how far can Gemini 4 alone take a scanned Mandumah document?

**Question.** Using only `gemini-4-argon` as a vision-language model (no Azure in the loop, no layout model),
what is the best way to turn our range of scanned Arabic journal articles into an excellent digital format —
text faithful to every mark, structure (headings, lists, footnotes linked to their markers, verse in two
half-lines, tables, LaTeX equations, figures, page furniture), reading order, positions — and what does it cost?
A pure exploration the owner asked for on 2026-10-15; several engineering agents each try an approach.

**Status.** Done 2026-10-15. Gemini spend **$13.34 of the $20 cap** (setup $0.004, A $2.53, B $1.98, C $2.96,
D $2.49, E $3.39; from `out/gemini_spend.jsonl`, 804 calls). Owner's report: `out/report.html` (built by
`report.py`; pictures of every approach, the accuracy dial, failures).

**Answer.** In one call per page or per article at about $0.018 a page (launch price), gemini-4-argon turns scanned
Arabic journals into well-structured documents far beyond Azure: block types right on 93–97% of lines (Azure 74%,
experiment 39's model 84.3% and dots.mocr 80.2% on the same 21 pages), real tables with merged cells, LaTeX that
renders, verse in half-lines, right-column-first order, footnotes linked across pages, article metadata, no
hallucinated passages, loops or truncation. Its text is about as accurate as Azure's (1.4–2% of words wrong, order
ignored; Azure 1.65%, dots.mocr 6.7%), better on born-digital pages, worse on the owner's gold scans (Azure 1.54%,
Argon alone 1.76–1.96%). It is **not exactly as printed**: it corrects misprints, adds hamzas, drops some printed
vowel marks and shaddas, normalises ه/ة, and identical calls differ by about a point. The most faithful text came
from Azure's words arranged by Argon (B, strict fixes: 0.83% on gold, 11 pages only).

## Method

* **Sample** (`choose_sample.py` → `out/sample.json`, images `out/pages/<pid>.jpg`, colour 300 dpi renders of the
  source PDF, the same pixel frame as every reference box). 25 pages: 5 of the owner's hand-corrected gold pages
  (34_yardstick, status done), 4 born-digital pages whose PDF text is the truth (36's bd set), and pages chosen for
  equations (3), tables (2), poetry (2), heavy footnotes (1), vowelled Quran (1), two/three columns (2), degraded
  pre-1960 print (2), mixed French/English (2), a front page (1). 21 of the 25 are experiment 39's layout test pages
  (every Azure line labelled by a Gemini Pro referee). All have Azure's lines (36 `out/ref/azure`) and Kraken's.
  Three short whole documents (`out/docs/<stem>.pdf` + Azure JSON) for whole-document approaches:
  `2382-005-003-001` (9 pages, equations/tables), `0747-001-003-001` (8 pages, vowelled verse and footnotes),
  `0197-002-001-003` (4 pages, plain; holds gold page p003).
* **One output format** for every approach: semantic HTML per page (or per document, one
  `<section class="page" data-page="N">` per page) — [FORMAT.md](FORMAT.md).
* **One client** (`common.py`): every call through `gemini()`, experiment cap **$20** (worst case refused before
  sending, threads counted), per-approach sub-caps (`subcap=("a1_", 3.0)`, `spent("a1_")`), cache, spend log
  `out/gemini_spend.jsonl` with tokens and seconds, whole-PDF input (`pdf=`). Price checked 2026-10-15 on
  ai.google.dev: $2 / $10 per million input / output tokens until 2026-11-30, **$4 / $20 from 2026-12-01**
  (the client switches by date).
* **One scorer** (`score.py out/<approach> [--pages sample|docs|all]`): (a) faithful/folded CER vs the truth
  (gold, born-digital) and vs Azure (agreement); (b) invented / dropped words per 1,000 vs Azure outside tables
  (experiment 36's anchoring; invented also unexplained by Kraken); (c) block types vs the referee's line labels
  (by text and by box); (d) word order (36's concordance), all pages and multi-column pages; tables (TEDS) and
  equations vs the gold files' Gemini 3.1 Pro drafts (agreement); (e) dollars and seconds per page from the log.
* **Pictures** (`render.py out/<approach>`): each HTML rendered in headless Chromium (Scheherazade New, KaTeX),
  `out/<approach>/side/<pid>.jpg` = scan | scan with the HTML's boxes coloured by block type | rendered page.
* **Baseline** `azure_baseline.py` → `out/a0_azure/`: Azure's lines in the format (free). Scored on the sample:
  CER vs gold 0.62% (flattered: the gold was corrected from Azure's draft), vs born-digital 2.7%; block types
  agree with the referee on 74% of lines (Azure has no list, verse, reference or equation kinds).

## Files

`common.py` client and paths · `choose_sample.py` · `score.py` · `render.py` · `azure_baseline.py` · `FORMAT.md`.
Outputs under `out/` (gitignored): `sample.json`, `pages/`, `docs/`, `src/` (the sample documents' PDF + Azure
JSON from S3), `a0_azure/`, one folder per approach, `venv/` (Playwright 1.64.0 for render.py).

## Approaches (2026-10-15)

| | approach | $ / page | words wrong, 9 truth pages (gold 5) | layout vs referee | notes |
|---|---|---|---|---|---|
| a0 | Azure's lines in the format (`azure_baseline.py`) | paid | 1.65% (1.54%) | 74.0% | baseline |
| A | one page image → one HTML page (`A_oneshot.py`; thinking low, ultra-high media) | 0.018 | 1.72% (1.96%) | 96.8% | thinking high ×3 cost, no gain; settings within run-to-run noise |
| B | Argon groups Azure's line ids into blocks; HTML built from Azure's text (`B_azure_anchored.py`) | 0.020 | 1.47% (1.32%); strict fixes v5 1.27% (0.83%) | 96.8% | 0 of 1,855 lines lost; 16% of v1's fixes wrong (author's spelling "corrected"), v5 7% |
| C | whole article PDF → one edition with metadata (`C_whole_document.py`) | 0.018 | 1.44% (1.86%) | 93.2% | heading levels 10/10 vs 6/10 page by page; 143/144 footnotes linked; no truncation at 19k tokens |
| D | draft → zoomed re-read of every region → page check (`D_agentic.py`) | 0.016–0.045 | strict draft 2.32%, all passes 2.09% (2.31%) | 92.9% | the strict "printed marks only" prompt halved errors (4.38% → 2.32%); passes add little |
| E | C + D's strict prompt + fixes, chunks for long articles, then a two-of-three vote (Argon, Azure, blind zoom) on disputed words (`best.py`) | 0.022 | 1.39% (1.76%) | 96.3% | 188/188 footnotes linked (22-page 0870 in 3 chunks); vote changed 89 of 971 words, some for the worse |

Words wrong = order-free word error vs the truth (D_subset.py's measure; both orders of tanween+alef counted the
same). E, C and B are a tie on 9 pages. Table (0.54–0.57 vs Azure 0.20, 4 tables) and equation scores (3 equations)
cannot rank the approaches; they are agreement with Gemini 3.1 Pro drafts.

A reviewer re-ran the scorer on every saved output (all quality numbers reproduced) and recomputed all 804 spend
rows. Corrections it made, applied in the report: C costs $0.0183 a page (not $0.0177); E's equation gain was how
leader dots were written; E's "lowest word error" is a tie; E's vote also wrote ة where the print has ه, cut زيادة to
يادة and flipped number pairs to Azure's order; D's and E's prompt rules were tuned on failures seen on the same 9
truth pages.

## What it changed

* Argon is ahead of every layout reader we have (experiment 39's model, dots.mocr) on block types and reading
  order, and the whole-article call adds metadata, heading levels, footnote links and joined page breaks for free.
* It does not replace Azure as the text: the faithful text layer still needs Azure (B-style anchoring) or another
  independent reader. Argon's language sense repairs the print, and a vote with Azure lets shared mistakes through.
* No word coordinates and no confidence: inkscript's ink PDFs still need Azure's boxes.
* Archive cost at E's $0.022 a page for ~15.9M pages: $353k Standard / $176k Batch until 2026-11-30, double after.
* Open: a larger truth set before choosing between A, B, C and E; pictures; articles over 22 pages; style.

Additional files: `A_oneshot.py`, `A_compare.py`, `A_golddiff.py`, `B_azure_anchored.py`, `B_fix_sheet.py`,
`C_whole_document.py`, `C_position.py`, `D_agentic.py`, `D_subset.py`, `best.py`, `E_report.py`, `report.py`.
Each approach's notes are in `out/<approach>/notes.md`.

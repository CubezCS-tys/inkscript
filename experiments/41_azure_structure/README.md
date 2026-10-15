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
* Owner's hand check pending (`out/handcheck/`).

## Files

`common.py` (exp 40's client: CAP $20, prices corrected) · `inventory.py` · `choose_sample.py` · `structure.py` ·
`score41.py` · `render41.py` · `sheets.py` · `handcheck.py` · `report.py`. Outputs under `out/` (gitignored):
`sample.json`, `inventory.json`, `pages/` (300 dpi renders), `argon/`, `flash/`, `argon_r2/`, `flash_r2/`,
`pilot_v1/` (the pilot's argon, flash and flash_med outputs, prompt v1), `side/`, `sheets/`, `handcheck/`, `scores.json`, `judged.json`, `report.html`, logs.

# 38 · Our own document parser: Azure's words in a model's layout, on the hardest pages

**Question (owner, 2026-10-12).** Azure's text is what we have for more than a million documents. Take it as the
words and use models for everything else (layout, reading order, columns, tables, equations, pictures, correction
"with understanding"): can that rebuild the hardest pages as native documents that are clearly better than the
current pipeline's editions (experiment 35), while keeping the text at least as accurate as Azure? Start with the
hardest pages, "to see if this is even useful".

**Answer (2026-10-12): partly yes.** The owner's page is `out/report.html` (main checkout): every hard page as
scan | old | new, the judge's words, the correction examples good and bad, tables and formulas beside their crops,
the pictures placed, the numbers and the spot-check.

- **Layout: better.** A blind judge (Gemini 3.1 Pro: the scan and the two layout-faithful rebuilds in a random
  order) preferred the new page on **18 of 33** hard pages (55%, Wilson 38–70%), the old on **4** (12%, 5–27%),
  tie on 11; closeness 3.79 vs 3.36 of 5. On the 9 plain gold pages: new 3, old 1, tie 5. A Claude reviewer who
  looked at all 44 pages by eye: new better on **28**, the same on 13, old better on **3** (all three table pages:
  0200, 0691, 0924); scores new layout 3.98, old layout 3.40, new one-column 3.34. What the new pages bring back:
  the **pictures** (15 placed; the old editions drop them), **typeset formulas** (19; the old garbled them), **ruled
  tables** (15), columns kept apart, list labels.
- **Text: Azure's, kept.** Every one of the 13,481 Azure words was placed exactly once (44/44 pages; 7 leftovers
  given blocks of their own, 17 kept as the text inside pictures). Against Azure on the 35 non-gold pages **no Azure
  word is lost** (word-bag missing 0.00%); 1.4% extra are dots.mocr's table cells Azure had no words for, marked as
  such. On the 9 gold pages the order-free word error is Azure 5.4% [2.6–8.2], new 5.5% [2.8–8.2]. Characters wrong
  in reading order rise from 0.65% to 5.5%, but almost all of it is one page (0355, two columns) where the gold
  keeps Azure's lines that run across both columns, so the right column-by-column order counts as an error; without
  it 0.60% → 0.96% (a picture label read into the picture on 0041, a few lines reordered).
- **Correction with understanding: not good enough; do not switch it on.** Gemini 3.8 Flash on each block's crop
  proposed 423 changes; the fixed rules applied 324. On the gold pages each change was scored on its line against
  the truth: **right 30, wrong 34, neutral 2** (precision 45%, 34–57%); word errors on those lines **85 before, 89
  after**; 4 of 9 pages got worse. It restores hamzas Azure added (right) but also adds hamzas old prints never had
  (وانما → وإنما, فانه → فإنه), "fixes" the author's own misprints (المتعمون → المتعلمون), splits printed joins, and
  modernises ى → ي (a title on 0465 now reads «في» where the page prints «فى») — exactly what the rules forbid.
- **Tables: the grid is dots', but Azure's words in it made them worse.** Judged blind against the crop, the new
  tables (Azure's words poured into dots.mocr's grid) score **2.8 of 5 vs 3.4** for dots.mocr's own HTML (better 1,
  worse 7, the same 7, n = 15): cells built by position merge or shift, and a row's text is sometimes put in the
  wrong cell. In the layout PDF they look better than the old (rules, rows) on most pages, but three table pages are
  worse than the old by eye.
- **Formulas: better.** Gemini 3.1 Pro checked each of dots.mocr's 19 formulas on its crop: 13 kept, 6 changed
  (5 fixed, 1 redone); judged 3.89 vs 3.47 for dots' LaTeX (better 6, worse 0). All 19 converted to MathML.

## Pages (`pages.py` → `out/pages.json`)

44 pages, inference only (nothing was tuned on them): 35 of the hardest yardstick pages, chosen by kind from
experiment 34's tags and dots.mocr's block categories — tables 8 (+3 equation pages with tables), equations 8 (two
of them with no old edition: one where dots read a displayed formula as text, one with nine matrix formulas),
magazines/decorative pages/pictures 8, footnotes 2, Latin mixed in 3, vowelled and Quran 4, old print 2 — every one
but those two with an experiment-35 edition of its document; and the **9 gold pages done** at the time of the run
(all "body" pages: no gold table or equation exists yet).

## Method (the parser, `experiments/38_parser/`)

| step | file | what |
|---|---|---|
| layout + words | `parse.py` | dots.mocr's blocks (experiment 36's raw outputs, scaled to the page), categories, reading order. Each Azure word goes to the block covering most of it (≥ 1/5), else the nearest within half a line height, else a leftover block of its own next to its nearest block. An Azure line across two blocks (two columns) is split by its words. A dots block with no Azure word keeps dots' text only where Kraken saw ink (1 block). Tables: Azure's words cut into segments at wide gaps, matched to dots' cells by text, the rest placed by row/column bands; a cell takes only segments that touch; a dots cell whose words Azure already has in its row stays empty (27); dots' left-to-right cell order is turned to reading order when the page shows it (6 tables). Pictures cropped in colour from the faithful PDF; captions tied to the nearest picture or table. |
| formulas | `formulas.py` | one Gemini 3.1 Pro call per formula: crop + dots' LaTeX → kept / fixed / redone; number split off as the label; MathML by latex2mathml (installed into `.venv`). |
| correction | `correct.py` | one Gemini 3.8 Flash call per block (per table), crop + Azure's lines; rules fixed before any page was seen: the words must be found, confidence ≥ 0.8, ≤ 3 words, no vowel-mark-only change, no deletion of words, one Azure line (added after a table cell built from two places was "joined" into one tall word). Every proposal logged with before, after, kind, reason, confidence and status; Azure's word kept in ALTO `<ALTERNATIVE PURPOSE="azure">`. |
| masters | `master.py` | JATS 1.4 + ALTO 4.4, one master per page, in the editions' id scheme (`p1b`, `p1t…c`, `p1eq`, `p1f`): sections from headings, `<list>` items with their label, `<fn-group>`, `<table-wrap>` (crop + XHTML in `<alternatives>`, dots cells `content-type="vlm-text"`), `<disp-formula>` (MathML + tex-math + crop), `<fig>` with caption and crop. Front matter from experiment 29's master. Valid against the official schemas 44/44 + 44/44. |
| editions | `editions.py` | experiment 35's `build_one` on each master (44/44, no error); renders scan, old page, new page, three-way and one-column pages. |
| measures | `measure.py`, `summary.py` | `inkscript score`'s `score_page` for Azure as is, Azure in the new layout, after correction and dots alone; an order-free word-bag error; each correction scored on its line against the gold; bootstrap and Wilson intervals. |
| judges | `judge.py` | blind side-by-side (scan, old, new shuffled per page) and tables/formulas against the crop, all Gemini 3.1 Pro. |
| report | `overlay.py`, `make_report.py` | blocks and reading order drawn on the scan; `out/report.html`. |

**Kraken as the net.** Of Kraken's 2,249 lines on these pages, 5 lie in no block (text the layout missed), 48 Azure
lines lie on no Kraken line (mostly tiny marks, page furniture and table digits), and no dots-only text lacks ink.

**src/ changes (worktree only, the edition tests pass).** `inkscript edition` learnt figures and list labels:
`model.py` reads `<fig>` (picture, caption) and `<list-item>` labels and ties a figure to its ALTO Illustration
(`p<n>f<k>` ids); the layout PDF draws the picture's crop where it was printed and skips the text inside pictures
and formulas (roles `pictureText`, `formulaInk`); the one-column PDF, the reading page, Markdown and the dataset
text carry the figures with their captions.

## What is wrong (the spot-check, 44 pages, 166 faults: 7 blockers, 41 major, 118 minor)

- **Tables**: 13 table faults (4 blockers): text drawn twice at a huge size in a few cells (0691, 0924, 0200, 0460-009),
  cells shifted or merged (judge: 7 of 15 worse than dots' own text), one-column tables running off the left edge
  (0200, 0562, 0827, 2025). Old still reads best on 0200, 0691, 0924.
- **Reading order on the one-column page** (8, 3 blockers): columns read in reverse or interleaved on 0465, 0478,
  0596, 0781, 0732; a poem's half-lines all right then all left (0747).
- Running heads and footers (28, minor), stray characters (22), font sizes (18), **bold** (13: bold quotations and
  headwords lost; dots gives no inline bold), Latin laid out right to left on the one-column page (9; D18's price),
  small ornaments blown up as pictures on the one-column page (0299, 0690, 1911), a picture's label read into the
  picture (0041), page number misread by Azure kept (0474: 26 for 36).
- Formulas: X ~ N(μ, Σ) as "X-M(2)" in the text (an inline formula: Azure's words, 1147).
- The correction step (above).

## Spend

Gemini **$3.08** of the $6 cap (`out/gemini_spend.jsonl`): corrections $2.26 (Flash, 601 calls), formulas $0.13 (Pro, 19),
judges $0.69 (Pro, 87 calls). Superseded judgements (before the table fixes, and the first table-judge prompt that did not say
cells may be listed in either direction) are kept in `out/superseded/`. GPU: none.

## What it changed

- D29 in `docs/decisions.md`: the parser keeps Azure's words and takes layout, tables' grid, formulas and pictures
  from the models; model correction stays off.
- `inkscript edition` places figures and list labels (above).
- STATUS and ideas updated.

## Next

1. Tables: keep dots.mocr's cell text where its grid and Azure disagree, and use Azure's words only to confirm
   (or Kraken/Azure to check digits) — the judge prefers dots' own cells; fix the one-column table width.
2. One-column reading order: follow dots' block order there too (the layout page already does).
3. Correction: only with a far stricter target (Azure's own low-confidence words, against a second reading such as
   amad-vlm6 or Kraken, never hamza/ى on pre-1980 prints), and measured on more gold pages before any use.
4. Bold: from the ink (stroke width) per word, since dots gives none.
5. More gold pages with tables and equations, so these can be scored against truth, not a judge.

## Files and outputs

Code: `common.py`, `pages.py`, `parse.py`, `formulas.py`, `correct.py`, `master.py`, `editions.py`, `overlay.py`,
`measure.py`, `summary.py`, `judge.py`, `make_report.py`. Outputs (gitignored, main checkout,
`/home/yassine/inkscript/experiments/38_parser/out/`, 180 MB): `pages.json`; `pages/<pid>/` (layout.json,
formulas.json, corrections.json, measures.json, crops/, master/ = the JATS + ALTO + scan PDF, edition/ = every
edition, shots/ = scan, old, new, three-way, one-column, overlay; `master_raw/`, `edition_raw/`, `shots_raw/` on 7
pages: the uncorrected test builds); `measures.json`, `summary.json`, `judge_sides.jsonl`, `judge_objects.jsonl`,
`spotcheck/<pid>.json`, `gemini_spend.jsonl`, `gemini_cache.jsonl`, `report.html`, `report_files/`, `superseded/`.

```
V=/home/yassine/inkscript/.venv/bin/python          # run from experiments/38_parser/ (common.py puts this worktree's src first)
$V pages.py; $V parse.py; $V formulas.py; $V correct.py; $V master.py; $V editions.py; $V overlay.py
$V measure.py --force; $V judge.py sides; $V judge.py objects; $V summary.py; $V make_report.py
```

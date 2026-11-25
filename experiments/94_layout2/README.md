# Experiment 94: layout, stage 2 — finer types, reading order, our own line finder

**Question (owner's go, 2026-11-09).** Experiment 92 (stage 1) showed what our layout tools do without Azure's page
structure: lines typed 90% right, reading order at 79.6% of Argon's steps (Azure 90.5%), and our own line boxes costing
the frozen reader +1.79 points of letters. Can a layout model retrained on Argon's fine roles, reading-order rules, and a
dedicated line finder close those gaps?

**Caps:** GPU $12, no Gemini, S3 egress ≤ 15 GB. The reader is frozen (experiment 89's v7-28M, `FINAL_READER.json`).

**Status: done (2026-11-09). GPU $6.91 of $12 (one RTX 5090, $1.27/h, 5.4 h), Gemini $0, S3 egress 0 GB** (every
page was already on disk). **Goals 1–3 miss their exit lines; only "missed lines ≤ 1%" passes.** Tables' reading order
is the one big gain (40% → 72% of Argon's steps).

## Pre-registered exit criteria (written 2026-11-09, before any test)

The test set is experiment 92's: 457 held-out pages, 23 journals (`92_layout/out/pages92.jsonl`, `ref92.jsonl`),
scored with experiment 92's conventions (lines Argon types "other" are left out of typing; order is Kendall tau and
"successor kept"; the reader test is `e2e92.py`'s, judged lines of experiment 81, pages bootstrapped 1,000 times).

1. **Finer block and line types.** A layout model retrained on Argon's fine roles over ~30,000 training-pool pages.
   - **Line typing ≥ 93%** against Argon, on experiment 92's coarse labels (the fine prediction folded to the eleven
     labels, so the number is comparable with round 2's 90.0%). The fine-label accuracy is reported too, without a
     threshold.
   - **Author/affiliation ≥ 85%**: of the lines whose reference is author or affiliation (Argon's byline, split by
     matching Argon's own metadata, below), the share predicted exactly (author as author, affiliation as affiliation).
   - **List precision ≥ 75%** (lines predicted list that Argon calls list).
2. **Reading order** on our own boxes (the line finder's boxes, typed by the layout model), against Argon's order,
   successor kept:
   - **two-column pages ≥ 95%**; **table pages ≥ 85%**; **all pages ≥ 90.5%** (Azure's own order).
3. **Our own line finder.** The frozen reader on our cuts vs Azure's cuts, experiment 92's end-to-end test, judged
   lines, letters wrong:
   - **PASS only if the upper end of the paired 95% interval of (ours − Azure) is ≤ +0.05 points** (non-inferiority).
     The point estimate is reported either way.
   - **Missed lines ≤ 1%**: share of truth lines (judged + agreed, Arabic) that no own box covers (`e2e92`'s "missed").
4. **Word boxes from the reader** (report only): word boxes from the frozen reader's CTC alignment on Azure's line
   cuts, against Azure's word polygons: mean IoU and share matched at IoU ≥ 0.5, on a sample of test lines.

**Reference caveats, fixed in advance.** Argon's "byline" holds both authors and affiliations; the split is made by
fuzzy-matching each byline line against Argon's metadata (`authors[].name` vs `authors[].affiliation` and its parts),
with a keyword fallback (جامعة, كلية, قسم, University, …), and is hand-checked on a sample of test lines before
scoring. Page numbers are header/footer lines with digits and no letters. Keywords lines fold into abstract.

## Rules kept

- No training on held-out journals (`76_finetune_pilot/out/split76.json`), locked journals or locked documents
  (`88_truth_and_lock/locked_old.py`), or any document of experiment 92's test set: asserted in code before training.

## Method

**Training pool (`build94.py train` → `out/train94.jsonl`).** Experiment 76's inventory: every answered article
(first copy) whose Argon raw files are on disk, of journals outside split76's held-out list, not locked (both guards),
no document of experiment 92's test set (all asserted). Pages usable as in experiment 92 (Argon blocks, ≥ 5 Azure
lines, ≥ 80% placed by Argon): **37,096 pages, 1,829 documents, 389 journals**; 3% of documents (54, 1,057 pages)
held out for validation. Every PDF and Azure JSON was already on local disk: **no S3 egress**. Line labels:
2.02 M Azure lines; fine types body 906k, table 520k, reference 201k, list 113k, header 71k, abstract 38k, page number
34k, heading 45k, caption 45k, footnote 15k, verse 8k, title 5.9k, author 5.6k, affiliation 3.7k, equation 2.5k;
directions: upright 2,010k, turned clockwise 8.4k, anticlockwise 5.1k, upside down 67.

**Reference for the fine types (`build94.py ref` → `out/ref94.jsonl`).** Experiment 92's reference plus each line's
fine type. Byline split checked by hand on all 102 test byline lines (`out/byline94_all.json`,
`out/byline94_hand.json`): 4 clearly wrong (a name called affiliation, a place called author, a source note, a
heading), 11 lines carry a name and a post or place together (either label is defensible); 94 of 98 clear lines right.

**Models (GPU host, `host94.sh`, `prep94.py`, `yolo94.py`).** Both start from experiment 39's round-1 weights
(DocLayout-YOLO, AGPL-3.0, internal use as in experiment 39), settings as experiment 39 (no mosaic, no flips, no
rotation augmentation), pages rendered at 1,536 px on the long side with pypdfium2 5.12.1.
- **Layout model:** 16 classes (`common94.FINE`), one box per Azure line, imgsz 1,280, batch 8, 2.5 h (8 epochs).
- **Line finder:** 4 classes = text direction (upright, turned clockwise, upside down, turned anticlockwise), imgsz
  1,536, batch 6, 2.5 h (5 epochs), on the real pages plus 7,548 synthetic copies (whole page turned 90° — 2,915; 1–4 lines on
  a dark band with light ink — 1,826; on a mid-grey band — 1,098; dotted leaders drawn beside short lines — 1,709).
- 41 pages with ≥ 300 lines were left out of training (`cap94.sh`): batch 16 ran the 32 GB card out of memory in
  the first minutes, and the box assigner's memory grows with the largest page of a batch.

**Reading-order rules (`order94.py`, developed on 600 DEV pages only: `orderdev94.py` → `out/orderdev94.json`).**
Azure boxes and Argon's types on the validation documents. Successor kept:

| rule set (dev) | all | single | two-col | tables | footnotes |
|---|---|---|---|---|---|
| experiment 92's XY-cut | 72.4% | 96.0 | 93.8 | 39.4 | 93.5 |
| + tables and verse read row by row as atoms | **89.7%** | 96.9 | 93.8 | **81.5** | 93.5 |
| + footnotes after the body | 89.5% | 96.9 | 93.8 | 81.5 | 90.2 |
| + header / page number out of the flow (no footnote rule) | 89.1% | 95.6 | 93.8 | 80.7 | 95.1 |
| all four (+ vertical gutters cut before horizontal gaps) | 89.0% | 95.6 | 93.4 | 81.0 | 94.6 |

Frozen before the test: **XY-cut + table/verse atoms read row by row** (rows = lines chained by vertical overlap,
so a tall header cell joins its row; cells = lines chained by horizontal overlap inside a row, right to left; lines in
a cell top to bottom), direction from the script. The other rules did not help on dev pages and were dropped.

**Word boxes (`words94.py`).** 400 Arabic lines of the test pages, Azure's cut (experiment 92's crops); the network
reads the crop flipped (`train89.LineSet`), which the mapping must undo.

Two lowered or raised XY-cut thresholds were also tried on dev (vertical gutter 0.3 or 0.2 line heights instead of
0.5; horizontal gap 0.6): no gain (`out/orderdev94.json`).

**Line cuts (`cut94.py`, `read94.py`, `e2e94.py`).** Own boxes at conf ≥ 0.25 (experiment 92's threshold),
de-duplicated, each turned into a 4-point polygon in its reading frame from its direction class, cut exactly as
experiment 92 (250 dpi, `cut_line(test=True)`, 48 px). A deskew variant (page tilt from the ink of wide boxes) was
compared on 150 DEV pages first (agreed lines, 5,049): plain +0.185 points (CI +0.10 to +0.29), deskewed +0.190 →
**plain boxes kept** for the test.

## Results (457 test pages, scored once)

| goal | measure | stage 1 (exp 92) | **stage 2** | exit | verdict |
|---|---|---|---|---|---|
| 1 | line typing, coarse labels | 90.0% (round 2) | **91.5%** | ≥ 93% | FAIL |
| 1 | author/affiliation exact (102 lines) | — (byline 50% as "heading") | **38.2%** | ≥ 85% | FAIL |
| 1 | list precision | 47.5% | **74.7%** | ≥ 75% | FAIL (by 0.3) |
| 2 | order, all pages (successor kept) | 79.6% | **86.3%** | ≥ 90.5% | FAIL |
| 2 | order, two-column pages (104) | 80.1% | **81.6%** | ≥ 95% | FAIL |
| 2 | order, table pages (59) | 40.4% | **71.5%** | ≥ 85% | FAIL |
| 3 | reader, ours − Azure, judged lines | +1.79 (+1.29 to +2.43) | **+1.20 (+0.79 to +1.70)** | upper CI ≤ +0.05 | FAIL |
| 3 | missed lines (judged + agreed, 13,241) | — | **0.79%** (judged alone 1.98%) | ≤ 1% | PASS |
| 4 | word boxes from the reader (400 lines) | — | 92% of Azure words matched horizontally | report | — |

### Goal 1: types (`score94.py` → `out/score94.json`, `out/lines94.jsonl`)

- Coarse 91.5% (17,485 lines; round 2 of experiment 39 on the same lines 90.0%). By layout: two-column 96.1%, single
  92.7%, footnotes 91.9%, tables 80.6%. Fine labels (16 classes): **90.8%**.
- Biggest confusions (coarse): **table → verse 492 lines** (glossary-like two-column tables, `out/look/0407-017-002-023_p007.jpg`;
  the row-by-row order still reads them right), list → body 256, body → list 198. List precision rose from 48% to 75%,
  recall 70%.
- Fine recall: body 97%, page number 97%, footnote 96%, verse 95%, reference 92%, caption/figure 86%, heading 80%,
  header 80%, table 79%, abstract 78%, list 70%, **title 68%, author 38%, affiliation 39%, equation 0% (18 lines)**.
- Authors and affiliations: 48% of them are called author or affiliation at all; the rest go to caption (14), title
  (9), heading (7), body (5). There are only 5.6k author and 3.7k affiliation lines among the 2 M training lines, and
  the test's bylines are mostly old-print "بقلم الأستاذ …" lines that look like headings. The reference itself is soft
  here (11 of 102 lines hold a name and a post together).

### Goal 2: reading order (`score94.py`)

| method (successor kept) | all | single | two-col | tables | footnotes | Latin pages (44) |
|---|---|---|---|---|---|---|
| **ours: own boxes, own types, frozen rules** | **86.3%** | 96.9 | 81.6 | **71.5** | 97.3 | 76.8 |
| own boxes, experiment 92's XY-cut | 79.7% | 96.3 | 81.4 | 40.0 | 97.3 | 71.2 |
| Azure's boxes, our types, frozen rules | 85.6% | 96.4 | 81.4 | 71.1 | 93.1 | |
| Azure's boxes, Argon's types, frozen rules | 85.9% | 96.4 | 81.1 | 73.1 | 93.1 | |
| (Azure's own order, experiment 92) | 90.5% | 96.1 | 96.6 | 68.7 | | |

- **Tables are now read better than Azure reads them** (71.5% vs 68.7%); typing is not the limit (Argon's own types
  give 73%).
- **Two columns did not move.** The dev pages had 94% already; the test journals' columns are the hard kind:
  narrow gutters where justified lines nearly touch across the gutter, so no clean white gap exists, plus pull-quotes
  and pictures inside the columns (`out/look/0549-000-347-005_p002.jpg`: a three-column page read across the rows).
  A cut on white gaps between boxes cannot see such a column; a column finder on aligned box edges, or a learned
  next-line scorer, is needed.

### Goal 3: our own line finder (`e2e94.py` → `out/e2e94.json`, `out/e2e94_lines.jsonl`)

| truth | lines | Azure's cuts | our cuts | ours − Azure (95% CI) | missed lines |
|---|---|---|---|---|---|
| judged (experiment 81) | 2,067 | 1.84% | 3.05% | **+1.20 (+0.79 to +1.70)** | 41 (1.98%) |
| judged, without 0097 | 1,698 | 1.21% | 2.10% | +0.89 (+0.50 to +1.29) | |
| agreed | 11,174 | 0 | 0.43% | +0.43 (+0.31 to +0.57) | 64 |
| DEV pages (other journals), agreed | 5,049 | 0 | 0.19% | +0.19 (+0.10 to +0.29) | 13 |

- Line finding at conf 0.25: 97.2% of Azure's lines matched one to one, precision 98.0% (round 2 of experiment 39:
  96.9% / 98.3%).
- **Where the letters go (judged):** missed lines +0.91 points, one-to-one cuts +0.25, split +0.02, merged +0.03.
  By layout: two columns +0.24, footnotes +0.77, single +1.53, tables +3.98; by era: pre-1950 +1.42, 1950–99 +0.73,
  2000+ +1.99.
- **What is still missed** (pictures looked at): text turned to an angle that is none of the four directions (chart
  axis labels at 45°, `out/look/0097-036-000-004_p037.jpg`, 13 lines on one page); short labels inside diagrams and
  the second line of a turned caption (`out/look/0108-000-019-003_p009.jpg`); 0097's pages again hold most misses
  (44 of 105).
- The line finder took a third off experiment 92's gap (+1.79 → +1.20). The dotted fill-in page of experiment 92
  (0097-038-001-006_p009) now loses 1 of its 33 truth lines (3 more are merged with a neighbour fragment); the remaining misses are mostly turned figure text, which the
  four direction classes and the whole-page turns of the synthetic data do not cover.

### Goal 4: word boxes from the reader (`words94.py` → `out/words94.json`)

400 Arabic lines, 3,879 Azure words, 3,866 reader words; the word count agrees on 89% of lines. Horizontally the
reader's words sit where Azure's do: **92% of Azure words matched one to one at x-overlap ≥ 0.5**, mean best x-IoU
0.81 (67% ≥ 0.8). As boxes, 82% matched at IoU ≥ 0.5 and mean IoU 0.57, because the reader's box spans the cut's full
height and Azure's word box is tighter (`out/look_words94.jpg`). One bug found on the way: the network reads each crop
flipped (`train89.LineSet`), so frame t sits at the crop's right end; mapped the other way the IoU was 0.37.

## What it changed

- Nothing in `src/`. The reader stays frozen.
- **Kept:** the layout model (`out/gpu/run_lay/best.pt`, 16 fine classes) replaces experiment 39's round 2 for typing
  (91.5% vs 90.0%, list precision 75% vs 48%); the line finder (`out/gpu/run_line/best.pt`) replaces it for lines
  (reader gap +1.20 vs +1.79); reading order = experiment 92's XY-cut with tables and verse read row by row.
- **Not yet:** our own boxes still cost the reader about one point of letters on judged lines; Azure's lines stay
  the input for anything that ships.

## Stage 3 (proposal)

1. **Turned and figure text** (most of the remaining reader gap): rotated-box training (oriented boxes, or a
   per-region angle head), with synthetic text at any angle, not only 90°; a "figure text" decision (keep or drop
   chart labels) agreed with the owner, since Argon itself types them caption.
2. **Columns:** a column finder from aligned box edges (left and right margins that repeat down the page), then the
   XY-cut inside each column; and a learned next-line scorer on Argon's order over the 37,096 pages (CPU), compared
   on dev before the test.
3. **Bylines:** byline data from the catalogue (author names per document are known), so author lines can be found
   by matching names; then one more layout round with author/affiliation up-weighted.
4. **Table vs verse:** add the glossary-like two-column tables to training with their Argon label, or merge the two
   classes for order (both are read row by row already).

GPU for 1 + 3: about $5 (left in this cap: $5.09).

## Files

- Code: `common94.py`, `build94.py`, `order94.py`, `orderdev94.py`, `prep94.py`, `yolo94.py`, `host94.sh`, `cap94.sh`,
  `gs94.py`, `cut94.py`, `read94.py`, `e2e94.py`, `score94.py`, `words94.py`, `look94.py`.
- Outputs (gitignored) in `out/`: `train94.jsonl` (+ `train94_stats.json`), `ref94.jsonl`, `byline94_*.json`,
  `orderdev94.json`, `pred94_lay.json`, `pred94_line.json`, `pred94_line_val.json`, `gpu/run_lay/`,
  `gpu/run_line/` (weights, results.csv, training logs), `score94.json`, `lines94.jsonl`, `e2e94*.json`,
  `words94.json`, `goals94.png`, `look/` (three panels: Argon | our types and order | line finder and missed lines).

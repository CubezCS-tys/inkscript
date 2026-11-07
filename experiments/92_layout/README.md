# Experiment 92: layout, stage 1 — where we stand without Azure's page structure

**Question (owner's go, 2026-11-06).** Our line reader (experiment 89's v7-28M) still needs Azure to find the lines and
to give the page its structure. How far do the tools we already have get on their own? The tools are experiment 39's
layout model (DocLayout-YOLO fine-tuned on Mandumah line boxes, rounds 1 and 2), Azure's paragraphs, and the "rivers
of paper". Four things are measured separately: (a) typing and grouping blocks, (b) reading order, (c) line finding,
including the end-to-end reader test, and (d) mastheads. Then: what fails, and what stage 2 should be.

**Status: done (2026-11-06). $0:** local CPU, niced, at most 2 cores; no GPU, no Gemini, no S3.

## Test set (`build92.py`)

- **457 pages**, 113 articles, 23 of experiment 81's 26 held-out journals (`split76.json`). Every page has Argon
  structure (experiments 41/43 and 74, through experiment 76's inventory), and **403 of them were also in experiment
  81's test**, so its judged lines give truth for (c).
- **Strata.** Era: pre-1950 34 pages, 1950–1999 241, 2000+ 182. Layout, from Argon's types and Azure's boxes: single
  column 240, two columns 104, tables 59, footnotes 54. Journal 0097 is capped at 140 pages and every article at 12.
  44 pages are mostly Latin (English or French).
- **Locked journals and documents** (`84/locked.py` and `88/locked_old.py`) are asserted absent in every script.
  **Every document with a page in experiment 39's training or validation data was excluded**, so the layout model
  never saw these documents. It did see other documents from 13 of these journals.
- **Unit:** Azure's 17,999 non-empty lines. Argon placed 17,873 of them; each gets Argon's block, its type and its
  rank in Argon's reading order.

**The reference is a model output too.** Argon edits Azure's lines and orders Azure's line ids, so its order leans
towards Azure's. I looked at 30 pages by eye: 8 single-column, 8 two-column, 7 table and 7 footnote pages, 1,261
lines (`out/spot30.json`, `out/look/spot_*.jpg`).
- Types: about 43 lines (3%) are doubtful. A full page of body text is called a list item (likely a list item
  continued from the previous page), 16 bulleted lines are called paragraphs, and 4 book-information lines under a
  title are called page header.
- Order: no errors on those 30 pages. One error was found elsewhere: a two-column reference list read left column
  first (0355-000-002-006_p024).
- So list vs paragraph is the softest part of the reference.

## Results

### (a) Block typing and grouping (`score92.py` → `out/score92.json`)

Typing uses experiment 39's eleven labels. 16,872 lines are typed; Argon's "other" lines are left out, as experiment
39 did.

| method | all | single | two-col | tables | footnotes |
|---|---|---|---|---|---|
| Azure (prebuilt-read: paragraphs plus a rare 'title' role, so effectively "everything is body") | 62.2% | 64.6 | 85.6 | 11.8 | 71.5 |
| exp 39 model, round 1 | **88.6%** | 88.5 | 94.3 | 77.6 | 91.2 |
| exp 39 model, round 2 | **90.0%** | 86.0 | 93.4 | 91.9 | 87.7 |

- **By label, round 2 (round 1).** The figures are recall; precision is in brackets where it matters.
  - furniture 92% (92%), precision 99%;
  - table 94% (77%);
  - body 92% (95%);
  - verse 86% (90%);
  - footnote 84% (96%);
  - list 84% (75%), **precision only 48%**;
  - heading 77% (74%);
  - references 73% (79%);
  - caption 64% (58%);
  - equation 17% (0%), on 18 lines.
- **Fine types inside "heading", round 2:** title 85%, section heading 82%, **byline (author and affiliation) 50%**.
- **Biggest confusions, round 2:** body → list (763 lines), references → list (139), table → verse (101), heading →
  body (73). Round 1 calls tables verse 460 times. Much of body → list sits on list-like pages, such as catalogue
  entries, where Argon itself is soft.
- **Grouping.** Argon's blocks are scored on consecutive pairs (is there a block break?):

  | method | F1 | precision | recall | Argon blocks reproduced exactly |
  |---|---|---|---|---|
  | Azure paragraphs | 0.71 | 0.56 | 0.95 | 82% |
  | our own lines (round 1 + a gap/indent rule) | 0.57 | 0.44 | 0.82 | 56% |
  | rivers | 0.21 | — | — | 8% |

  The rivers' blocks are white-space islands, often several paragraphs, so they do not match Argon's paragraphs.
- **Missing from the model's label set.** It cannot say title vs heading, author vs affiliation, abstract, page number
  vs running header, or figure. Those types exist only in Argon's labels.

### (b) Reading order

Each method is compared with Argon's order: Kendall tau per page (mean), and "successor kept", the share of Argon's
line-to-next-line steps the method also takes (strict: one misplaced line breaks two steps).

| method | all: tau / kept | single | two-col | two-col + footnotes (32 pages) | tables |
|---|---|---|---|---|---|
| Azure's own order | 0.968 / **90.5%** | 0.992 / 96.1 | 0.957 / 96.6 | 0.982 / 98.0 | 0.868 / 68.7 |
| our XY-cut on Azure's boxes | 0.941 / 78.7% | 0.991 / 95.7 | 0.908 / 81.1 | 0.963 / 94.0 | 0.755 / 38.7 |
| our XY-cut on our own boxes (round 1) | 0.940 / 79.6% | 0.992 / 96.6 | 0.901 / 80.1 | 0.952 / 93.1 | 0.750 / 40.4 |
| rivers' blocks | 0.889 / 82.5% | 0.989 / 95.9 | 0.639 / 80.7 | 0.605 / 76.6 | 0.834 / 56.6 |

- The XY-cut (`common92.xycut_order`) cuts at the widest white gap, horizontal or vertical. Columns are read right to
  left, or left to right when the page's Latin letters outnumber its Arabic ones. Always reading right to left costs
  the 44 Latin pages: two-column tau falls from 0.90 to 0.82.
- **Single-column and footnote pages are solved** by geometry alone: 96–98% of steps kept.
- **Tables are the big loss.** Argon reads a table row by row; the XY-cut reads it column by column (40% of steps
  kept).
- **Two columns lose about 15 points against Azure.** Three causes, each seen in pictures:
  - **columns that start at different heights** (a heading over one column only), where the widest-gap cut slices
    across the columns (0355-000-002-006_p024);
  - **Latin pages**, where the direction is known only from the script;
  - **rotated (landscape) tables**, where the model also misses the turned caption lines (0097-035-000-001_p027).

### (c) Line finding and the end-to-end reader test (`cut92.py`, `read92.py`, `e2e92.py`)

**Line finding.** The model's own boxes are matched one to one with Azure's lines, greedily by IoU ≥ 0.5, after
class-agnostic de-duplication.

| model | conf | recall of Azure's lines | precision |
|---|---|---|---|
| round 1 | 0.25 | 95.9% | 98.6% |
| round 2 | 0.25 | 96.9% | 98.3% |
| round 2 | 0.1 | 97.9% | 97.3% |

**The decisive test.** The final reader (v7-28M, weights sha-checked) read 17,996 Azure cuts and 17,510 cuts from
round 1's own boxes. Both were cut the same way: a 250-dpi render, `cut_line(test=True)` at 48 px, and an upright
4-point polygon for our boxes. Round 2's read was stopped to save time; its detection is scored above. Letters
wrong count every letter, without punctuation (experiment 81's form). Arabic lines only.

| truth | lines | Azure's cuts | our cuts | difference (95% CI, pages bootstrapped) | lines wrong: Azure's → ours |
|---|---|---|---|---|---|
| exp 81's judged lines | 2,067 | 1.84% | 3.63% | **+1.79 (+1.29 to +2.43)** | 35.1% → 38.4% |
| judged, without 0097 | 1,698 | 1.21% | 2.39% | +1.18 (+0.69 to +1.73) | |
| agreed lines (Azure = reader on Azure's cut) | 11,174 | 0 by construction | 0.96% | +0.96 (+0.75 to +1.21) | 0 → 4.5% |

The judged lines are experiment 81's sample, which over-samples hard lines and is not re-weighted here. So the
absolute level is high; the paired difference is the measure.

**Where our cuts lose letters (judged lines, points of letters):**
- **missed lines** (no own box covers the line; 53 of 2,067 lines): **+1.25**;
- one-to-one cuts that read worse: +0.42;
- split lines: +0.11;
- merged lines: +0.01.

By layout, judged: two columns +1.08, footnotes +1.10, single +1.95, tables +5.2 (wide CI). By era: pre-1950 +0.79,
1950–1999 +1.45, 2000+ +3.25.

**Verdict: not yet.** Our boxes find 96–97% of the lines and could carry the reader on clean single-column print,
but on these pages they double the letters wrong. Two thirds of the loss is lines the model never boxes: dotted
fill-in lines, dark bands, rotated text, small marginal lines. The rest is looser upright boxes on tilted or curved
lines (Azure gives a rotated polygon). A line finder has to close both before it replaces Azure.

### (d) Mastheads and running headers (`masthead92.py` → `out/masthead92.json`)

**Candidates.** 16,017 test-page lines with at least 4 letters, so page numbers alone are out.

**Methods.**
- **The repetition rule** is experiment 90's `masthead90.py`, unchanged. Its pools are every page of all 144
  held-out articles on disk, by issue and by journal. It found 2,064 repeated band lines.
- **The layout model** counts a line when its label is furniture.

**Hand check.** I looked at 72 lines, up to 12 per agreement pattern of (rule, round-1 model, Argon), using
`out/look/mast_grid_*.jpg` and `out/masthead92_hand.json`. I also looked at 24 band lines that all three left
unflagged (`mast_band_*.jpg`): none was a masthead.

**Results.** Precision and recall below are the hand verdicts weighted to all candidates.

| method | precision | recall | F1 |
|---|---|---|---|
| repetition rule | **99.5%** | 74% | 0.85 |
| model round 1, furniture | 93% | 81% | 0.86 |
| model round 2, furniture | 97% | 80% | 0.88 |
| **rule or round 2** | **97%** | **97%** | **0.97** |
| Argon header/footer (reference) | 98% | 100% | 0.99 |

**What each method misses:**
- **The rule misses:**
  - pools too small to repeat (journals 0549, 0656, 0407 have few articles on disk);
  - journal 0097's calligraphic footer, which Azure reads differently on every page, so its text never matches;
  - alternating headers in small issues.
- **The model misses:** 0097's footer on its dark band (on some pages) and English running heads; its 12 own
  false alarms (round 1) are signatures, table titles, section labels and article titles.
- **Argon:** of its 12 header lines that neither tool flags, 8 are real (0097 footers, column rubrics such as «اعرف
  وطنك»); 4 are display article titles.
- **Owner's decision applied:** detect and mark. The union of the two is the stage-1 detector; its text comes from
  the catalogue.

## Gap analysis (pictures in `out/look/`, each looked at)

1. **Types the owner needs, but the model was never taught:**
   - title vs heading;
   - author, affiliation and abstract;
   - page number vs running header;
   - figure regions.

   Bylines are right only 50% of the time as "heading". Argon has all of these on 40,000+ pages.
2. **List vs paragraph.** This is the model's worst confusion (list precision 48%) and also the reference's softest
   point. Catalogue and glossary pages (0656-014-004-008_p002) are list-like either way.
3. **Tables.**
   - Typing is fine in round 2 (94%).
   - Reading order is wrong by construction: cells go column by column instead of row by row.
   - Round 1 calls two-column tables "verse".
4. **Two-column order.**
   - Columns that start at different heights need a column finder before the XY-cut (the rivers' gutters are the
     natural one).
   - Latin pages need their direction from the reader's script.
5. **Line finding failures** (see (c)):
   - fill-in-the-blank lines with dotted leaders (0097-038-001-006_p009: the model boxes 12 of 20 lines);
   - text on dark bands;
   - rotated pages;
   - display titles drawn as pictures, which Azure misses too (0549-014-157-007_p001).
6. **Equations:** 18 lines in the set, which is too few to judge (round 2: 17%).

## Stage 2 proposal (with costs)

Costs assume a datacenter RTX 5090 at about $0.85/h, as in experiments 39 and 89.

1. **Retrain the layout model on Argon's labels at scale.**
   - About 30,000 pages from non-held-out, unlocked journals, with Argon's fine types:
     - title, heading level, byline split into author and affiliation by matching Argon's metadata text;
     - abstract, keywords;
     - header / footer / page number;
     - footnote, reference, list, table, caption, figure box, equation.
   - Two heads: lines, and block regions (the union of each block's lines).
   - **No Gemini (the labels exist); GPU about 8–10 h, $7–9.** That is just over today's $8 cap, so either one round
     at about 6 h ($5) or a cap of $10.
   - Exit: ≥ 93% line typing on this test set, byline ≥ 85%, list precision ≥ 75%.
2. **Reading order without a model first ($0, CPU):**
   - columns from the rivers' gutters before the XY-cut;
   - page direction from the reader's script;
   - tables row by row using the model's table cells.

   Then, if needed, a small learned "next line" scorer trained on Argon's order over the same 30,000 pages (CPU or
   under 1 GPU hour, < $1). Exit: two-column steps kept ≥ 95%, tables ≥ 85%.
3. **Line finding:**
   - a dedicated line detector at higher resolution, trained on Azure's line polygons over the same pages, plus
     synthetic dark-band and dotted-leader lines (experiment 84's renderer), and a page-rotation check;
   - **GPU about 4 h, about $3.5.**
   - Exit: the end-to-end reader on our own cuts within 0.05 points of Azure's cuts.
4. **Mastheads:** ship rule ∪ layout model now ($0). In production the pool is the whole issue from the catalogue,
   which fixes the rule's small-pool misses.

**Total for stage 2: about $12 GPU, $0 Gemini, S3 egress about 15 GB to fetch the 30,000 pages' scans.**

## What it changed

- Nothing in `src/`.
- For the layout track it sets the baseline: what is solved (single column, footnotes, furniture, table typing), what
  is not (tables' order, two-column order, fine types), and what our own boxes cost the reader today (+1.8 points of letters on judged lines, mostly missed lines).
- The masthead detector for the understander is rule ∪ model.

## Files

- Code: `common92.py`, `build92.py`, `yolo92.py`, `score92.py`, `masthead92.py`, `cut92.py`, `read92.py`,
  `e2e92.py`, `look92.py`.
- Outputs (gitignored) in `out/`:
  - `pages92.jsonl`, `ref92.jsonl`;
  - `yolo92_r1.json`, `yolo92_r2.json`, `rivers92.json`;
  - `lines92.jsonl`, `score92.json`;
  - `masthead92*.json`;
  - `own92.jsonl`, `crops48/`, `read/`;
  - `e2e92.json`, `e2e92_lines.jsonl`;
  - `look/` (three-panel pictures: Argon reference | our model's lines and order | rivers).
- `out/venv`: torch CPU + doclayout-yolo 0.0.4 (AGPL-3.0, as in experiment 39; internal use).

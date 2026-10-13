# 39 — Ink as geometry, and rivers of paper (2026-10-12)

**Question.** The owner, thinking about how to "attack" a document: what does the traced ink geometry (the
"liquid round the letters", `src/inkscript/geometry/trace.py`) look like on very different pages, and can the
white space between the ink, the "rivers of paper", find a page's columns and blocks without a model?

**Method.** Seven pages (the fixture and experiment 38's pages: vowelled, magazine, Quran, table, equations,
two columns) traced with `trace.page_blobs`, redrawn from the outlines alone and compared dot by dot
(`look.py`, `report.py`). Ten pages run through `rivers.py`:
- Ink is smeared sideways so each line becomes a bar.
- Tall thin channels of paper (at least 8 lines tall) are column gutters.
- Flat channels wider than 1.7× the page's own median line gap are breaks between blocks.
- Long printed rules are walls.
- The ink left between them is a block.

Captions were written after looking at every image (`rivers_report.py`). Nothing paid.

**Result.**
- **Geometry:** 830–1,983 shapes and 18k–49k corner points per page. Redrawn from the shapes alone, a page
  matches 95.0–97.5% of the scan's ink. What is missed is letter edges and the scanner's dark page border.
  Shapes are islands of ink, not letters.
- **Rivers, what they get right:**
  - columns on every two-column page;
  - body and references, split by a printed rule;
  - equations, footnotes and a table, each its own block;
  - a table's column gaps, which show as gutters;
  - the two halves of a verse.
- **Rivers, what they miss:**
  - a single column whose headings and footnotes are marked by size, indents or short rules rather than space;
  - bulleted points;
  - grey photos, which count as paper.

**The other senses** (`senses.py`, `senses_report.py` → `out/senses.html`). On the two pages where the rivers saw one block,
every Azure line was labelled from the ink and Azure's words alone, without using the page's hand labels and with no model.
- Signals from the ink: letter size, stroke thickness, spacing above, indents, a short rule.
- Signals from Azure's words: a leading dash, numbering, footnote numbers that match markers in the body.
- Every line came out right on both pages:
  - the header row;
  - paragraphs;
  - the numbered heading, with strokes 1.23× the page's own;
  - the verse;
  - the footnotes under the rule, with letters about 0.9×;
  - the bullets and their continuations;
  - the page number.
- This is a demonstration, not a measurement. The rules were tuned on these two pages in four rounds.

**Scored on the 44 pilot pages, untuned** (`score_layout.py`, `score_report.py` → `out/layout_score.html`).
- No page has hand layout labels (the 9 gold pages were corrected for text only), so Gemini 3.1 Pro labelled every line from
  the image alone. I checked its two biggest disagreements by eye; it was right both times. $0.52.
- Lines the rules are meant for (body, heading, footnote, list, verse, furniture): **47%** agree overall.
  - plain single-column text (19 pages): **72%**;
  - tables: 32%;
  - equations: 30%;
  - columns: 26%;
  - decorative: 19%.
- Causes:
  1. **One column assumed:** 389 lines were called verse, only 6% right.
  2. **One footnote makes every later line a footnote,** and table rules start it: 549 lines called footnote, 16% right
     (real footnotes found 85%).
  3. **Lists only by dash:** 14% found.
  4. **Furniture only at the top:** 25% found.
  5. **Headings too varied for one rule:** 27% found.

The perfect result on two pages was the tuned kind. The rules belong after the rivers (columns, tables and equations set
apart first), with a model for what measurement can't settle.

**The small model on the same lines** (`score_model.py`, no spend: experiment 36's dots.mocr run). Each Azure line takes
the type of the dots.mocr block covering it.
- All labelled lines: dots.mocr **80.5%**, the rules 34.6%.
- Lines the rules handle: dots.mocr 74.5%, the rules 47%.
- By kind of page, dots.mocr:
  - plain text 89%;
  - tables 92%;
  - equations 88%;
  - columns 70%;
  - decorative 22%.
- Where dots.mocr is weak:
  - lists 19% (273 list lines called plain text);
  - verse 0% (it has no such label);
  - headings 57%.
- A naive mix (dots.mocr, plus the rules' verse) was worse, 70%, because the rules over-call verse.

**A trained layout model** (2026-10-13). The owner asked to label a few thousand pages with a referee and fine-tune
a small model, so Gemini is not needed at run time.
- Labels: `train_pages.py` drew 2,700 pages from 228 documents (at most 40 a document, none from the 44 pilot pages);
  Gemini 3.8 Flash labelled every Azure line (2,699 pages; agrees with Pro on 92.7% of lines). Gemini spend for the whole
  experiment: $11.92 (cap $15).
- Model: DocLayout-YOLO (DocStructBench weights) fine-tuned to detect the line boxes with eleven labels, at 1280 px
  (`make_yolo.py`, `gpu/`). Split by document: train 2,508 pages, val 185 (22 documents), test = the 44 pilot pages
  labelled by Gemini 3.1 Pro.
- Run: one RTX 5090 (Vast, datacenter), 2.0 h, **$1.70**. Training stopped itself at epoch 52 (no gain in 20), keeping
  epoch 32 (val mAP50 ≈ 0.69). The library's own final step crashed (fusing Conv+BN breaks its dilated block); the saved
  weights predict fine unfused, on this machine's CPU (`predict_local.py`, 1.5 s a page, 1 GB peak).
- Scored on the 44 test pages (`score_yolo.py`, 2,075 lines): model **87.7%**, dots.mocr 84.4%, rules 39.5%.
  - By kind of page, model: plain text 95%, decorative 95%, columns 86%, tables 86%, equations 74%.
  - By label, model: body 96%, verse 96%, footnote 95%, table 89%, furniture 87%, references 78%, heading 64%,
    list 54%, equation **0%** (only 77 equation lines in training).
  - On labels dots.mocr can say at all (no verse, no references) dots is better: 91.7% vs 88.0%.
  - Model, but dots.mocr wherever it says table or equation: **92.1%**.
- `report_yolo.py` → `out/layout_model.html`: the scores, the training curve, six pages side by side.

**What it changes.** It is a thinking aid for the owner's "map" idea: the ink is a model-free survey of the page.
The rivers give exact edges and columns; a model that sees the whole page names the blocks and covers what white
space does not show. Nothing in `src/` changed.

**Outputs** (gitignored):
- `out/report.html`: the geometry, scan beside shapes beside redraw, plus close-ups.
- `out/rivers.html`: the ten river pages.
- `out/layout_model.html`: the trained layout model against dots.mocr and the rules; weights in `out/gpu/out/run/weights/best.pt`.

# 36 · VLM bake-off: which open vision-language model reads Mandumah pages

**Question.** Which open VLM should be the main whole-page reader of the open stack (text, tables, equations,
reading order)? How often does each one invent or drop text, and how well does Kraken (experiment 33) catch it?

**Answer (2026-10-12): dots.mocr**, with Kraken beside it as the checker. The owner's page is
`out/report.html`: bars with intervals, real lines from every reader with the differences marked, one table and
one equation from each model beside the scan, an invention with Kraken's flag, and reading order drawn on a
two-column page. Candidates and how each was run: [models.md](models.md). Decision: D28 in
[docs/decisions.md](../../docs/decisions.md).

## Method

- **Readers.** dots.mocr, dots.ocr, PaddleOCR-VL-1.5 (full pipeline: PP-DocLayoutV3 + VL-0.9B), Qwen3-VL-32B AWQ,
  Qwen3-VL-8B, amad-vlm6 (an Arabic fine-tune of Qwen2.5-VL-7B that gives plain text only). Each was run with its
  authors' recipe, greedy, 8,192-token cap, no prompt tuning. All ran on one rented RTX 5090 (vLLM 0.13; Paddle on
  its own server), one model at a time ([gpu/](gpu/): `setup.sh`, `orchestrate.sh`, `vlm_client.py`,
  `paddle_run.py`). Azure (today's reader) and Kraken (33's round-A model plus the fine-tuned line finder, on CPU:
  [kraken_check.py](kraken_check.py)) were scored on the same pages.
- **Pages (258)** ([pack.py](pack.py), [bd.py](bd.py)): the 202 yardstick pages of experiment 34, and 56 born-digital
  pages from experiment 33's held-out documents, whose PDF text layer is the truth. Three sets, never pooled:
  `gold` (the owner's corrected pages, read afresh on every run: **6 done pages** at the final re-score,
  2026-10-12 14:10), `bd` (56 pages vs the PDF's own text), `ys_azure` (all 202 yardstick pages vs Azure: agreement,
  not accuracy).
- **Measures**: the scoring section below.

## Result

Final re-score 2026-10-12 14:10, gold = 6 done pages. Faithful character error rate (every vowel mark and hamza
counts), 95% interval by document bootstrap:

| reader | gold CER | born-digital CER | vs Azure CER | invented /1k words, bd / vs Azure (outside tables) | dropped /1k, vs Azure | looped /1k, vs Azure | pages given up / runaway (vs Azure) | marks P/R, bd | word order, multi-column | judge: tables / equations (1–5) | pages/h, $/1k pages |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Azure | 0.9% [0.4–1.7] (flattered) | 3.1% [1.8–4.9] | — | 1.2 / — | — | — | — | 89/89% | — | — | — |
| **dots.mocr** | **3.0%** [1.7–4.6] | **5.5%** [3.0–9.2] | **13.7%** [10.0–17.6] | 2.6 / **0.9** | 15.2 | 0.6 | 0% / 0% | 79/60% | **86.5%** | **3.44 / 2.42** | 2,807, $0.17 |
| dots.ocr | 3.6% [2.4–5.3] | 7.3% [3.8–11.6] | 18.5% | 1.6 / 2.1 | 20.8 | 0.9 | 1% / 1% | 71/51% | 79.8% | 2.66 / 2.06 | 2,648, $0.18 |
| amad-vlm6 (text only) | **1.5%** [0.8–2.7] | **3.6%** [2.6–4.8] | 18.4% (8.7% healthy) | 1.0 / 1.5 | 9.1 | 29.6 | 0% / 2% | 67/74% | 86.5% | — | 3,051, $0.15 |
| PaddleOCR-VL-1.5 | 5.8% [3.8–9.1] | 25.8% [14.6–39.3] | 50.1% | 2.7 / 22.4 | 50.8 | 41.5 | 0% / 1% | 58/46% | 54.8% | 2.22 / 1.71 | 5,486, $0.09 |
| Qwen3-VL-32B AWQ | 102% (5.2% healthy) | 38.1% (11.7% healthy) | 44.7% (18.8% healthy) | 0.8 / 2.2 | 242 | 79.3 | 23% / 8% | 8/76% | 87.9% | 1.78 / 1.39 | 326, $1.44 |
| Qwen3-VL-8B | 12.1% | 145% (17.6% healthy) | 105% (30.2% healthy) | 2.0 / 2.8 | 166 | 714 | 6% / 12% | 6/45% | 53.9% | 1.22 / 1.03 | 1,059, $0.44 |
| Kraken (the checker) | 6.0% [3.9–9.2] | 9.5% [4.8–15.9] | 19.0% | 3.3 / 7.5 (its false-alarm floor) | 17.2 | 0.0 | — | 86/52% | 90.0% | — | CPU |

Full tables (every stratum, intervals): `out/headline.md`; every number: `out/results.json`; per page:
`out/eval_pages.jsonl`.

What the numbers show:
- **dots.mocr is the best layout reader on every measure.** It never ran away or gave a page up, it almost never
  invents outside tables (0.9 words per 1,000), it keeps two columns in order, and its tables are the only ones the
  judge rates good (3.44 of 5; TEDS 0.66 against the Gemini-pro drafts). Its weak spots: it leaves out more than it
  invents (15.2 per 1,000 vs Azure; table pages and reading-order differences inflate the 13.7% agreement figure),
  it drops vowel marks (recall 60%, Azure 89%), and equations are weak (2.42 of 5; it gave none for 29%). Its
  worst invention: English inserted into an Arabic heading (`bd_2571-006-011-016_p009`).
- **dots.ocr** is a step behind dots.mocr everywhere.
- **amad-vlm6** reads plain text best (gold 1.5%, born-digital 3.6%) but gives no boxes, layout, tables or
  equations, loops more (29.6 per 1,000) and ran away on 2% of pages: a text cross-check, not the main reader.
- **PaddleOCR-VL-1.5** reads two-column Arabic left column first (word order 54.8%), invents (22.4 per 1,000 vs Azure,
  e.g. a table of Arabic-Indic numbers read as Latin letters, `bd_2532-029-002-016_p012`) and drops (50.8). Cheapest.
- **Qwen3-VL**: the 32B gives up on 23% of pages (it answers a text page as one `<img>` with an imgur link) and runs
  away on 8%; the 8B loops (714 repeated words per 1,000). Both add vowel marks the page does not print (precision
  6–8%). On its healthy pages the 32B is decent (5.2% gold) but 9× slower than dots.
- **Kraken as the checker** flags 92–100% of each VLM's truth-based inventions (born-digital pages); on truth pages
  no VLM invention of 5+ words went unflagged. Its precision is low on good readers (dots.mocr 11% on bd, 9% vs
  Azure) because most of its flags fall where Kraken itself misreads (tables), and 44–64% on Paddle. It finds
  44–99% of the dropped text. So it says where to look, not what is wrong.

## What it changed

- The open stack's three layers become: **dots.mocr as the main reader** (text, blocks with boxes, tables, reading
  order), **Kraken as the checker** (a second, independent reading of every line; its disagreements mark where a
  VLM may have invented or dropped text), **amad-vlm6 as a text cross-check** on doubtful blocks. Qwen3-VL and
  PaddleOCR-VL are dropped (D28; `docs/ideas.md`).
- Open: equations (every model weak; dots.mocr 2.42 of 5), vowel marks, and dots.mocr's dropped text.
- **The licence must be cleared first.** dots.ocr and dots.mocr are MIT plus an agreement whose §3.3(c) forbids
  "unauthorized digitization of publications" and whose §5.4 limits training other models on its outputs
  ([models.md](models.md)). The owner has to decide before dots.mocr's readings are used as training data (e.g.
  silver lines for Kraken) or in the product. Paddle, Qwen and amad are Apache-2.0.

## Limits

- Very few gold pages (6), none with a table or an equation: gold intervals are wide; tables and equations are graded
  by Gemini 3.1 Pro (`judge.py`) or compared with Gemini-pro drafts (TEDS, LaTeX similarity), not with truth.
- Azure's gold number is flattered: the gold was corrected from Azure's draft.
- The born-digital truth has ligature-order defects (about 0.5 dropped words per 1,000 under every reader); the
  `bd_2532` running heads, scrambled in the text layer, are excluded.
- Qwen ran without fp8 KV cache and without async scheduling (setup problems on the rented card) and mostly without
  boxes; its speed and some failures may improve with another setup.
- Every model ran with its authors' recipe, no tuning; the held-out pages were only read.

## Spend

GPU: $0.95 logged (2.03 h at $0.469/h, `out/gpu_spend.jsonl`); the Vast credit went from $20.378 to $19.318, i.e.
$1.08 by the credit drop ($20.38 → $19.30, disk included; the instance was destroyed, `vastai show instances` showed 0 at 14:20). Gemini judge: $0.56 (`out/gemini_spend.jsonl`). Total about $1.64.

## Scoring (built before the VLM outputs landed)

```
V=/home/yassine/inkscript/.venv/bin/python
$V convert.py                 # out/raw/<tag>/ -> out/pred/<tag>/ (+ .kl re-cut); azure, kraken, synth_azure too
PYTHONPATH=../../src $V evaluate.py   # -> out/results.json, out/eval_pages.jsonl, out/score/<reader>.json (3.5 min, 0.17 GB)
$V judge.py estimate          # Gemini judge of tables/equations: cost only; `run --limit 3` = the 3-call test
$V headline.py                # -> out/headline.md
$V make_report.py             # -> out/report.html (numpy + opencv; KaTeX from cdnjs renders the equations)
```

- [convert.py](convert.py): dots (JSON blocks, boxes in the resized image's pixels, salvages output cut at the token
  cap), Qwen `qwenvl html` (data-bbox on 0–1000; box-less html parsed too; text wrapped in a picture kept), PaddleOCR-VL
  `parsing_res_list`, amad plain text. Block text is split on newlines (paragraphs); the `.kl` variant re-cuts each
  block on the Kraken lines inside it, for the line-level measures only. Tables: HTML plus cell lines; display
  equations: LaTeX only; page header/footer kept as furniture.
- [evaluate.py](evaluate.py): three page sets, never pooled: `gold` (done pages, score.py), `bd` (born-digital
  text layer, digits folded), `ys_azure` (all 202 yardstick pages: agreement with Azure, not accuracy). Strata:
  split, decade band, vowelled/Quran, table, equation, multi-column, footnotes, Latin, and "healthy" pages (not
  empty, not runaway). 95% intervals by document bootstrap (1,000 draws). TEDS is paired by box where boxes exist.
- Invented and dropped text are counted in words, order-free (the docstring has the rule). It was
  checked on `synth_azure`, a calibration reader: Azure's reading with one line from another page inserted, one line
  dropped and a loop on a fifth of the pages. The rule finds 88–95% of the inserted words. Kraken can misread
  but cannot invent, so its "invented" rate is the rule's false-alarm floor for a reader that weak: 3.3 per
  1,000 words on bd and 7.5 per 1,000 vs Azure outside tables, far more on tables.
- [judge.py](judge.py): one Gemini call per table/equation (63 on the yardstick pages), all readers' versions
  anonymised in one request; cache, spend log `out/gemini_spend.jsonl`, $3 cap, no retry of a truncated answer.
  A reader that gave nothing is graded 1 locally, not sent.
- [headline.py](headline.py): `out/headline.md`, from results.json and judge.jsonl.
- [make_report.py](make_report.py): `out/report.html`, the owner's page (1 MB).

## Files

`models.md` (research and run recipes), `bd.py`, `bd_look.py`, `pack.py`, `kraken_check.py`, `watchdog.sh`,
`gpu/` (rented-GPU scripts), `convert.py`, `evaluate.py`, `judge.py`, `headline.py`, `make_report.py`. Outputs
(gitignored) in `/home/yassine/inkscript/experiments/36_vlm_bakeoff/out/`: `pack/` (page images, manifest),
`raw/<tag>/` (each model's raw answers, `run.json` speeds), `pred/<tag>/` (converted), `ref/` (Azure,
born-digital truth), `kraken/`, `results.json`, `eval_pages.jsonl`, `headline.md`, `judge.jsonl`,
`gpu_spend.jsonl`, `gemini_spend.jsonl`, `report.html`.

# Experiment 75 status (2026-11-04, evening)

| what | state | date |
|---|---|---|
| lab package `labocr/` (schemas, ingest/render, JSONL adapters, runs in SQLite, evaluation, annotations, CLI) | built; 27 tests pass (`experiments/75_ocr_lab/tests/test_lab.py`) | 2026-11-04 |
| workers: PaddleOCR-VL-1.6 (pipeline / bare_ocr / layout_stage), Nuqta-4B (as_written / markdown / _fast / _speedfix), CPU fixture | real inference on RTX 4060 Ti and RTX 5090 | 2026-11-04 |
| /lab on the Desk (document switcher; Compare / Correct / Scores; speed by card) | works on dev :8154/:8155; **not deployed** (lead) | 2026-11-04 |
| document 1 (2399-003-008-002 p21, clean modern) | owner: Nuqta exact; correction rev1 (text only, entered by lead). Characters wrong: Azure 20, Nuqta Markdown 17, Paddle 1.6 83 (5090 run; 85 on the 4060 Ti run), Paddle 1.5 75, Nuqta 0 (flattered) | 2026-11-04 |
| document 2 (0018-010-003-002 p3, 1937 print) | 5 engine runs + Azure + Argon (ours) + exp 36 Paddle 1.5 on /lab; disagreements only; **waiting for the owner** | 2026-11-04 |
| speed | Nuqta 79 s (4060 Ti) ≈ 77 s (5090): bottleneck = PyTorch 2.9 bf16 conv3d in the patch embedding; **speed fix (F.linear) 20 s, identical text**; Paddle 16–20 s on both | 2026-11-04 |
| GPU spend | session 1 (4060 Ti) $0.287; session 2 (RTX 5090, $0.935/h) $0.53 at 34 min, left open (90-min idle keeper, $10 cap) | 2026-11-04 |
| document 2 scores (owner rev1, punctuation ignored) | Nuqta 3, Azure + Argon 3, Azure 4, Paddle 1.6 52 | 2026-11-04 |
| document 3 (0877-007-027-003 p4, two columns + 8 footnotes, 1964) | Argon right; Nuqta as written drops the left column; Nuqta Markdown right order, complete; Paddle left column first, an empty region, footnotes untyped; combination (Paddle regions + Nuqta text) complete, + RTL column rule = right order | 2026-11-04 |
| owner decision | PaddleOCR dropped as a reader (kept on /lab behind "show dropped readers"); no Paddle text variants from doc 4 on | 2026-11-04 |
| GPU | total $1.366; session 3 destroyed after doc 3 (none running) | 2026-11-04 |
| text measure on /lab | order-free headline (word bags, punctuation ignored; missing words count), reading order effect shown apart; docs 1–3 | 2026-11-04 |
| next | owner's feedback on doc 3 + the layout decision → document 4 (tables); not started | |

# Experiment 69 — progress log

- 2026-11-02: read exp 66 (270 + 40 judged fixes), exp 65 (v3.6 check2), prompt43 / run43, exp 60.
- `select69.py`: 299 pages hold exp 66's judged fixes (almost one judged fix per page). Chose 44 one-page windows,
  stratified: 12 with a bad fix (B), 12 with an overwritten misprint (M), 10 good fixes on poor prints (Azure: ≥ 12%
  of the page's words < 0.80 or median < 0.95), 10 good fixes on clean prints; 36 journals, 1920s–2020s; saved answers
  all Argon (v3.3 40, v3.5b 2, v2 2). -> `out/pages69.json`.
- `prompts69.py`: v3.6 / v3.6-nofix (bullet removed, nothing else) / v3.6-faded (reworded), registered at run time.
- `run69.py`: run43's Batch machinery, answers to `out/<tag>/raw`, spend to 43's log, cap relative to the log at the
  start (`out/baseline_spend.json`), max output 6,000 per one-page request.
- Run 1: v3.6 on the 44 windows (Batch) — submitted.
- Run 1 v3.6 (44 windows, Batch): $0.939; 1 page (0496 p15, a big table) hit 6,000 output tokens, rerun at 16,000
  ($0.036). Run 2 v3.6-nofix: $0.953. Total so far $1.928.
- `units69.py v36 nofix`: 501 words changed by some condition; 110 differ between the conditions and were not judged
  by exp 66 -> judged on the scans (`sheets69.py`, `zoom69.py`, `lab69.py` -> `out/labels69.tsv`; 15 U).
- First score (`score69.py v36 nofix`, 88 decidable units): letter shapes v3.6 +8 net (-3, +20 by pages), hamza / ya /
  ta marbuta even (10 / 10), punctuation -7 (v3.6 keeps «((» more). 72 of 88 units differ between the two runs: run-to-run
  variation is large, so a replicate is worth the money.
- Run 3/4: replicate of both on 30 of the pages (all bad and misprint pages but 0496, 4 good-poor, 4 good-clean),
  tags v36r / nofixr.
- Runs 3/4 (v36r $0.604, nofixr $0.624): total **$3.156**. 54 more units judged (`EXP69_UNITS=units_r.jsonl`).
- Replicate: letter-shape net 0 (run 1 +7); hamza +12 from one page whose hamza policy flipped (run 1: the opposite
  on another page). Fix-set overlap v36/nofix = v36/v36r = nofix/nofixr (Jaccard ≈ 0.54): the bullet is in the noise.
- Exp 66's judged B+M made again: 25/48 with the bullet, 25/48 without; with the guard 15 / 16. Good kept 26 vs 27 / 31.
- 1080 p8 (exp 65's faded page): the no-bullet prompt also missed 3 of the 4 "lost" fixes -> window/run variance.
- No reworded variant run ($0.84 left): the bullet is not followed as worded, the faded loss is not the bullet's.
- `pool69.py` -> `out/pooled.json`; README written; recommendation: drop the bullet, keep the guard.

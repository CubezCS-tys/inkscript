# Experiment 52 (gate 1, one journal) — progress

Owner approved 2026-10-22: hard Gemini cap $32 on top of the spend log. Prompt v3.5b, thinking low, Argon, Batch.

- 11:58 CDT log sum $75.902 (2,469 rows) -> absolute cap **$107.90** (recompute before each paid launch).
- 11:58 journal 0130 مجلة الطفولة العربية, articles 2005-2025: 389 catalogue records, **195 in the main bucket** (years
  present: 2005-2008, 2017-2019, 2023-2025; 2009-2016 and 2020-2022 not in the bucket); 3,669 printed pages by the
  catalogue (18.8 a page an article). ids: out/ids_all.txt. Fetch (PDF + JSON) launched into out/fetch/ (fetch.log).
- Letter fix: out/lettersfix/ in exp 43 still building its last control (first 300, --off) at 11:46; letters43.py +
  lettersfix43.py exist and the exam/first-300 letter-fix builds are done and valid -> used as is.
- 12:30 fetch done: 195/195 PDF + JSON (881 MB), all pass fetched43.problems -> out/sample52_all.json (3,667 pp).
- 12:35 plumbing (no output change for other runs): set d = out/sample52.json in run43 / pictures43 / flags43 /
  views43 / judge43 (RUNS j0130, j0130_final; JUDGE43_PW env for the Playwright python) / patches43 / summary43 /
  retry43 (patches -> out/j0130_final/patches) / lettersfix43. exp43/out/j0130 and j0130_final are symlinks to this
  experiment's out/. Playwright: exp 40's venv is not on the server; out/pwvenv (playwright 1.63.0 = the cached
  chromium-1243, opencv) made here; shots43 tested OK.
- 12:40 dry runs: all 195 $35.06 expected (worst $83.81); 2010-2025 (126 art., 2,439 pp, 300 requests) $22.86
  (worst $55.60). Whole journal + judge ~ $42.8 > $32 -> **run 2010-2025** (= 2017-2019 + 2023-2025; the bucket has
  no 2009-2016). out/PLAN.md. out/sample52.json = the 126.
- 12:42 watchdog52.sh started. Letter-fix agent is rebuilding first-300 (its own snapshot code, ~0.8 GB); 34 GB avail.
- 12:43 run43 launched: `run43.py --set d --prompt v3.5b --thinking low --run j0130 --cap 103.30` (log $75.902;
  cap = log + 27.40; out/j0130/run.log). Resume: same command.
- (clock note: the times above were written ~30 min ahead; from here they are `date`, CDT.)
- 12:45 watchdog52 killed run43 at 3.09 GB while it built job 1 (nothing sent, nothing spent; 1,010 page renders kept).
  Cause: run43 keeps every article's Azure JSON cached and every request line in memory. Fix (no output change):
  run43 drops an article's Azure JSON after building its request; jobs cut at --max-enqueued 2.5M tokens.
- 12:55 relaunched: same command + `--max-enqueued 2500000` (run_killed.log kept).
- 13:07 job 1 (85 first chunks, worst $14.72) SUCCEEDED 12:56 -> ~13:06: 85/85 usable; log $81.003
- 13:3x job 2 (80: 41 first + 39 second chunks, worst $14.46) SUCCEEDED: 80/80 usable; log $87.004
- 13:5x job 3 (72, worst $12.87): 70/72 usable, 2 MAX_TOKENS (0130-020-080-001 c17-24, 0130-025-099-004 c11-20) -> rechunk after the run; log $92.706. Job 4 (36) sent.
- 14:36 run done (10 jobs; 298 answers usable + 2 MAX_TOKENS); log $97.302 (run $21.40). 14:38 rechunk43 --run j0130: 0130-020-080-001 17-24 -> 17-19,20-22,23-24 (+25-31); 0130-025-099-004 11-20 -> 11-13,14-16,17-19,20 (+21-28); retry run (--stems, cap 103.30) launched (out/j0130/retry.log). rechunk43 sees set d (one-line change).
- 14:5x plain build (lettersfix43 plain, set d): 124/124 masters JATS DTD + ALTO XSD valid, 376 MB peak; letter fix: ی>ي 210, ک>ك 117, ی>ى 26, ھ>ه 9, ہ>ه 3 (306 words, 0 unplaced, 0 lines left)
- 14:54 retries done (9 requests, all STOP, $0.521); **126/126 articles answered**; log $97.823 (run incl. retries $21.92)
- 15:0x 0130-020-080-001 JATS invalid: two table footnotes (calls in a cell, p22) had their only paragraph moved into table-wrap-foot by enrich43 (v3.5 code), leaving fn with a label alone. Fix in enrich43.apply: such a footnote moves whole into table-wrap-foot (id kept, call still resolves). Rebuilt: **126/126 JATS DTD + ALTO XSD valid**; test_enrich43 3 passed. Letter fix on the 2: ی>ي 40, ک>ك 2, ی>ى 1.
- 15:15 views 126; flags (rules 15232e3fc5): high 21 / medium 96 / low 162 over 2,439 pp (0.86 / 3.94 / 6.64 per 100 pp; table_cells_lost 20 of the high); summary: $21.515 for the answers in the masters. judge_pages52.py: 239 flagged pages + 50 random unflagged (seed 5245) = 289 (out/j0130/pages_judge.txt); look-10 draw seed 5246 (out/look10.json). Judge screenshots running.
- 15:2x judge shots done (289). Platform: gate1.db = backup-API copy of platform_v2.db; load47 --run j0130 --kind base (ink47.azure_paths now also reads out/sample52_all.json: one line) 126 loaded; link47 --db gate1.db --work out/link_work (orphans 0). Pre-judge test of measure52/catalogue52 run (bridges_j0130_pre.json). 15:5x judge batch launched: Argon, judge v2, 289 pages, JUDGE43_CAP=107.30 (out/j0130/judge_batch.log)
- 15:52 judge job SUCCEEDED: 289/289 pages, $2.078 ($0.0072 a page); log $99.901
- 15:5x decide (frozen two keys) -> out/j0130_final/patches: 30 findings on 289 pages (flagged 239: none 216, auto 2, retry 5, owner 16; random 50: none 47, owner 3); routes auto 3 / retry 5 / human 22 (wrong_kind 22, picture_box 4, table_box 3, text_not_on_scan 1); 25 proposed edits in 18 articles, 3 with two keys (judge_summary52.py -> out/j0130/judge_summary.json). Retries (retries52.py, seed 5247): 5 of 5 sent, all STOP, all pass the code check, $0.245; log $100.146.
- 16:10 final (out/j0130_final; final52.sh): 8 patches applied in 6 articles (judge two-key 3 on 0130-020-079-001: picture boxes; retries 5); 126/126 JATS DTD + ALTO XSD valid; final flags high 21 / medium 94 / low 162 (0.86 / 3.85 / 6.64 per 100 pp); views 126; index pages j0130 + j0130_final, symlinked in exp 41 views (http://127.0.0.1:8899/j0130_final/index.html 200). Look at 10 random pages (seed 5246) beside the scan: right 9, minor 1, serious 0 (out/look10_verdicts.json).
- 16:1x load47 --run j0130_final --kind final (126 shown) + link47 + checks47 on gate1.db (orphans 0). Measures: measure52 (journal + 600 + 20 same-size draws of 126, seed 5250), catalogue52 (probe A matcher on gate1.db: 16.9% held; 39 inside-journal links, 38 right by reading, 11 self-citations), detect52 (154 tasks touching the journal, counted only), fields52.
- 16:3x owner's page out/gate1.html -> experiments/49_correction_desk/web/public/gate1/index.html; next.config.js rewrite + gate1; next build + restart.sh; curl :8004/gate1/ 200.
- README, experiments/README line, docs/STATUS row written. **DONE. Spend $24.24 (log $75.902 -> $100.146; cap $107.90).** Watchdog stopped.

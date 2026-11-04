# Experiment 70 (gate 2's pilot, journal 0165) — progress

Owner approved: journal 0165 «مجلة الطفولة والتنمية», 2010-2025, hard Gemini cap **$55** for everything. Prompt v3.6
(= v3.5b + P1-P3), thinking low, Argon, Batch; Word route with the cheapest model exp 53 supports (Flash, lean).

- 17:23 CST exp 43 spend log sum **$104.098** (3,238 rows) -> absolute cap **$159.10** (recompute before each paid launch).
  Live state: exp 68 went live at 17:16 (release R20261102T231619, /audit -> 68_go_live/out/audit_live, API restarted 17:18).
- 17:24 inventory (sample70.py inventory): 363 records = scan 145 + Word 218 + nowhere 0 (as exp 54); Word files 104 .doc,
  114 .docx. Years: Word 2010-2015, 2020, 2022 (+8 of 2016, 28 of 2021); scan 2016-2019, 2023-2025 (+10 of 2021).
- 17:25 watchdog70.sh started; fetch of the 145 (inkscript fetch, 4 workers, nice, S3 read-only) -> out/fetch/.
- 17:28 fetch done: 145/145 PDF + JSON (422 MB), all pass fetched43.problems -> out/sample70.json (2,841 pp).
- Plumbing (no output change for other runs; originals in out/code_before/): set f = out/sample70.json in run43 /
  lettersfix43 / pictures43 / rechunk43 / patches43 / retry43 (patches -> out/j0165_final/patches) / judge43 (RUNS
  j0165, j0165_final) / summary43 / views43 / flags43; ink47.azure_paths reads sample70.json. exp43/out/j0165 and
  j0165_final are symlinks to this experiment's out/.
- Word-route loading (new): load47 `--word DIR` (no Azure / ALTO; documents row level 'legacy-pdf', in_main_bucket 0,
  legacy_only 1, docx sha as the source hash); parse46 BLOCK_ID also takes the Word route's `wN` / `hN` ids (page
  NULL). Prototype on a scratch copy (exp70_proto.db) with 3 of exp 53's 0130 Word masters: 139 blocks, 22
  citation mentions, 4 bylines, 22 sections, 231 table cells, orphans 0.
- 17:31 dry run (v3.6, set f): 353 requests, 10.6M in; **$20.84 expected, $63.81 worst** (Batch now).
- 17:32 run43 launched: `run43.py --set f --prompt v3.6 --thinking low --run j0165 --cap 144.10 --max-enqueued 2500000`
  (log $104.098; run cap = log + $40, leaving $15 under the $159.10 absolute cap for judge / retries / Word step).
- 17:35 Word files: 218/218 in out/word/docx (114 .docx copied, 104 .doc converted by soffice, 2.4 min, 0.67 GB peak). Check (word70 check, title share >= 0.6 of the catalogue title's words in the opening 3,000 characters, runs joined as Word draws them): **218 accept, 0 reject**; first page same 212, off 1-3 3, off +29 1 (0165-005-017-007, title 1.00: the catalogue's page is off), no number 2. Legacy PDFs fetching (S3 legacy/, read-only).
- 17:4x scan job 1 (97 first chunks) SUCCEEDED, 97/97 usable; log $108.440. Job 2 (90) sent.
- 17:4x Word code build (word70 build = build53 pointed at out/w0165_code): first pass 217/218 valid; fixes in
  build53 (originals in out/code_before/): (1) a restarted endnote numbering reused id en1 -> unique ids; (2) 0165 has
  no abstract and opens «مقدمة» under the byline: the body now starts at such a heading (BODY_HEAD), and lines after a
  byline stop being "affiliation" at running text (> 25 words, a body heading, or > 6 words with no institution
  word) - before, body sentences («مقدمة», a paragraph) were stored as affiliations; (3) 0165 prints the author's
  post and institution in an author note («* أستاذ ... كلية ... جامعة ...»): such a note now becomes the contrib's
  aff (specific-use author-note) + xref, by byline order (note_aff). Result: **218/218 DTD-valid**, 234 contribs (all
  with authority ids... 223 + 11 printed-only), 173 with an aff (156 from author notes), 2,848 headings, 2,913
  references (2,592 with code fields), 182 footnotes, 109 typed endnotes, 281 tables, 185 figures; 2.4 min, 0.38 GB.
  12 of 218 stems have no legacy PDF in S3 (pdfmap without positions).
- 17:5x wordmodel70: requests (lean text-only: every heading with level + following words, every reference entry,
  title + opening; prompt v3.6's W schema and doc_type list copied verbatim): 218 requests, 873k tokens in, batch
  expected ~$1, worst $2.12. **Pilot** (20 articles, seed 7020, Standard, gemini-3.8-flash, thinking low): **$0.122**.
  Checked by me (out/w0165_model/pilot_review.txt, pilot_refs.txt): headings - 134 level changes, mostly re-basing
  the outline (code's top level 2 -> 1) and making series consistent (ثالثا 3->1 beside أولا/ثانيا; siblings 2/3 -> 3),
  9 to paragraph («راجع في ذلك», lead-ins), 17 to caption; one doubtful (a two-line heading split). References, 40
  random side by side: model better than code in ~25 (theses typed with university, journals split from comma
  styles code left as "other", given/surname split, series «عالم المعرفة» out of the title), same in ~11, worse in 1
  (a newspaper web item typed other); 2 name-order slips; 3 of 3 "not a reference" right (endnote paragraphs and an
  English abstract code had put in the reference list). Verdict: good -> full Batch.
- 17:59 Word Batch: 198 requests, worst $1.951 (wordmodel70 batch --cap 146).
- 18:04 Word Batch collected: 198 (196 usable: 1 MAX_TOKENS on a 162-entry list, 1 malformed JSON). wordmodel70
  retry (Standard, references in parts of 50): both answered; one batch answer had left out 219 of 292 references
  (0165-005-020-006): asked again in parts. **Word step total $1.24** (pilot $0.122 + Batch $0.822 + retries $0.30).
- wordmodel70 apply -> out/w0165_final/masters: **218/218 DTD-valid**; doc types research 112, report 44,
  editorial 41, review 16, book_review 3 (reviewed book as product); headings: 1,215 level changes, 220 -> paragraph,
  53 -> caption, 30 -> quote, 24 -> list item; references: 2,508 code fields replaced by the model's W, 144 newly
  given fields, 260 entries with no new work («مرجع سابق» / op. cit., stray notes, an English abstract: their code
  fields removed), 33 extra works in one entry not written, 1 W empty after the substring check (code kept).
  Fix on the way: a reviewed book's `product` must follow fpage/lpage (3 invalid -> fixed).
- 18:1x load47 --word into a work copy (~/data/platform_v2/exp70_work.db, backup-API copy of the live DB):
  w0165_final 218 loaded, orphans 0, 69 s, 0.23 GB.
- 18:3x scan run done: 7 rounds, 351 answers usable + 2 malformed JSON (0165-000-050-004 c17-22, 0165-000-050-006
  c19-27; finish STOP, so not a rechunk case); renamed .failed1.json and asked again (run43 --stems, 1 round, both
  usable, $0.135). **145/145 articles answered; run $20.57** (log $104.098 -> $124.665, minus the Word step's
  $1.20 logged meanwhile). run43 peak RSS 3.31 GB (time -v; the watchdog's 15 s poll did not see it over 3 GB).
- 18:42 plain build (build70.sh = lettersfix43 plain, set f): letter fix ی>ي 82, ک>ك 62, ی>ى 15, ھ>ه 2 (142 words,
  0 unplaced); 144/145 valid: 0165-009-031-001 had three empty list-items left when enrich43 moved table-note bullet
  paragraphs into table-wrap-foot -> enrich43 now removes an emptied list-item (and an emptied list); test_enrich43
  passes; rebuilt: **145/145 JATS DTD + ALTO XSD valid**, peak 0.29 GB.
- 19:1x flags (rules 41dcb4348e): high 21 / medium 97 / low 214 over 2,841 pp (0.74 / 3.41 / 7.53 per 100 pp); views
  145; summary. judge_pages70.py: 295 flagged pages + 50 random unflagged (seed 7045) = 345; look-10 seed 7046.
- 19:2x look at 10 random pages beside the scan (look70.py -> out/look10/, verdicts out/look10_verdicts.json):
  **right 9, minor 1, serious 0; 0 words wrong** (the minor: Latin inside Arabic lines kept in visual order).
- spot checks (spot70.py -> out/spot70.txt; 10 articles + 20 references per route, read by hand): scan titles,
  authors, positions, affiliations right; 2 of 10 lpage differ from the catalogue (0165-000-050-006 105 vs 121:
  the reader's printed range is wrong; 0165-000-051-002 45 vs 44); 20 scan references: 19 fields right, 1 minor
  (volume «23;7»). Word: bogus page "affiliations" (headings such as «مقدمة:», «تقديم:», «الغذاء:» taken as the
  line under a byline) -> build53 stops at a label ending «:», a line with no letters, a sentence; rebuilt (block
  ids unchanged on all 218, so the model's answers still apply); 3 residual (one sentence, «خلفية», «خلفية الدراسة»);
  20 Word references: right fields, 4 «مرجع سابق» / Ibid. with no new work (correct).
- judge: shots + Batch (Argon, judge v2, JUDGE43_CAP 150) launched.
- 19:42 judge Batch: 345/345 pages, **$2.419** ($0.0070 a page); log $127.084. decide (frozen two keys): 28 findings
  on 345 pages (flagged 295: none 271, auto 1, retry 6, owner 17; random 50: none 49, owner 1); routes human 21,
  retry 6, auto 1 (wrong_kind 13 human; table_box 6 human + 4 retry; verse_layout, wrong_order 1 retry each).
- 20:0x retries70.py: first pass refused by retry43's cap (it reads JUDGE43_CAP, default $38.92: nothing sent, the
  6 empty records moved to out/judge/retry/j0165_stopped_capbug/ in exp 43); rerun with JUDGE43_CAP=150: 6 of 6 sent,
  all STOP, 5 pass the code check (apply), 1 to a person; **$0.303**; log $127.387.
- 20:01-20:11 final70.sh -> out/j0165_final: 6 patches applied in 6 articles; **145/145 JATS DTD + ALTO XSD valid**;
  final flags high 21 / medium 95 / low 215; views 145; summary.
- 20:11-20:27 load70.sh into the work copy: j0165_final 145 (362 s, 0.17 GB), w0165_final 218, link47 (own cache
  out/linkwork, 9 min, 0.21 GB): orphans 0. ids68 compare against the live snapshot (out/ids_compare.txt): every person
  (1,947), institution (669), publication (2,018) the same row; cited works 9,186 same + 29 merged; the 23
  unresolvable are the same 23 as before; Desk-named ids all resolve except CRTJTVTZSQ (as before, exp 68).
- 20:28 dry run (dryrun70.py, schema test_e70dry): 2,738 applied, 9 superseded, 3 orphaned (exp 68's three), 1
  conflict (the «المقدّمة» demo); constraints hold, 0 FK violations.
- 20:29-20:33 golive70.sh: backups (platform_v2 / link cache / desk schema, 20261102T202906); work copy -> platform_v2.db;
  **release R20261103T023001** (--keep 8; fingerprint 8c6d2895…); audit61 on it (925 articles, 218 Word skipped, 119 s);
  aggregate61 failed on prompt "v3.6" (VERSIONS) -> added; before_after vs exp 68's live audit; /audit pointer ->
  out/audit_live. 0165: 90,189 lines, 99.981% accounted, 17 generic-only.
- 20:4x measure70 on the release (out/measure70.json); 31 cross-journal links read by hand (29 right, 1 doubtful, 1
  wrong); new vs existing entities counted.
- 21:xx tests (root 111 passed + 7 skipped; Desk 93 passed): exp 43 84 passed, test_ids47 1, test_audit61 7; Desk: 3 failures fixed (2 pinned pre-exp-68 data:
  test_audit -> exp 61's audit via DESK_AUDIT_DIR, test_pipeline -> 2 affiliations / the faculty's English twin row;
  1 from this load: test_rules detector counts 93 / 609); root test_docs needed the index line. README, index line,
  STATUS, project.json timeline written. **Spend $23.29 (log $104.098 -> $127.387).** Watchdog stopped at the end.

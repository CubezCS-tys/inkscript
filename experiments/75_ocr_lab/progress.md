# Experiment 75 progress log

- 2026-11-04 11:10 read the brief, CLAUDE.md, exps 34/36/41/58/59/60. Picked exp 34 gold candidates. Then the lead
  fixed document 1 = 2399-003-008-002 p21; its exp 34 file was found to be an unchecked draft (status todo).
- the owner's change (via the lead): no gold truth, a fresh correction on /lab, scores only against it; the
  gold-derived truth I had drafted was removed before it was written; the lab never reads the gold text.
- built labocr (schemas, ingest, transport + worker base, normalisers, runs, evaluation, annotations, report, CLI)
  and 26 tests (all pass). Added rapidfuzz 3.14.6 to the repo venv. pypdfium2 pin 5.12.1 checked.
- model cards fetched at pinned revisions (out/cards/); weights' LFS sha256 recorded.
- the lead's change: the GPU lives for a working session; wrote gpu_session.py (keeper: per-minute spend log,
  90-min idle, $10 cap, destroy + verify).
- 17:40 UTC rented RTX 4060 Ti 16 GB (offer 57913313, $0.269/h, datacenter, rel 0.9991); link 7.9/7.9 MB/s; set-up
  in its own venvs; weights hash-checked.
- Nuqta as_written 79 s, markdown 81.5 s. Paddle pipeline: the first attempt hung for 645 s (CPU 100%, GPU 0) and
  was stopped by its PID, recorded as failed. Run directly, the pipeline took 19 s; the worker's fd-1 handling was
  fixed, then 20 s. bare_ocr 16.6 s; layout_stage failed to load once (a pipeline_version argument; recorded),
  then 1.0 s.
- the owner's decision: next sessions on a 32 GB+ card (default changed; doc 1 stays on the 4060 Ti).
- /lab built (Compare, Correct, Scores), dev servers :8154/:8155. Fixes after looking: the loop flag gave false
  alarms (the page itself prints a phrase three times), so it now flags back-to-back loops only (+test); line
  breaks kept in the side-by-side texts; engine cards moved below the scan; letter changes shown LTR-isolated.
- browser check on a test copy (labtest_app.py): start → select Arabic line → edit → save rev 1 → scores → reload:
  all passed; real lab has 0 annotations.
- README / STATUS / DEPENDENCIES written; doc1.py takes --dataset/--stem/--page; Argon importer added for doc 2.
- (doc 1 feedback, via the lead) Nuqta exact by eye; the lead saved rev1 (text only). Session 1 ended by the lead at $0.287.
- doc 2 = 0018-010-003-002 p3: doc1.py (now taking arguments) ingested it; fixed Azure paragraphs without regions;
  Argon importer used (6 blocks).
- session 2: RTX 5090 (offer 45508888, $0.935/h, rel 0.9975, link 5.6/5.5 MB/s). Fixes to the offer filters (31 GB,
  cuda_max_good) and to setup (cu129 Paddle wheel on Blackwell).
- runs: Nuqta doc2 as_written 82.7 s / markdown 79.6 s; Paddle doc2 pipeline 16.2 / bare 15.2 / layout 1.0 s;
  doc1 re-runs on the 5090: Nuqta 76.5 s (no faster), Paddle 16.0 s (one word differs from the 4060 Ti run).
- diagnosis: fast kernels (fla + causal-conv1d prebuilt wheel, /opt/nuqta_fast) did not help (78.6 s); a profile
  showed 59.6 s in one torch.conv3d (the vision patch embedding); cuDNN off did not help; conv as F.linear: 20 s,
  identical text on both docs. Added as the `patch_embed_as_linear` setting / variant `as_written_speedfix`.
- bundle: runs priced by the session they ran in; "speed by card" table; identical readings collapsed in
  Compare; "flattered" by engine + prompt; scores cache versioned (scores/2); /lab document switcher; categories
  from the data; "not corrected" when a correction has no regions. Shots 20–23 looked at.
- doc 2 feedback: owner's rev1 (punctuation spaces not restored); scores (no punctuation): Nuqta 3, Argon 3, Azure 4,
  Paddle 1.6 52, which matches the lead's numbers.
- doc 3 = 0877-007-027-003 p4 (two columns + 8 footnotes; Azure + Argon on disk). The first 5090 rental (Czechia)
  failed the link test: a 900 s scp timeout hid it for 10 min, destroyed, $0.167. Link test now 45 s,
  bad machines remembered, `start RTX_5090`. Second 5090 (Alberta): Nuqta speedfix 41.9 s, markdown 51.8 s, card
  default 104.4 s; Paddle 27.2 / 26.0 / 1.0 s; combination (combo.py) 69.8 s; first combo skipped Paddle's empty
  region, re-run over every region; rtl_order.py derived order. GPU destroyed ($0.263).
- owner: "drop paddle": Paddle text readings hidden on /lab behind "show dropped readers" (regions still
  available); shots 30–34 looked at.
- order-free text measure on /lab (bag headline, reading order effect apart, ≈ N words); doc 3 default right = Nuqta Markdown speed fix, warning on as written (reader_notes.json); scores cache scores/3; shots 40–42 looked at.

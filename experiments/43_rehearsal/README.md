# Experiment 43 — dress rehearsal: prompt v2, rules in code, Batch API

**Question.** Experiment 41's approach (Azure's lines + page images → Gemini 4 Argon returns the structure as line
ids → `masters.py` makes JATS + ALTO and every format) passed the owner's hand check on five articles. Before a dress
rehearsal on ~300 unseen articles: close the known gaps (another article on a shared page, list vs body, endnotes,
"noise" with words, verse Azure read as one line, silently repaired misprints), and get the rehearsal ready to run
through the Gemini Batch API under a cap.

**Status (2026-10-18).** Step 1 done; a 4-article Batch test ran ($0.30, section "Batch test"): the Batch
request shape, costs and the new labels are confirmed.
Owner's page: `out/prompt_v2.html` (`page43.py`; images in `out/prompt_v2/`; works on a phone). Experiment 41 is
untouched: its prompt and code are imported, never edited; this experiment's harness rebuilds 41's 55 masters byte
for byte from 41's answers (`replay43.py harness`: 55/55 identical) before applying anything new.

## Prompt v2 (`prompt43.py`; 41's `structure.PROMPT` stays as it was)

1. **other_article** — a block type for the end or start of a different article on a shared page, with how to see
   the boundary (a new title / author / heading style, a closing signature or end mark or rule, a change of topic,
   the position at the top of the first page or of a "بقية ص" jump, or the bottom of the last page). Never noise.
2. **Lists** — list_item only for short parallel items (number/letter/bullet, one to three lines, often indented);
   running prose that opens with a number or ordinal is a paragraph; a number with a few words on its own line is a
   heading; in doubt (> 3 lines) paragraph; one decision per article.
3. **Endnotes** — footnote = at the foot of the calling page; **endnote** = gathered at the end of the article or a
   section under هوامش / الهوامش / الحواشي / الإحالات / المراجع والهوامش / Notes / Références, ids `en-M`
   (`en-S-M` if numbering restarts); calls link to either; sources without call numbers stay references.
4. **Noise** — only marks without words (ornaments, rules, specks, show-through); text of another article is
   other_article, running heads header/footer, anything else a block. Code enforces it (below).
5. **Verse in one Azure line** — a verse block's `"cut": {"3:4": K}` (the first K of Azure's words are the right
   half) instead of retyped `splits`; `"ornaments": [{"line", "word", "text"}]` for decorative marks Azure read as
   words: they leave the text, their ink stays in the ALTO.
6. **Misprints (D30)** — "does the INK show exactly the letters of 'to'?" before every fix; a printer's error is a
   `sic` flag only, the text keeps the print. Three contrasting cases written in: المتعمون (no fix, flag المتعلمون;
   41's Argon had "fixed" it), أصلبا → أصلها (a real Azure misreading: fix, no flag), A930 (fix to the ink ٨930
   **and** flag 1930; 41's Flash had written 1930).
7. **Smaller gaps** — column headings and unit words (مليم جنيه, 0924) are header cells of their table; author
   `name` without a role phrase (ضبطها وشرحها، بقلم … go in `role`; 0747's byline); `missed` never for running heads
   or page numbers (41's 10 appended running heads).

## Rules in code (`rules43.py`, applied to every answer before assembly; `masters43.py`, `views43.py`)

| rule | what it does | replay of 41's 55 answers |
|---|---|---|
| never noise | a line with words (≥ 4 letters at a plausible width, not a sliver at the page edge) called noise or left out goes back: 1–2 lines into the touching block of running text, a longer run as its own block `other`, `from_noise`, one per column, placed in reading order; counted and logged | **26 lines** (all 0656 p4, now 2 flagged blocks); 15 other "noise with letters" are 1–3-letter specks and stay noise |
| broken splits | a split whose parts are not Azure's text (41 then dropped the line): rebuilt from Azure's words at the same cut when the word counts match, else undone | **1** (0355 21:63, both column halves back; 41's only dropped line) |
| other_article | masters: out of the JATS; ALTO TextBlock `role.otherArticle`; Layout view faded + "another article" | 0 (v1 answers have none); simulated on 0656: 26 lines |
| verse cut / word boxes | `cut` → splits of Azure's words; every split part drawn from its own Azure word boxes (41 cut the line box by letter count) | 170 split lines in 11 articles get word boxes |
| ornaments | the model's list checked against Azure's text; code backstop: a lone ٥ ه * ※ = ° … at a verse half's inner edge (« » . : - only when it sits in a wide gap), not a call marker, not inside a fix; text out, ALTO `role.ornament` | 1 (0747 3:4 ٥); Argon had removed most ornaments through "fixes" already |
| endnotes | endnote → footnote with `note_kind: endnote`, linked by id | 0 (unit-tested) |
| fixes counted | spacing-only (12, mostly Azure gluing words: right) and hamza / ya / ta-marbuta-only (84) fixes counted, not changed | |

**Replay result** (`replay43.py all` → `out/replay/compare.json`, `rules_log.json`): JATS text identical in 52/55;
changed on purpose in 0656 (+26 lines, 216 words), 0355 (+20 words), 0747 (one ornament out). ALTO identical in
43/55 apart from the two new role tags, 9 more differ only in box coordinates (word-boxed split lines). The owner's
five hand-checked articles: 2382, 0877, 1140 identical; 0924 same text, 29 split lines re-boxed; 0747 one ornament
out of the text, 13 verse lines re-boxed. Simulated v2 answers (`replay43.py simulate`, labelled simulated
everywhere): 0656 with its top half as other_article; 0747 with its splits as word cuts. Unit tests:
`.venv/bin/pytest -q experiments/43_rehearsal/test_rules43.py` (11 pass). Nothing under `src/` changed.

**Honest limits.** The code cannot tell another article's text from this one's: without the v2 label it keeps the
text (flagged) in the article. On 0747 p3 the verse halves moved little: Azure glued the ornament to a word
("أسد؟(٥"), which no word-level rule can separate. List vs body, endnotes, the misprint rule and the small prompt gaps
can only be measured with calls.

## Running it (`run43.py`; first calls: the Batch test below)

`--set a` = 41's 55 articles (run `v2_55`), `--set b` = `sample43.json` (run `v2_fresh`). `--mode batch` (default)
or `standard`; `--cap USD` required; `--dry-run`; resume from `out/<run>/raw/`; spend in `out/gemini_spend.jsonl`
(41's client, re-pointed); `--assemble` = rules + masters. A later chunk needs the previous chunk's answer (outline,
last block), so Batch runs in **rounds** (all first chunks, then second, then third), one job at a time, each cut to
the requests whose worst case fits under the cap and to `--max-enqueued` input tokens (4.5M; Argon Tier 1 allows 5M
enqueued). Requests are JSONL lines `{"key", "request"}` with images inline (base64), uploaded through the File API.

**Dry run (a), 55 articles** (calibrated on 41's 67 billed chunks; output +10% for v2): 67 requests in 3 rounds
(55 / 10 / 2), 399 pages, 1.43M input tokens, ~0.38M output (worst 1.60M).
| | expected | worst case |
|---|---|---|
| Batch now (to 30 Nov 2026) | **$3.35** | $9.42 |
| Batch from 1 Dec 2026 | $6.70 | $18.84 |
| Standard now | $6.70 | $18.84 |
| Standard from 1 Dec 2026 | $13.40 | $37.68 |
(41's Argon run cost $6.00 Standard for the same pages with prompt v1.) A cap of $10 lets round 1 go whole on Batch.

## Batch API (ai.google.dev, read 2026-10-18 by a sub-agent)

* Supported: the model pages of `gemini-4-argon` and `gemini-3.8-flash` both list Batch API "Supported".
* Price: Batch = 50% of Standard. Argon $1.00 / $5.00 per M tokens (input / output incl. thinking) through 30 Nov
  2026, **$2.00 / $10.00 from 1 Dec 2026** (Standard $2/$10 → $4/$20); Flash Batch $0.375 / $1.875, doubling 1 Jan
  2027. No long-context tier. Argon has implicit caching only (no explicit cache in Batch).
* Mechanics: inline requests up to 20 MB, or a JSONL file up to 2 GB via the File API
  (`client.files.upload(..., mime_type="jsonl")`, `client.batches.create(model=, src=file.name, config=)`); poll
  `client.batches.get`; states PENDING / RUNNING / SUCCEEDED / FAILED / CANCELLED / EXPIRED (> 48 h); target 24 h;
  results `job.dest.file_name` → `client.files.download`, matched by key, kept 6 weeks. Limits: 100 concurrent batch
  jobs; Argon enqueued tokens 5M (Tier 1) / 500M (Tier 2) / 1B (Tier 3).
* **Not confirmed in the docs** (all three answered by the Batch test below): base64 `inline_data` images inside the JSONL (the REST request shape; `--upload-images`
  sends pages through the File API instead), the per-part `media_resolution` field name in Batch, usage metadata per
  response (read as `usageMetadata`). A first small job (two or three articles) should check these before the 55.

## Batch test (2026-10-18, owner-approved, cap $2): **$0.30 billed**, everything worked first time

`run43.py --set a --run batch_test --stems 0656-016-001-011 0747-001-003-001 0781-010-055-015 0767-010-002-007
--cap 2` (prompt v2, Argon, thinking low, images inline) plus `probe43.py` (one page, five ways of sending it).
Four of 41's articles, chosen for the new labels: 0656 (another article on p4), 0747 (verse halves with ornaments),
0781 (endnotes under «المراجع:» on p6, calls on pp1-6), 0767 (endnotes under «التهميش:» on p11-12 for calls in
the *first* chunk: two chunks, so it also tests round 2 and the carried state). Outputs `out/batch_test/` (raw,
rules, masters, views, shots/side_*.jpg = scan beside Layout view, batch/round*.jsonl, probe.json, run.log).

**The unknowns.**
1. *Images*: base64 `inlineData` inside the JSONL works (all 5 requests); File API `fileData` (`--upload-images`)
   works too and costs the same tokens. Inline it is: no extra uploads, the JSONL is ~1 MB a page
   (18.7 MB for round 1's 18 pages; the 55's ~400 pages ≈ 0.4 GB, under the 2 GB file limit).
2. *Resolution field*: the part field is `"mediaResolution": {"level": "MEDIA_RESOLUTION_HIGH"}` (the SDK's REST
   shape, camelCase, now what `run43.py` sends); snake_case `media_resolution` is read too. Measured on one page:
   no field 1107 image tokens, HIGH 1107, LOW 260 (camel and snake alike). HIGH is the default; we keep it explicit.
3. *Usage metadata*: every response carries `usageMetadata` (`promptTokenCount`, `candidatesTokenCount`,
   `promptTokensDetails` by modality); no `thoughtsTokenCount` at thinking "low" (41's Standard calls had none
   either). The spend log is therefore real tokens × the Batch price. Note: it is *our* computation from the
   tokens, not Google's invoice; the console bill should be checked once after the 55.
4. *Turnaround*: probe 2.6 min; round 1 (4 requests, 18 pages) 4.1 min from create to end; round 2 (1 request)
   2.5 min. Total wall time ~8 min for both rounds, nowhere near the 24 h target. (One day's evidence, small jobs.)
5. *Parsing and resume*: the result file is JSONL `{"key", "response"}`, parsed by `collect()` unchanged; 5/5
   usable (finish STOP). Round 2 was built from round 1's saved answer (0767's second chunk numbered its endnotes
   en-15… after the first chunk's en-1…en-14). A rerun printed "nothing left to send" without calls.
6. *Cost*: **$0.2952** for the 5 requests (109,682 input, 37,111 output tokens) + $0.0048 probes = **$0.300**
   logged. The dry run said $0.29 expected, $0.71 worst; the same five chunks cost $0.5555 on Standard in 41
   (Batch = exactly half at the same token counts: v2's prompt adds ~1,400 input tokens a chunk; output ±10%).

**Did the new labels fire?** (masters `out/batch_test/masters/` vs 41's masters vs the replay of 41's answers)

| article | prompt v2 on Batch | 41 (v1) | replay (v1 + code rules) |
|---|---|---|---|
| 0656 p4 | **other_article**: 6 blocks = lines 4:1–4:26 (the top half, the other article), faded and labelled in the view; JATS body 1,478 words | 1,479 (those lines silently noise) | 1,695 (kept, flagged `from_noise`) |
| 0747 verse | **12 cuts** (`"cut"`), **33 ornaments** listed, 30 accepted, 3 rejected by code (glued to a word: «أسد؟(٥», «دائمةً»», «وإن»»), 0 sic; ALTO `role.ornament` 32 | 0 ornaments out | 1 |
| 0747 notes | 76 footnotes, **76/76 calls linked** | 69/76 | 69/76 |
| 0781 p6 | **14 endnotes** (`en-1…14`), 14/14 linked | 14/14 (as footnotes) | 14/14 |
| 0767 p11-12 | **24 endnotes**, **24/24 linked across the chunk boundary** | 10/24 (the first chunk's 14 calls unlinked) | 10/24 |

The 33 ornaments are Azure's readings of the ✿ between verse halves: ٥ « » . ! = * ، ﴿ at the end of a first
half (`out/batch_test/shots/side_0747_p003.jpg`, `_p005.jpg`: halves side by side, the stars gone, the three glued
ones still visible as in the replay). 0656 p4 (`side_0656_p004.jpg`): the "بقية ص ٣٣" continuation below the rule
stays this article, as it should. 0781 p6 (`side_0781_p006.jpg`): the endnotes sit in their column with linked calls.
0656, 0781, 0767 body text otherwise identical to 41 (±1 word).

**Gaps found.** (a) The masters lose `note_kind`: endnotes are written as ordinary `<fn id="fn-pP-N">` in JATS
(linked correctly, but not marked as endnotes; JATS would want them in a `<fn-group content-type="endnotes">`).
Not fixed here: it changes the masters the replay checks byte for byte. (b) 0747 had 108 "fixes" (41's Argon fixed
too); the misprint rule only shows when the owner's judged items come back in the 55.

**Changes to run43.py.** Request JSON now camelCase as the SDK sends it (`inlineData`, `mediaResolution`,
`generationConfig`, `thinkingConfig.thinkingLevel: "LOW"`; the lower-case "low" enum was the one real risk);
`--run NAME` (a separate output folder, so the test does not resume into `v2_55`); each round records its create /
end time; an answer without usage metadata would log its worst-case share instead of $0. `replay43.cmd_compare`
works on a masters folder with only some articles. Nothing broke during the run.

**For the 55**: `run43.py --set a --cap 10` (Batch, inline images, HIGH, 60 s poll). Expected $3.35, worst $9.42
(dry run; this test landed on its estimate). The test's $0.30 is in the same spend log, so the cap counts it. Run
before 1 Dec (prices double). Expect round 1 as one job (~1.4M tokens, under the 4.5M per-job limit).

## The fresh sample (`sample43.py` → `sample43.json`; proposal, not run)

300 whole articles of 1–30 pages, none in experiment 35's sample or editions, 40's sample or 41's 55; ≤ 3 per
journal. **186 local** (on this machine with PDF + Azure JSON: experiment 41's inventory of 931, minus 205 used,
minus 222 longer than 30 pages = 504 candidates) chosen first for layouts, then decades; **114 from the catalogue**
(`~/.cache/inkscript/catalogue/catalogue.sqlite`, 3.2M documents, 5,343 journals; 60,000 stems drawn at random, seed
43, kept if a 1–30-page article with a year) to fill the decades the machine lacks and French / English; fetched from
`s3://mandumah-source-docs/<id>/<id>.{pdf,json}` with `inkscript fetch --id-file out/fetch/ids.txt --out out/fetch`
(reserve list `out/fetch/reserve_ids.txt`, 100 stems, to swap in after their layouts are measured).

Strata: decades pre-1960 34 · 1960s 34 · 1970s 34 · 1980s 34 · 1990s 33 · 2000s 33 · 2010s 43 · 2020s 42 · unknown 13;
226 journals; 3,482 pages (catalogue page counts for the 114), 494 chunks. Layouts (local documents only, heuristics
in `out/features43.json`): tables 42 (rows of ≥ 3 short cells), two columns 49, verse 9 (mirrored half-lines whose
second halves rhyme), equations 10 (experiment 39's maths pages), French 23, English 30 (Latin share > 0.3; catalogue
language for the 114), shared pages 17 (the catalogue's page range meets another article of the same issue on one
page). Checked by eye on contact sheets: tables right; the first verse and shared heuristics were wrong (lists in
columns, title pages) and were replaced by the rhyme and catalogue tests. Verse and equations are short: the
catalogue part is mostly old decades, where verse is common, so its layouts are to be measured after the fetch.

**Dry run (b)**: 494 requests (rounds 300 / 138 / 56), 12.3M input tokens, ~3.4M output: **Batch $29.5 now
($59 from 1 Dec), Standard $59 ($118 from 1 Dec)**; worst case Batch $79 now. Round 1 alone is ~7.5M input
tokens: two jobs under the Tier 1 enqueue limit.

## What's next

1. Owner looks at `out/prompt_v2.html`; decide the cap (the dry run suggests $10 on Batch for the 55).
2. ~~A small Batch check~~ (done, "Batch test"), then `run43.py --set a --cap 10`
   (prompt v2 on the 55) before 1 Dec; compare with 41 (types, endnote links, list/body stability, sic vs fix on the
   judged items, noise with words should be 0 before the code backstop).
3. Fetch the 114 catalogue documents, measure their layouts, swap from the reserve to fill verse / equations, then the
   rehearsal (`--set b`).

## Files

`prompt43.py` (prompt v2) · `rules43.py` (code rules) · `test_rules43.py` · `masters43.py` (41's masters + v2 code) ·
`views43.py` (Layout view from a masters folder) · `replay43.py` (harness, rules, masters, compare, simulate) ·
`shots43.py` (Layout-view screenshots; experiment 40's Playwright venv) · `page43.py` (owner's page) · `run43.py`
(Batch / Standard runner, dry run) · `probe43.py` (Batch request-shape probe) · `sample43.py` + `sample43.json` (fresh sample). Outputs under `out/`
(gitignored): `replay/`, `masters/` (v2 rules), `masters_id/` (harness), `masters_sim/`, `simulated/`, `views/`
(simulated), `views_replay/`, `shots/`, `prompt_v2.html` + `prompt_v2/`, `v2_55/dry_run.json`, `v2_fresh/dry_run.json`,
`features43.json`, `catalogue_draw.json`, `fetch/ids.txt`.

# Experiment 43 — dress rehearsal: prompt v2, rules in code, Batch API

**Question.** Experiment 41's approach (Azure's lines + page images → Gemini 4 Argon returns the structure as line
ids → `masters.py` makes JATS + ALTO and every format) passed the owner's hand check on five articles. Before a dress
rehearsal on ~300 unseen articles: close the known gaps (another article on a shared page, list vs body, endnotes,
"noise" with words, verse Azure read as one line, silently repaired misprints), and get the rehearsal ready to run
through the Gemini Batch API under a cap.

**Status (2026-10-18).** Step 1 done; a 4-article Batch test ran ($0.30, section "Batch test"): the Batch
request shape, costs and the new labels are confirmed. The feedback loop (flags → review page → marks → gold set +
issues, version stamps) is built and tested without calls (section "Feedback loop"). The run of the 55 cost $3.18 (section "Run of the 55");
the owner's review of it led to three code rules and view changes (section "Owner's review of the 55") and three
prompt proposals (section "Decisions pending"), which the owner decided: prompt v3 is live, with the empty JATS
slots filled in code; a 6-article Batch test cost $0.62 (section "Prompt v3 and JATS coverage").
v3 lost pictures; a code rule now draws every ink region without text as a figure (another article's pictures muted,
out of the JATS) and prompt v3.1 asks for symbols / hieroglyphs / cartoons as figures: $0.19 test on 0493 and 1769
(section "A picture is never lost").
Code fixes before the 300 (D33 metadata, overlapping blocks, pictures inside a line, new flags, MathML names; prompt
v3.2 candidate with parsed references, not live): section "Code fixes before the 300".
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
| other_article | masters: out of the JATS; ALTO TextBlock `role.otherArticle`; Layout view: one quiet mark per region, "Hide other articles" (since the owner's review; first: faded + a label per block) | 0 (v1 answers have none); simulated on 0656: 26 lines |
| verse cut / word boxes | `cut` → splits of Azure's words; every split part drawn from its own Azure word boxes (41 cut the line box by letter count) | 170 split lines in 11 articles get word boxes |
| ornaments | the model's list checked against Azure's text; code backstop: a lone ٥ ه * ※ = ° … at a verse half's inner edge (« » . : - only when it sits in a wide gap), not a call marker, not inside a fix; text out, ALTO `role.ornament` | 1 (0747 3:4 ٥); Argon had removed most ornaments through "fixes" already |
| endnotes | endnote → footnote with `note_kind: endnote`, linked by id | 0 (unit-tested) |
| exclamation (2026-10-18) | a fix writing a standalone «(!)» as «(١)» refused, a call on it dropped | 0197 p2 (also in 41's answers) |
| text in figure (2026-10-18) | a running-text block wholly inside a figure's box becomes the figure's text (not for a background picture that also holds the title / a heading / the byline) | v2: 0493 p1 |
| figure trim (2026-10-18) | a figure box running over a title / heading / byline line, or a caption line in its top / bottom fifth, cut back (< 30%) | v2: 4 figures (0493, 1769) |
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

## Run of the 55 (prompt v2) (2026-10-18, owner-approved, cap $10): **$3.18 billed, 67/67 answers, no regression that matters**

`run43.py --set a --cap 10` (Batch, inline images, HIGH resolution, thinking low; run `v2_55`). Outputs `out/v2_55/`
(raw, rules, masters, views, shots/side_*.jpg, compare.json/.txt, flags.txt, hand5_blocks.txt, run.log, progress in
`out/progress.md`).

**Spend** (from `out/gemini_spend.jsonl`): the 67 requests **$3.1846** (1,347,148 input, 367,496 output tokens; the dry
run said $3.35 expected, $9.42 worst); the log's total with the Batch test is **$3.4846**. All 67 finished STOP, the
largest answer 17,189 output tokens. The console bill is still to be checked once against our token count.

**Turnaround**: round 1 (55 requests, 216 MB of JSONL) 5.2 min from create to end, round 2 (10) 2.5 min, round 3 (2)
3.4 min; 19 min wall from launch to the last answer, ~4 min of it building and uploading round 1's file.

**Failures and retries**: one. The first launch was refused before any job existed (400: *Batch requests cannot ask for
more than 32,768 output tokens*; three long chunks asked for up to 33k under 41's `max_out`). `run43.py` now caps Batch
requests at `BATCH_MAX_OUT = 32768` (41's largest answer was 13.9k); relaunched, nothing was sent twice, $0 lost.
Assembly: one master failed the JATS DTD (1148 p6: the model wrote an empty table row, every column covered by rowspans
from the header; masters wrote `<tr/>`). New code rule `empty_rows` in `rules43.py` (row dropped, the rowspans over it
shortened; test added); **55/55 JATS DTD + ALTO XSD valid**. `gold43.py check`: the 5 gold articles unchanged by the rule.

**Against experiment 41** (`compare43.py --run v2_55`; 41 = its Argon answers and masters, replay = those answers
through the v2 code rules):

| over the 55 | 41 | replay | v2 |
|---|---|---|---|
| words in JATS body | 127,626 | 127,861 | 127,049 |
| blocks | 4,646 | 4,648 | 4,638 |
| footnotes + endnotes | 444 + 0 | 444 + 0 | 347 + **200** |
| calls in the answers / linked | 467 / 360 | 467 / 360 | 490 / **483** |
| verse cuts / ornaments out of the text | 0 / 0 | 0 / 1 | 22 / 60 |
| other_article blocks | 0 | 0 | 39 (7 articles) |
| misprints flagged (sic) | 178 | 178 | 219 |
| fixes (only hamza / alif / ya / ta marbuta; only diacritics) | 1,146 (86; 23) | same | 997 (66; 17) |
| noise lines with words in the masters | 41 | 15 | 16 |
| flags43: high / medium / low | — | 5 / 56 / 25 | 3 / 27 / 20 |

Reading order: the same as 41 in 48 articles; 77 lines move in 7, 42 of them in 1010 (its poem taken out) and 15 in
1147 (equations re-cut). Block types are the same in most articles; where they change it is mostly references →
endnotes (0355, 1769, 0049: now linked) and quote → paragraph (1769's figure notes).

Where v2 differs, judged next to the scan (`out/v2_55/shots/side_*.jpg`):
* **other_article, all right**: 1010 (a framed filler poem by another author, pp 2–8; 41 had it as 32 verse blocks
  inside the article: −415 body words), 0924 p1 (the end of the previous report, signed), 0493 p4 (a separate news
  report after the article ends), 0447 p3 (the column «ترياق الحياة»), 0690 p1 (the end of the previous letter, signed),
  0656 p4 (as in the test). The 2 `other_middle` high flags (0447, 0493) are these right ones.
* **Endnotes**: 0355 51/51, 1769 43/43, 0767 25/25, 0781 14/14, 0049 11/15 linked (41: 0, 0, 10, 14, 3).
* **Lists vs references, inconsistent both ways**: 1140 (the author's publications, pp 2–11) references → list items in
  the body (+1,617 body words, text identical); 0382 (a bibliography article) list items → references (body −1,003).
  The text is the same; one rule is needed for "a list of works that *is* the article".
* **Fixes**: 1769 has 21 that write the print's dotted ي in على / إلى (right on the scan, one over-reach on 2:13); 0549
  has 2 (41: 33, mostly Azure's garbled calligraphic title, which v2 calls a figure; the title comes from the
  catalogue); 0692 50 (41: 29).
* **Figure descriptions** are now English (41: Arabic): the article-text diff of 1769 is mostly those, not print.
* **Small regressions**: 0197 one call no longer linked (the model wrote Azure's «(!)» as the marker of «(١)»): 1/2
  (*corrected after the owner's review*: the print has «(!)», the author's exclamation; both 41 and v2 wrongly "fixed"
  it into a call; now kept as «(!)» by a code rule);
  0747 75/76 (the batch test had 76/76; one call given on a cut line as the whole line); 2382's English title and the
  received/accepted dates are now "other" (41: a heading, and part of the byline).

**The five hand-checked articles** (`out/v2_55/hand5_blocks.txt`, every block-level difference): **0747** and
**0877** blocks identical to 41 (0747: 12 cuts, 33 ornaments out, 75/76 calls). **0924** better: page 1's top half
(the previous report) is now another article; p4's table title a caption (right); p2 one line heading → paragraph and
p7 two numbered items list → paragraph and a heading h3 → h2 (neutral). **1140** blocks the same except the
references → list items above (text identical; owner's choice). **2382** p1 only: «الملخص:» and «Abstract:» headings
split from the abstracts (right), the English title heading → other and the dates byline → other (the dates better, the
title worse). None loses text. Verdict: at least as good, with 2382's English title the one step back.

**Views**: `out/v2_55/views/index.html` (served as http://127.0.0.1:8899/v2_55/index.html), 55 articles, 9 marked
"look first" (1010, 0924, 0493, 0447, 1140, 0382, 2382, 1769, 0197), each with one line on what changed vs 41.
`out/v2_55/make_index.py` builds it from `compare.json`.

**Verdict**: prompt v2 does what it was written for (another article, endnotes, verse cuts and ornaments) on the 55,
for $3.18 on Batch, with no lost text and five small regressions listed above. To decide with the owner: the list vs
references rule, the English figure descriptions, translated titles as "other".

## Owner's review of the 55 (2026-10-18; no calls)

The owner looked at the Layout views of the run of the 55 (scan left, ours right) and named five things. Each was
traced, fixed in code where it could be, and looked at next to the scan. Before / after pairs (scan | ours):
`out/v2_55/shots/before/side_*.jpg` and `out/v2_55/shots/after/side_*.jpg` (`side43.py`); masters and rules as they
were before: `out/v2_55/before_feedback/`. Issues log: `issues.md` i1–i5.

1. **Page number missing on a first page** (owner's note said 0382; it is **0197**, p1 «-٨-»: the article whose p2
   shows «- ٩ -», the same article as item 2; 0382 p1 has its ٤٢٥). **Azure never read it**: no line or word at the foot
   of p1 in Azure's JSON (`content` has no «٨» outside «رقم (٨)»). Every page-number line Azure did read in the 55 is
   already placed as furniture (185 lines, none called noise or left out), so a "page numbers are always furniture" rule
   would change nothing. Not invented in code (i1, won't fix; inferring it from the next page's number is possible but
   would be text no OCR saw).
2. **«(!)» on 0197 p2** («وهكذا (!)»): the print has the author's exclamation (zoomed on the scan). Where «(١)» came
   from: a **Gemini fix**, «(!)» → «(١)», plus a call to the page's note «١ - المترجم». **41 made the same fix and
   linked it** (2/2 calls); v2 made the fix but gave the marker as «(!)», so the call did not link: the run report's
   "regression" was the fix half-failing, not v2 being worse. Code rule `rules43.exclamation`: a fix that writes a
   standalone «(!)» as «(١)»/«(1)» is refused and a call on it dropped; a glued «word!» (0747's calls, which Azure reads
   as «!») is left to the model (tested). Now «(!)», unlinked; the note «١ - المترجم» is a note without a call (flags43:
   +1 note_no_call). Fires once in the 55 (and once in 41's answers). (i2)
3. **Pictures with text inside** (0493 p1, the TV drawing whose screen holds a paragraph Argon called an abstract).
   Code rule `rules43.text_in_figure`: a block of running text whose every line lies ≥ 80% inside a figure's box is the
   figure's text (its lines become the figure's lines), except when the figure also holds a title / heading / byline
   line (then it is a background picture under the page's own text: 0881 p1's banner photo under the title, byline and
   abstract stays as it is). Fires once in the 55 (0493). `masters43` writes the words of any figure (these, and the
   lines Argon itself gave inside figures: 41 kept those in the ALTO only) as `<fig>…<p content-type="text-in-figure">`
   (JATS 1.4 allows paragraphs in fig; 55/55 DTD + XSD valid): 26 figures in 6 articles. The view draws the picture only,
   with a small **text** button that opens the words in a box (Copy / Close; `shots/after/figure_text_box_0493_p001.png`).
   **Overlap with the title**: Argon's box began inside the title's second line; `rules43.figure_trim` cuts a figure box
   back to the edge of a title / heading / byline line it runs over (less than half inside) or a caption line in its
   top or bottom fifth, when the cut is < 30% of the box: 4 figures in the 55 (0493 p1; 1769's «شكل رقم (N)» labels on
   pp 11–12, which were drawn twice).
4. **"Another article" marking.** Is 0493 p4 really another article? **Yes**: printed p7, a news report on the Arab
   Council for Childhood and Development's debate («مناظرة الأطفال والقائمين على إعلام الطفل», «إعلام صديق للطفولة»),
   with its own headline and photos; the article (a survey by د. محمد محمود عطا) ends on printed p6
   (`side_0493_p004.jpg`). The catalogue's page range includes p7, Argon's label is right. The view now marks each
   contiguous run of another article's blocks once: a thin rule on the region's outer side and one small label
   "from another article" at its top; its text slightly muted (no fading of whole blocks, no dashed boxes, no repeated
   labels); pictures and captions between or inside its blocks belong to it. A bar button **Hide other articles** hides
   them all (remembered in the browser; storage in try/catch). Seen on 0493 p4, 1010 p2 (a framed bookshop ad inside the
   page), 0447 p3, 0924 p1. Limit: the four photos of 0493 p4 are still `<fig>`s in 0493's JATS (Argon labelled them
   figure, not other_article); the view assigns them to the region, the masters do not yet.
5. **Text running under pictures** (0493 p4's round photo). The view now wraps running text round a figure that
   intrudes into its box: floats at the start of the block's text, one per printed line beside the figure, as wide as
   the print leaves that line short (Azure's line boxes), so the text follows the circle as the print does. Measured in
   Chromium on the 12 articles with figures (text-node line fragments more than 30% under a figure's box):
   **45 before → 22 after**; 0493 12 → 0. What remains: 0881 p1 (10; the banner photo with the title and abstract
   printed on it, as in print) and 1769 (12; picture boxes that still include the «شكل رقم» label above them, drawn
   over by our label). The round photo's crop is its square box, so the print's text at its corners shows in the crop.

**Numbers after the review** (all 55 rebuilt from the saved answers; `compare.json`, `flags.json`): JATS body words
127,049 → 127,266 (+217: figure words now in the fig, 0493's TV paragraph moved out of the body), blocks 4,638 → 4,637,
fixes 997 → 996, calls 490 → 489; flags 3 high / 27 medium / 21 low (+1 low: 0197's note without a call). Masters
changed in 7 articles (0041, 0197, 0408, 0493, 1147, 1769, 2382). Gold check: 2382 changed only by its chart labels
«EGR END POV» now in the JATS fig; accepted (`gold43.py accept 2382-005-003-001 --run replay --why …`); then 5/5 the
same. Unit tests: test_rules43 16 pass (4 new). **Layout PDFs not regenerated**: this experiment's views never wrote
the print pages (`views43.py` skips `write_layout_print`), so the v2 run has no Layout PDFs to remake.

## Decisions pending (proposals only; no prompt change made, no calls) — decided 2026-10-18, now prompt v3 (next section)

Drafted as `prompt43.PROMPT_V3_CANDIDATE` / `META_FULL_V3_CANDIDATE` (each change a replacement of one v2 passage,
`V3_CHANGES`; not used by `make_prompt` or `run43.py`).

* **(a) References vs list.** Recommendation: *references only for a section the article presents as its sources (a
  references / bibliography heading, or an article that is itself a bibliography); an author's list of own works in
  the body is a list.* That keeps 0382 (a bibliography article) as references and makes 1140's publications list a
  list, which is what v2 did; v2 chose right on both, but by accident of wording, so it should be written down. Cost:
  ~90 tokens a chunk.
* **(b) English translated title.** Recommendation: a title block with `"lang"` and `"translated": true` (never other,
  never a heading), and `trans_titles` in the metadata; masters write JATS `<trans-title-group xml:lang="en">` under
  `<title-group>`, and the view shows it under the title. Needs the masters side before it goes live (2382's English
  title is "other" in v2, a heading in 41: both wrong).
* **(c) Figure descriptions in the article's language** (Arabic for an Arabic article; v2 wrote English, 41 Arabic).
  Recommendation: yes; they are alt-text for readers of the article.

## Prompt v3 and JATS coverage (2026-10-18; owner's decisions (a)–(c); paid test $0.62 on Batch)

**Prompt v3 is live** (`prompt43.PROMPT_V3` / `META_FULL_V3`, each change one replaced passage of v2 in `V3_CHANGES`;
`run43.py --prompt v3`; answers record `"prompt": "v3"`, the masters' stamp hashes the v3 text; v2 stays the default
name so the run of the 55 keeps its stamp). What v3 adds to v2:
* **(a) references vs list** (owner): reference = an entry of a section the article presents as its sources (المراجع،
  المصادر، Bibliographie, References …) or of an article that *is* a bibliography; an author's list of own works or works
  listed in the body = list_item.
* **(b) translated title** (owner): the title printed in another language is a title block with `"translated": true`
  (code: type `trans_title`), plus `trans_titles` in the metadata. Masters: `trans-title-group[@xml:lang]
  [@specific-use="printed"]/trans-title` holding the printed lines (ids → ALTO), `trans-subtitle` split off when it
  matches the catalogue's; **printed wins**: the catalogue's copy is dropped when it has the same words, else kept as
  `alt-title[@alt-title-type="catalogue-translation"]`. For older answers a code rule finds it (a Latin block on page 1
  matching the catalogue's translated title: 2382 in v1 and v2 answers).
* **(c) figure descriptions in Arabic and English** (owner): `"description": {"ar", "en"}`. JATS 1.4 (checked against the
  local DTD: `fig` takes `(alt-text | long-desc)*`) → **two `alt-text`**, the article's language first, `xml:lang` on the
  other; all valid. The Layout view uses the article's language for the image's alt and shows both on hover.
* **boxed** — a block type for text in a frame or tinted box (pull-quote, highlighted fact, sidebar), `"box": K` groups
  one box's blocks → JATS `boxed-text`, drawn as a tinted box. The text-in-figure rule now also covers boxed blocks
  (v3 called 0493 p1's TV-screen paragraph "boxed"; it stays the picture's text, the owner's earlier choice).
* **quotations** — every Quran verse or quotation printed on its own lines is a quote block (→ `disp-quote`); inline
  quotations stay in the paragraph.
* **metadata**: `history` (received / revised / accepted / published / online, the printed date and its line) and
  `aff_parts` (department, institution, city, country, each an exact substring of the printed affiliation).
Not changed: the prompt still shows its metadata example with doubled braces `{{` (inherited from experiment 41's
template: the spec is passed as a value, not formatted); the model reads it fine, left as it is so v2 and v3 differ only
by the changes above.

**JATS slots filled in code** (`jats43.py`, called by `Master43.build`; ids kept so every ALTO block still points at its
element and the Layout view draws it where printed). Counts over the 55 (v2 answers through today's code,
`out/v3_test/v2_now`, against the masters of the morning; full table and the slots not filled, with why:
**`jats_coverage.md`**):

| slot | before → now (55) | from |
|---|---|---|
| `abstract` / `trans-abstract[@xml:lang]` (`abstract-type="printed"`, heading as its `title`) | 0 → 8 + 6 (all 20 abstract paragraphs; 0 left in the body) | blocks "abstract" (or paragraphs the metadata lists) |
| `kwd-group[@kwd-group-type="author-printed"]`, one `kwd` each | 0 → 10 groups, 52 kwd in 7 articles | blocks "keywords", else the metadata's strings; catalogue groups stay, `specific-use="catalogue"` |
| `trans-title-group` printed (+ `trans-subtitle`) | 0 → 1 (2382) | (b) |
| `history/date` (+ printed `pub-date` with day) | 0 → 9 dates in 4 articles (2382, 1147, 1148, 0767) + 1 | v3 `history`; else printed labels on the first / last page followed directly by a date (تاريخ الاستلام / الإستقبال / التحكيم / القبول / النشر، مقبول للنشر بتاريخ، Received …) |
| `aff` parts: `institution[@content-type=dept\|orgname]`, `country` | 0 → 21 dept, 25 orgname, 7 country in 29 affiliations | v3 `aff_parts`; else a country list and institution words; tagged in place, string unchanged |
| `contrib-id`, `name-alternatives` (ar + en names), `role` | 0 → 39 authors | the catalogue person whose printed / Arabic name matches |
| `fn-group[@content-type="endnotes"]` (heading → its `title`) | 0 → 200 notes in 6 articles, 5 titles; footnotes in `fn-group[@content-type="footnotes"]` | endnote ids `en-…`; calls unchanged, still linked |
| `boxed-text` | 0 → 0 (v2 has no type) | v3 "boxed" |
| `ack`, `app-group/app` | 0 → 0 (no such heading in the 55) | a section headed شكر وتقدير / Acknowledgements, ملحق / الملاحق / Appendix |
| `fig/alt-text` with `xml:lang` | 32 English descriptions now say so | (c) |

Editions: `inkscript edition` already reads front abstracts, keywords and translated titles, so with the abstracts out of
the body each prints once; a dates-only block goes to the printed front-matter blocks. **One line in `src/`**:
`edition/model.py` now reads `back/ack` and `back/app-group` after the body (before, text moved there would have been
lost from editions); `pytest -q` 118 pass. Quotations: the 55 hold 9 `disp-quote` and **no** paragraph that is only a
Quran verse (37 paragraphs quote one inline); inline Quran (`named-content[@content-type="quran"]`) is not tagged yet
(the verse crosses printed-line targets; next candidate, see `jats_coverage.md`).
**Validation**: 55/55 (v2 answers, today's code) and 6/6 (v3) JATS DTD + ALTO XSD valid (`coverage43.py build`).
Unit tests: `test_jats43.py` (6: dates, history labels, section heads, keywords and affiliation parts, the v3 rule,
the edition reading ack / appendix); `test_rules43.py`, `test_flags43.py` unchanged, 31 pass in all.
**Gold check**: three items changed, each accepted with the reason (`gold43.py accept`): 0747 and 1140 by the catalogue
person / affiliation tags only (no printed text changed); 2382 by (b), the history dates and the abstracts / keywords
moving to the front (blocks and printed text unchanged). Then 5/5 the same.

**Paid test** (`run43.py --set a --prompt v3 --run v3_test --cap 5.48`: the log stood at $3.4846, so at most $2 more):
6 articles chosen for the changes (2382 title / dates / abstracts, 0493 boxes / figures, 1140 and 0382 list vs
references, 1769 and 0355 endnotes and figures); 10 requests in 3 rounds, all STOP, **$0.6194** (247,105 input, 74,455
output tokens; dry run said $0.63 expected, $1.58 worst); log total now **$4.104**. v3 answers are 4% shorter than v2's
on the same chunks (74k vs 77k output tokens). `v3diff43.py` → `out/v3_test/v3_vs_v2.txt` (both through today's code, so
only the prompt differs); pages looked at next to the scan: `out/v3_test/shots/views/side_*` (v3) and
`out/v3_test/shots/views_v2/side_*` (v2).

| article | v3 vs v2 (judged on the scan) |
|---|---|
| 2382 | **Better.** p1: the English title is a translated title block (v2: other); `history` returned exactly (2022/05/12, 07/01, 07/15, lines 1:8–1:10); `aff_parts` institution جامعة المرقب, country ليبيا. «الملخص:» left inside the abstract block (v2 split it as a heading; both fine). Text identical. |
| 0493 | **Better, one view loss.** The three pull-quotes (p1 «١٠ ساعات متوسط مشاهدة الأطفال يومياً لبرامج التلفزيون», p2, p3) are boxed (v2: quote) and drawn as boxes. Affiliation split right (كلية التربية للطفولة المبكرة / جامعة القاهرة / مصر). p4: v3 put the other article's photos into other_article, so they leave 0493's JATS (right: the owner's earlier "limit" closed) but the Layout view no longer draws those pictures (worse to look at). |
| 1140 | **Better (a).** p1's four publications are list items like pp 2–11 (v2: paragraphs on p1). Text identical. |
| 0382 | **Same (a).** The bibliography stays references. |
| 1769 | **Mixed.** Endnotes 43/43 linked, 16 figure descriptions in both languages. **Worse**: 8 hieroglyph lines are no longer figures (pp 3–5; v3 left Azure's junk for them as noise, 19 lines without words, so their pictures are not drawn), and only 18 fixes against v2's 44 (v2's 21 fixes that wrote the print's dotted ي in على / إلى are not made: the text keeps Azure's reading there). Inscription translations pp 3–6 are now quotes (11), defensible. |
| 0355 | **Same.** Endnotes 51/51 linked; 9 numbered items decided list vs paragraph the other way on p7 / p11; fixes differ (v2 joined kashida-split words such as «التـ ـطور», v3 did not): run-to-run variance, not the v3 changes. |

**Worse with v3, to watch in the rehearsal**: pictures the model now files under other_article or leaves as noise are
not drawn (0493 p4, 1769 pp 3–5); fewer fixes on 1769 (variance or the longer prompt). Views:
`out/v3_test/views/index.html` (v3 and v2 per article), served as http://127.0.0.1:8899/v3_test/index.html (symlink
`experiments/41_azure_structure/out/views/v3_test`).

**Structured references (plan, not built).** Today a reference is `ref/mixed-citation`: the printed entry, untouched.
Parsed parts (`element-citation` with `person-group`, `year`, `article-title`, `source`, `volume`, `fpage` …) would let
the corpus link citations. Options: (1) **prompt**: v3 returns `"parsed": {authors, year, title, source, volume, issue,
pages, publisher, place}` per reference / endnote, each an exact substring; cost ~+30 output tokens per entry (the 55
have 186 references and 200 endnotes: ~+12k tokens, ~$0.07 on Batch; the 300 rehearsal ~+$0.4); quality unknown on
Arabic entries with Hijri dates and «د.ت» / «د.ن». (2) **parser** (no calls): Arabic and Latin patterns plus AnyStyle /
GROBID-style CRF for the Latin entries; free but weak on Arabic. (3) **both**: the model's parts checked by code
(substring, year range), the parser where the model is silent. Storage: `ref` with the printed `mixed-citation` *and*
an `element-citation` (JATS allows several citations in one `ref`); this needs one change in `inkscript edition`
(`model.read_body` now renders every child of `ref`, so a second citation would print the reference twice). Test:
hand-mark the parts of ~100 entries from 20 articles (Arabic, French, English; references and endnotes), score
per-field exact match; build it only if the parts are right on ≥ 90% of fields. Not done in v3: the edition change,
and no gold to measure against yet.

Files: `jats43.py` (the slots), `test_jats43.py`, `coverage43.py` (build + count), `v3diff43.py` (v3 vs v2),
`jats_coverage.md`; outputs `out/v3_test/` (raw, rules, masters, v2_now = v2 answers through today's code, views with
v2/ inside, shots, v3_vs_v2.txt/.json, coverage_v2.md, progress.md, run.log).

## A picture is never lost: code rule + prompt v3.1 (2026-10-18; owner-approved, cap $1; **$0.189 billed**, log $4.293)

**Problem** (owner, on the scans): prompt v3 lost pictures v2 drew. 1769 pp3–5: the hieroglyph strips were no longer
figures and Azure's reading of them («FRES safd.», «=DO», «DOA», «D A», «#») ran in quote blocks of the body text;
0493 p1: the cartoon beside «مقالات» was not drawn; 0493 p4: the other article's photos were filed under other_article
and not drawn at all.

**Code rule `rules43.pictures`** (after the answer; `ink43.py` measures the page; no calls):
1. *Ink without text.* On the 300 dpi render read at 100 dpi, ink = grey < 110 or a saturated colour (not on tinted
   paper); blanked: every Azure line box (grown 0.3 line heights) except narrow junk lines, and every figure / table /
   equation the answer has; thin rules (straight runs ≥ 8% of the page, < 1.5 mm thick) removed; strokes joined at
   2.5 mm; pieces of one strip joined (same row, gap ≤ 2.5 heights, strips ≤ 50/1000 high); two pieces with printed
   words between them joined (a cover cut by its own title), two photos with bare paper between them kept apart. Kept:
   ≥ 25 × 15 / 1000, area ≥ 1500, ≥ 6% ink in its box, not a shadow / solid tab at the page edge. Not a picture:
   a region holding or touching the title / a heading / the byline, or round a white-on-black title (0355 pp1–2's
   banners, 0331's hand-lettered title), a bar (≥ 10:1 and ≥ 35% full), the box round a page number, and anything at
   the same place (or mirrored) on another page of the chunk (running-head logos, page-number ornaments).
2. *Junk.* A line with no real word (Arabic ≥ 2 letters at confidence ≥ 0.5, or Latin with lower case, ≥ 3 letters,
   ≥ 0.6: transliteration «nbt», «hk3t» is text; «FRES», «DoC», «=10», digits, lone marks are not) touching a found
   picture is the picture's: out of every block, ALTO only as **`role.pictureJunk`**. Inside a figure the model drew,
   a line is junk only with no 2-letter Arabic word, no real word and Azure unsure (mean confidence < 0.6, < 0.4 with
   digits): a diagram's labels («EGR» «POV» at 0.9+, a chart's scale, 0041's Arabic labels) stay its text.
3. A found picture becomes a JATS `fig` (crop of the page) with `specific-use="ink-without-text"`, and
   `fig-type="decoration"` when < 150/1000 both ways with no words read from it (0493 p1's cartoon, 0197's end fleuron).
4. *Another article's picture* (the running text nearest to it is other_article): **not in this article's JATS**; its
   crop and an ALTO `Illustration` tagged `role.otherArticle` with the crop as `FILEID`; the Layout view draws it muted
   with that article's region and hides it with "Hide other articles". Chosen over keeping it in the JATS tagged: the
   JATS is this article (editions print it), and the ALTO already holds the other article's text the same way.
5. *Swapped box.* A figure box over ≥ 3 lines of text whose x/y-swapped box covers none is swapped back (v3's 0355 p1
   photo came as [y0, x0, y1, x1]); this runs before text-in-figure.

**How often it fires** (`pictures43.py --run R` → `out/R/pictures.json`, contact sheets `out/R/pictures/*.jpg`; every
firing looked at on the sheets):
| answers | new figures from ink | junk lines out of text / figure text | figures of another article | skipped (furniture, banners, bars, page-number boxes) |
|---|---|---|---|---|
| v2, the 55 | 6 in 6 articles (0197 end fleuron, 0355 p2 arrow, 0732 key-pattern band, 0498 p8 swash, 1769 p5 two inline groups) | 1 / 11 (1769 «FRES safd.», «LITERAT», «ifwants mound the branded»…, 1147 «72») | 4 (0493 p4) | 72 |
| v3 test (6) | 16 (1769 pp3–5: 10 hieroglyph strips and groups; 0493 p1 cartoon, p4 three photos + cover; 0355 p2 arrow) + 0355 p1 box swapped | 15 / 2 | 4 | 4 |
| v3.1 (2) | 1 (1769 p5) | 1 / 10 | 4 | 0 |
Before tuning, the same detector also took running-head logos (0498, 0418, 0920, 7956, 2502: 37 firings), a stroke
of 0331's hand-lettered title, 0498's page-number box, 1140's black bars, 2571's thumb tab and 0513's tinted page;
each is now a named skip above. **Replay of the 55 v2 answers** (`out/v31_test/v2_now/`, against the same answers
through this morning's code `out/v3_test/v2_now/`): 55/55 DTD + XSD valid; JATS text identical in 48; 0197, 0355, 0498,
0732 +1 figure each, 1769 +2 figures, 15 junk words out of figure text and «lo» out of a paragraph, 1147 one «72» out of a chart's text, 0493
four figures (and 55 words printed in them) moved out of the JATS as the other article's. No word of body text lost,
nothing doubled (a found picture never overlaps one the answer has: those are blanked). `gold43.py check`: 5/5 the
same. `flags43.py --run v2_55`: unchanged (51 flags).

**Prompt v3.1** (`prompt43.PROMPT_V31`, `V31_CHANGES`; `run43.py --prompt v3.1`): the figure entry gains "symbols,
hieroglyphs, logos, stamps, cartoons and decorative pictures are figures too, even small ones; what Azure read from
them ("FORM", "DoC", "=10", digit soup) is not text: put those lines in the figure's "lines", never in body text; such
junk inside a line of real text goes in "ornaments" with "picture": true". Code: a `"picture": true` ornament may have
letters (normal ornaments ≤ 1), but is refused where Azure read a real word; it leaves the text and its ink is ALTO
`role.pictureJunk`.

**Retest on Batch** (`run43.py --set a --prompt v3.1 --run v31_test --stems 0493… 1769… --cap 5.10`): 3 requests, all
STOP, $0.043 + $0.101 + $0.045 = **$0.189**. All three answers through today's code (`out/v31_test/masters`,
`v3_now/`, `v2_now/`), looked at next to the scan (`out/v31_test/shots/{v31,v3,v2}/side_*.jpg`):
| page | v2 | v3 | v3.1 |
|---|---|---|---|
| 1769 p3 | 3 strips figures (one with «FRES safd.» as its text, now out) | strips were quotes; now 3 figures from ink, junk out | 3 strips figures, junk out of body and figure text |
| 1769 p4 | 4 strips figures | now 3 figures from ink (one strip whole) | 3 figures |
| 1769 p5 | figures + 2 inline groups from ink | now 4 figures from ink | 3 figures + 1 from ink; FORM-like words out |
| inline signs in Arabic lines (FORM, 2996776, =10, lo, ARD…) | in the body (as in v3) | in the body | **10 out of the body** (picture ornaments); 001880, «جدـ» still in (not listed) |
| 0493 p1 cartoon | figure | now figure from ink (decoration) | figure |
| 0493 p4 photos + cover | figures in 0493's JATS; now out of the JATS, drawn muted | none; now 4 from ink, drawn muted | 4 figures, drawn muted, out of the JATS |
Views: `out/v31_test/views/index.html` (v3.1, v3, v2 per article), http://127.0.0.1:8899/v31_test/index.html (symlink
`experiments/41_azure_structure/out/views/v31_test`).

**Fewer fixes on 1769** (v2 44, v3 18, v3.1 20). The gap is orthography: the dotted ي in على / إلى that the print
shows (v2 12, v3 0, v3.1 0) and hamza the print lacks (أمام → امام: v2 8, v3 3, v3.1 1). Azure reads 20 على and 10 إلى
on pp1–8 against 45 علي and 8 إلي, so the print's dotted form is the rule there. Both v3 answers make the other fixes
(footnote markers, ش in شكل, superscripts) as v2 did. Prompt v3 did not touch the fix passage; it adds two-language
descriptions, quotes and boxes to the same output (tokens: v2 18.7k, v3 18.2k, v3.1 18.9k, all STOP), so the model
now spends less attention on orthography: a prompt-length effect, repeated in two v3 runs, not variance. Not changed:
loosening D30 is not the answer (each of these is a real ink-exact fix, the rule allows it); options for the owner:
(1) one sentence in the fix passage naming ى/ي and hamza as misreadings to fix when the ink shows them; (2) a code
flag (no fix) on Azure's low-confidence على / إلى (`flags43` `fixes_orth` counts the opposite direction today).

**Limits / worse.** A picture inside a printed line (1769's inline groups) drawn from the ink overlaps that line's text
in the Layout view (the text box is the whole line); 0493 p4's round photo already did. Single letters read at high
confidence inside a figure («D A», «#») stay the figure's text (they cannot be told from a diagram's «K»). Furniture
is recognised only within one chunk (a one-page chunk cannot see a repeat). The junk words inside Arabic lines need
the model (v3.1): confidence alone is not enough (166 low-confidence Latin / digit words in Arabic lines over the 55,
most real).

Files: `ink43.py`, `pictures43.py` (counts, sheets, `--build`), `rules43.py` (`pictures`, `figure_swap`,
`junk_line`, `bridged`…), `masters43.py` (`other_figure`, `pictureJunk`), `views43.py` (`other_pictures`),
`prompt43.py` (v3.1), `test_rules43.py` (+4 tests, 35 pass with jats / flags); outputs `out/v31_test/` (raw, rules,
masters, v3_now, v2_now, views, shots, run.log, v2_now_vs_before.txt, pictures.json), `out/v2_55/pictures*`,
`out/v3_test/pictures*`.

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

## Feedback loop (2026-10-18; owner-approved; no calls)

So that the 300-article rehearsal points at its own doubtful pages, the owner marks them, each pattern becomes a
code rule or a prompt change, and nothing regresses on what the owner has already checked.

**How to use it** (any run of `run43.py`; `replay` = experiment 41's 55 answers through today's rules):
1. *run* — `run43.py --set b --cap …`, then `run43.py --set b --assemble` (rules + masters, version-stamped).
2. *flags* — `flags43.py --run v2_fresh` → `out/<run>/flags.json` + `flags.txt` (per article: high / medium / low,
   first reason). Works on whatever answers exist (unfinished articles listed as pending); only reads the run.
3. *review* — `review43.py --run v2_fresh` → `out/<run>/review.html`: spots most serious first, each with the scan
   and our Layout view cropped to the same place (spot outlined), the reason, **yes, right / no, wrong** + note,
   filter by severity, "next unmarked", **Export my marks** (JSON). Self-contained, works on a phone; marks kept in
   the browser (localStorage, try/catch). Layout screenshots by experiment 40's Playwright venv (under 1 s a page, cached in `out/<run>/review/shots/`; the replay's 86 spots: 8.3 MB page, rebuilt in 13 s).
4. *import* — `gold43.py import review_v2_fresh.json`: "yes" spots join the gold set (`gold/<stem>__<run>.json`,
   snapshot of today's output, scope = those lines); "no" spots become open issues (`issues.json` → `issues.md`,
   with the note and a pattern name = the flag kind).
5. *rule* — fix the pattern in `rules43.py` (free, replayed on saved answers) or in the prompt (needs calls); set
   the issue's status: `gold43.py issue i3 --status "code rule" --pattern list-vs-body --rule "…"`.
6. *gold check* — `gold43.py check`: today's rules + masters on every gold article's saved answers, diffed with its
   snapshot (block kinds and levels, lines, text, reading order, call → note links; for whole articles also the JATS
   text, links and notes). Plain report; **exit 1 on any change**. A change on purpose:
   `gold43.py accept STEM --run R --why "…"`. `gold43.py stale`: masters made with older code or prompt text.

**Flags** (`flags43.py`, thresholds in `T`; unit tests `test_flags43.py`, 9 pass): failed / cut-off / retried
calls, cost far above the run's median per page; lines with words called noise or left out (what rules43 rescued:
a run of ≥ 3 lines = high) and specks still left as noise; a line placed twice; calls without a note (per page;
article-wide high when ≥ 5 and ≥ half the calls), calls whose marker is not in the line, notes without a call;
verse cuts that do not fit Azure's words, repaired splits, ornaments the code could not take out; "another article"
in the middle of a page, on an inner page, or over 40% of the lines; a page whose running-text mix (body / list /
verse) is far from both neighbours' (list vs body); heading levels jumping by 2; ragged table rows (spans counted);
LaTeX that does not convert to MathML; a page with ≥ 8 and ≥ 3× the article's median fixes; ≥ 3 hamza/ya-only
fixes on a page (D30: ink or silent repair?). The type-mix rule first used every block type and fired on table
and reference pages (2382, 0924): it now looks at running text only, and only between two neighbours.

**On experiment 41's 55 (replay; prompt v1 answers)**: 5 high, 56 medium, 25 low.
| kind | high | medium | low |
|---|---|---|---|
| call_no_note | 4 (0355 29/29, 1769 43/43, 0049 9/12, 0767 15/25 calls unlinked: endnotes v1 did not know) | 31 (pages) | |
| noise_rescued | 1 (0656 p4, 26 lines: the other article) | | |
| math_failed | | 15 (1148, 1147: `\begin{aligned}`) | |
| fixes_many | | 7 (2382 p6, p7; 0629, 0682, 0870, 0881) | |
| note_no_call | | 2 (0694: 59/59 notes uncalled) | 7 |
| verse_cut | | 1 (0355 21:63, the repaired split) | |
| type_mix | | | 9 (list vs body: 0498, 1106, 0474, 0881, 0478, 0058, 1769) |
| fixes_orth / noise_left / cost_high | | | 6 / 2 / 1 |

**The owner's five**: 0747, 0877, 0924, 1140 — no flags; 2382 — two medium `fixes_many` (p6 10, p7 13 fixes:
Azure's "In" for "ln" in regression tables; right fixes, so these would be "yes" in a review). No high flag.
**Batch test (prompt v2, 4 articles)**: 0 high, 0 medium, 2 low (0747 p3, p5: the 3 ornaments glued to words).
The four high `call_no_note` of the replay are what v2's endnotes fixed: 0767 on v2 has none.

**Gold set** (`gold/`, 5 items, all whole articles, run `replay`): 0747 from the owner's block-by-block marks
(183/183 yes, imported from `41_azure_structure/out/handcheck/marks/`), 2382, 0877, 0924, 1140 "right by eye, no
faults found" (41's hand check, 2026-10-16). Snapshots are today's rules on 41's answers; each file's `basis` says
how that differs from what the owner saw (0747: one ornament out, 13 verse lines re-boxed; 0924: 29 lines re-boxed;
the rest identical). `gold43.py check`: **5/5 the same**, exit 0. Issues: none yet (`issues.json`, `issues.md`).

**Version stamp** (`masters43.py`): every master built with the rules carries JATS `custom-meta` `stamp-prompt`,
`stamp-prompt-hash` (sha1 of the prompt text: v1 = 41's `structure.PROMPT`, v2 = `prompt43.PROMPT_V2`),
`stamp-rules-hash` (sha1 of rules43.py, masters43.py and 41's structure/reader/masters.py), `stamp-model`,
`stamp-run`, `stamp-made`, and a sidecar `<stem>.stamp.json`. `replay43.py compare` strips the stamp (still 52/55
JATS identical to 41). Limit: a raw answer records only the prompt *name* (run43.py writes `prompt: "v2"`), so the
prompt hash is of today's text under that name; if the v2 text is edited, give it a new name.

## Code fixes before the 300 (2026-10-18; owner-approved; no calls)

Five fixes from the owner's marks on the Layout views, plus a prompt v3.2 candidate (not live). Everything replayed
free on the saved answers: the 55 (v2), the v3 test (6) and the v3.1 test (2), through today's code
(`pictures43.py --run R --build out/fixes/R_after`): **55/55, 6/6, 2/2 JATS DTD + ALTO XSD valid**. Before / after,
scan beside our view: `out/fixes/shots/before/`, `before_v31/` and `out/fixes/shots/after/`, `after_v31/`,
`after_v3/` (0355 p1–2, 0478 p4, 1769 p3–5, 1010 p2 / p6, 1148 p3, 0924 p5, 0422 p1); views of the 55:
`out/fixes/views/mirror/<stem>.html`. JATS text of the 55 against this morning's masters (`out/fixes/v2_jats_diff.txt`):
**51 identical**; 0355 and 0422 (D33 title / author), 2382 (MathML names), 1769 («٥ D D 0», Azure's reading of a
hieroglyph strip now an inline picture, leaves the text; it stays in the ALTO as pictureText). Issues i6–i10.

1. **D33 metadata** (`meta43.py`, called at the end of `Master43.build`). A title or byline printed visibly as a
   fragment of a fuller form (every printed word inside it, a word cut by the design: tatweel at its edge, and
   longer than any printed piece) → the full form, from the catalogue first, unless the catalogue is only the
   printed fragments run together (then it was read from the cut print), else Gemini's reading; spelt word by word as
   the print / Gemini spell it where they are the same word (ى / ي, hamza, tashkeel aside). A title with a misprint
   flag → the flag's correction. JATS: `article-title` = corrected; the printed lines, with their id and line targets
   (the ALTO points at them), in `alt-title[@alt-title-type="printed"]` (a title piece on page 2 leaves the body the
   same way); author: `string-name` = corrected, `string-name[@specific-use="printed-on-the-page"]` = the printed
   pieces; a misprint flag in a keyword / affiliation / translated title is corrected in place (none in the tests).
   Log: one `custom-meta` "metadata-change" per change and `<stem>.metachanges.json` beside the masters (printed,
   corrected, source, reason, the other sources' forms). A person's correction wins: `corrections/<stem>.json`
   (`{"by", "title", "authors": {"1": ...}, "reason"}`, the hook for the future correction tool; none exists yet).
   View: the header shows the corrected title / author with a small "corrected" mark; hover / focus shows the
   printed form, the source and the reason. **Fires**: 0355 (v2) title «أثر التطور الاجتماعى على تطور الأشكال الفنية
   في القصة المصرية الحديثة» (source catalogue; printed «أثر التـ عَلى تطـ فنى القـ … ـور الاجتماعى ـور الأشكال الفنية
   ـصَة المصريّة الحديثة»; the owner's «فى» comes out «في»: the print's word is a flagged misreading «فنى», so the
   catalogue's spelling is used) and author **«يوسف الشارونى» (source Gemini, not the catalogue)**: the catalogue's
   authority 130243 reads «الشوني، يوسف», exactly the visible pieces «يوسف الشـ» (p1) + «ونى» (p2) joined; the letters
   «ار» are lost in the spread's gutter, and Gemini's «الشارونى» is the critic Yusuf al-Sharouni (the subject, the
   Egyptian story, fits). The catalogue's form is in the log; **a person should confirm** (and the catalogue record
   may need the same fix). v3 answer of 0355: title the same; author not changed (v3's Gemini gave the fragments
   «يوسف الشـ ونى» as the name: no source holds a fuller form). 0422 title misprint «تضمنتة» → «تضمنته» (Gemini's
   sic flag). Other cut or decorative titles in the 55: none fires (0331's hand-lettered title and 0447's display title
   print whole; 0355 is the only title cut by the design). Not done: author names Gemini silently normalised where no
   byline block exists (26 contribs have no printed byline block on page 1; their printed form is not known to code).
2. **Blocks on top of each other** (0478 p4). The Layout view's boxes (`views43.pieces43`, replacing 41's
   `pieces_of` for text): (a) a box is cut where its lines change width sharply (a line ≥ 1.5× the piece's lines and
   reaching out of it by ≥ 25%, in a piece of ≥ 2 real rows), and again where the column resumes; the text flows
   through the parts (0478 p4's «يعرف وقت الدوره…» ends in two full-width lines: now a column box and a full-width box);
   Azure lines of one printed row stay one row however far apart (they started a new box before: 1010 p2 «Hirschfeld»
   / «Tanner», 1769 p3 / p5 first rows); a row Argon put out of order inside the same column is not a column turn (1010
   p6). (b) `rules43.long_headings`: a heading of > 3 printed rows (or 3 and > 4× the article's median heading words)
   keeps its short top rows, the rest (≥ 2 rows, ≥ 12 words, wide rows) becomes a paragraph; kept whole and flagged
   otherwise. (c) `rules43.header_text`: a header / footer line of ≥ 5 words, ≥ 15 letters, not journal / date
   furniture, unlike the running heads of the chunk's other pages, sitting next to the running text in its column →
   back into the article (list item when it opens with a number and the next block is a list item). **On the saved
   answers (b) and (c) do not occur**: v2's 0478 p4 has the heading as 4 Azure lines on 2 printed rows and the page
   number with the running head in its own header block (the overlap was (a) alone); 41's v1 answer had the heading
   and paragraph in one list item. Both rules are unit-tested on a 0478-like page; over the 55 (b) keeps 2 headings
   whole and flags them (0447 p1 display title, 7956 p2 English title), (c) fires 0 times (every long header line is a
   running head: 0058, 0200, 0478, 1000, 1148, 1769 …). **Overlaps over the 55** (two text boxes > 25% of the
   smaller): **11 → 3**: 0478 p4 (4 → 0), p7, 1010 p2, p6, 1769 p5 fixed; left: 0682 p26 (Azure's own boxes of two
   footnote lines overlap), 0924 p5 (the unit words «مليم جنيه» print on the heading's row), 1148 p3 (an equation
   on two rows round a text line). 10 width cuts (0422, 0478 ×2, 0877 ×4, 1010 ×3).
3. **Pictures inside a printed line** (1769 pp3–5). Masters: a picture inside a row of running text (≤ 3.2 of the
   row's line heights, overlapping it by half, within 3 line heights of its words) is an `<inline-graphic
   specific-use="picture-in-line">` at its place in the paragraph (after the words that come before it; ALTO
   `Illustration` pointing at it); a v3.1 picture ornament (Azure's junk word inside a line) becomes the same, its box
   from the ink round the junk word (real words blanked, signs of one group joined); a picture on a line of its own
   stays a `fig`. View: the row is cut round the picture (the words on each side their own boxes, from Azure's word
   boxes). p3's top lines overlapping themselves: the row's two Azure lines (Azure cut it at the picture) became two
   boxes, the second covering the rows below (fixed by keeping rows together, 2 above). **Fires**: v2 3 inline
   pictures (1769 p5: 2 from the ink rule + 1 model figure), v3 3, v3.1 11 (8 from picture ornaments). Left: groups
   neither the model nor the ink rule found (1769 p3 «يخص [group] nbt», «001880») are not drawn.
4. **New flags** (`flags43.py`): `overlap` (two text boxes of the view after its box cutting overlapping > 25% of the
   smaller by area; masters built in a temporary folder, `views43.measure`), `inline_picture_over_text`,
   `long_heading` (split: low, kept: medium), `header_running_text` (medium). On the 55: overlap 3, long_heading 2,
   inline_picture_over_text 0, header_running_text 0; all flags: high 3, medium 32, low 24 (`out/v2_55/flags.txt`).
5. **Tidy-ups**. (a) MathML (`masters43.mathml43`): a run of 3+ capitals with a subscript or under \ln / \log /
   \Delta is one `mml:mi`; plain ln / log / sin … the function; matrix products stay letters (1147's VRV', IWX,
   WRW: first draft merged them, narrowed). 2382: 12 names (END, EGR, POV), the only change; gold accepted. (b) The
   figure "text" button only for ≥ 4 words or ≥ 20 letters; the words stay in the JATS (1769: 8 buttons → 2).
   (c) **Byline / dates from their JATS slots: left as is.** 30 of the 33 printed front-matter blocks hold printed
   words no slot holds (role phrases «بقلم»، «إعداد»، titles «د.», labels «تاريخ الاستلام», emails, affiliations run
   in); the view shows the print, so reading from the slots would drop printed words. The custom-meta is the printed
   block, not a duplicate.

**Gold check**: 2382 changed by 5a only (MathML names; LaTeX, blocks, printed text unchanged): accepted; then **5/5
the same**. Unit tests: `test_rules43.py` +3 (long heading split / kept, running text out of a header), all 41
pass in the experiment (rules, jats, flags, refs).

**Prompt v3.2 candidate (not live; `prompt43.PROMPT_V32`, `V32_CHANGES`; `run43.py --prompt v3.2` would select it)**
= v3.1 plus (i) in the fix passage: "if the ink shows ي (dotted) or a hamza and Azure read ى or no hamza, fix it to
what is printed; never add dots or hamzas the print lacks" (owner-approved; 1769: v2 12 such fixes, v3 / v3.1 none);
(ii)–(iii) a "PARSED REFERENCES" paragraph: each reference block adds `"parsed": [W]`, each footnote / endnote
citing works `"cites": [W, …]`, W = {type, authors [{surname, given}], year, title, source, volume, issue, pages,
publisher, place, doi, url, lang}, every value an exact substring of the printed entry, Hijri years and «د.ت» /
«د.ن» as printed, ibid-style notes none (prompt +1,232 characters). Masters ready (`refs43.add_parsed`, called by
`build43`; reads the fields from the answer files since `structure.assemble` drops unknown block keys): `ref` keeps
the printed `mixed-citation` and gains one `element-citation[@publication-type]` per work (person-group / name,
article-title or chapter-title, source, year, volume, issue, fpage / lpage, publisher, pub-id doi, ext-link);
a note gets `<p content-type="parsed-citations">` holding its element-citations; a field that is not a substring of
the print is dropped and counted; no-op on today's answers. Tested on a hand-made answer marked SIMULATED
(`test_refs43.py`, 3 pass, DTD-valid). `src/inkscript/edition/model.py`: a `ref` with a mixed-citation skips its
element-citation, a note skips the parsed-citations p, so an edition prints each reference once (`pytest -q` 118
pass). **Cost**: the 55 hold 186 references and ~264 notes citing ~310 works: ~1.24 works a page, ~80 output tokens
a work (155 at worst) → ~+100 output tokens a page, ~+700 an article (+10%); **the 300 sample: ~0.35M extra output
tokens, ~$1.7 on Batch now ($3.5 from 1 Dec), worst ~$3.4 ($6.8)**, plus ~0.17M input for the longer prompt (+$0.17).

Files: `meta43.py` (D33), `refs43.py` + `test_refs43.py` (parsed references), `views43.py` (`pieces43`,
`row_round_pictures`, `overlaps`, `measure`, the corrected mark, the figure-text threshold), `masters43.py` (inline
pictures, `tight_picture`, `mathml43`, the D33 / refs hooks, `<stem>.metachanges.json`), `rules43.py`
(`long_headings`, `header_text`), `flags43.py` (4 kinds), `prompt43.py` (v3.2); outputs `out/fixes/` (`*_before`,
`*_after`, `views*`, `shots/`, `overlaps_*.json`, `gold_check.log`, `flags_v2_55.txt`, `v2_jats_diff.txt`).

## What's next

1. Owner looks at `out/prompt_v2.html`; decide the cap (the dry run suggests $10 on Batch for the 55).
2. ~~A small Batch check~~ (done, "Batch test"), ~~then `run43.py --set a --cap 10`~~ (done, "Run of the 55": $3.18).
   Owner looks at `out/v2_55/views/index.html` (the 9 marked first); decide the list-vs-references rule.
3. Prompt v3.1 (v3 + pictures) is the candidate for the rehearsal (`--prompt v3.1`; section "A picture is never lost");
   decide the fix-count question there (ى/ي and hamza). Prompt v3 (owner's (a)–(c) + boxed text, quotations, history, affiliation parts): run the rehearsal with
   `--prompt v3`; watch pictures filed as other_article / noise and the fix count (section "Prompt v3 and JATS coverage").
4. Fetch the 114 catalogue documents, measure their layouts, swap from the reserve to fill verse / equations, then the
   rehearsal (`--set b`).

## Files

`prompt43.py` (prompt v2) · `rules43.py` (code rules) · `test_rules43.py` · `masters43.py` (41's masters + v2 code) ·
`views43.py` (Layout view from a masters folder) · `jats43.py` + `test_jats43.py` (JATS slots) · `coverage43.py`, `jats_coverage.md` · `v3diff43.py` · `flags43.py` + `test_flags43.py` (doubtful spots) ·
`review43.py` (owner's review page) · `gold43.py` + `gold/` (gold set, check, stale, issues) · `issues.json` / `issues.md` · `replay43.py` (harness, rules, masters, compare, simulate) ·
`side43.py` (scan beside our Layout view, one JPEG a page) · `shots43.py` (Layout-view screenshots; experiment 40's Playwright venv; now waits for the mirror's `fitted` class instead of a 60 s timeout, `SHOTS_SCALE`) · `page43.py` (owner's page) · `run43.py`
(Batch / Standard runner, dry run) · `compare43.py` (a run vs 41 and the replay, per article) · `probe43.py` (Batch request-shape probe) · `sample43.py` + `sample43.json` (fresh sample). Outputs under `out/`
(gitignored): `replay/`, `masters/` (v2 rules), `masters_id/` (harness), `masters_sim/`, `simulated/`, `views/`
(simulated), `views_replay/`, `shots/`, `prompt_v2.html` + `prompt_v2/`, `v2_55/dry_run.json`, `v2_fresh/dry_run.json`,
`features43.json`, `catalogue_draw.json`, `fetch/ids.txt`.

# Experiment 60 — Claude Opus 5.5 as the reader, head to head with Gemini 4 Argon

**Question (owner, 2026-10-31).** Put Claude Opus 5.5 (`claude-opus-5-5`) in Argon's place in our real pipeline:
same requests (page images + Azure's numbered lines + context, answers in line ids only, D30), same rules43 →
enrich43 → masters43 code, same gold. Is it a better reader, a better reader for some passes (references,
metadata), or not? Cap $40 of Anthropic spend; no Gemini calls.

**Status.** Done 2026-10-31. **$30.78** spent (list price of billed tokens; 196 Messages requests + 3 free token counts, all logged in
`out/calls.jsonl`). Side-by-sides looked at in Chromium: `out/side/index.html` (front page), `out/side/t1.html`
(44 proof pages), `out/side/t2.html`, `out/side/t2_tables.html`. Log of the work: [progress.md](progress.md).

## Answer

**Not as the reader.** At the setting that matches Argon's (thinking low → effort low), Claude follows the
line-id contract perfectly, but it does the *reading* part of the job far less: it leaves Azure's misreadings in
place, does not report table cells Azure never read, parses far fewer works in footnotes and drops fields from
long reference lists. Effort medium (Opus 5.5's default) narrows this only a little. It also costs about **2.6×
Argon per page today** (≈1.3× after Argon's price doubles on 1 December). Not recommended for any pass either:
references and metadata are where it is weakest.

| Test 1: proof pack (exam, v3.3) | Argon, first answer | Claude, effort low |
|---|---|---|
| 60 pages right / minor / serious | **42 / 18 / 0** (after judge + patches: 43 / 17 / 0) | **15 / 42 / 3** |
| wrong words, the 10 word pages (1,532 words) | 0 | **21 (1.4%)** |
| metadata fully right (30 articles) | **25** | 15 |
| citations fully right (69 of the 80 sampled) | **47** | 16 (27 not parsed at all) |
| fields of those citations right / loose / missing / wrong | 263 / 14 / 10 / 0 | 151 / 9 / 126 / 1 |
| Azure fixes proposed (the same 124 chunks, 899 pages) | 2,309 | 252 |
| `sic` (printed misprints flagged) | 451 | 7 |
| missed text (cells Azure did not read, …) | 23 | 5 |
| works parsed in footnotes / endnotes | 1,078 in 814 of 1,245 notes | 430 in 392 of 1,260 notes |
| lines left out / used twice / invented ids (36,820 lines) | 0 / 2 / 0 | 1 / 0 / 0 |
| invalid or unparseable answers | (exam: 3 of 491) | **0 of 196** |

| Test 2: gate 1 (0130, v3.5b, 12 articles, 224 pages) | Argon | Claude |
|---|---|---|
| document type | 12 / 12 the same (research ×9, editorial, report) | same |
| corresponding author | none found | none found |
| reference works with a title / authors (424 works) | **423 / 419** | 207 / 219 |
| … with editors / translators / edition / cited pages / Hijri calendar | **10 / 16 / 16 / 9 / 9** | 1 / 6 / 7 / 3 / 4 |
| affiliation split (institution parts / countries in the masters) | **33 / 10** | 19 / 4 |
| Azure fixes proposed | 375 | 12 |
| tables: cells in the 12 articles' tables | 2,404 | 2,267 (empty cells and empty rows dropped; stacked rows kept stacked) |
| figures in the masters | 39 | 22 (0130-020-079-001 p17: 5 captioned photos → 2 pictures, captions merged or lost) |
| note calls linked | same | same |

**What Claude is better at (small, real):**
- **It does not "fix" what the print says.** Argon sometimes corrects a printed misprint or a right Azure reading:
  0732 p17 printed «للتواقع» (Argon → للواقع, against D30); 2483 p24 «first» → Argon «firsf», «subsequently» →
  «subsequeently»; 2483 p3 «أستراتيجية» → Argon «أستواتيجية»; 0664 p2 «يريد» → Argon «يزيد»; 0631 p3 a printed «:»
  and «..» → Argon «.» and nothing. Claude kept all of these as printed. (These were inside pages the proof pack
  called right, so the proof's "0 wrong of 1,532" was very slightly generous to Argon.)
- **Cleaner metadata in a few spots:** a kicker label kept out of the title (0331 «جدول أعمال :»), the book's
  «تأليف …» line not made the subtitle (0735), an affiliation without the person's job title (1036), a reference
  year without the day and month (gate 1, «2007، 31-29 ديسمبر» → 2007), the cited pages «ص 118 - 119» of a book
  put in `cited` where Argon put them in `pages`.
- **Perfectly well-formed:** 196 of 196 answers clean JSON on the first try, no truncation, no invented ids.

**What Claude is worse at (large):**
- **Azure's misreadings stay.** 0201 p3 «وهي» for وعي and a smudged أهداف left as «اهـ.٤١،»; 0135 chemical names
  (dgmC, NHZOAc, dIN3); 0295 p3 table decimals (٢٣٩ for ٢٣ر٩, ١٢٨٨ for ١٢ر٨); 1173 p8 all 18 superscript note
  markers left as « " vi" X" » so the notes do not link; 0416 «مد» for the ligature محمد; display titles in stylised
  type read as Azure read them (0597 «الفتنة يا ◌ً الليجا الجد», 0924 «ضَاءِكَةُ الأَعْنَ الَهْلِيَّةُ»).
- **Unread table cells are not reported** (0201 p11: 14 row numbers, 0295 p3: 3 cells): both pages stay serious;
  Argon's `missed` let the code rule place them.
- **References.** Footnote works mostly not parsed; in long reference lists many works lose their title / authors
  (0130-020-077-002: 3 of 39 with a title); editors after «تحقيق» / «(Eds.)», translators after «ترجمة», editions
  («3rd ed.», «ط2») and Hijri years mostly not marked.
- **Metadata.** Co-authors left out (2483: 2 of 7; 1633: 1 of 8; 1036: the translator), titles cut or split
  (2483, 8480), 1289's title words reversed and its printed page not read (the catalogue's wrong 51–52 stands).
- **One structural error of the kind the judge argued about:** 0732 p13 the three-column strip of another text
  under the rule is read into the article's body (Argon: other_article). Counted serious here; the proof pack had
  called the judge's same unmarking "doubtful".

**Effort medium** (the same 42 chunks holding the 60 pages, with Gemini's exact requests; $6.41): fixes 77 → 176
(Argon 604), missed cells 0 → 1 (Argon 18), works in notes 83 → 134 (Argon 160); on the 60 pages, lines whose text
differs from Argon's 202 → 171, pages identical to Argon's 17 → 17; 0201 p11 gets 1 of its 14 cells, 0295 p3 none.
More thinking helps a little; it does not close the gap.

## Privacy (read before any page was sent)

Read 2026-10-31, before the first call:
- **Training:** "By default, we will not use your inputs or outputs from our commercial products (e.g. … Anthropic
  API …) to train our models" (privacy.claude.com, article 7996868); exceptions are explicit feedback and an
  explicit opt-in. Commercial Terms: "Anthropic may not train models on Customer Content from Services";
  "Customer Content is Customer's Confidential Information"; the customer owns its inputs and outputs.
- **Retention:** API inputs and outputs are deleted "within 30 days of receipt or generation" (article 7996866),
  longer only for a service under the customer's control (Files API), by agreement, for Usage Policy enforcement
  (flagged content up to 2 years, classifier scores 7 years) or by law. The Message Batches API stores requests
  and results up to 29 days and offers `DELETE /v1/messages/batches/{id}` (platform.claude.com, batch-processing).
- **Zero data retention:** available by agreement with Anthropic sales for the Messages API (Opus 5.5 is not one
  of the "Covered Models" that require 30-day retention); the Batch API is *not* ZDR-eligible (it must store jobs).
- Verdict: no training by default + limited retention → go. **Sent:** the chunks of 93 exam articles (899 pages:
  the 60 proof articles up to their last sampled page, the chunks holding 69 of the 80 sampled citations), 12
  gate-1 articles (224 pages), the same 281 exam pages again at effort medium, and one page image + one chunk's text
  to the free token-counting endpoint. Nothing else. **Every batch was deleted on Anthropic's side right after its
  results were collected** (13 of 13, `out/*/batches.json`); the 2 pilot calls (Standard) follow the 30-day rule.
  Production use should go through a ZDR agreement on the Messages API (no Batch discount then).

## Method

- **Requests** (`common60.py`, `run60.py`). `prompt43.make_prompt` builds the prompt and images exactly as for
  Gemini; `samereq60.py` checked that it rebuilds the stored exam / gate-1 Gemini requests **byte for byte** (text
  and images, 5 chunks). Each Gemini part becomes a Messages API block in the same order ("Image k:" text, then the
  base64 JPEG, then the prompt). Only plumbing differs: Gemini's `responseMimeType: application/json` became one
  system line ("Answer with the JSON object only …"); thinking "low" became `output_config.effort: "low"` (Opus 5.5
  always thinks; effort is its only control); `max_tokens` = Gemini's allowance + 8,000 for thinking. No prompt
  text was changed (it has no Gemini-specific phrasing that needed it).
- **Context of later chunks.** For the 60 page + metadata articles, chunk *n* gets the outline and last block from
  **Claude's own** earlier answers (`run43.state_for` on our raw folder), in rounds, as the pipeline runs. For the
  citation-only chunks (no earlier Claude chunk), Claude got the **exact request Gemini got** (context from Argon's
  earlier answers), read back from `43_rehearsal/out/v33_300b/batch/`. The medium arm used the exact Gemini
  requests too.
- **Batch.** Message Batches, ≤150 MB of payload per batch (a 73-request batch was refused with 413 at 256 MB),
  custom ids `q0000…` mapped back (stems hold commas, not allowed in ids), cap check before each batch on the worst
  case (input estimate + every request's `max_tokens`), results saved in experiment 41/43's raw format, batch deleted.
- **Build** (`build60.py`). The answers through today's rules43 + the letter fix (as production since 2026-10-22)
  + enrich43 + masters43, with experiment 43's code unchanged, into `out/<run>/build/`; Argon's same answers through
  the same code into `out/<run>/argon_build/` (the fair twin: its metadata equals the judged fix-3 masters on all
  30 articles, its pages equal them on 54 of 60, the other 6 differ only by the letter fix or one judge edit).
  A master needs every chunk, so where Claude was not asked for a chunk Argon's answer stands in
  (`out/<run>/hybrid_who.json`); only Claude's pages are scored. 93 + 12 + 32 masters, all JATS DTD + ALTO XSD valid.
  render43's page check was made read-only for this process (no page re-rendered, nothing written into exp 43).
- **Scoring, test 1** (the proof pack's rubric and gold). Where Claude's master shows a page, a metadata field or a
  citation exactly as Argon's, it takes the proof pack's verdict (after fix round 3); everything that differs was
  judged by hand against the scan, line by line (`pages60.py`, `side60.py`, `score_pages60.py`; `meta60.py`,
  `score_meta60.py`; `cites60.py`, `score_cites60.py`). As in the proof pack, a hamza, a vowel mark or a dotless ى
  that Azure normalised is an orthographic difference, not a wrong word. Every hand verdict, with its reason, is in
  `out/t1/page_verdicts_claude.jsonl` and the HAND tables of the two score scripts.
- **Scoring, test 2** (`t2compare60.py`, `tables60.py`). Both readers answer in Azure's line ids, so a reference
  block is the same block in both: its works are compared key by key; disagreements in `out/t2/disagreements.jsonl`.
  Adjudicated against the scan / printed lines: the 13 v3.5b-field cases listed under "What Claude is worse at" and
  "better at", the 6 tables and 2 figure pages of `t2_tables.html`, 6 random text-difference pages of `t2.html`
  (Argon right on every sampled text difference there).

## Cost, tokens, speed

| | Claude Opus 5.5 | Gemini 4 Argon |
|---|---|---|
| price per MTok in / out | $4 / $20 (Batch $2 / $10) | Batch $1 / $5 now ($2 / $10 from 1 Dec 2026) |
| tokens per page in / out (v3.3) | 7,538 / 581 | 3,363 / 892 |
| one 2,400 × 1,527 page image | **4,733 tokens** (count_tokens; Opus 5.5's high-resolution tier caps at 4,784) | 1,107 (media HIGH) |
| prompt text, 7 pages of lines | 17,295 tokens (1.86 characters a token) | ≈ 13.5k |
| per page, Batch, v3.3 / v3.5b | **$0.0209 / $0.0239** (effort medium $0.0228) | $0.0080 / $0.0105 (exam with judge: $0.0094) |
| per page, Standard (list) | $0.042 / $0.048 | — |
| per article (11.35 pages, the exam's mean) | $0.237 Batch | $0.090 (with judge $0.106) |
| **per 1M documents** (11.35 pages each) | **$237k** Batch v3.3, $272k v3.5b; $474k / $543k Standard | $90k v3.3, $119k v3.5b now; $180k / $238k after 1 Dec |
| latency | Batch: 13 batches of 1–33 requests, each done within 2–4 min; Standard: 22.5 s (7 pages), 23.7 s (3 pages) | Batch jobs 2.4–7 min |

The image is most of Claude's input (≈ 63% of tokens). Prompt caching would save little here: the fixed
instructions come after each chunk's lines in this prompt (a reordered prompt could cache them, ~5% of input).

## Recommendation

1. **Keep Argon as the reader.** At matched settings Claude is worse on every gold measure except "never changes the
   print", and costs 2.6× (1.3× after 1 December).
2. **Not for a references or metadata pass either**: those are its weakest parts here (16 vs 47 citations, 15 vs 25
   metadata), and v3.5b's new reference fields mostly go unmarked.
3. **Worth carrying over:** the cases where Argon "fixed" the print (للتواقع، firsf، subsequeently، أستواتيجية،
   يزيد) suggest a check in our own rules: a fix that turns a dictionary word into a non-word, or changes a word
   the ink shows clearly, should become a `sic` flag or be refused. Claude's restraint here is the behaviour D30 asks for.
4. If Claude is tried again, it should be at effort high with a ZDR agreement on the Messages API (no Batch
   discount then, ≈ $0.05–0.06 a page) and only on a pass where its restraint is the point (e.g. a second opinion
   on Argon's fixes), not as the reader.

## Files

- `common60.py` client, request plumbing, pricing, call log; `run60.py` Standard / Batch runner with cap and resume;
  `plan60.py` the test-1 plan; `reqindex60.py`, `samereq60.py` the stored Gemini requests and the byte-for-byte check.
- `build60.py` rules → masters for Claude and the Argon twin; `audit60.py` lines left out / twice / invented, fixes, missed.
- `pagedump60.py`, `pages60.py`, `side60.py`, `shots60.py`, `score_pages60.py`; `meta60.py`, `score_meta60.py`;
  `cites60.py`, `score_cites60.py`; `t2compare60.py`, `tables60.py`; `index60.py`.
- `out/` (gitignored): `calls.jsonl`, `t1/` `t2/` `t1m/` (raw answers, builds, scores), `side/` (pages and shots).
- The `anthropic` SDK (2.3.0) was installed into `.venv` for this experiment; `pyproject.toml` was not changed.
- Cosmetic, not fixed: masters43 writes "Gemini 4 Argon" in the ALTO processing note and the `fix.argon` tag
  whoever the reader was (only this experiment's out/ masters carry it).

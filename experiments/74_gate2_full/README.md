# Experiment 74: the rest of gate 2 — eight more education journals and 0130's Word years

> **PARKED (2026-11-04, ≈11:15 CST, by the owner via the lead: gate 2 paused for another experiment).** Safe stop:
> nothing is half-loaded; the platform DB and the Desk are consistent; no model call is running or queued.
>
> **Live release: `R20261104T151029`** (22,121 decisions applied, 0 orphaned, 4 conflicts — listed under Issues).
> `/audit` points at `out/audit_live`. **Spend: $365.23 of the $400 cap** (reading $325.51, librarian $39.72;
> `python3 spend74.py`, per journal `python3 cost74.py`). Nothing was spent after the stop.
>
> | journal | read (scan / Word) | 10 pages + audit | in the platform | librarian | releases |
> |---|---|---|---|---|---|
> | 1001 | done (89 / 102) | pass (0 words; leak 0.157%) | live | **applied** | R20261103T120721, R20261103T155409 |
> | 0840 | done (82 / 116) | pass (1 word; 0.025%) | live | **applied** | R20261103T125053, R20261103T164042 |
> | 0097 | done (83 of 84 / 72) | pass (0; 0.011%) | live | **applied** | R20261103T160343, R20261103T192456 |
> | 0130 Word years | done (– / 175) | – (no scans) | live | **applied** | R20261103T174811, R20261103T230107 |
> | 0246 | done (194 / 269) | pass (0; 0.337%) | live | **applied** | R20261103T205906, R20261104T151029 |
> | 0013 | done (124 / 124) | pass (0; 0.015%) | live (reading R20261104T003753) | **verified, NOT applied** (plan ready: 5,427 decisions, 486 tasks; its dry run was stopped at the park — redo it) | — |
> | 0011 | done, judged, built valid (130 / 194) | **look FAILED** (3 words wrong) | not loaded | not run | — |
> | 0523 | done, judged, built valid (346 / 161) | **look FAILED** (5 words wrong, 3 serious pages) | not loaded | not run | — |
> | 1182 | Word route built (334); **scans not read: over the cap** | – | not loaded | – | – |
>
> **Next, in order (to resume):**
> 1. **0013's librarian** (verified: hand check 227 right / 8 minor / 4 wrong of 239, failing kinds held; alarm 59/60):
>    `cd experiments/49_correction_desk && LIB74_J=0013 LIB74_RELEASE=/home/appuser/data/desk/releases/R20261104T003753.db
>    .venv/bin/python ../74_gate2_full/lib/dryrun74.py --out <scratch>`; put this pass's conflicts in
>    `out/0013/lib/exclude74.json`; `cd ../74_gate2_full/lib && LIB74_J=0013 LIB74_RELEASE=<same> ../../49_correction_desk/.venv/bin/python plan74.py`;
>    then `LIB74_RELEASE=<same> bash golive74.sh 0013` (backup, import ~1.5 h, release). Telegram line for 0013 after it.
> 2. **The owner decides on 0011 and 0523** (read and valid, failed the ten-page look): a second ten-page sample, a
>    targeted fix of the faults seen (joined words in tables; «إذ» read «إذا»), or load as is. To load one:
>    `bash load74.sh J && bash gate74.sh J && bash golive_load74.sh J`, then `lib/run_lib74.sh J <release> <guard>` and
>    the librarian steps of `lib/common74.py` (review by hand, hand check, dry run, `lib/golive74.sh J`).
> 3. **1182** needs ≈ $87 for its scans (dry run `out/1182/j1182/dry_run.json`) + ≈ $15 judge / librarian — a new
>    approval: `run43.py --set g --run j1182 --prompt v3.6 --thinking low --cap <log + 100> --max-enqueued 1800000`, then
>    `finish_read74.sh 1182`, and the steps above. Its Word route is built (`out/1182/w1182_final`, 334 valid).
> 4. Desk tests: `experiments/49_correction_desk/tests/test_rules.py` pins the detector counts (93 / 609, now 106 / … after the loads): re-pin on the
>    final release; `experiments/49_correction_desk/tests/test_release.py`'s link47 timeout is already raised to 90 min (the run passed 30 min on the
>    grown platform). Run the suite off-hours (45+ min).
> 5. Classic pages: published for every scan run read (`views74.sh J`; j1001, j0840, j0097, j0246, j0013, j0523 and
>    their `_final`); the held 0011 not linked (run `views74.sh 0011` if it is loaded).
> 6. The gate-2 summary below uses the live release; re-run `bridges74.py` after 0013's librarian.
>
> Open issues for the lead: two look failures (0011, 0523); 1182 over the cap; four Desk conflicts (the known
> CF622F7PED split; exp 72's relate on CCTVAJDDCR; exp 64's Zaytuna link — the 0246 load put Jordan's
> «Alzaytona University» on machine row I4PE3FZMDC; a link_publication on CFWGE8ZK7S); link47 drops author-only
> catalogue persons (9 ids over the loads); the P6 / D43 rules mistype Dissertation Abstracts entries; the D44 rule and
> Opus' retitles are held; the API needs no restart for data (it reads the newest release) — the code changed in
> `desk/release.py` (CLI releases only) and exp 70's pending `index_pages.WHOLE_JOURNALS` restart is still pending.

**Question** (owner-approved 2026-11-03; HARD CAP $400 of model spend, Gemini and Anthropic together). Read the
remaining journals of experiment 54's selection the way experiment 70 read 0165 (scans + Word files, 2010–2025), run
the production librarian of experiment 72 on what each one adds, and load 0130's Word-only years. Journal by journal:
read, judge, build valid masters, load into a copy of the platform and swap, check on the scans and in the audit,
librarian, verify, apply as Desk decisions, release. Stop a journal whose quality gate fails; stop before $400.
Then answer gate 2's question across all ten: **do these education journals form a citation network?**

**Answer (on the live release, seven journals: 0130, 0165, 1001, 0840, 0097, 0246, 0013 — 1,920 articles).**
- **Yes, they form a network.** Of the 42 ordered pairs of journals, **30 (71%) cite each other** at least once; 252
  references go from one of these journals to another (`out/bridges74.json`; row cites column):

  | | 0013 | 0097 | 0130 | 0165 | 0246 | 0840 | 1001 |
  |---|---|---|---|---|---|---|---|
  | **0013** | (155) | 0 | 4 | 2 | 7 | 3 | 1 |
  | **0097** | 0 | (10) | 2 | 4 | 5 | 0 | 0 |
  | **0130** | 46 | 4 | (88) | 31 | 9 | 1 | 5 |
  | **0165** | 5 | 1 | 19 | (63) | 0 | 0 | 2 |
  | **0246** | 15 | 13 | 9 | 6 | (26) | 2 | 1 |
  | **0840** | 40 | 2 | 0 | 0 | 5 | (8) | 0 |
  | **1001** | 0 | 4 | 1 | 0 | 3 | 0 | (6) |

  (In parentheses: references to the journal itself.) The two psychology journals pair up (0840 → 0013: 40), the
  childhood journals cite each other and 0013, and the Syrian 0246 cites five of the six.
- **Authors and cited works are the bridges; institutions are not.** Against 10 random sets of the same size from
  the random 600: shared byline authors with the other journals 5–49 per journal (random 0.6–2.1); shared cited works
  469–1,361 (random 62–142, six to ten times as many); shared institutions 27–63 (random 31–68: chance).
- **Held share** (references whose card links to a Mandumah publication, after the librarian): 1001 17.2%, 0840
  14.6%, 0097 18.5%, 0130 16.4%, 0246 18.8%, 0165 11.9%; 0013 11.7% before its librarian.
- **Quality.** Six scanned journals passed the ten-page look (0–1 word wrong) and the audit (leak 0.011–0.337%); two
  failed it (0011, 0523) and are held. Every live release replays every Desk decision with 0 orphans. Librarian hand
  checks (every sampled decision read, 1,527 in all): 1,458 right, 60 minor, 9 wrong; the kinds that fell under 98%
  were held as Desk tasks.
- **Cost: $365.23 of $400** for six journals live + 0130's Word years + two read-and-held journals + 0013's
  librarian prepared; 1182's scans did not fit.


## Per journal

| journal | articles (scan + Word) | spend | 10 pages on the scans | audit leak | librarian (hand check) | releases | state |
|---|---|---|---|---|---|---|---|
| **1001** مجلة جامعة طيبة للعلوم التربوية (SA) | 191 (89 + 102) | $32.49 | 4 right, 6 minor, 0 serious; 0 words wrong | 0.157% | 2,602 decisions; 281 right, 43 minor, 1 wrong of 325 (D44 and retitles held) | R20261103T120721 (reading), **R20261103T155409** | live |
| **0840** دراسات نفسية (DZ) | 198 (82 + 116) | $19.10 | 4 right, 6 minor, 0 serious; 1 word wrong | 0.025% | 1,737; 210 right, 2 minor of 212 | R20261103T125053, **R20261103T164042** | live |
| **0097** المجلة العربية للتربية (TN) | 155 (83 + 72; 1 not read) | $29.90 | 9 right, 1 minor; 0 | 0.011% | 2,597; 238 right, 1 minor of 239 | R20261103T160343, **R20261103T192456** | live |
| **0130** مجلة الطفولة العربية, Word years (KW) | 175 (0 + 175) | $6.98 | — (no scans) | — | 2,875; 223 right, 3 minor of 226 | R20261103T174811, **R20261103T230107** | live |
| **0246** مجلة اتحاد الجامعات العربية للتربية وعلم النفس (SY) | 463 (194 + 269) | $71.87 | 4 right, 6 minor, 0 serious; 0 words wrong | 0.337% | 7,653; 279 right, 3 minor, 4 wrong of 286 (P6, P6+D43 held) | R20261103T205906, **R20261104T151029** | live |
| **0013** دراسات نفسية (EG) | 248 (124 + 124) | $66.35 | 9 right, 1 minor; 0 | 0.015% | 5,427 planned, not applied (parked); 227 right, 8 minor, 4 wrong of 239 (P6, P6+D43, R6, Flash parent held) | R20261104T003753, — | live reading; librarian pending |
| **0011** رسالة الخليج العربي (SA) | 324 built (130 + 194) | $41.69 | 3 right, 7 minor; **3 words wrong** | — | not run | — | **held: look gate failed** |
| **0523** مجلة الدراسات التربوية والنفسية (OM) | 507 built (346 + 161) | $92.68 | 2 right, 5 minor, **3 serious; 5 words wrong** | — | not run | — | **held: look gate failed** |
| **1182** مجلة جامعة القدس المفتوحة … (PS) | Word route built (334) | $4.17 | — | — | — | — | **not read: no room under the cap** |

Spend is per journal from experiment 43's log (read, judge, page retries, Word step) plus the librarian's own log
(`cost74.py`). Total **$365.23** of $400: reading $325.51 (scan read $279.15 incl. resends and rechunks, judge $24.46, page retries $4.44, Word step $17.45 — `cost74.py`), librarian $39.72.

## Method (what changed against experiments 70 and 72)

Everything follows experiment 70 (reading) and experiment 72 (librarian). Changes, each made because a journal
needed it, with the original code kept in `out/code_before/`:

**Reading (scan route).**
- Set `g` in experiment 43's scripts: every `out/<J>/sample.json`; a run `j<J>` takes its journal.
- run43 resends a malformed-JSON answer once automatically (`.failed1.json`; it fired and worked on 0011 and 0097);
  drops each article's Azure JSON after use in the dry run and in `ready_chunks` (the 346-article dry run hit 3 GB);
  deletes a Batch job's uploaded input once the job is done (the File API holds 20 GB a project: it filled at 08:0x,
  stopping two reads and a judge; this experiment's 56 used uploads were deleted, 10.7 GB).
- `META43_CATALOGUE_FIRST=1`: the catalogue's page range wins when it spans the scan's pages (exp 70's issue 4).
- leaks43 puts a printed copyright line before a license (88 of 1001's masters were invalid); masters43 drops an
  `fn-group` left empty.
- A chunk the model refuses (empty answer, finish none, on Batch and Standard): 0097-038-002-005 page 21 — the
  44-page article is left out rather than forced.
- The judge's pages skip an article with no master; `JUDGE43_CAP` always set; `| head` removed from the chain (it
  killed one judge).

**Word route** (`word74.py`, `wordmodel74.py`; build53 fixes). The ten-article front-matter look per journal found
a new layout in almost every journal:
- 1001: English articles whose body became a string of trans-abstracts (43 in one); names with note markers joined
  by «، و»;
- 0840: «name (*)، institution، e-mail» on one line per author, two authors' groups on one line;
- 0097: a note call glued to a name («…الفيومي)»), a book review's «العنوان الأصلي» note;
- 0523: «name1 وname2» bylines (split only when both halves are catalogue names), received / accepted dates inside
  affiliations, author notes holding only a label, table rows emptied by rowspans.
- Long reference lists go in parts of 50; failed answers are asked again automatically.
- soffice conversions time out per batch and are retried one by one (one .doc hung 25 minutes); 2 of 0011's files
  and 1 of 1182's could not be converted.
- Rejected files read by hand: 4 accepted (1001 ×1, 0246 ×3: English / French text of the Arabic title, a title
  spaced differently).

**Platform** (`load74.sh`, `gate74.sh`, `golive_load74.sh`). Each journal is loaded into a backup-API copy of the
live DB, then link47, the id check, a dry-run release in a throwaway schema, and the audit of the journal's scan
articles on that dry release, before the copy replaces the live DB.

**Librarian** (`lib/`, experiment 72's code per journal; see `lib/common74.py`). Experiment 72's lessons in code,
plus what the hand checks here found:
- whole cards for split questions; twin rows only for "rows are one body"; K1c's venue test on distinctive words;
- a D44 rule (same text in another journal) — **held** after 1001's hand check (27 of 32 "other journals" were the
  same journal under another printed name);
- Opus' not-a-work retitles — **held** (13 of 29 titles cut at the wrong place);
- K1c never links a card that is not a thesis to a thesis record (1001's #308; D43);
- no link on a card the same plan splits; "none" answers to "a unit's parent?" apply nothing;
- decisions the dry run finds in conflict are excluded (`exclude74.json`);
- 0246 only: P6 and P6+D43 held (9/11 and 13/15: Dissertation Abstracts / ProQuest entries typed as journals).
- The authority review is done by hand per journal (`out/<J>/lib/inst/review74_input.json`): 17 + 17 + 19 + 21 + 18
  + … new bodies, the regional education departments mapped to their ministries, schools and projects refused.
- Every hand check read every sampled decision (an agent, with the printed evidence beside each).

**The quality gate.** Ten random pages per journal read beside the scan crops (an agent; I re-checked a page of each
failing or borderline journal myself). A word is wrong when its letters differ from the print or when two printed
words are joined; a space the print lacks and the text restores, Latin citation order, kept line-end hyphens,
tashkil, ي/ى, ه/ة and alef-hamza forms are minor (`out/look10_summary74.json`). A serious page or > 1 wrong word
stops the journal; so does an audit leak rate > 0.5% or a librarian kind under 98% on the hand check (that kind is
held).



## Issues

1. **Two journals fail the look**: 0011 (3 words wrong: two joined words in a table head, a scan speck) and 0523 (5
   words wrong, «إذ» read «إذا» twice). Both are read, judged, built, valid, with views; not loaded. The lead /
   owner decides: a second sample, a targeted fix, or load as is.
2. **Budget**: the eight journals' pages cost $0.008–0.016 each (0165: $0.0073), $384 by the dry runs for the read
   alone; 1182's scans were not read.
3. **Ids**: link47's relink drops catalogue-authority persons that are only authors of cited works (3 + 2 + 1 + 1 + 2
   ids over the loads); no Desk decision names them.
4. **Conflicts that appeared** (not orphans): exp 72's relate on CCTVAJDDCR (since 0097's pass), exp 64's link of a
   Libyan statement to «جامعة الزيتونة» (the 0246 load put Jordan's «Alzaytona University» on that machine row and
   flipped its country), a link_publication on CFWGE8ZK7S. The librarian should split row I4PE3FZMDC.
5. **Desk release bug fixed**: two joined twin cards each linked to one publication tripped the one-best-link index
   (`desk/release.py`, op_link_publication).
6. **Desk tests**: 99 passed, 2 failed from data growth (link47 on the live copy now passes 30 minutes; the pinned
   detector counts). The link47 timeout is raised to 90 minutes in `experiments/49_correction_desk/tests/test_release.py`; the detector pins in `experiments/49_correction_desk/tests/test_rules.py` are to be re-set on the final release.
7. The File API quota; the watchdog raised knowingly to 5 GB (flags43 on 346 articles peaked at 3.79 GB).

## Files

Scripts (this folder): `sample74.py`, `word74.py`, `wordmodel74.py`, `absprobe74.py`, `build74.sh`,
`judge_pages74.py`, `judge74.sh`, `judge_summary74.py`, `retries74.py`, `final74.sh`, `finish_read74.sh`,
`after_build74.sh`, `look74.py`, `views74.sh`, `make_index74.py`, `load74.sh`, `dryrun_load74.py`, `gate74.sh`,
`golive_load74.sh`, `review_view74.py`, `bridges74.py`, `spend74.py`, `cost74.py`, `watchdog74.sh`; the librarian in
`lib/` (`common74.py` documents the steps; `run_lib74.sh`, `lib_models74.sh`).

`out/` (gitignored, Mandumah text): `fetch/` (1,389 PDFs + Azure JSON), `<J>/` per journal (sample, inventory, word,
jJ / jJ_final, wJ_code / wJ_model / wJ_final, look10, ids, dry runs, audits, `lib/`), `audit_live/` (the /audit
pointer), `bridges74*.json`, `look10_summary74.json`, `logs/`, `code_before/`.

Progress notes: `progress.md`.

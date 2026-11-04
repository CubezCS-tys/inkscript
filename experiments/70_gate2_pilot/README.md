# Experiment 70: gate 2's pilot, one whole journal by both routes (0165 «مجلة الطفولة والتنمية»)

**Question** (owner-approved, 2026-11-02; hard cap $55 of Gemini for everything). Run gate 2's first journal whole:
0165, 2010–2025, 363 research articles. 145 have a scan (and Azure's OCR in S3); 218 exist only as the publisher's
Word file. Read the scans as gate 1 did, with prompt v3.6. Build the Word-only articles by experiment 53's Word route,
including its text-only model step, which had never been run at scale. Load both into the platform and make a Desk
release on which every decision replays. Then measure gate 2's question on the first pair of journals: **do education
journals cite each other?** Should the other nine journals follow as they are?

**Answer.**
- **Done, for $23.29 of the $55 cap.** The scan route cost $22.09 (read $19.37, judge $2.42, page retries $0.30), or
  **$0.0078 a page**; gate 1 cost $0.0099. The Word route cost **$1.20**, or $0.0055 an article.
- **All 363 articles are valid masters.**
  - Scan route: 145 of 145 are JATS DTD + ALTO XSD valid.
  - Word route: 218 of 218 are DTD valid. All 218 Word files passed the title check; none was another article.
- **New live release `R20261103T023001`.** Every Desk decision replays: 2,738 applied, 9 superseded, and the known
  3 orphans and 1 conflict. No existing id changed.
- **Quality.** Ten random pages read beside the scan: **9 right, 1 minor, 0 serious, 0 words wrong**. In the audit,
  **99.981%** of 0165's printed lines are accounted for; 17 lines are in generic text only.
- **The journals cite each other, and the Word route makes most of those citations visible.**
  - 0130 → 0165: **15 references** in 8 articles. 11 of them land on 0165 articles read here, and 6 of those 11 are
    Word-route articles.
  - 0165 → 0130: **16 references** in 11 articles. They point at 0130 issues from 2002 to 2016, none of which has been
    read yet.
  - Inside 0165: 59 references, 21 of them to articles read here, written 0 to 9 years apart. 11 of the 21 targets
    are Word-route articles.
- **Bridges between the two journals, against random sets of the same size.**
  - Shared authors: **17** against **0.0**.
  - Shared cited works: **157** against 26.3, six times as many.
  - Article pairs coupled by a shared cited work: **313** against 118.
  - Shared institutions: **17** against 16.1, no more than chance. The big Egyptian and Saudi universities appear
    everywhere.
- **Recommendation: yes, the other nine can follow as they are.** Make the small fixes listed under "Before the nine",
  and keep the Word-route checks and the cost guards.

## The set and the inventory

The catalogue lists research records (`type = 'بحوث ومقالات'`) for journal 0165 from 2010 to 2025. **363** of them,
the same count as experiment 54. `sample70.py inventory` gives `out/inventory.json`:

| year | scan | Word | nowhere |
|---|---|---|---|
| 2010 | – | 18 | – |
| 2011 | – | 14 | – |
| 2012 | – | 12 | – |
| 2013 | – | 11 | – |
| 2014 | – | 9 | – |
| 2015 | – | 32 | – |
| 2016 | 17 | 8 | – |
| 2017 | 22 | – | – |
| 2018 | 25 | – | – |
| 2019 | 31 | – | – |
| 2020 | – | 51 | – |
| 2021 | 10 | 28 | – |
| 2022 | – | 35 | – |
| 2023 | 18 | – | – |
| 2024 | 14 | – | – |
| 2025 | 8 | – | – |
| **all** | **145** (2,841 pages) | **218** (114 `.docx`, 104 `.doc`) | **0** |

- **Fetch.** `inkscript fetch` was used, read-only on S3, with 4 workers. It returned 145 of 145 PDF + JSON pairs
  (422 MB), and all pass `fetched43.problems`.
- **Legacy PDFs** (`legacy/`, read-only): 206 of 218 were fetched. The 12 missing ones only mean a pdfmap without
  positions.

## Method

**Scan route.** This is gate 1's sequence (experiment 52), with today's code. Plumbing for set `f` was added to the
experiment 43 scripts; the originals are in `out/code_before/`. Every step and its time is in
[progress.md](progress.md).

1. **The read.** Command: `run43.py --set f --prompt v3.6 --thinking low --run j0165 --cap 144.10 --max-enqueued
   2500000`, on Batch.
   - The dry run expected $20.84 (worst $63.81).
   - It ran in 7 rounds and 353 requests.
   - Two answers came back as malformed JSON (finish STOP, so not a rechunk case). They were asked again: 2 of 2
     usable, $0.135.
   - Result: **145 of 145 articles answered.** Peak memory 3.31 GB (`time -v`). The watchdog polls every 15 s and
     missed the peak; see Issues.
2. **Masters.** Built with `build70.sh` (lettersfix43 plain), which runs the D30 guard and experiment 65's leak
   fixes.
   - The letter fix changed 161 letters in 142 words: ی→ي 82, ک→ك 62, ی→ى 15, ھ→ه 2. None was left unplaced.
   - One article, 0165-009-031-001, was invalid. A table note printed as bullet items left empty `list-item`s. Fix in
     `enrich43`: an emptied item is removed, and an emptied list with it.
   - Result: **145 of 145 valid.**
3. **Flags and judge.**
   - Flags: high 21, medium 97, low 214, over 2,841 pages.
   - The judge (Argon, judge v2, Batch) saw 295 flagged pages plus 50 random unflagged ones (seed 7045), 345 pages
     in all, at **$2.42**.
   - The frozen two keys sorted 28 findings: 1 auto, 6 retry and 21 to a person (13 wrong_kind, 6 table_box,
     2 other).
   - Retries: 6 of 6 sent at **$0.30**. 5 pass the code check; 1 goes to a person.
   - Patches: `final70.sh` applied 6 in 6 articles. **145 of 145 valid.**
   - Final flags: high 21, medium 95, low 215.
4. **Views.** Pages: http://127.0.0.1:8899/j0165_final/index.html. `j0165` and `j0165_final` are symlinked in
   experiment 41's views.

**Word route** ([word70.py](word70.py) + [wordmodel70.py](wordmodel70.py)).

1. **Files.**
   - `.docx` files were copied as they are; `.doc` files were converted by soffice (own profile, batches of 20).
     218 of 218 in 2.4 minutes.
   - The **first-page / title check** (experiments 53 and 54). A file is accepted when at least 60% of the catalogue
     title's words appear in its first 3,000 characters, with each paragraph's runs joined as Word draws them.
     - **218 accepted, 0 rejected.**
     - The first page number matches the catalogue in 212. It is 1–3 pages off in 3, has no number in 2, and is off
       by +29 in 1 (0165-005-017-007, whose title share is 1.00: the catalogue's page is off).
     - The page test alone would have rejected 4 right files, as experiment 54 found.
     - A naive join of Word's runs would have rejected 0165-006-024-003. Its letters are split across runs
       («د ور ال أ سرة»).
2. **Code-only JATS.** `build53`, pointed at `out/w0165_code`. Fixes made for this journal; each is in
   `out/code_before/`:
   - Endnote numbering that restarts (two «1») reused the id `en1`. Ids are now unique.
   - 0165 prints no abstract. The body opens with «مقدمة» right under the byline, so body sentences were stored as
     *affiliations*. The body now starts at such a heading (`BODY_HEAD`). Lines under a byline stop being an
     affiliation at running text, at a label ending in «:», at a line with no letters, or at a sentence.
   - 0165 prints the author's post and institution in an **author note** («* أستاذ … كلية … جامعة …»). Such a note
     now becomes the contrib's `aff` (`specific-use="author-note"`) with an `xref`, assigned by byline order. 168
     affiliations come from notes.

   Result: **218 of 218 valid**, built in 2.3 minutes at 0.38 GB.

   | part | count |
   |---|---|
   | contribs | 234 (223 with an authority id) |
   | contribs with an affiliation | 173 |
   | headings | 2,848 |
   | references | 2,913 (2,592 with code fields) |
   | footnotes | 182 |
   | typed endnotes | 109 |
   | tables | 281 |
   | figures | 185 |
3. **The text-only model step** (experiment 53's "lean" call, never run before).
   - **Model: gemini-3.8-flash**, the cheapest experiment 53 priced ($0.375 / $1.875 per M tokens on Batch), with
     thinking low.
   - **What it is sent:** each heading with its level, label and the first words after it; each reference entry with
     its id; the title and the opening. The W schema and the doc_type list are copied verbatim from prompt v3.6.
   - **What it returns:** only the heading changes, the parsed works, and the document type. **It never sees or
     changes a word of text.**
   - **How it is applied:**
     - headings are re-nested from a flat outline (a block always goes into the last open section, so the JATS order
       holds);
     - each W is written by `refs43.citation`, which keeps only values that are substrings of the printed entry;
     - the doc type is written as meta43 writes it.
   - **Pilot first** (20 articles, Standard, $0.122). I read it myself: `out/w0165_model/pilot_review.txt` and
     `pilot_refs.txt`.
     - Headings: mostly re-basing the outline (code's top level 2 becomes 1) and making series consistent (ثالثا 3→1
       beside أولا / ثانيا). Lead-ins and «راجع في ذلك» become paragraphs. One doubtful split.
     - References, 40 random side by side: **the model is better than code in ~25**, the same in ~11 and worse in 1.
       2 have a name-order slip.
     - 3 of 3 "not a reference" calls were right.
   - **Then Batch** for the other 198 ($0.822). Two answers failed: one hit MAX_TOKENS on a 162-entry list and one
     was malformed JSON. One answer left out 219 of its 292 references. All three were asked again in parts of 50
     ($0.256).
   - **Total $1.20.**
   - **Applied** ([`out/w0165_final/apply.json`](out/w0165_final/apply.json)): **218 of 218 valid**.
     - Doc types: research 112, report 44, editorial 41, review 16, book review 3 (each reviewed book written as a
       `product`).
     - Headings: 1,215 levels changed; 220 became paragraphs, 53 captions, 30 quotes, 24 list items.
     - References: 2,508 have the model's fields in place of code's, 144 got fields for the first time.
     - 260 entries carry no new work («مرجع سابق», Ibid., notes): code's fields were removed and the entry is marked.
   - Every page number after the first is an **estimate, flagged in a `page-numbers` custom-meta (D36)**.
4. **Verdict on the Word route: good, keep it.** The text is the author's own (no reading errors), and the model step
   is cheap and helps. The weak spots are listed under Issues: front-matter edge cases and 3 residual bogus
   affiliations.

**Platform, Desk, audit** ([load70.sh](load70.sh), [golive70.sh](golive70.sh), [dryrun70.py](dryrun70.py)).

1. **Loading the Word route (new).** `load47 --word DIR` loads masters with no Azure reading and no ALTO.
   - The documents row gets level `legacy-pdf`, in_main_bucket 0 and legacy_only 1, with the docx sha as its source
     hash.
   - `parse46.BLOCK_ID` also accepts the Word route's `wN` / `hN` ids, with page NULL.
   - Nothing changes for scan runs: no scan master has such ids.
2. **Load into a work copy, then link.**
   - `~/data/platform_v2/exp70_work.db` is a backup-API copy of the live DB.
   - `load47 j0165_final` (362 s, 0.17 GB) and `w0165_final` (0.23 GB).
   - `link47` with its own cache (`out/linkwork`, 9 min, 0.21 GB). **0 orphans.**
3. **Id stability** (`ids68.py compare`, `out/ids_compare.txt`).
   - Every person (1,947), institution (669) and publication (2,018) id that existed before is the same row.
   - Cited works: 9,186 are the same row and 29 resolve through merged_ids.
   - The 23 unresolvable cited-work ids are exactly the 23 that were unresolvable before this experiment.
   - Every id a Desk decision names resolves, except CRTJTVTZSQ, as before (experiment 68 explains it).
4. **Dry-run release** (`dryrun70.py`, throwaway schema `test_e70dry`).
   - **2,738 applied, 9 superseded, 3 orphaned, 1 conflict.** These are exactly experiment 68's 3 re-anchor orphans
     and the «المقدّمة» demo conflict.
   - Every constraint holds; 0 foreign-key violations; 34 decisions found their moved twin line.
5. **Live** (`golive70.sh`, 20:29–20:33).
   - Backups:
     - `~/data/platform_v2/backups/platform_v2.before_exp70_20261102T202906.db` (quick_check ok);
     - `link_cache47.before_exp70_20261102T202906.json`;
     - `~/data/desk/backups/desk_schema_before_exp70_20261102T202906.{dump,sql}`.
   - The work copy was copied over `platform_v2.db`, and the release was built with `--keep 8`, so no copy was
     pruned.
   - **Release `R20261103T023001`**, 2026-11-02 20:30 CST, fingerprint `8c6d2895…`.
6. **Audit** (experiment 61's code). Word-route articles are skipped, since they have no scan;
   `out/audit_live/skipped_word_route.json` lists the 218.
   - 925 articles in 119 s on 3 workers.
   - The /audit pointer `~/data/desk/audit_current` now names `experiments/70_gate2_pilot/out/audit_live`.
   - The previous audit (`68_go_live/out/audit_live`) is the "before": `out/audit_live/before_after.md`.
   - The 780 earlier articles are unchanged: **99.814%** accounted, 808 generic-only lines.
   - The 145 scan articles of 0165: 90,189 lines; **99.981%** accounted; **17** generic-only lines and 0 nowhere.
     That is a leak rate of 0.019%; 0130 has 0.040% and the random 600 0.24%.
   - The leak table moved by +10 "other" lines, +9 author posts (mapping), +3 affiliations (mapping).

## Results: gate 2's question

All measures are on the release DB (machine reading + every Desk decision), with [measure70.py](measure70.py). Inside
a set, the measure is experiment 52's `measure52.measure`, unchanged. Between sets, each figure is set against 20
random sets of the same size drawn from the random 600 (seed 7070). Output: `out/measure70.json`.

**Citations between the journals.** Each is a reference whose card has an accepted best link to an article of the
other journal.

| | references | citing articles | cited articles | of which read here |
|---|---|---|---|---|
| 0130 → 0165 | **15** | 8 | 15 | **11** (6 Word route, 5 scan) |
| 0165 → 0130 | **16** | 11 | 13 | 0: they cite 0130 of 2002–2016, which is not read (0130's Word years are not done) |
| 0165 → 0165 | 59 | 27 | 45 | **21** (11 Word route), written 0–9 years apart |
| 0130 → 0130 (gate 1) | 37 | | | 9 |

- **Read one by one** (the 31 links between the journals):
  - 0130 → 0165: **14 right, 1 doubtful**. A 2017 conference paper is linked to the 0165 article of 2019 with the
    same title: the same text, D44-like.
  - 0165 → 0130: **15 right, 1 wrong**. A master's thesis is linked to the 0130 article drawn from it. Under D43 these
    are two works.
- **Names the other journal in print:**
  - 0130's references name 0165 in 14, all of them linked.
  - 0165's references name 0130 in 26, of which 14 are linked. The other 12 are an undercount: their target record is
    not matched yet.
- **0165 → the catalogue:** 673 of 6,374 references (**10.6%**) land on a work Mandumah holds. For 0130 the figure is
  16.8% and for the random 600 2.6%. These use link47's links plus the Desk's; probe A's matcher was not run here.

**Shared people, institutions and works between the two journals.**

| bridge | 0130 × 0165 | 0130 × random sets of 363 (mean, range) | 0165 × random sets of 126 |
|---|---|---|---|
| **authors in both** (byline person ids) | **17** | 0.0 (0–0) | 0.8 (0–3) |
| institutions in both (org level) | 17 | 16.1 (11–19) | 12.5 (7–17) |
| **cited works in both** | **157** | 26.3 (20–34) | 11.0 (4–19) |
| coupling edges (an article pair citing a common work) | **313** | 117.6 (74–151) | 42.1 (14–90) |
| 0130 articles coupled to the other set | **74 of 126** | 32.6 | – |
| 0165 articles coupled to 0130 | **98 of 363** | – | 8.6 |

**Inside 0165** (gate 1's measures), against 20 random sets of 363 drawn from the 600:

| bridge | 0165 (all 363) | scan 145 | Word 218 | random 363 (mean) | 0130 (gate 1) |
|---|---|---|---|---|---|
| authors with 2+ articles | **55 of 273** | 21 of 124 | 33 of 174 | 3.9 | 16 of 130 |
| byline authors with an authority id | 98% | 98% | 98% | 91% | 99% |
| repeat co-author pairs | 0 | 0 | 0 | 0 | 1 |
| institutions in 2+ articles | 29 of 108 | 12 of 44 | 16 of 81 | 26.3 | 25 of 67 |
| affiliations at an institution seen in 2+ articles | **69%** | 73% | 53% | 42% | 75% |
| references (Quran excluded) | 6,374 | 3,688 | 2,686 | 5,931 | 3,920 |
| cited works shared by 2+ articles | **210** | 73 | 42 | 77.9 | 121 |
| largest coupled group | **125 of 204** | 56 of 112 | 26 of 92 | 42.2 | 72 of 114 |

What the tables say:
- **Authors and cited works are the strong bridges, between the journals as inside them.**
  - The same 17 people sign in both journals, against none in a random set of the same size.
  - The two journals share six times as many cited works as 0130 shares with random articles.
  - Three in five of 0130's articles (74 of 126) cite a work some 0165 article also cites.
- **Institutions are not a bridge between these two.** Shared institutions are no more than chance: Cairo, Ain
  Shams, Helwan and King Saud appear everywhere. Inside 0165, institutions recur only a little more than at random.
- **The Word route is what makes the years connect.**
  - Without it, 0130 → 0165 would reach 5 read articles instead of 11, and 0165's citations to its own read articles
    would number 10 instead of 21.
  - 0165's citations to 0130 all go to 2002–2016. Those years are 0130's Word years (experiment 53 built 2009–2016),
    still not loaded.

**New against existing entities** (the librarian has not run on them):

| | touched by 0165 | existed before | new |
|---|---|---|---|
| persons signing 0165 articles | 277 | 38 | 239 |
| institutions (org level) | 108 | 32 | 76 |
| cited-work cards cited by 0165 | 5,322 | 185 | 5,137 |
| publications 0165 cites (accepted links) | 605 | 22 | 583 |
| 0165's own publications | 363 | 12, already present as cited targets | 351 |

The detectors now find 93 author-less works (was 67) and 609 «possible same work» pairs (was 291).

**Quality.**
- **Ten random pages beside the scan** (seed 7046; `out/look10_verdicts.json`; the scans and text are in
  `out/look10/`):
  - **9 right, 1 minor, 0 serious, 0 words wrong.**
  - The minor one: Latin inside Arabic lines was kept in visual order, «(Human Rights Education (HRE» in a heading.
  - These pages are clean digital typesetting; 0165's prints are easier than 0130's.
- **Metadata spot check**, 10 scan articles and 10 Word articles against the catalogue (`out/spot70.txt`):
  - Titles, authors, posts and affiliations are right.
  - In 2 of 10 scan articles the printed lpage differs from the catalogue. 0165-000-050-006 gives 105 for 121: the
    reader's range is wrong. 0165-000-051-002 gives 45 for 44.
  - The Word metadata, after the fixes above, is right in 10 of 10. Before them, 2 of the 10 had a heading («الغذاء:»,
    «تقديم:») as the affiliation; both now carry the author note's real affiliation. One printed name keeps «إعداد:».
- **Reference spot check**, 20 per route: scan 19 right and 1 minor (volume «23;7»); Word 20 right, 4 of them
  «مرجع سابق» / Ibid. entries correctly given no new work.
- **Audit leak rate for 0165:** 17 of 90,189 lines (0.019%).
- **Judge:** 28 findings on 345 pages, against 30 on 289 in gate 1. The random unflagged pages hold 1 finding in 50.

## Spend (experiment 43's log; one log for everything)

Cap $55, so the absolute cap was $159.10.

| part | $ |
|---|---|
| scan read (353 requests + 2 asked again) | 19.367 |
| judge (345 pages) | 2.419 |
| page retries (6) | 0.303 |
| Word step: pilot (20, Standard) | 0.122 |
| Word step: Batch (198) | 0.822 |
| Word step: retries in parts | 0.256 |
| **total** | **23.289** |

- The log went from **$104.098 to $127.387**.
- Per unit: $0.0078 per scan page, $0.152 per scan article, $0.0055 per Word article.
- The 10 journals of experiment 54 at these rates: about 38,913 pages × $0.0078 + 1,768 × $0.0055 ≈ **$313**.
  Experiment 54 estimated ≈ $456.
- Prices double on 1 December (Argon) and on 1 January 2027 (Flash).

## Issues found (and what was done)

1. **Peak memory.** run43 peaked at 3.31 GB. The watchdog polls every 15 s against a 3 GB limit and did not see it.
   The machine had 33 GB available.
   - For the nine: run one journal at a time with `--max-enqueued 2000000`, or raise the watchdog's per-process limit
     knowingly.
2. **retry43's cap.** It reads `JUDGE43_CAP` and defaults to $38.92. The first retry pass was refused and left 6
   empty records, which I moved to `43_rehearsal/out/judge/retry/j0165_stopped_capbug/`.
   - Always export `JUDGE43_CAP` for retries.
3. **Malformed JSON with finish STOP** (2 of 353 scan answers; 1 of 218 Word answers). run43 marks these failed and
   stops the article.
   - Renaming the `.failed.json` and re-running with `--stems` works. A small resend command would save the step.
4. **Printed lpage taken from the reader.** 2 of 10 spot-checked scan articles disagree with the catalogue.
   - The catalogue should win for the page range (D33-like). Not changed here.
5. **Word-route front matter is journal-specific.** 0165's "abstract-less, author-in-a-note" layout broke experiment
   53's 0130-tuned front parser. It is fixed, but each new journal's first build should get a 10-article front-matter
   look before its model step. 3 bogus page affiliations remain («خلفية», «خلفية الدراسة», one sentence).
6. **The Word step skipped references.** One answer covered 73 of 292 entries; `wordmodel70 retry` fills the gaps.
   - For the nine: send lists over 80 entries in parts from the start.
7. **Desk tests** (`experiments/49_correction_desk/tests`).
   - **Caused by experiment 68's go-live:**
     - `test_audit` pinned experiment 61's leak 1:31, which experiment 65 fixed. The test now reads experiment 61's
       own audit through `DESK_AUDIT_DIR`.
     - `test_pipeline` now sees 2 affiliations (the English twin is a field), and the faculty shows as its English
       twin row IP0XR2KXSC. That row duplicates I1NW24RKQM «كلية علوم التربية», a librarian task.
   - **Caused by this experiment's data:** `test_rules`' detector counts went 67 / 291 → 93 / 609.
   - All three were updated with comments. **93 passed.**
8. **Gate 1's page pool.** The live gate 1 page counted every non-0130 `final` article as "random". After this load
   that would include 0165's 363. `index_pages.WHOLE_JOURNALS = {J0130, J0165}` now keeps whole-read journals out of
   the random pool. **This needs an API restart** (below).

## What the lead must run

**The API.** It reads the newest release and the /audit pointer on every request, so the new data and the new audit
are already served. The changed **code** needs a restart: `index_pages.WHOLE_JOURNALS` (gate 1's random pool).
Until the restart, the gate 1 page's "random" columns include 0165.

```
cd /home/appuser/inkscript/experiments/49_correction_desk
# stop the running API (started 17:18, pid of ".venv/bin/python -m desk.cli serve"), then
.venv/bin/python -m desk.cli serve
```

**The web.** No web file changed, so no rebuild is needed. Journal 0165's page appears at `/journals/J0165` from the
release.

**Not run** (the next step, as instructed): the librarian passes on the 239 new persons, 76 new institutions and
5,137 new cited-work cards.

**Reverting:**
1. Copy `~/data/platform_v2/backups/platform_v2.before_exp70_20261102T202906.db` back over `platform_v2.db` with the
   backup API, and do the same for the link cache.
2. Set `copy_deleted_at` on release `R20261103T023001`.
3. Write `/home/appuser/inkscript/experiments/68_go_live/out/audit_live` into `~/data/desk/audit_current`.

## Before the nine

The other nine journals can follow with the same scripts. They need set letters, or better, a journal parameter in
`run43` / `sample70`. Before they run:
- resend malformed-JSON answers automatically (Issue 3);
- let the catalogue's page range win (Issue 4);
- do a 10-article front-matter look per journal on the Word route before its model step (Issue 5);
- split long reference lists for the Word step (Issue 6);
- load 0130's Word years (2009–2016, built in experiment 53 and never loaded). 0165's 16 citations to 0130 all
  point there;
- the librarian on 0165's new entities first, so that its rules learn Egyptian institutions before 1,600 more
  articles arrive.

## Files

**Code:**
- `sample70.py` (inventory, scan ids, sample);
- `word70.py` (Word files, check, code build);
- `wordmodel70.py` (the model step: requests, pilot, batch, retry, apply);
- `build70.sh` and `final70.sh` (from experiment 52);
- `judge_pages70.py`, `judge_summary70.py`, `retries70.py` and `make_index70.py` (from experiment 52);
- `look70.py` and `spot70.py` (quality looks);
- `load70.sh`, `dryrun70.py` and `golive70.sh`;
- `measure70.py`;
- `watchdog70.sh`.

**Code changed elsewhere** (originals in `out/code_before/`):
- experiment 43: set `f` in run43, lettersfix43, pictures43, rechunk43, patches43, retry43, judge43, summary43,
  views43 and flags43; enrich43's emptied list-items;
- experiment 47: `load47 --word`; `ink47.azure_paths` reads sample70;
- experiment 46: `parse46.BLOCK_ID` takes `wN` / `hN`;
- experiment 53: `build53` (unique endnote ids, BODY_HEAD, the affiliation stop rules, author-note affiliations);
- experiment 61: `audit61` skips Word-route articles; `aggregate61` knows v3.6;
- experiment 49: `index_pages.WHOLE_JOURNALS`, and the three tests above.

**`out/`** (gitignored; Mandumah text):
- `fetch/` (422 MB), `sample70.json`, `inventory.json`, `word70.json`;
- `j0165/` (raw, rules, masters, views, flags, judge, retries plan) and `j0165_final/`;
- `word/` (docx 218, legacy_pdf 206, check.json), `w0165_code/`, `w0165_model/` (requests, answers, batch, pilot
  review), `w0165_final/`;
- `audit_live/`, `measure70.json`, `ids_before.json`, `ids_compare.txt`, `dryrun70_test_e70dry.json`,
  `release70.json`;
- `look10/`, `look10_verdicts.json`, `spot70.txt`;
- `logs/`, `linkwork/`, `code_before/`.

**Data:**
- `~/data/platform_v2/platform_v2.db` (live) and its backup above;
- `~/data/platform_v2/exp70_work.db`, the work copy, now identical to the live DB;
- `~/data/desk/releases/R20261103T023001.db`.

**Can be deleted (proposed, not done):**
- `~/data/platform_v2/exp70_work.db` (1 GB, a copy of the live DB);
- `out/w0165_code_v1/` (the code masters before the last affiliation fix);
- `out/word/profile/` (soffice's profile);
- the throwaway schema `test_e70dry`;
- `43_rehearsal/out/judge/retry/j0165_stopped_capbug/`.

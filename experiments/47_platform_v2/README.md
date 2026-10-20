# Experiment 47 — the platform database, version 2

**Question.** Platform v1 (experiment 46) stored one reading of each article. Its links were keyed to rows that
change from run to run, and it counted «المرجع السابق» as a fake work→work link. Can a second design keep everything
we hold that Web of Science does not? That means the scan itself, two readings of the text, the full correction
history, the quality record, Arabic scholarly conventions and Mandumah's whole catalogue, each first-class and tied
together. Can it be built from the same sources, reconcile with v1, and take the next run tonight?

**Answer (2026-10-20, $0, no paid calls).** Yes. An independent verifier ([VERIFY.md](VERIFY.md)) then found ids
that moved on every rebuild, a people layer that depended on step order and several wrong values; all of them are
fixed in [Fix round 1](#fix-round-1-2026-10-20) below, and the numbers in this README are those of the rebuilt db.

- **The database.** `/home/yassine/data/platform_v2/platform_v2.db` (SQLite, 277 MB) is built from the same
  sources as `platform.db`. It holds 83 tables of the design, one builder report table and 15 views, with
  169 foreign-key column pairs (161 keys) declared.
- **Checks.** There are 0 orphans, and every view runs.
- **Serving.** It is served read-only at **http://127.0.0.1:8003/platform_v2**, with 17 canned queries. The schema
  diagram is at http://127.0.0.1:8003/diagram/schema47.html, and the "show me the ink" page is at
  http://127.0.0.1:8003/diagram/ink.html?a=6479508497353429 (that anchor is «السابق نفسه» of `0069-000-026-005`
  fn-p15-13, boxed on its page; anchor keys are hashes of `stem|p<page>|w<first>-<last>` since fix round 1, so the
  link survives every rebuild).
- **Build time.** A full build from scratch takes 2 min 5 s and peaks at 146 MB memory. That covers the four loads,
  the linking, the checks and the diagram.

How it was built: the design is in [DESIGN.md](DESIGN.md) and [schema47.sql](schema47.sql), commit 83fa6ea. The
audits behind it are `audit_*.md`. This README covers the build.

## How it is built

```
/home/yassine/data/platform_v2/build47.sh        # the whole build; each step below can be run on its own
P=experiments/47_platform_v2; D=/home/yassine/data/platform_v2/platform_v2.db
.venv/bin/python $P/load47.py --db $D --run v33_300
.venv/bin/python $P/load47.py --db $D --run v2_55
.venv/bin/python $P/load47.py --db $D --run v33_300_judged --stem 0368-000-013-009    # as experiment 46 does
.venv/bin/python $P/load47.py --db $D --run v33_300_final
.venv/bin/python $P/link47.py --db $D             # back references, cited works, links, hand checks, metrics
.venv/bin/python $P/checks47.py --db $D           # reconciliation with platform.db, orphans, examples -> out/checks47.json
.venv/bin/python $P/diagram47.py --db $D          # schema47.html + ink.html into /home/yassine/data/platform_v2/
python3 $P/meta47.py                              # metadata47.json (descriptions, label columns, canned queries)
.venv/bin/python $P/test_ids47.py [--full]        # two clean builds, two step orders, two hash seeds: same ids and rows
```

**The exam runs.** Once their masters exist, they load with the same command and appear beside final:

```
.venv/bin/python $P/load47.py --run v33_300b
.venv/bin/python $P/load47.py --run v33_300b_final
.venv/bin/python $P/link47.py
```

- A name containing `300b` makes the run kind `exam`, so a b-run can never take the shown version from
  `v33_300_final`.
- `--kind` overrides that.
- The loader is idempotent. A version whose inputs are unchanged is skipped: the sha covers the JATS, ALTO, D33
  sidecar, patches sidecar and stamp. A changed version replaces only its own rows and keeps its `version_id`.
- The run-level files are re-read and replaced for that run only. These are flags, patches, judge answers and the
  raw chunk costs.

**Serving.**

```
setsid nohup .venv/bin/datasette serve /home/yassine/data/platform_v2/platform_v2.db -h 127.0.0.1 -p 8003 \
  --metadata experiments/47_platform_v2/metadata47.json --plugins-dir experiments/47_platform_v2/plugins \
  --static diagram:/home/yassine/data/platform_v2/ --static pages:/home/yassine/inkscript/experiments/43_rehearsal/out/pages \
  --setting sql_time_limit_ms 15000 --setting max_returned_rows 2000 >> /home/yassine/data/platform_v2/datasette.log 2>&1 &
```

- The `pages` mount serves the page images to the ink page. Like `diagram`, it exposes those files on localhost.
- The plugin `plugins/fold47.py` adds `fold()` and `stem47()` as SQL functions, so a search can be typed as printed.
  For example, «الإسلام» returns hits here. Experiment 46 returned none for it.
- The plugin does not open the database for writing.

**Sources** (read, never written):

- the masters of `experiments/43_rehearsal/out/<run>/masters`;
- each run's `flags.json`, `patches/`, `raw/` chunk files, and the judge answers `out/judge/answers/<model>/<run>/`;
- `judge_verdicts43.json`, `judge_truth43.json` and `gold/`;
- each document's Azure JSON. All 354 are local, at the paths the sample files of experiments 41 and 43 name.
- `marc.db`, opened read-only;
- experiment 46's `link_checks`, read from `platform.db`, which is opened read-only.

**Code reused from experiment 46, imported and not copied.**

- `parse46.parse_article` provides the article-level rows.
- `load46.catalogue`, `match_authors` and `disagreements` provide the print-versus-catalogue comparison.
- `inst46.rebuild` builds the institutions. It runs in a scratch in-memory db, and its keys become stable `I` ids.
- `link46.link_catalogue` and `link_articles` do the matching, and `link46.tkey` builds title keys.

**The code here.**

| file | what it does |
|---|---|
| [ink47.py](ink47.py) | Reads Azure's words and lines, reads the ALTO, and matches each ALTO word to its Azure word. |
| [parse47.py](parse47.py) | Turns one master into the rows of its version, with character positions mapped onto Azure words. |
| [load47.py](load47.py) | Loads the versions, chooses the shown version, and loads flags, patches, judge calls and costs, reviews, search and pages. |
| [biblio47.py](biblio47.py) | Builds the catalogue, publication, assertion, date, journal, people, institution and report rows. |
| [link47.py](link47.py) | Does the citation work. |
| [checks47.py](checks47.py) | Checks the result against v1. |
| [diagram47.py](diagram47.py) | Draws the schema page. |
| [meta47.py](meta47.py) | Writes `metadata47.json`. |
| [common47.py](common47.py) | Shared helpers: Arabic name parts, calendars, ISSN check digits, the Quran's sura table, and the schema with its deviations. |

## The ink: every value points at Azure's words

- **Matching ALTO words to Azure words.** Each ALTO word is matched to its Azure word by box, at 300-dpi pixels. On
  three test articles, 16,834 ALTO words matched: 16,822 to exactly one Azure word, 5 to several (where a fix joined
  words) and 7 to none.
- **Anchors.** An anchor is `<stem>|p<page>|w<first>-<last>` in Azure's own word numbering, which no run can
  renumber. There are 87,466 anchors:
  - 20,020 at word precision, for corrections, citation mentions, note calls and bylines;
  - 65,404 at line precision, for blocks, flags and judge findings;
  - 2,042 boxes, for figures.
- **The line crosswalk.** `line_map` (341,629 rows) maps each run's ALTO line to Azure's 'P:N' line, which is the
  label flags, patches and judge targets use. It agrees with the label the masters print on each fix and misprint in
  26,751 of 26,939 cases.
  - In the three v33 runs there are only 19 disagreements.
  - In `v2_55` there are 169. That run's masters were made by experiment 41's older code. This is worth a look
    before trusting v2_55 flags by line.
- **Which anchors point where.**
  - Corrections: 24,916 to their words, 1,973 to their line only, 54 to nothing.
  - Flags and judge findings: on the Azure lines they name.
  - Citation mentions: on the words of their own span inside the note.

## Results

### Reconciliation with platform.db

Full table: `reconciliation_v46` in the db, and `out/checks47.json`. Where a concept maps one to one, the counts
are equal. The shown versions' key columns were compared with EXCEPT both ways and show 0 differences:

- blocks (stem, block_id, text);
- notes;
- fixes (id, Azure reading, print);
- misprints (id, printed, proposed);
- figures;
- the shown run per article.

| v46 | rows | v2 | rows | why different |
|---|---|---|---|---|
| articles | 354 | documents / publications with a file / shown versions | 354 / 354 / 354 | = |
| article_runs | 655 | versions | 655 | = (all versions keep their content now: 98,398 blocks in all) |
| blocks, notes, figures | 51,791 / 4,084 / 1,910 | the same, shown versions | 51,791 / 4,084 / 1,910 | = |
| note_calls | 4,024 | note_calls (shown) | 4,024 | = (54 are now marked `no-target`) |
| fixes / misprints | 13,369 / 1,798 | text_corrections azure-misread / misprint | 13,369 / 1,798 | = |
| metadata_changes | 174 | corrected metadata_assertions (shown) | 174 | = (the 3 «translated title» changes included) |
| works | 4,789 | citation mentions with a parsed citation | 4,789 | = |
| works | 4,789 | cited_works | 3,080 | repeats inside and across articles are one card |
| back_references | 544 | ibid / op_cit / loc_cit mentions | 650 | every marker of a note counts, and so do bare «السابق» / «نفسه» |
| citation_links | 790 | citation_links + work_relations + resolutions | 138 + 187 + 481 | real links only (below); 21 of the 138 are rejected decisions |
| link_checks | 54 | reviews (link_checks) | 54 | = |
| flags | 1,666 | flags | 1,665 | `1764-003-005-006` has a flag in v33_300's flags.json but no v33_300 master |
| judge_findings | 634 | judge_calls / judge_findings | 607 / 219 | v46's 415 "none" rows are clean calls |
| patches | 124 | patches | 125 | key `run\|stem\|patch_id`: j-1677-p1-1 of two articles no longer collide |
| article_authors / affiliations | 413 / 247 | byline_mentions / affiliation_mentions (shown) | 413 / 247 | = |
| article_authors | 413 | authorships | 461 | twins become one authorship; catalogue-only contributors are added |
| catalogue_disagreements | 253 | catalogue_reports (print vs catalogue) | 253 | = (plus 11 invalid-ISSN reports: journals of link targets now count in every build order) |
| catalogue_records | 354 | catalogue_records (by 999$c) | 666 | plus the 312 catalogued-only publications that links and relations point at |

Other counts, by area:

- People and institutions: 580 persons (548 with an authority id or catalogue row, 32 provisional), 1,287 person
  names, 315 institutions.
- Journals and catalogue: 403 journals, 654 issues, 885 catalogue contributors.
- Search and dates: 62,924 search units, 971 publication dates.
- Arabic and the Quran: 60,682 transliteration pairs, 4,102 verse lines, 451 Quran places.
- Each of these is explained in the reconciliation table.

### «المرجع السابق» resolves to the first full citation

- **The rule.** `link47.resolve` walks each article's citation mentions in reading order: notes in printed order,
  and the reference list placed by page.
- **Grouping.** Full citations and short forms of the same work are one in-article work. Same title, or the same
  author with most title words, counts as the same work. That catches a misprinted title.
- **Where a back reference points.** It goes to that work's first full citation, never to another back reference.
  0 rows point at a back reference. 2 point at a mention later in reading order: a reference-list entry printed after
  the notes, when the work has no earlier full citation (the work is right). Chains collapse in one step.
- **«المرجع السابق» with several earlier works by the author** (fix round 1): the citation-style rule. Title words
  printed beside the name decide (the work's own title first, then the book a chapter sits in); then a printed year;
  then the cited page running on from the pages already cited for one of the works; failing all of these, the work
  by that author cited most recently, with score 0.5 and the ambiguity written in `resolve_evidence`. Every
  resolution carries its score: 0.95 title words, 0.9 one work or the mention before, 0.75 page continuity, 0.7 the
  author's only work with unexplained words beside it, 0.5 ambiguous.
- **Counting.** Each back reference counts as one more mention of the work in `v_times_cited`.

The shown versions hold these citation mentions:

| kind | count |
|---|---|
| full | 3,248 |
| short | 1,508 |
| ibid | 244 |
| op_cit | 403 |
| loc_cit | 3 |
| quran | 111 |

How the 650 back references were handled:

| outcome | method or reason | count |
|---|---|---|
| resolved (481 in all) | previous mention | 149 |
| | previous mention, chain collapsed | 114 |
| | same author, the only earlier work | 107 |
| | same author with title words | 62 |
| | same author, title words tied, decided by the cited page | 19 |
| | same author with the printed year («ROLDAN et al., 2006, op. cit.») | 13 |
| | title words | 9 |
| | same author, most recent of several works (score 0.5, ambiguity recorded) | 7 |
| | «مؤلفنا السابق»: the article author's own earlier work | 1 |
| counted once, as the citation just parsed before it (20) | «Pincus: Economic Aid, op. cit.» | 20 |
| unresolved, reason recorded (149 in all) | names a work not parsed earlier | 90 |
| | the back reference before it is unresolved | 33 |
| | a citation-like note without a parsed citation lies in between | 22 |
| | no earlier mention | 4 |

Short forms: 577 of 1,508 are tied to a first full citation (525 before fix round 1); the rest name works the
article never cites in full.

In v46, 303 of 544 back references were resolved.

**The owner's example: 0069-000-026-005.** v46 pointed fn-p15-13 and fn-p16-1 at the same notes as v2 does, but as
fake work→work links. It did not see fn-p15-5, fn-p15-1, fn-p14-5 or fn-p14-13 at all.

| note | printed | v2: counts for the first full citation |
|---|---|---|
| fn-p15-13 | «السابق نفسه» | fn-p15-12, «بدر الدين بن مالك، ألفية ابن مالك، تحقيق باسمة درويش…», previous mention |
| fn-p16-1 | «ابن عقيل (672هـ) شرح ابن عقيل، مرجع سابق» | fn-p14-4, «ابن عقيل (769هـ) شرح ابن عقيل على ألفية ابن مالك…», same author with title words |
| fn-p15-5 | «نفسه» | fn-p15-3, «أبو الفتح عثمان بن جني… اللمع في النحو…». The note before it, fn-p15-4 «اللمع في النحو، 59», is a short form of the same work, so the chain collapses |
| fn-p15-1 | «السابق ص 1/32» | fn-p14-14 «الإنصاف في مسائل الخلاف», through fn-p14-15 (chain collapsed) |
| fn-p14-13 | «ابن هشام، أوضح المسالك 1/31» (short form) | fn-p14-11, its full citation |
| fn-p14-5 | «ابن عقيل: السابق ص1/48» | fn-p14-4, same author, earliest |

**citation_links holds real links only.**

- It has 138 rows, all from a cited work to a publication:
  - 91 accepted links to the catalogue (title confirmed by `link_catalogue`, **and** the cited authors agree with
    the record's authors: a shared name word in either script, the record's Latin heading and the catalogue's own
    Arabic↔Latin pairs included, one misread letter allowed). Only these are `best = 1`;
  - 25 catalogue candidates (7 title-only with authors agreeing, 18 with no author on one side to compare) and 1
    archive-article candidate;
  - 21 rejected: the record's own authors contradict the citation («مدخل إلى الحجاج» by محمد الولي is not the
    record by رتيمي / خليفة). They are kept as decisions, with the evidence, and no view counts them.
- It holds 0 rows from a back reference and 0 from an article to itself.
- The 188 review, study and part matches are `work_relations`: 59 `is_reviewed_in`, 99 `is_studied_in` and 30
  `is_part_of`.
- The 315 catalogued-only targets are publications `W<999$c>`. A link therefore survives the day such an item is
  scanned.

**The 54 hand checks of experiment 46** are carried into `reviews`. Each is keyed to its v2 subject (`mention_id` or
`mention_id->W<c999>`), with a fingerprint.

- Catalogue links: of 25 right or near, 25 are still accepted links and 1 is gone. The 3 rightly withheld are now
  `is_studied_in` relations.
- Back references marked right in v46 (19):
  - 17 resolve to the same work;
  - 1 resolves to a different work: 0344 «op. cit.», now counted inside its own AGUESSY citation;
  - 1 is unresolved.
- Back references marked wrong in v46 (6):
  - 2 now resolve elsewhere: Pincus, and «L'Esprit piagetien»;
  - 2 are now left unresolved rather than guessed;
  - 2 are still wrong.

### What only this database can answer

Each item below is a canned query at :8003, and each one returns rows:

- **show_me_the_ink**: any citation, with its crop on the scan. All but 4 of the shown mentions have an anchor.
- **corrections_ledger**: shows what Azure read and with what confidence, what the page says, and what is proposed
  for a misprint, which is never applied (D30).
- **metadata_as_printed_and_corrected**: shows every reading of each field side by side, with the one chosen and the
  rule that chose it.
  - The readings are: printed per version, D33-corrected, catalogue, and the Gemini front page.
  - The Gemini front page is in the Azure JSON of 146 documents.
- **most_cited_works**: a cited-reference index that includes books. The shown versions cite 1,689 book cards and 165 chapters (a chapter is its own card since fix round 1). The
  top works are «لسان العرب», «الكتاب» (Sibawayh) and «وفيات الأعيان», each cited by 6 articles, with every back
  reference counted.
- **author_self_citations**: 24 true self-citations (4 before fix round 1). A cited author is the citing author when
  they share a Mandumah authority id (4), or when the cited author's full name (two words or more) equals a byline
  name of an article citing the work (18, e.g. محمد بوبوش, علي الزاملي, فكتور الكك, أحمد كمال الدين موسى). A shared
  surname is never enough.
- **quran_index** and **quran_places**: 451 places, of which 317 have a sura and aya. The 134 quotations in ﴿…﴾ with
  no reference beside them wait for a reference text.
- **verse_search**: 4,102 verse lines, vowelled, searched without vowels.
- **least_trusted_blocks**: trust is computed from Azure confidence, fixes, flags and retries. Each citation
  mention also carries the corrections and flags whose ink overlaps its own words.
- **catalogue_reports**: 264 reports for Mandumah, each with who is right and, for page ranges, the page-number ink.
- **versions_side_by_side**: shows each run's reading of a document, why one is shown and what it cost.
- **flags_on_the_ink**: flags and judge findings, each on its ink.

Other parts of the database:

- **Arabic names** are split into ism, nasab, nisba, laqab and kunya, with titles («د.», «أ. د.») kept on the byline
  mention.
- **`translit_pairs`** holds 60,682 Arabic↔Latin name-token pairs, learned from 1.08M catalogue headings.
- **Both calendars**: 32 hijri dates, each with its gregorian twin.
- **`external_ids`** links publications to their DOI, 999$c, 001, Qdrant doc id and S3 key.
- **`model_calls`** holds 1,676 calls, which put a cost on each version and judge look.

## Deviations from schema47.sql

Each deviation is applied in `common47.schema_sql`:

1. **`citation_mentions.mention_id`** is unique per version, not globally. The id is built on Azure word numbers so
   that the same citation has the same id in every run. With all versions in the db, it cannot be globally unique.
2. **`reconciliation_v46`** is an extra builder-report table.
3. **Ids** (fix round 1). Public ids are `A`/`I`/`C` + 9 Crockford base-32 characters of a hash of the natural key
   (`ANH46TF8C2` = `auth:311655`), not the running numbers `A000123` of the design, and every surrogate integer key
   (`version_id`, `anchor_pk`, `mention_pk`, `authorship_pk`, `assert_pk`, `report_pk`, `finding_pk`, `date_pk`,
   `cited_work_pk`, `link_pk`, block and search `uid` …) is a 53-bit hash of its row's natural key
   (`common47.STABLE_PK`). A running number depends on what was loaded first; a hash does not.
4. **Reconciliation with v46** is done on the documents v2 holds: `platform.db` now also holds the exam
   (`v33_300b`, `v33_300b_final`, 300 more articles), which loads here with the two commands above.

## What is not filled, and why

| what | state | why |
|---|---|---|
| `printed_fixed` | NULL throughout | The masters' text already carries Azure's fixes, and a misprint's proposed form is in `text_corrections`. Links are made on the printed form (`matched_on = printed`). |
| `vector_points`, `search_feedback` | empty | The Qdrant snapshots (436 GB) and the MySQL dumps are in S3 and were not read. The columns of `search_feedback` wait for a dump to be inspected. |
| `merged_ids` | empty after a clean build | A cited work, person or institution id that a later load or link retires is written there (old → new); a document whose primary catalogue record changes too. A clean build retires nothing. |
| `quran_ayat` | structure only: 114 suras, 6,236 ayat, no text | The owner picks a reference text and its licence (DESIGN §10). |
| `supervisions` | 3 rows | Only from the theses among the loaded records. The catalogue's 245k supervisor rows wait for the owner (question 9). |
| Hadith collections | kept as books | Question 6 is open. |
| Persons | authority ids first, then careful clustering | An authority id in hand is the person. A printed name with none joins the one authority person carrying that folded name when the catalogue gives the heading to no other authority id; otherwise names cluster only with a second signal (journal, institution, e-mail, co-author), and a lone name stays a provisional person of its own mention (32 such). |
| Several rows under one 999$c | collapse into one | No report is written for them yet. None of the 354 files is named by two different 999$c. |

## Files

| file | what |
|---|---|
| `out/checks47.json` | reconciliation, EXCEPT comparisons, keys and orphans, examples, hand checks |
| `/home/yassine/data/platform_v2/` | `platform_v2.db`, `build47.sh`, `build47.log`, `link47.log`, `metrics47.json`, `link_cache47.json`, `schema47.html`, `ink.html`, `datasette.log` |
| [progress_build.md](progress_build.md) | the build log |
| [progress_fix.md](progress_fix.md) | the fix-round-1 log |
| [test_ids47.py](test_ids47.py) | two clean builds compared table by table |

## What it changed / next

- `v33_300b` and `v33_300b_final` load with one command each, as exam versions beside final, and `link47.py` links
  them.
- Upstream, for experiment 43, nothing is required. Two changes would make the line crosswalk exact rather than
  box-matched: Azure word ids on ALTO strings, and a 'P:N' label on every TextLine.
- Questions for the owner are unchanged from DESIGN.md §10.

## Fix round 1 (2026-10-20)

The verifier's failures ([VERIFY.md](VERIFY.md)), each fixed at its root, with the change and how it was checked.
Measured on the rebuilt db (clean build, `build47.sh`); the db the verifier read is kept as
`/home/yassine/data/platform_v2/platform_v2.db.bak-20261020-fix0`. `checks47.py` now writes every measure below to
`out/checks47.json` under `fix_round_1`.

| # | failure | root cause | change | evidence |
|---|---|---|---|---|
| 1a | `link47` re-run re-minted 948 of 3,073 cited-work ids | the card key took the "most common author word" from a Python set, whose order changes with the hash seed; ids were running numbers | card key `cw:<title>\|<container>\|<author word>` with every tie broken by sort; public ids are a hash of the key (`common47.hashed_id`); a card whose key moved keeps the id most of its members had, and an id no card keeps is written to `merged_ids` | `test_ids47.py`: relink with nothing changed, and a second clean build under another hash seed, give the same 3,080 cards and ids |
| 1b | `load47` renumbered authorship, assertion, report, finding and date pks on every load | rows deleted and re-inserted with AUTOINCREMENT keys | every surrogate key is a 53-bit hash of the row's natural key (`common47.STABLE_PK`, filled by `insert()`): authorships by (pub, position, role), assertions by (pub, field, form, source, version, value), mentions by (version key, mention id), versions by `V:<stem>@<run>`, anchors by anchor key, block and search `uid` by version + unit | same test: every table equal row by row, keys included |
| 2 | `load47` after `link47` added 57 nameless persons, 41 supervisions, renumbered 10 institutions, added 4 reports | supervisions, persons, institutions and ISSN reports were rebuilt from whatever the db held at that moment, and only `load47` rebuilt some of them | one `biblio47.refresh_global` (supervisions, persons, institutions, ISSN reports) ends both `load47` and `link47`, so the result is a function of the db, not of the last step; supervisors and students get their names from every catalogue heading of their authority; institutions read affiliations in a fixed order; a version shown once keeps its affiliation text as loaded | build B of the test is final → base → link → base again → link again; it equals build A (base → final → link) |
| 3a | La Rosa: ~25 « La preuve » op. cit. sent to the wrong one of two same-titled chapters; one ignored its quoted title | a chapter was known by its book's title, so the quoted «La preuve» matched nothing and "most recent work" decided | the cited work is the chapter, its book is its container; the citation-style rule (title words → year → page continuity → most recent with score 0.5) | 0419: every «La preuve, op. cit., p. 946…966» goes to fn-p2-5 (*Droit international pénal*, p. 945) by page continuity (0.75); «… in Commentaire du Statut de Rome, p. 1584» to fn-p3-1 (0.95); «Réflexions sur l'apport …» is left unresolved: no earlier work of La Rosa has that title |
| 3b | ibid. stopped at an untied short form (2280); 986 of 1,511 short forms unresolved | a short form whose parsed form lost its title was never compared with the full citations | a citation without a parsed title takes the title of the full citation of the same author printed in its text (the first one printed, when several are), else the only one of that author and year | 2280: all «Rafi-ud-Din, The Qur'ān and Modern Knowledge, p. …» go to fn-p8-2, and fn-p14-1 «Ibid.» with them; short forms tied 525 → 577 |
| 3c | 0295: explanatory note in between; 2319: ROLDAN vs ROLDÁN | any short note with a digit broke the chain; author words were not accent-folded | a note breaks «المرجع نفسه» only when it looks like a citation (a page, a back reference, a publisher, §, affaire / jugement) and does not start with «*»; author and hint words are accent-folded | 0295 fn-p2-5 → fn-p2-3; 2319 fn-p25-7 and fn-p25-11 → fn-p21-2 (same author + year 2006); 0419 fn-p16-8 «Ibid» after an unparsed judgment is now left unresolved (v46 and v2 had sent it to La Rosa) |
| 3d | «0 point at a later repeat» was not exact | 0328 fn-p4-1 was typed `short` | a title-less citation with author, place, year and a quoted title in the print is `full`; claim corrected | 2 back references point at a later reference-list entry (was 7); the README says so |
| — | the verifier's 15 sampled back references | | | 15 of 15 now point where the verifier read them (was 11) |
| 4 | 23 of 40 candidate links contradicted by the catalogue's authors | a title match was enough for a candidate, and author or year for an accepted link | `link47.judge_link`: best = 1 only when the authors agree (a shared name word, either script, catalogue Latin headings and transliteration pairs, «عبد X» joined, one misread letter allowed); contradicted matches are `rejected` with the evidence; a confident match with no author to compare is only a candidate | 0 best links without author agreement; 0 candidates contradicted; 21 rejected (all read by hand: e.g. «المجاعات في إفريقيا» → W790023 and «مدخل إلى الحجاج» → W817634 among them); the v46 hand check «العبلي for العيلي» stays accepted |
| 5a | بهي الدين حافظ merged with حافظ، صلاح الدين | a weak name score (0.72) took the catalogue's authority | a weak match keeps the authority only if the catalogue's given name is in the printed name (or its initial: «M. Seklani»); else `weak-name-rejected`, the authority id noted in the evidence and not taken | W136062 is بهي الدين حافظ, provisional; 15 weak matches keep their authority, 2 are rejected |
| 5b | زكي نجيب محمود was two persons; 16 authority ids dropped | weak matches made provisional persons | authority ids first: whenever one is in hand it is the person | 0 authorships whose authority id is in hand but not their person; ANH46TF8C2 holds both articles |
| 5c | 14 names garbled with death notes, years empty | the heading was turned round at its first comma | `common47.split_life` takes «ت. 1427 هـ» off before turning the heading round, and fills the birth/death years in both calendars | 0 names with a life note; 22 persons with a death year (نجيب محفوظ 1427/2006) |
| 5d | «رئيس التحرير», «أسرة التحرير» stored as persons | | an editorial role is an `editor` authorship with no person; an editorial body a `corporate` one with an institution | 0 such persons |
| 5e | non-ISO country codes; `affiliation_mentions.country_code` empty | inst46 keeps an unknown country as printed | `common47.country_iso` (inst46's table plus French, English and long Arabic forms) | 0 non-ISO codes; 146 of 146 printed countries coded |
| 5f | Constantine merged with Constantine 2 | inst46 folds the number away | an affiliation naming a numbered university links to the institution of that number (or a new one, `split-from` the base) | «جامعة قسنطينة 2 - عبد الحميد مهري» links to its own institution |
| — | name clustering | | a name with no authority joins an authority person by name only when the catalogue gives that heading to no other authority id; names cluster only with a second signal (journal, institution, e-mail, co-author), never by name alone (audit P4) | 32 provisional persons |
| 6 | a card lost its authors when its first member had none; a self-citation hidden (0328) | authors came from the representative mention only | authors from the representative, else the most common author list of all members; a cited author whose full name (2+ words) equals a byline name of a citing article is that byline's person | 0 such cards; self-citations 4 → 24, the verifier's 8 missed ones included (محمد بوبوش, علي الزاملي, سحر الشوربجي, أحمد أبو الوفا, فكتور الكك ×2, عبد الرحمن عمر الماحي, أحمد كمال الدين موسى via «مؤلفنا السابق») |
| 7a | 461 `line_map.region_id` rows (keyword and byline TextBlocks) pointed at nothing | those JATS blocks had no line list of their own | a block takes the lines of the ALTO TextBlock carrying its id or pointing at it by `xlink:href` (a block continued on the next page too) | 0 line_map rows pointing at nothing |
| 7b | provenance gaps | | catalogue assertions carry the load; Gemini front-page assertions carry the actor `model:gemini-front-page` and the Azure JSON they were read from; patch applications are written only for versions this run loaded (no more version-less copies per load) and carry the load that built the version; retry patches carry their model; registry ids always carry a load | all five counts 0 |

**The stable-id test** (`test_ids47.py --full`, 5 min, peak 0.6 GB). Build A loads v33_300, v2_55, the judged copy
and final, then links, under `PYTHONHASHSEED=1`. Build B, under seed 2, loads them in the reverse order, links, loads
v33_300 again on top of the linked db, and links again with nothing changed. All 81 tables are then compared row by
row, every column but the clock and load-event ones (`created`, `load_id`, …), the id registry on its live ids.
Result: **identical** — the same 580 persons, 315 institutions, 3,080 cited works, 10,934 citation mentions and 461
authorships under the same ids, and the same content everywhere. On the way it caught four more step-order effects,
also fixed: an anchor's method label taken from whichever run wrote it first, a patch copied into two runs' folders
recorded from whichever was loaded last, a misread keyword term left behind by a version no longer shown, and
`chosen_by` / `runs.note` left over from a version shown earlier. The small form (8 documents, 1 min) runs under
pytest: `.venv/bin/pytest -q experiments/47_platform_v2/test_ids47.py`.

**Hand checks of experiment 46 after the fix.** 17 of the 19 back references v46's checker marked right resolve to
the same work. The other two: 0344 «op. cit.» is counted inside its own AGUESSY citation (as before), and 0419
fn-p9-7 «La preuve, op. cit., p. 959» now goes to the chapter in *Droit international pénal* (p. 945) rather than
the one in the *Commentaire* (p. 1588) — the verifier's reading, by the page numbers; the v46 checker had not told
the two chapters apart. Of the 6 marked wrong, 4 now resolve elsewhere (Pincus and «L'Esprit piagetien» count
inside their own citation, «Land Evaluation Part II» goes to Part II, ROLDÁN to ROLDÁN) and 2 are left unresolved.

**Not changed, and why.**

- Short forms still unresolved (931) name works the article never cites in full; there is nothing to tie them to.
- 19 candidate links have no author on one side to compare. They stay candidates; a person decides.
- The reconciliation with v46 is on the 354 documents v2 holds: `platform.db` has since loaded the exam's 300.

**Files of this round** (in `/home/yassine/data/platform_v2/`): `platform_v2.db.bak-20261020-fix0` is the db the
verifier read; `platform_v2.db.fix1-draft` and `.fix1-draft2` are this round's intermediate builds (proposed for
deletion, 0.55 GB together); `link_cache47.json.bak-fix0` and `metrics47.json.bak-fix0` are the earlier cache and
metrics; `build47_fix1.log` and `checks47_fix1.log` are the logs of the final build.

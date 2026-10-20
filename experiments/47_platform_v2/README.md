# Experiment 47 — the platform database, version 2

**Question.** Platform v1 (experiment 46) stored one reading of each article. Its links were keyed to rows that
change from run to run, and it counted «المرجع السابق» as a fake work→work link. Can a second design keep everything
we hold that Web of Science does not? That means the scan itself, two readings of the text, the full correction
history, the quality record, Arabic scholarly conventions and Mandumah's whole catalogue, each first-class and tied
together. Can it be built from the same sources, reconcile with v1, and take the next run tonight?

**Answer (2026-10-20, $0, no paid calls).** Yes.

- **The database.** `/home/yassine/data/platform_v2/platform_v2.db` (SQLite, 277 MB) is built from the same
  sources as `platform.db`. It holds 83 tables of the design, one builder report table and 15 views, with
  169 foreign-key column pairs (161 keys) declared.
- **Checks.** There are 0 orphans, and every view runs.
- **Serving.** It is served read-only at **http://127.0.0.1:8003/platform_v2**, with 17 canned queries. The schema
  diagram is at http://127.0.0.1:8003/diagram/schema47.html, and the "show me the ink" page is at
  http://127.0.0.1:8003/diagram/ink.html?a=1674 (that anchor is «السابق نفسه» of `0069-000-026-005` fn-p15-13, boxed
  on its page).
- **Build time.** A full build from scratch takes 2 min 2 s and peaks at 153 MB memory. That covers the four loads,
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
| works | 4,789 | cited_works | 3,073 | repeats inside and across articles are one card |
| back_references | 544 | ibid / op_cit / loc_cit mentions | 650 | every marker of a note counts, and so do bare «السابق» / «نفسه» |
| citation_links | 790 | citation_links + work_relations + resolutions | 134 + 188 + 482 | real links only (below) |
| link_checks | 54 | reviews (link_checks) | 54 | = |
| flags | 1,666 | flags | 1,665 | `1764-003-005-006` has a flag in v33_300's flags.json but no v33_300 master |
| judge_findings | 634 | judge_calls / judge_findings | 607 / 219 | v46's 415 "none" rows are clean calls |
| patches | 124 | patches | 125 | key `run\|stem\|patch_id`: j-1677-p1-1 of two articles no longer collide |
| article_authors / affiliations | 413 / 247 | byline_mentions / affiliation_mentions (shown) | 413 / 247 | = |
| article_authors | 413 | authorships | 461 | twins become one authorship; catalogue-only contributors are added |
| catalogue_disagreements | 253 | catalogue_reports (print vs catalogue) | 253 | = (plus 7 invalid-ISSN reports) |
| catalogue_records | 354 | catalogue_records (by 999$c) | 669 | plus the 315 catalogued-only publications that links and relations point at |

Other counts, by area:

- People and institutions: 506 persons, 1,001 person names, 312 institutions.
- Journals and catalogue: 404 journals, 657 issues, 888 catalogue contributors.
- Search and dates: 62,924 search units, 971 publication dates.
- Arabic and the Quran: 60,682 transliteration pairs, 4,102 verse lines, 451 Quran places.
- Each of these is explained in the reconciliation table.

### «المرجع السابق» resolves to the first full citation

- **The rule.** `link47.resolve` walks each article's citation mentions in reading order: notes in printed order,
  and the reference list placed by page.
- **Grouping.** Full citations and short forms of the same work are one in-article work. Same title, or the same
  author with most title words, counts as the same work. That catches a misprinted title.
- **Where a back reference points.** It goes to that work's first full citation, never to another back reference.
  0 rows point at a back reference, and 0 point at a later repeat. Chains collapse in one step.
- **Counting.** Each back reference counts as one more mention of the work in `v_times_cited`.

The shown versions hold these citation mentions:

| kind | count |
|---|---|
| full | 3,245 |
| short | 1,511 |
| ibid | 244 |
| op_cit | 403 |
| loc_cit | 3 |
| quran | 111 |

How the 650 back references were handled:

| outcome | method or reason | count |
|---|---|---|
| resolved (482 in all) | previous mention | 147 |
| | previous mention, chain collapsed | 117 |
| | same author, earliest | 106 |
| | same author with title words | 64 |
| | same author, most recent of several works (score 0.6, reason recorded) | 39 |
| | title words | 9 |
| counted once, as the citation just parsed before it (20) | «Pincus: Economic Aid, op. cit.» | 20 |
| unresolved, reason recorded (148 in all) | names a work not parsed earlier | 87 |
| | the back reference before it is unresolved | 27 |
| | an unparsed short note lies in between | 29 |
| | other | 5 |

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

- It has 134 rows, all from a cited work to a publication:
  - 94 accepted links to the catalogue (title, plus author or year, confirmed by `link_catalogue`);
  - 39 catalogue candidates with title only;
  - 1 archive-article candidate.
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
- **most_cited_works**: a cited-reference index that includes books. The shown versions cite 1,859 book cards. The
  top works are «لسان العرب», «الكتاب» (Sibawayh) and «وفيات الأعيان», each cited by 6 articles, with every back
  reference counted.
- **author_self_citations**: 4 true self-citations, found because the cited author and the citing author share a
  Mandumah authority id. A shared surname is never enough.
- **quran_index** and **quran_places**: 451 places, of which 317 have a sura and aya. The 134 quotations in ﴿…﴾ with
  no reference beside them wait for a reference text.
- **verse_search**: 4,102 verse lines, vowelled, searched without vowels.
- **least_trusted_blocks**: trust is computed from Azure confidence, fixes, flags and retries. Each citation
  mention also carries the corrections and flags whose ink overlaps its own words.
- **catalogue_reports**: 260 reports for Mandumah, each with who is right and, for page ranges, the page-number ink.
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

## What is not filled, and why

| what | state | why |
|---|---|---|
| `printed_fixed` | NULL throughout | The masters' text already carries Azure's fixes, and a misprint's proposed form is in `text_corrections`. Links are made on the printed form (`matched_on = printed`). |
| `vector_points`, `search_feedback` | empty | The Qdrant snapshots (436 GB) and the MySQL dumps are in S3 and were not read. The columns of `search_feedback` wait for a dump to be inspected. |
| `merged_ids` | empty | Nothing has merged yet. A document whose primary catalogue record changes writes a row there. |
| `quran_ayat` | structure only: 114 suras, 6,236 ayat, no text | The owner picks a reference text and its licence (DESIGN §10). |
| `supervisions` | 3 rows | Only from the theses among the loaded records. The catalogue's 245k supervisor rows wait for the owner (question 9). |
| Hadith collections | kept as books | Question 6 is open. |
| Persons | not clustered | Persons come from authority ids. A printed name with no authority id stays a provisional person per mention, unless it equals the name of an authority person seen elsewhere (`name-key-to-authority`). |
| Several rows under one 999$c | collapse into one | No report is written for them yet. None of the 354 files is named by two different 999$c. |

## Files

| file | what |
|---|---|
| `out/checks47.json` | reconciliation, EXCEPT comparisons, keys and orphans, examples, hand checks |
| `/home/yassine/data/platform_v2/` | `platform_v2.db`, `build47.sh`, `build47.log`, `link47.log`, `metrics47.json`, `link_cache47.json`, `schema47.html`, `ink.html`, `datasette.log` |
| [progress_build.md](progress_build.md) | the build log |

## What it changed / next

- `v33_300b` and `v33_300b_final` load with one command each, as exam versions beside final, and `link47.py` links
  them.
- Upstream, for experiment 43, nothing is required. Two changes would make the line crosswalk exact rather than
  box-matched: Azure word ids on ALTO strings, and a 'P:N' label on every TextLine.
- Questions for the owner are unchanged from DESIGN.md §10.

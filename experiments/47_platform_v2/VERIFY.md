# Experiment 47: independent check of platform_v2.db

Checked on 2026-10-20 by a verifier who built nothing. The checks ran against `/home/yassine/data/platform_v2/platform_v2.db`
(build `6089dc4`), `DESIGN.md` / `schema47.sql`, `platform.db` (v46), the masters in
`experiments/43_rehearsal/out/<run>/masters`, the Azure JSON and `marc.db`.

- Every source was opened read-only. Every rebuild ran on copies in the session scratchpad, and the link step's
  cache and metrics went to the scratchpad too.
- No protected file was touched, and no paid call was made.

## Verdict

**Not ready to be called final. The structure and the reconciliation hold, but rebuilds do not keep their ids, and
several values are wrong.**

- **What holds.** The schema matches the design, there are no orphans, the counts reconcile with v1 and the masters,
  the ink anchors are right, and `citation_links` obeys the owner's rules: no back references, no same-article rows,
  and no work-to-work rows.
- **What fails.**
  - Re-running the build changes the ids of a third of the cited works.
  - The people layer depends on the order the steps were run in.
  - Some «المرجع السابق» go to the wrong one of two works by the same author.
  - About half of the `candidate` citation links are contradicted by the catalogue's own authors.
  - Some person merges are wrong, or missed even though the catalogue's authority id is in hand.

| # | check | result |
|---|---|---|
| 1 | Tables, columns, FKs and indexes against `schema47.sql` | **PASS** |
| 2 | Orphans: declared FKs, plus undeclared references inside a version | **PASS, one gap** |
| 3 | Counts against `platform.db`, recomputed independently | **PASS** |
| 4 | 5 random articles against their JATS and MARC | **PASS, two gaps** |
| 5 | 15 random back references, judged by reading the notes | **FAIL: 11 right, 2 wrong, 2 missed** |
| 6 | `citation_links`: same-article, back-reference and work-to-work rows | **PASS on the rules, FAIL on candidates** |
| 7 | Provenance on values | **PASS, with gaps** |
| 8 | People and institution merges, 20-row sample | **FAIL: 18 of 20 right, plus systematic misses** |
| 9 | Idempotency: `load47` twice on a copy, plus `link47` on a copy | **FAIL: ids are not stable** |
| 10 | Ink anchors against the Azure JSON (25 random) | **PASS** |
| 11 | Every view runs; self-citation | **PASS for the 4 found; the measure undercounts** |

---

## 1. Schema against the design: PASS

I applied `schema47.sql` to an empty database and compared it with the built db (`sqlite_master`, `table_info`,
`foreign_key_list`, `index_list`).

- **Tables and views.** All 87 design tables are present: the 83 tables plus the FTS shadow tables. All 15 views are
  present.
- **The only extra table** is `reconciliation_v46`, which the README declares.
- **Columns and foreign keys** are identical in every table.
- **The only index difference** is on `citation_mentions` (`cm_mention_id` against `cm_mention_key`). This is the
  declared deviation: mention ids are unique per version.
- **Totals.** 169 FK column pairs are declared, `PRAGMA foreign_key_check` returns 0 rows, and `integrity_check`
  returns ok.

## 2. Orphans on undeclared references: PASS, one gap

Many intra-version references are not declared as FKs: `(version_id, block_id)`, `section_id`, `note_id` and so on. I
checked 18 of them with joins on version_id plus the column. 17 have 0 orphans. These include `blocks.section_id`,
`notes.first_block_id`, `note_calls.block_id`, `text_corrections.block_id`, `citation_mentions.block_id` and the note
container, `flags.block_id`, `figures.caption_block_id` and `line_map.block_id`.

- **Gap: `line_map.region_id` points at nothing in 461 rows**, covering 130 regions in the shown run.
  - These are the ALTO TextBlocks of the front matter: 96 keyword groups (`kwd-group`) and 33 bylines (`contrib`).
  - They are in neither `page_regions` nor `blocks`.
  - Example: `0069-000-026-005` p2b7, whose lines carry fix4 and fix5 at "2:12".
  - A flag or fix on a keyword or byline line therefore lands on no row.
- **Note.** In `catalogue_record_documents`, 626 stems are not in `documents`. These are files the catalogue names
  but that were not loaded, which is as designed.

## 3. Counts against platform.db (v46): PASS

I recomputed these myself from both databases, attached together:

- **Shown run.** The shown run per article differs in 0 of 354.
- **EXCEPT both ways.** blocks (stem, block_id, text), notes (stem, note_id, text), fixes (id, Azure reading, print) and
  abstracts (stem, text) each give 0 rows in both directions.
- **Keywords.** v1's 1,179 rows reduce to 1,173 = `count(DISTINCT stem, term, source)` in v1, which explains
  `publication_keywords`.
- **Journals and issues.** The journals and issues of the 354 loaded documents' publications are exactly v1's 261 and
  353. The extra 143 journals and 304 issues belong to the 315 catalogued-only publications, and no journal or issue
  is unused.
- **The `reconciliation_v46` table** (50 rows) matches what I found.

## 4. Five random articles against their JATS and MARC: PASS, two gaps

The sample (seed 4720) was `0135-025-001,002-002`, `0200-000-140-006` (v2_55), `2449-000-023-005`, `0328-000-032-006`
and `0368-000-003-003`. I parsed the JATS with ElementTree, which is independent of parse46/47.

| field | result |
|---|---|
| authors (`contrib/string-name`) | 5/5 equal. Titles («الدكتور», «أ .د») are stripped into `titles`, and the printed form is kept |
| affiliations (`aff`) | 5/5 equal, text identical |
| keywords | the masters' `kwd` equal `publication_keywords` (source masters). Catalogue keywords are added as source catalogue |
| notes | count equal in all 5 (39, 0, 40, 23, 76). Text equal for every note (0 mismatches) once the `parsed-citations` paragraph is excluded |
| abstracts | printed abstracts are stored per paragraph and concatenate to the JATS abstract (0135, 2449). Catalogue abstracts are added as form `catalogue` |
| cited works | parsed citation mentions = number of `element-citation` in the JATS (69, 0, 71, 39, 37) = v1 `works` |
| authorships against marc.db | every authorship has the right c999, catalogue seq and authority id (316420, 258560/466223/492159, 392411, 321619, 325120) |

**Gaps, both from 0328-000-032-006:**

- **A full citation in a footnote is typed `short`.** fn-p4-1 «Les principes généraux de la procédure…» by Chaudet is
  a full citation but has kind `short`. All five «Chaudet، المرجع السابق» therefore resolve forward to the reference
  list entry r14 (page 16), not to the first full citation.
  - Separately, the misprinted reference entry r16 «Trautè élémentaire de drait administratif» did not join the card
    of fn-p4-1 «Traité élémentaire de droit administratif» (C0000561 and C0000576).
- **A true self-citation is missed.**
  - The author «أحمد كمال الدين موسى» cites his own «نظرية الإثبات في القانون الإداري» (r4 names him), and
    «مؤلفنا السابق» («our earlier work») is in fn-p11-1.
  - The card C0000565 has **no `cited_work_authors`**, because its first member (fn-p4-1) has no author.
  - Over the archive, 8 cards have no authors although one of their members has parsed authors.

## 5. «المرجع السابق» / ibid. / op. cit.: 15 random back references (seed 15047): FAIL

I read each back reference's note, and the notes before it.

| # | article, note | printed | v2 points at | verdict |
|---|---|---|---|---|
| 1 | 0069-000-026-005 fn-p14-8 | السابق ص 118 | fn-p14-7 الزجاجي، الإيضاح… ص 117 | right |
| 2 | 0135-025-001,002-002 fn-p4-1 | نفسه، 159/2 | fn-p3-1 الخصائص (the short form fn-p3-4 is in between) | right, chain collapsed |
| 3 | 0295-020-002-007 fn-p2-5 | المصدر السابق نفسه، ص٢٥ | unresolved ("a short note lies in between") | **missed**: the note in between (fn-p2-4) is an explanatory «* لم تتوفر احصاءات…», and the work is fn-p2-3 (p. 24 → p. 25) |
| 4 | 0368-000-003-003 fn-p15-4 | المصدر ذاته ص ٦٥ | fn-p14-16 (the الطليعة interview) | right |
| 5 | 0419-000-044-007 fn-p5-5 | La Rosa, « La preuve », op.cit., p.954 | fn-p3-1 (« La preuve » in *Commentaire du Statut de Rome*, p. 1588) | **wrong**: see below |
| 6 | 0419-000-044-007 fn-p12-2 | La Rosa, Juridictions pénales internationales, op.cit. | fn-p2-6, the first full citation | right |
| 7 | 0658-049-003-006 fn-p7-8 | نفس المصدر | fn-p7-7 «أشرف السوانح» (short, the only mention) | right |
| 8 | 1110-020-001-047 fn-p21-10 | شحاتة: المرجع نفسه | r25 (reference list, pp. 19–20, which comes before the endnotes on pp. 21–23) | right |
| 9 | 1110-020-001-047 fn-p21-11 | المرجع نفسه | r25 | right |
| 10 | 1110-020-001-047 fn-p23-7 | المرجع نفسه | r8 أفا والمغراوي، الخط المغربي | right |
| 11 | 2147-009-002-002 fn-p10-10 | دنيا عبد العزيز فهمي المرجع السابق | fn-p9-4 | right |
| 12 | 2280-006-001-014 fn-p14-1 | Ibid., pp. 97-99 | fn-p13-8, a **short form** «Rafi-ud-Din, The Qur'ān and Modern Knowledge» | **wrong**: the first full citation is fn-p8-2 |
| 13 | 2280-006-001-014 fn-p20-2 | Ibid. | fn-p19-5 "What is Man" | right |
| 14 | 2319-000-022,023-022 fn-p25-7 | ROLDAN et al., 2006, op. cit. | unresolved ("names a work not parsed earlier") | **missed**: fn-p21-2 «ROLDÁN, L., BENDALA… 2006» (accent only) |
| 15 | 2319-000-022,023-022 fn-p25-16 | MARISCAL et al., 2003, op. cit. | fn-p24-16 MARISCAL… 2003, Almoraima 29 | right (the mention's printed span starts with the previous citation's tail) |

The result is 11 right, 2 wrong and 2 missed. None of them points at another back reference. The causes,
followed across the whole database:

- **Two works by one author with the same title: "same-author-latest" picks wrongly.**
  - In 0419, La Rosa has two chapters both called « La preuve ».
    - fn-p2-5 is in *Droit international pénal*, p. 945.
    - fn-p3-1 is in *Commentaire du Statut de Rome*, p. 1588.
  - The op. cit. locators run 946, 947, 954, 955, 956 … 966, which continue fn-p2-5. v2 sends about 25 of them to
    fn-p3-1 with score 0.6.
  - fn-p2-9 «« La preuve », op.cit., p.946» goes to fn-p2-6 *Juridictions pénales internationales*. The quoted title
    hint is ignored, and this is the one row in all 39 same-author-latest rows where the quoted title contradicts the
    target.
  - The cited page number would separate the two works.
- **Short forms are not tied to their full citation when the parsed form has no title.**
  - 986 of the 1,511 short mentions in the shown versions have no resolution.
  - At least 44 of them contain, in their printed text, the title of an earlier full citation in the same article.
    In 2280 alone, about 10 «Rafi-ud-Din, The Qur'ān and Modern Knowledge, p. …» are not counted for fn-p8-2.
  - Back references that follow such a short form stop at the short form (case 12).
- **Accent folding.** «ROLDAN» against «ROLDÁN» leaves 2 back references unresolved (fn-p25-7, fn-p25-11).
- **The builder's claim "0 point at a later repeat" is not exact.** 7 resolved back references point at a mention later
  in reading order, always a reference-list entry after the notes:
  - 0328: 5 (because fn-p4-1 was typed `short`);
  - 0290 fn-p8-2 → r10;
  - 1453 fn-p3-5 → r61.

  The work is right in each case.
- **What does hold.**
  - 0 back references resolve to a back reference, and 0 cross versions.
  - When a target has an earlier full member of the same card, it is always the first one (0 exceptions).
  - Part-of-citation markers (20) are not double counted in `v_mention_work`.

## 6. citation_links: PASS on the owner's rules, FAIL on candidates

- **The rows.** There are 134, all `target_kind = 'publication'` and all with an existing `target_pub_id`.
  - 0 come from a back-reference mention.
  - 0 are same-article: no member of the cited work belongs to a version of the target publication, in any version.
  - 0 are work-to-work. `work_relations` also has 0 same-article rows and 0 rows whose object is a cited work.
  - Every row has score, method, evidence, asserted_by and link_run_id. There is at most one `best` link per work.
- **The accepted links.** I checked 10 random accepted links against the MARC record (title, author and year). All 10
  are right.
- **Fail: the candidates are not "real links".**
  - 23 of the 40 `candidate` rows cite a work whose printed authors share no name token with the target record's
    catalogue authors. 12 others have no author to compare.
  - Examples:
    - «المجاعات في إفريقيا» by عبد العظيم محمد الشيخ → W790023 «المجاعة في إفريقيا» by علي، توري / أبو كروق.
    - «مدخل إلى الحجاج» by محمد الولي, 2011 → W817634, by رتيمي / خليفة, 2016.
    - «تقرير التنمية الإنسانية العربية» (UNDP) → W214722 «حوار حول تقرير…».
  - The catalogue already contradicts these rows. They should be rejected, or held outside `citation_links`.

## 7. Provenance: PASS, with gaps

Every link, membership, authorship, affiliation link and relation row has `method`, `asserted_by` and `evidence`. All
content rows carry `version_id`. The gaps:

- **Catalogue assertions.** The 5,843 `metadata_assertions` with form `catalogue` have `load_id` NULL. They do carry
  `export_id`, and DESIGN §6 says "every row traces to a `load_id`".
- **Gemini-title assertions.** The 146 with form `gemini-title` have no actor_id, version_id or export_id. Only
  `source = 's3-gemini-title'` says where they came from, although they were read from local Azure JSON.
- **Content patches with no version.** 29 `patch_applications` of content patches (mark_noise, set_kind) are `applied`
  with `version_id` NULL, while the schema comment says content patches carry the version built. A new copy of these
  29 rows is added on every load (see §9).
- **Two patches with no actor.** `gemini-retry` patches r-0368-p11-1 and r-1080-p9-1 have actor_id NULL.
- **Persons registered with no load.** 87 person ids in `id_registry` have `created_load` NULL.

## 8. People and institution merges, 20-row sample: FAIL

The sample was 12 persons with more than one name key (seed 2020) and 8 institutions with more than one name
(seed 31).

- **Persons: 11 of 12 right.**
  - **Wrong:** A000372 joins the printed «بهي الدين حافظ» (byline of 0331-000-054-001 / W136062) with the catalogue's
    «حافظ، صلاح الدين» (weak-name, 0.72). The first names differ, and the preferred name became the catalogue's.
  - **Right:** A000373 «يوسف الشارونى»/«الشوني، يوسف», which is a catalogue misspelling worth a report. Also right:
    A000106, A000405, A000283, A000273, A000292, A000231, A000260, A000332 (Arabic and Latin twins), A000095 and
    A000056.
- **Institutions: 7 of 8 right.**
  - **Doubtful:** I000051 merges «جامعة قسنطينة» with «جامعة قسنطينة 2 - عبد الحميد مهري», which have been separate
    universities since 2011.
  - **Right:** Cairo (including «Cairo Unverssity»), Salahaddin, UMT Lahore, Tikrit, Baghdad, Ehya and Babylon.
- **Systematic problems found while sampling:**
  - **Authority ids are dropped.** The 17 `weak-name` authorships make provisional persons that drop the authority id
    their catalogue contributor carries (16 distinct authorities), yet take the catalogue's name.
    - Example: «زكي نجيب محمود» is **two persons**, A000221 and A000222, although both catalogue rows carry authority
      311655.
  - **Life notes inside names.** 14 persons have the death note inside `preferred_name_ar`, with the name order
    broken: «نجيب، ت. 1427 هـ محفوظ», «حمد، ت. 1421 هـ الجاسر», «محمد بن أبي بكر بن أيوب، ت. 751 هـ ابن قيم الجوزية».
    `death_year_h` and `death_year_g` are empty.
  - **Roles as persons.** «رئيس التحرير» (A000371) and «أسرة التحرير» (A000402) are persons. They are an editorial
    role and a corporate byline.
  - **Countries.** `institutions.country_code` holds 20 values that are not ISO codes («Algérie», «Irak», «Pakistan»,
    «باكستان», «الجمهورية العربية السورية», «Kingdom of Bahrain», «La Libye»). `affiliation_mentions.country_code`
    is NULL in all 457 rows.

## 9. Idempotency: FAIL

Everything ran on scratch copies, with `link47` redirected to a scratch data folder.

- **`load47` run twice** (v33_300, v2_55, v33_300_judged --stem 0368-000-013-009, v33_300_final). Each pass reported
  "0 loaded, all unchanged".
  - From pass 1 to pass 2, the content is identical once surrogate keys are excluded (0 differing rows in 12 tables).
  - **But the surrogate keys are renumbered on every load.** `authorship_pk` went from 1246–1708 to 2100–2562, and
    `assert_pk`, `report_pk`, `finding_pk` and `date_pk` changed too. The 180 `supersedes` values move with them.
    Any URL or review that names an authorship or assertion by its pk breaks on the next load.
  - `patch_applications` grows by 29 rows per load: the version-less rows in §7.
- **`load47` on the built db changes it.** The built db has had `link47` run on it. A load on top of that changes:
  - `persons` 506 → **563**: 57 new `catalogue-authority` persons with **NULL name**.
  - `supervisions` 3 → **44**.
  - `person_authorities` 457 → 514, and `id_registry` 3,900 → 3,957.
  - `institutions` 312 → 311, with 10 I ids renumbered (I000155/156, 169/170 …).
  - `institution_names` 325 → 312, and `affiliation_links` 396 → 395.
  - `catalogue_reports` 260 → 264.

  The database therefore depends on the order its steps were run in. The documented exam workflow (`load47 --run
  v33_300b`, then `link47`) will change the people layer of articles the exam does not touch.
- **`link47` re-run alone on a fresh copy, with nothing changed.**
  - `cited_works` goes from 3,073 to **4,021**: **948 cards (31%) are retired as `merged` and re-minted with new
    ids**. For example, C0000002 «دراسة لبعض عوامل السوء النفسى…» becomes C0003074.
  - `merged_ids` stays empty.

  This breaks the design's promise of an append-only registry with stable C ids and retired ids recorded (DESIGN §3).

## 10. Ink anchors against the Azure JSON: PASS

I took 25 random word-precision anchors of shown citation mentions and read the words first..last of that page
straight from the Azure JSON.

- **Text.** `text_azure` equals the Azure words in 25 of 25.
- **The printed citation matches** in 23. The other two are Azure misreadings that the print fixed («الفكت» → «النكت»,
  «وبنية» → «بغية»), so the ink is right. One span runs one word past the citation's end.
- **Mention ids are stable across runs.** 5,383 of the 5,403 v33_300 mention ids recur in v33_300_final for the same
  article (99.6%). `anchor_key` is unique.

## 11. Views and self-citation

- **Views.** All 15 views run: `v_articles` 354, `v_times_cited` 3,073, `v_author_self_citations` 4, and so on.
- **The 4 self-citations are right**: الهمالي, اللمكي, شوقي صلاح أحمد إسماعيل and عمر بيشو.
- **The measure undercounts.**
  - Of 11 cases where the byline name equals a cited author's printed name in full, inside the same article, 7 are not
    counted. They are محمد بوبوش, علي الزاملي, سحر الشوربجي, أحمد أبو الوفا, فكتور الكك (×2) and عبد الرحمن عمر الماحي.
  - Adding 0328 أحمد كمال الدين موسى, §4, makes 8.
  - The view needs both sides tied to a person through an authority id, and cited authors rarely are. An exact
    full-name match within the article was never accepted as evidence. This is a choice to put to the owner, not a
    bug, but "4 self-citations" should be read as a floor.

## Failures

1. **Ids are not stable across rebuilds.**
   - `link47` re-run with nothing changed re-mints 948 of 3,073 cited-work ids, and `merged_ids` stays empty.
   - `load47` renumbers authorship, assertion, report, finding and date pks on every load.
2. **The build depends on step order.** `load47` after `link47` adds 57 nameless persons and 41 supervisions,
   renumbers 10 institutions and adds 4 reports.
3. **Back references (15-row sample: 11 right).**
   - About 25 La Rosa « La preuve » op. cit. in 0419 go to the wrong one of two same-titled works. One ignores its
     quoted title.
   - Ibid. stops at an untied short form instead of the first full citation (2280).
   - Misses: an explanatory note in between (0295), and accents (ROLDAN, 2319).
   - 986 of 1,511 short forms are unresolved, at least 44 with an earlier full citation in their text.
4. **citation_links candidates.** 23 of 40 candidates are contradicted by the catalogue's authors, so they are not
   real links.
5. **People.**
   - Wrong merge: بهي الدين حافظ with صلاح الدين حافظ.
   - Authority ids dropped on 17 weak-name authorships, which splits زكي نجيب محمود (authority 311655) into two
     persons.
   - 14 names garbled with death notes.
   - Editorial roles stored as persons.
   - Non-ISO country codes.
6. **A cited work loses its authors when its first member has none** (8 cards). This hides a self-citation (0328).
7. **Smaller gaps.**
   - 461 `line_map.region_id` rows (keyword and byline blocks) point at no row.
   - In 0328, a full footnote citation is typed `short`.
   - Provenance gaps: catalogue assertions have no load_id; the gemini-title assertions have no actor; 29 content
     patch applications have no version.

## How to reproduce

The scripts and copies are in the session scratchpad:

- `v/c4.py`: the five articles.
- `v/c5_samples.txt`: the 15 back references with their context.
- `v/tabhash.py`: per-table hashes.
- `v/runlink.py`: `link47` with `common47.DATA` redirected.

The idempotency runs were:

```
cp platform_v2.db idem.db
for each run: .venv/bin/python experiments/47_platform_v2/load47.py --db idem.db --run <run>   (twice)
.venv/bin/python runlink.py link_only.db <scratch dir>                                           (on a fresh copy)
```

Then compare the per-table hashes, and rows with the surrogate keys excluded.

---

## Re-verify round 1 (2026-10-20)

Checked by a second verifier who built nothing, against the rebuilt `/home/yassine/data/platform_v2/platform_v2.db`
(build of `549506d`, sha256 `b8ba63a6…66b11`, unchanged by this check). Every source was opened read-only; every
build ran on copies in the session scratchpad (`…/scratchpad/rv/`), with `link47 --work` pointed there. No paid call.
`platform.db`, `marc.db` and the served db have the same sha256 after the check as before. Datasette was not
restarted (the served db was not rebuilt).

### Verdict

**Close, but not yet final.** Ten of eleven checks pass, most of them cleanly. Ids are now stable: two clean
builds under different hash seeds and step orders, and a re-load and re-link of the served db, give the same ids
and rows. Back references, links and provenance hold up. **Check 8 fails, narrowly.** The new step that ties cited
authors to persons gives two works by «عبد الحليم محمود» (the Azhar shaykh, catalogue authority 438086) to a
different person, the psychologist «السيد، عبدالحليم محمود» (authority 123266). This breaks the README's own rule.
The «جامعة قسنطينة 2» fix also covers only the university level: that university's faculty and department still
sit under «جامعة قسنطينة».

| # | check | result |
|---|---|---|
| 1 | Schema against `schema47.sql` | **PASS** |
| 2 | Orphans, declared and undeclared, `line_map.region_id` included | **PASS** (the round-0 gap is closed) |
| 3 | Counts against `platform.db`, on the 354 documents v2 holds | **PASS** |
| 4 | 5 random articles + 3 citation-heavy ones against JATS and MARC | **PASS** |
| 5 | 15 new random back references (seed 2610), plus round 0's 15 | **PASS: 13 right, 0 wrong, 2 missed (upstream text); round 0's 15 are now 15/15** |
| 6 | `citation_links`: the owner's rules, author agreement, samples | **PASS, one minor gap** |
| 7 | Provenance | **PASS** (all five round-0 gaps are 0) |
| 8 | People and institutions: 20-row sample + systematic checks | **FAIL: sample 20/20, but one wrong identity and one wrong parent** |
| 9 | Idempotency: 2 clean builds, load ×2 + relink on a copy, exam load on a copy | **PASS, one minor gap** (5 display labels depend on load order) |
| 10 | 25 random ink anchors against the Azure JSON (seed 2525) | **PASS 25/25** |
| 11 | Views and self-citations | **PASS: 15 views run; 24/24 self-citations right** |

### 1. Schema: PASS

I applied `schema47.sql` to an empty db and compared `sqlite_master`, `table_info`, `foreign_key_list` and
`index_list`.

- The db has 87 design tables plus `reconciliation_v46`, which is declared, and all 15 views.
- Columns and FKs are identical. There are 169 FK column pairs, `foreign_key_check` returns 0 rows, and
  `integrity_check` returns ok.
- The only index difference is the declared one: `citation_mentions.mention_id` is unique per version.

### 2. Orphans: PASS

- **19 undeclared intra-version references** were joined on `version_id` + column. All 19 have 0 orphans. They are
  the `block_id` of abstracts, bylines, mentions, flags, assertions, note calls, Quran citations, table cells,
  corrections and line_map, plus `blocks.section_id/note_id/figure_id`, `notes.first_block_id`, figure caption and
  anchor blocks, `sections.parent_id/heading_block_id` and `verse_lines.group_block_id`.
- **`line_map.region_id` → neither `page_regions` nor `blocks`: 0** (was 461). Every line_map row has exactly one of
  block_id and region_id. 674 byline lines and 390 keyword lines now sit on their blocks.
- Mention containers have 0 orphans, and 0 resolutions cross a version.
- `merged_ids` is empty, as expected after a clean build.

### 3. Counts against platform.db: PASS

`platform.db` now holds 654 articles. The 354 that v2 holds were compared, with EXCEPT both ways:

| table | result |
|---|---|
| shown run | differs in 0 of 354 |
| blocks, notes, fixes, misprints | 0 / 0 rows both ways |
| abstracts (printed 241, catalogue 138) | 0 / 0 |
| article_runs ↔ versions | 655, 0 / 0 |
| figures | 1,910 = 1,910 |
| note_calls | 4,024 = 4,024 |
| bylines / affiliations | 413 / 247, equal |
| journals / issues of the 354 | 261 / 353, equal; 0 unused journals or issues |
| parsed mentions | 4,789 = v1 `works` |
| keywords | 1,179 → 1,173 distinct, equal |

- **Figures.** The ids of 365 inline formulas and pictures differ, which the schema declares: they now get
  anchor-based ids.
- **Keywords.** Two rows differ only in the printed form, which keeps a trailing «.» and the «مصطلحات أساسية:»
  prefix.

### 4. Articles against JATS and MARC: PASS

The first sample (seed 9131) was `0382-016-063-013`, `0197-002-001-003`, `7672-000-000-015`, `1010-006-011-015` and
`0919-000-157-021`. Because it had few citations, I added a second sample (seed 9132) of articles with at least 20
mentions: `2205-000-024-006`, `1875-005-020-001` and `2307-036-001-009`. I parsed the JATS with ElementTree.

| field | result |
|---|---|
| authors | 8/8 equal. Titles are stripped into `titles`, and the printed form is kept |
| affiliations | 8/8 equal |
| keywords | equal |
| notes | count and text equal: 0 mismatches over 116 notes |
| abstracts | each printed `abstract` / `trans-abstract` is one row, with its heading «المستخلص:» stripped |
| element-citation against parsed mentions | 12, 48, 65 and 26: equal |
| authorships against marc.db | right c999, catalogue seq and authority id in every one of the 10 authorships |

### 5. Back references: PASS

**Fresh sample** (seed 2610). Each note was read with the notes before it.

| # | article, note | printed | v2 → | verdict |
|---|---|---|---|---|
| 1 | 0069 fn-p15-1 | السابق ص 1/32 | fn-p14-14 الإنصاف, through fn-p14-15 | right |
| 2 | 0344 fn-p18-4 | «…Extrait de l'affirmation de l'identité culturelle op. cit. p. 49» | part-of-citation | right by the rule: counted inside the Césaire citation |
| 3 | 0344 fn-p26-1 | (٦٧) نفس المرجع السابق ص ٢٧٧ | fn-p25-2 C.R.E.S. | right, but see the gap below |
| 4 | 0368-003 fn-p14-8 | شرابي، المصدر السابق ص ٢١٦ | fn-p14-4, the Arabic book, p. 215 | right |
| 5 | 0368-003 fn-p14-9 | Waskow, From Race Riot to Sit-In, op. cit. | fn-p13-15 | right |
| 6 | 0368-013 fn-p26-16 | غلاب وعبدالحكيم، المصدر السابق | fn-p26-14, a short form: the article has no full citation of it | right |
| 7 | 0419 fn-p7-9 | La Rosa, Juridictions pénales internationales, op.cit. | fn-p2-6 | right |
| 8 | 0419 fn-p10-9 | La Rosa, « La preuve », in Commentaire…, op.cit., p. 1594 | fn-p3-1 | right |
| 9 | 0419 fn-p14-2 | La Rosa, Juridictions…, op.cit., p.293 | fn-p2-6 | right |
| 10 | 0702 fn-p10-6 | Crawshaw, op.cit.p. 114 | unresolved, "names a work not parsed earlier" | **missed**: fn-p10-2 «Nancy Craws haw, The Cyprus Revolt» (the name is split in the text) |
| 11 | 1326 fn-p16-4 | مصطفى حجازي، المرجع السابق، ص. 66 | fn-p14-5, the only (short) mention of الأحداث الجانحون | right |
| 12 | 1377 fn-p16-5 | نفسه، ص ٥-١٢ | fn-p16-4 الجواد والسيف المكسور | right |
| 13 | 1577 fn-p21-18 | نتائج التعداد السكاني 2006 م، مرجع سابق | fn-p21-11 «النتائج الأولية للتعداد العام للسكان 2006» | right |
| 14 | 1769 fn-p16-7 | H.Refai, op.cit, p.390 | unresolved | **missed upstream**: fn-p15-20 «Refai, H., Überlegungen zur Baumgöttin, BIFAO 100, 2000» is printed, but the masters parsed no citation in it |
| 15 | 1967 fn-p13-15 | المرجع نفسه، ص152 | fn-p13-14 المطرب | right |

- **Result: 13 right, 0 wrong, 2 missed.** Both misses come from the text v2 was given: a name split by a space,
  and a full citation the masters did not parse. Neither is a resolution error.
- **Round 0's 15 back references are now 15/15.** 0295 → fn-p2-3. 0419 fn-p5-5 → fn-p2-5 by page continuity
  (0.75). 2280 fn-p14-1 → fn-p8-2. 2319 fn-p25-7 and fn-p25-11 → fn-p21-2 by author and year. The other 10 are
  unchanged.
- **La Rosa in 0419.** All 21 «La preuve, op.cit., p. 946–966» go to fn-p2-5 (*Droit international pénal*). All 7
  «… in Commentaire …» go to fn-p3-1. fn-p5-10 «p.208» is ambiguous, so it gets score 0.5 with the ambiguity
  written down.
- **The builder's numbers reproduce exactly.**
  - Mentions by kind: full 3,248, short 1,508, ibid 244, op_cit 403, loc_cit 3, quran 111.
  - Back references: 650, of which 481 resolved, 20 part-of-citation and 149 unresolved, each with a reason.
  - 0 point at a back reference. 2 point at a later reference-list entry. 0 skip an earlier full member of their
    card.
  - 577 of the 1,508 short forms are tied.
  - The method table matches the README row for row.
- **Minor gap: double count.** In 0344, «نفس المرجع السابق» is split into two mentions, an ibid «نفس المرجع» and an
  op_cit «السابق ص …», in fn-p25-3 and fn-p26-1. Each pair counts twice in `v_times_cited`. It is the only case in
  the archive (2 pairs).

### 6. citation_links: PASS, one minor gap

**The owner's rules.**

- There are 138 rows, all targeting an existing publication.
- 0 come from a back-reference mention. Every via-mention is a member of its card.
- 0 are same-article, in any version. 0 work_relations are same-article, and 0 are work→work.
- 0 rows lack score, method, evidence, asserted_by or link_run_id.
- No card has more than one best link. 0 best links are not accepted, and 0 links sit on merged cards.

**Author agreement, rechecked with my own token matcher.** It folds Arabic letters, drops «ال», and ignores common
given names.

- Accepted: 90 agree. The 91st, «لايف عورة البنيوي» against «البنوي، نايف عودة», agrees under the builder's
  one-letter rule, and it is right.
- Candidates: 0 are contradicted once the transliterations are read. My 3 "contradict" are Khidir = خضر, Abdul
  Razzaq = عبدالرزاق and هيتكوت = هيثكوت. The other 18 have no author on one side.
- Rejected: 21, all with contradicting authors.

**Samples.**

- 10 random accepted links (seed 6061) against MARC title, author and year: **10/10 right**.
- 8 random rejected links (seed 6062): **8/8 rightly rejected**. For example, «التأديب في الوظيفة العامة» (عبد الفتاح
  حسن, 1964) is not the 1983 thesis by حمود, and «Financial Markets…» (MohielDin, 1992) is not the 2025 record by
  الزواوي.

**Minor gap.** «الإرهاب الجديد: الشكل الرئيسي للصراع المسلح» by أحمد إبراهيم محمود → W307323 (محمود، أحمد إبراهيم,
2002, same title) is kept as a candidate with "no author to compare". Its evidence shows empty author lists,
although the card does have that author. The authors were probably added to the card after the link was judged. It
is a real link held back, not a false one.

**Note.** Several of the 18 no-author candidates are clearly not the cited work. Examples: «مجلة الرسالة» → an
article about that journal; «دائرة المعارف الإسلامية», «جمهورية أفلاطون» and «كشف الظنون» → a review of it. They
are candidates, and no view counts them (`v_pub_times_cited` = 91 = accepted). That is consistent with the rule.

### 7. Provenance: PASS

| measure | count |
|---|---|
| catalogue assertions without load_id | 0 (none at all without one) |
| gemini-title assertions without actor | 0 of 146 (`model:gemini-front-page`, with the Azure JSON path in `reason`) |
| applied content-patch applications without version | 0 (126 applications in all, no more per-load copies) |
| patches without actor | 0 |
| id_registry or persons rows without created_load | 0 |
| authorships, members, affiliation links or relations without method, asserted_by or evidence | 0 |
| resolved mentions without a method | 0 |
| unresolved back references without a reason | 0 |

### 8. People and institutions: FAIL (narrow)

**Sample.**

- **Persons: 12 of 12 right** (seed 3030, from 494 with more than one name key). A7DJ7674PT, AABVJ1MB75,
  AS081B1FBJ, AV8SNY8K3H, AM6377JMSH, A35EYHV3BZ, A0TC33E45B, AAJEAVNWAX, AFRKEQ956T, ATEQAA1A7S, ABQSVC17AJ and
  AWGCM3JRY6: Arabic and Latin headings and the printed and cited forms of one authority each.
- **Institutions: 8 of 8 right** (seed 41, from 13 with more than one name). They are Salahaddin, Baghdad, Ehya,
  Tikrit, Basra, Cairo's «كلية التجارة» (both affiliations are Cairo), UMT and Alexandria.

**Round 0's systematic failures are fixed.**

| round-0 failure | now |
|---|---|
| زكي نجيب محمود split in two | one person ANH46TF8C2 holding both articles; 1 person by that name |
| بهي الدين حافظ merged with صلاح الدين حافظ | W136062 is a provisional بهي الدين حافظ, method `weak-name-rejected` |
| authorships with a catalogue authority but another person | 0 such persons. The 35 such rows are corporate catalogue-only contributors, which go to institutions |
| life notes in names | 0; 22 persons have a death year (نجيب محفوظ 1427/2006) |
| roles as persons | 0. «رئيس التحرير» is an `editor` authorship with no person; «أسرة التحرير» is a corporate authorship |
| non-ISO country codes | 0 (institutions and affiliations); 146/146 printed countries coded |
| nameless persons | 0 |

**Failures.**

1. **Wrong identity: «عبد الحليم محمود».**
   - Three cited authors printed «عبد الحليم محمود» are given authority **123266**, the person «السيد، عبدالحليم
     محمود» (`match_method = name-key-to-authority`, 0.7). The three works are «أبو مدين الغوث» (1191-000-014,015-011),
     «التفكير الفلسفى فى الاسلام» (1377-008-001,002-002) and «علم النفس العام» (0175-010-037-007).
   - marc.db gives the heading «محمود، عبدالحليم» to authority **438086** (67 records), and to 491220 and 637316 as
     well.
   - The first two works are by the Azhar shaykh, not the psychologist. The README rule ("joins the one authority
     person carrying that folded name when the catalogue gives the heading to no other authority id") is
     therefore broken.
   - **The cause, reproduced.**
     - `common47.name_key('السيد، عبدالحليم محمود')` gives `'عبدالحليممحمود'`, the same key as
       `name_key('عبد الحليم محمود')`. «السيد» is dropped as the title "Mr." even when it is the heading's family
       name.
     - `homonym()` looks only for other holders of the *authority's* own heading, «السيد، عبدالحليم محمود». It
       does not look for holders of the cited name.
     - `key_auth` knows only the authorities already in the db.
   - Of the 57 cited authors matched by name, this is the only case where the cited name is not exactly a name of
     the person and another authority carries it exactly. The other 6 inexact ones are `name-equals-citing-byline`,
     where the byline form is right.
2. **Wrong parent: «جامعة قسنطينة 2».**
   - The university is now its own institution, IXTRD7CFDX (`…+university-number`).
   - But the same affiliation's faculty, IZ52SW23WE «كلية العلوم الاقتصادية», still has parent **I74YWM4TF4
     «جامعة قسنطينة»**. Its department, I24J1QK18D, sits under that faculty.
   - The split was made at the university level only. The faculty and department keys (`fac:org:جامعهقسنطينه/…`)
     still drop the number.

### 9. Idempotency: PASS, one minor gap

I ran four builds on copies, with an empty link cache each time. Each peaked at about 150 MB.

| build | what | result against the served db or B1 |
|---|---|---|
| B1 | clean, the `build47.sh` order, `PYTHONHASHSEED=7` | **identical to the served db** in all 83 compared tables, every column. Only `load_events.args` (the db path) differs, and `reconciliation_v46` is empty because `checks47` was not run |
| B2 | clean, `PYTHONHASHSEED=13`: final → judged → **link** → v2_55 → v33_300 → **link** | identical to B1 in 80 tables once clock and load-event columns (`created`, `load_id`, `built_load`, …) are excluded. Differs only in **5 `subject_terms.term_ar` display labels** (below) and in the event tables (`load_events`, `link_runs`, `link_run_versions`) |
| B3 | the served db + all four loads twice + link | identical to the served db (only new event rows). The loads alone change nothing either |
| B4 | the served db + `v33_300b` + `v33_300b_final` + link (the exam workflow) | see below |

**B4, the exam workflow.**

- The shown version of 0 old documents changes.
- All 580 person ids and 315 institution ids stay live.
- 3 of the 3,080 cited-work ids are retired, and all 3 are recorded in `merged_ids`. The new members joined their
  cards, so 4 old mentions follow them.
- 0 old authorships change their person, 0 old resolutions change, and 0 old affiliation links change. 0 orphans.

**Minor gap.** `subject_terms.term_ar` takes the spelling of whichever record was loaded first. Under B1 and B2 the
labels differ for «الاعاقة / الإعاقة العقلية», «علم الإجتماع / الاجتماع», «الاخلاق / الأخلاق المهنية», «الأجنبية /
الاجنبية» and «الاطفال / الأطفال». Ids and keys are equal. The builder's test did not catch it because its two
orders load v33_300's records first in both builds.

- The builder's `pytest test_ids47.py` passes (52 s).

### 10. Ink anchors: PASS

I took 25 random word-precision anchors of shown mentions (seed 2525, from 2,977) and read them from the Azure
JSON, with words numbered from 1.

- `text_azure` equals the Azure words in **25/25**.
- The box is within 15 px of the words' union, at 300 dpi, in **25/25**.
- At least 70% of the printed citation's tokens are in the ink in **25/25**.
- `anchor_key` is unique. 4 shown mentions have no anchor.
- 5,383 of the 5,403 v33_300 mention ids recur in final.
- The README's ink link (anchor 6479508497353429 = `0069-000-026-005|p15|w216-217`) and `ink.html` return 200.

### 11. Views and self-citations: PASS

- **Views.** All 15 run: `v_articles` 354, `v_times_cited` 3,080, `v_pub_times_cited` 91 and so on.
- **Self-citations.** All **24** rows of `v_author_self_citations` were read: the byline, the cited author as
  printed, and the work. All 24 are the citing author's own work.
  - They include round 0's 4 and its 8 missed ones: محمد بوبوش, علي الزاملي, سحر الشوربجي, أحمد أبو الوفا, فكتور
    الكك ×2, عبد الرحمن عمر الماحي and أحمد كمال الدين موسى.
  - The rest include Hossein Askari ×3 and the co-authors of W663920.
- **Datasette :8003.** All 17 canned queries return 200 with rows, given a stem or `q` where they take one. :8001,
  :8002 and :8899 were not touched.

### What still has to be fixed

1. **«عبد الحليم محمود» → 123266.** The cited-author `name-key-to-authority` match needs two changes. It should not
   drop «السيد» (or another title-like word) when it is a heading's family name. And it should refuse a match when
   marc.db gives the *cited* folded name to any other authority id, not only when it gives the target's heading to
   one.
2. **«جامعة قسنطينة 2».** Its faculty and department should hang under IXTRD7CFDX, not under «جامعة قسنطينة».

Minor, worth a line in the README:

- the 5 order-dependent `subject_terms` labels (choose by a sort, not by load order);
- the 2 «نفس المرجع السابق» pairs in 0344 counted twice;
- «الإرهاب الجديد» left as a candidate on stale author evidence;
- back references missed because of upstream text: a split name, or a full citation the masters did not parse.

### How to reproduce

The scripts are in the session scratchpad, `rv/`:

| script | what it does |
|---|---|
| `builds.sh` | builds B1–B3 |
| `b4.sh` | the exam load |
| `cmp.py A B <ignored columns>` | compares two dbs table by table on every column, and names the column that explains each difference |
| `c1_schema.py`, `c2_orph.py`, `c3_counts.py`, `c4.py` / `c4b.py`, `c5.py <seed>`, `c6.py` | checks 1–6 |

Checks 7–11 are SQL in this section's numbers.

---

## Re-verify round 2 (2026-10-20)

Checked by a verifier who built nothing, against the rebuilt `/home/yassine/data/platform_v2/platform_v2.db`
(build of `95012e2`, sha256 `0e6d57da1003…`, unchanged by this check). Every source was opened read-only. Every build
ran on copies in the session scratchpad (`…/scratchpad/rv2/`), with `link47 --work` pointed there. No paid call was
made. `platform.db`, `marc.db`, the served db and the derived `marc_heading_keys47_*.sqlite` have the same sha256
after the check as before. Datasette was not restarted, because the served db was not rebuilt.

### Verdict

**Pass, with minor gaps.** All eleven checks pass. Both round-1 failures are fixed at their root:

- «عبد الحليم محمود» no longer goes to 123266, and an independent scan of marc.db finds 0 clashes in the 33
  name-to-authority matches.
- Constantine 2's faculty and department hang under IXTRD7CFDX, and 0 faculty or department in the archive has
  another university as parent.

Two clean builds under new seeds and a new step order are identical to each other except for **2 publisher country
codes**, a new instance of the order-dependence class that round 1 found in subject labels. The 2449 hint fix
changed more back references than the README says: 28 notes in 8 articles. Nearly all of these changes are
corrections, but 2 became unresolved although their work is cited earlier.

| # | check | result |
|---|---|---|
| 1 | Schema against `schema47.sql` | **PASS** |
| 2 | Orphans, declared and undeclared | **PASS** |
| 3 | Counts against `platform.db` on the 354 documents | **PASS** |
| 4 | 5 random articles (seed 20261) + 3 citation-heavy ones (seed 20262) against JATS and MARC | **PASS** |
| 5 | 15 new random back references (seed 4471), plus every change since round 1 | **PASS: 13 right, 0 wrong, 2 missed (upstream)**; gap below |
| 6 | `citation_links`: rules, author agreement, samples (seeds 7171/7172) | **PASS** |
| 7 | Provenance | **PASS** (all 0) |
| 8 | People and institutions: sample (seeds 4040/51) + systematic checks | **PASS** (round-1 failures fixed) |
| 9 | Idempotency: 2 clean builds, reload ×2 + relink, exam load, all on copies | **PASS, one minor gap** (2 publisher countries depend on load order) |
| 10 | 25 random ink anchors (seed 8383), plus all 2,951 word anchors | **PASS 25/25 text and box**; gap below |
| 11 | Views, self-citations, Datasette :8003 | **PASS** |

### 1–3. Schema, orphans, counts: PASS

I re-ran round 1's scripts on the served db.

- **Schema.** There are 87 design tables plus the declared `reconciliation_v46`, and all 15 views. Columns and FKs
  are identical, with 169 FK pairs. `foreign_key_check` returns 0 and `integrity_check` returns ok. The only index
  difference is the declared one.
- **Orphans.** All 19 undeclared intra-version references have 0 orphans.
  - `line_map.region_id` pointing at nothing: 0.
  - Mention containers: 0 orphans.
  - Cross-version resolutions: 0.
  - `merged_ids` is empty, as expected after a clean build.
- **Counts.**
  - Shown run differs in 0 of 354.
  - blocks, notes, fixes, misprints, abstracts (printed 241, catalogue 138) and article_runs: 0 / 0 rows both ways.
  - Figures: 1,910 = 1,910. Note calls: 4,024 = 4,024. Bylines: 413 = 413. Affiliations: 247 = 247.
  - Journals and issues: 261 / 353, with 0 unused.
  - Parsed mentions: 4,789 = v1 `works`. Keywords: 1,179 → 1,173 distinct, as in round 1.

### 4. Articles against JATS and MARC: PASS

The samples were:

- seed 20261: `0955-000-025-001`, `2051-000-002-017`, `0619-001-004-010`, `0295-020-002-007`, `0290-000-005-003`;
- seed 20262, articles with at least 20 mentions: `1580-005-010-029`, `2228-014-051-037`, `0527-046-003-024`.

The results, field by field:

- **Authors and affiliations.** 8/8 equal, with titles stripped.
- **Keywords.** Equal.
- **Notes.** Count and text equal, with 0 mismatches over 188 notes.
- **Element-citations against parsed mentions.** 0, 13, 5, 50, 71, 18, 22 and 25: equal in all 8.
- **Abstracts.** Stored per paragraph. Once the JATS heading («الملخص», «Abstract») is dropped, the paragraphs
  concatenate to the JATS abstract.
- **Authorships against marc.db.** All 9 have the right c999, catalogue seq and authority id. This includes the
  merged «زكي نجيب محمود» (ANH46TF8C2, 311655) and the supervisor of 0527 (catalogue-only, 402814).

### 5. Back references: PASS, one gap

**Fresh sample, seed 4471.** I read each note with the notes before it.

| # | article, note | printed | v2 → | verdict |
|---|---|---|---|---|
| 1 | 0368-003 fn-p13-18 | Barrington Moore, Jr. op. cit. | fn-p13-6 Moore, *Political Power and Social Theory* | right |
| 2 | 0368-003 fn-p13-21 | المصدر ذاته (after two ibid and the Moore op. cit.) | fn-p13-6 | right |
| 3 | 0368-003 fn-p14-6 | شرابي، المصدر السابق ص ٢١٥ | fn-p14-4, the Arabic book, p. 215 | right |
| 4 | 0419 fn-p10-1 | La Rosa « La preuve », op.cit., p.959 | fn-p2-5 (*Droit international pénal*), by page continuity | right |
| 5 | 0419 fn-p10-9 | … in Commentaire …, op.cit., p. 1594 | fn-p3-1 | right |
| 6 | 0590 fn-p10-21 | الماوردي: نفس المرجع ص٢٤٢ | r14 الأحكام السلطانية | right |
| 7 | 0877 fn-p3-6 | نقض ١٢ يونيو ١٩٣٩ - المرجع السابق | unresolved | **missed upstream**: the work, «مجموعة القواعد القانونية…» in fn-p3-1, is printed, but these v2_55 masters have 0 element-citations |
| 8 | 1110 fn-p21-21 | الدالي … الخطاطة، المرجع السابق | r18 الدالي (the reference list precedes the endnotes) | right |
| 9 | 1421 fn-p11-14 | وزارة الإعلام والثقافة: المصدر السابق | fn-p11-1 | right |
| 10 | 1769 fn-p15-7 | ليز مانكة، المرجع السابق | unresolved | **missed upstream**: fn-p15-5 «ليز مانكة، التداوي بالأعشاب…» is printed, but the masters parsed no citation in it (same class as round 1's Refai) |
| 11 | 1967 fn-p14-4 | المصدر نفسه، ج2، ص254 (after the short form «العمدة، ج2، ص255») | fn-p13-11 ابن رشيق، العمدة | right |
| 12 | 2449 fn-p26-31 | روبرت سارجنت. (المرجع السابق) | fn-p25-5 سارجنت، شعر ونثر من حضرموت | right (was wrong in round 1's db: fn-p26-19) |
| 13 | 6643 fn-p12-3 | نفسه: 160/10 | fn-p11-8 المعسول | right |
| 14 | 6643 fn-p12-17 | نفسه: 428 | fn-p12-8 شعر داود الرسموكي | right |
| 15 | 7606 fn-p2-1 | … Loïc PASCO, L'évolution des cérémonies…, op.cit. | fn-p1-1 PASCO | right |

**Every change since round 1.** I diffed every back reference of the shown versions against
`platform_v2.db.bak-20261020-fix1`.

- **Spans.** The printed span of 175 back-reference mentions changed. It now starts at the note number or the
  author («12. السابق 1/34», «Barrington Moore, Jr. op. cit.»). Op. cit. mentions went from 403 to 401 (0344).
- **Targets: 28 notes in 8 articles.** The builder reports "14 back references in 3 articles". Mention by mention:
  - **2449: 11 notes, now right.** The ناجي, سارجنت and العمري ones go to their own works. The السقاف ones go to r1
    or fn-p26-14 (two forms of one 1974 article; 0.5 where both are earlier).
  - **0344: 3 notes.** fn-p25-3 and fn-p26-1 each hold one ibid now. fn-p22-3 «Annuaire CDI. op. cit.» → fn-p18-1
    «Annuaire CDI».
  - **Wrong before, right now (11).**
    - 0368 fn-p13-18…23 (6): previously sent to Arendt's *Between Past and Future*.
    - 0461 fn-p6-12: the OECD *Performance Measurement*.
    - 6508 fn-p10-2: *Jeux et activités ludiques*.
    - 7606 fn-p5-1, fn-p6-3 and fn-p6-4: PASCO, Reydellet and Köhler.
  - **Wrong before, wrong now (1).** 0310 fn-p12-2 «CHEN, Chen. «Le roman policier de Fred Vargas…». Op.Cit.»
    goes to fn-p9-1, Vargas's novel *L'Homme à l'envers*, at 0.7 ("the author's only earlier work").
    - The name in the title was taken for the author.
    - The thesis is cited nowhere earlier, so this should be unresolved. Before, it went to fn-p12-1.
  - **Wrong before, missed now (2), both in 0702.**
    - fn-p10-17 «أحمد إبراهيم محمود. المصدر السابق، ص٤٦» is unresolved, although fn-p9-8 is his full citation of
      «الإرهاب الجديد» (p. 45 → 46). It is the same all-common-given-names blind spot that fix 5 cured in
      `link47.judge_link` but not in the back-reference resolver.
    - fn-p10-21 «أدونيس العكرة. المصدر السابق» is unresolved, although fn-p9-4 is his «الإرهاب السياسي». That full
      citation is typed `short`.
- **Archive-wide.** Of the 97 unresolved back references with an author hint, 9 have an earlier full or short mention
  whose printed text contains that hint (7 in round 1's db). These 9 are the two 0702 notes plus pre-existing ones,
  such as 0590 «الدكتور عبد الحكيم حسن» (r15).
- **Gap: minor.** The fix is a clear net gain: 11 + 11 corrected, 2 now missed instead of wrong. The README
  undercounts its reach, though. The resolver's author match still fails on all-common names and on full citations
  typed `short`.

### 6. citation_links: PASS

- **Rows.** There are 138: 92 accepted, 25 candidates and 21 rejected.
- **The owner's rules.** All hold at 0: rows from a back reference, via-mentions outside their card, same-article
  links or relations, work→work relations, links to a non-publication, rows missing provenance, best links not
  accepted, and links on merged cards. There is at most 1 best link per card.
- **My token matcher against the catalogue authors.**
  - Accepted: 91 agree. The 92nd is round 1's «لايف عورة البنيوي» = «البنوي، نايف عودة», which is right.
  - Candidates: 4 agree and 18 have no author to compare. The 3 "contradict" are round 1's transliterations
    (Khidir = خضر, Abdul Razzaq = عبدالرزاق, هيتكوت = هيثكوت).
  - Rejected: 21, all contradicting.
- **«الإرهاب الجديد»** → W307323 is accepted and best, with `whole_name` evidence. It is the **only** link that
  agrees on the whole name alone, with no shared tokens.
  - The `checks47.json` measure "best links agreeing on the whole name only = 50" is mislabelled. It counts every
    evidence that carries a `whole_name` key.
- **10 random accepted links (seed 7171) against MARC title, author and year: 10/10 right.**
  - The differences are OCR or edition only: «العبلي» for the catalogue's «عبدالله، عبدالحكيم حسن», 1974; «ليلى /
    نيلي المسعودي»; 1994 against 1995.
- **8 random rejected links (seed 7172): 8/8 rightly rejected.** Examples: «البداية والنهاية» by ابن كثير → a 1994
  record by ونوس; Lewis's *Unlimited Supplies of Labor* → *…of Capital* (1967).

### 7. Provenance: PASS

Every round-1 measure is 0:

- catalogue assertions without load_id;
- gemini-title assertions without an actor (0 of 146);
- applied content patches without a version (126 applications in all);
- patches without an actor;
- id_registry or persons rows without created_load;
- authorships, members, affiliation links or relations without method, asserted_by or evidence;
- resolved mentions without a method;
- unresolved back references without a reason.

### 8. People and institutions: PASS

**The round-1 failures.**

- **«عبد الحليم محمود».** The three cited «عبد الحليم محمود» now have no authority. The four printed forms in v2
  are:
  - «علم النفس الاجتماعى والإعلام» (1979), printed «عبد الحليم محمود السيد» → 123266, the psychologist. This is
    right: his heading turned round is exactly that name.
  - «علم النفس العام», «أبو مدين الغوث» and «التفكير الفلسفى فى الاسلام»: unmatched. This is a miss, not a wrong
    identity.
- **Independent homonym scan.** I did not use the builder's index. I read every heading in marc.db (Arabic and
  Latin), turned it round, dropped the life note and folded it with my own rules. Of the **33** `name-key-to-authority`
  cited-author matches, **0** carry a name that another authority id also carries, and all 33 equal their own
  authority's heading. There are 0 name-only authorship matches.
- **Constantine 2.** IXTRD7CFDX «جامعة قسنطينة 2» → INEH6E8Q4G faculty → I586QN4MX5 department (one affiliation).
  Across the archive, 0 faculties have a parent other than their affiliation's university, and 0
  departments a parent other than their faculty (or their university when there is no faculty). 0 institutions are
  pointed at by nothing.

**Samples.**

- **Persons: 12/12 right** (seed 4040, from 494 with more than one name key): A2EHVHCH29, ABBX1EX6BV, AMVBK9V75R,
  AR7K9RGSC3, AW82QKA96E, AJ1F75BWEJ, AJ2ES029G3, AMZW0BTWXT, ASQD5XTSJN, AMJQSTMJVH, ABWJSZFRFA and ATZ8M3GZAE. In
  each, the Arabic and Latin headings and the printed forms belong to one authority.
- **Institutions: 8/8 right** (seed 51; only 8 have more than one name). They are Salahaddin, Babylon, UMT, Cairo
  (with «Cairo Unverssity»), Ehya, Tikrit, Baghdad and Constantine 2.

**Systematic checks.**

- 0 authorities on two persons, 0 nameless persons, 0 life notes in names, 0 roles as persons.
- 0 non-ISO country codes in institutions or affiliations.

**Small notes, not failures.**

- Both «جامعة قسنطينة» institutions have no country code (DZ).
- The department «التجارية وعلوم التسيير» is the tail of the faculty name «كلية العلوم الاقتصادية، التجارية وعلوم
  التسيير», split at its comma by inst46's parse.

### 9. Idempotency: PASS, one minor gap

Four builds ran on copies, in parallel, in 3:26 with a peak of 156 MB each. Each started from an empty link cache
in its own work folder.

| build | what | result |
|---|---|---|
| A | clean, the `build47.sh` order, `PYTHONHASHSEED=31` | **identical to the served db in 79 tables, every column**. `citation_links` and `metadata_assertions` differ only in `created`; the event tables and `reconciliation_v46` differ because `checks47` was not run |
| B | clean, `PYTHONHASHSEED=57`, a new order: v2_55 → **link** → final → v33_300 → **link** → judged → **link** | identical to A in 80 tables once the load and clock columns are excluded. **Differs in 2 `publishers.country_code`** (below) and in the event tables |
| C | the served db + all four loads twice + link | identical to the served db in all 81 compared tables once the load and clock columns are excluded. The loads alone change only `load_id`s and event rows |
| D | the served db + `v33_300b` + `v33_300b_final` + link (the exam workflow) | see below |

**D, the exam workflow.**

- Documents go from 354 to 654, and the shown version of 0 old documents changes.
- All 580 old person ids are still present with the same status, and all 315 old institution ids are still present.
- 3 old cited-work ids are retired, and all 3 are in `merged_ids`.
- 0 old authorships change or vanish. 0 old resolutions change, and 0 old affiliation links change. FK check: 0.
- **One old link changes, rightly.** «كشف الظنون» (C098G0W6PP) gains two exam members that name حاجي خليفة, so its
  candidate → W232413 becomes `rejected (authors contradict)`.

**Minor gap: publisher country by load order.**

- `biblio47` keys a publisher on its name alone (`P` + sha1 of the name key). The publisher is inserted with
  `INSERT OR IGNORE`, so its country is that of whichever journal loads first.
- Two names belong to different bodies in different countries:
  - «المجلس الإسلامي الأعلى»: TN under A, DZ under B;
  - «مجمع اللغة العربية»: SY under A, EG under B.
- So each is also two publishers merged into one.
- The builder's `test_ids47.py --full` did not catch it because its three orders load these journals in the same
  order. Its quick test, `pytest test_ids47.py`, passes (57 s).

### 10. Ink anchors: PASS, one gap

**Sample of 25** (seed 8383, from 2,951 word anchors of shown mentions). I read the words straight from the Azure
JSON, numbered from 1 per page.

- `text_azure` equals the Azure words in **25/25**.
- The box is within 15 px of the words' union in **25/25**.
- At least 70% of the printed citation's tokens are in the ink in **24/25**. The exception is 0909 fn-p16-9: the
  anchor `w208-214` «(الأصل الألماني: 1987 بعنوان: Theologie in Aufbruch» starts 4 words early and stops before
  «، منشورات Piper Verlag).» (w215–219).

**All 2,951 word anchors.**

- Text and box are right in **2,951/2,951**.
- The token cover is ≥ 70% in **2,860 (96.9%)** and < 50% in 20. Round 1's db gives 2,881/2,977 and 24, so this is
  not a regression, only a gap the 25-sample hid.
- The < 50% cases include:
  - four 0870 «المرجع السابق» anchors placed on neighbouring words;
  - 0694 «7. Ibid, p.4» on the single word «to»;
  - long citations cut at a line end (1453, 2319);
  - Azure misreadings («الفكت» for «النكت»).
- `anchor_key` is unique. 4 shown mentions have no anchor.

**Documentation gap.** The README's demo link `ink.html?a=6479508497353429` returns 200, but that anchor no longer
exists.

- The back-reference span now includes the note number, and the «السابق نفسه» of 0069 fn-p15-13 is now anchor
  4584737663546638, `0069-000-026-005|p15|w215-217`.
- The page will show nothing for the old id.

### 11. Views, self-citations, Datasette: PASS

- **Views.** All 15 views run: `v_articles` 354, `v_times_cited` 3,080, `v_pub_times_cited` 92 and so on.
- **Self-citations.** `v_author_self_citations` has the same 24 rows as round 1's db, which round 1 read one by one.
  Listing them again with the byline and cited forms shows every one is the citing author's own work.
- **Datasette :8003.** It runs on the 11:11 db.
  - All 17 canned queries return 200.
  - `ink.html` and `schema47.html` return 200.
  - :8001, :8002 and :8899 were not touched.

### What is left (minor; none blocks)

1. **Back-reference resolver.**
   - It does not use an earlier full citation whose author is all common given names (0702 fn-p10-17), or one typed
     `short` (0702 fn-p10-21).
   - It takes a name inside a quoted title for the author (0310 fn-p12-2 → Vargas's novel).
   - The README should say that the hint fix moved 28 notes in 8 articles, not 14 in 3.
2. **Publishers keyed on name alone.** Two homonymous publishers in different countries are merged, and their country
   depends on load order (`publishers.country_code`, 2 rows).
3. **Ink.**
   - 91 of 2,951 word anchors (3.1%) cover less than 70% of their printed citation.
   - The README's demo anchor id is stale.
4. **checks47's "best links agreeing on the whole name only = 50"** counts the evidence key, not the case. The true
   number is 1.
5. **Upstream text.** 0877 (v2_55 masters with no parsed citations) and 1769 fn-p15-5 (a full citation not parsed).

**Not from this check:** `experiments/43_rehearsal/out/fix3/count_paren.py` appeared at 11:22, during this check. It
was written by another session. Experiment 47's code does not write there, and nothing tracked in 43 or 46 changed.

### How to reproduce

The scripts are in the session scratchpad, `rv2/`:

| script | what it does |
|---|---|
| `builds.sh` | builds A–D |
| `cmp.py A B <ignored columns>` | compares two dbs table by table, as in round 1 |
| `c1_schema.py`, `c2_orph.py`, `c3_counts.py` | checks 1–3 |
| `c4.py`, `c4b.py`, `c4abs.py` | check 4 |
| `c5.py 4471` | the back-reference sample |
| `c5chg.py` / `c5diff.py` | back-reference targets and spans against the fix1 backup |
| `c5miss.py` | unresolved back references whose author is printed earlier |
| `c6.py`, `c6s.py` | check 6 |
| `c8a.py` | the independent marc.db homonym scan |
| `c10.py`, `c10all.py` | ink: the sample and all anchors |

## After re-verify round 2: what the builder changed (2026-10-21)

Not a verification; a pointer for the next verifier. The round-2 gaps were fixed by the builder and are described in
the README's "Follow-up to re-verify round 2": publishers keyed on name + country (5 names now two bodies each,
`test_ids47.py --full` identical in 81 tables), `ink.html` links by note or anchor key, the whole-name-only measure
(1, not 50), and 4 back references (0310 fn-p12-2 now unresolved; 0702 fn-p10-17 → fn-p9-8, fn-p10-21 → fn-p9-4;
0590 fn-p10-16 → r15). Not yet checked by anyone independent.

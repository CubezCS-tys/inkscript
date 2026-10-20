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

# Audit: the bibliographic layer of platform.db (articles, journals, issues, catalogue, ids, runs)

2026-10-20. Read-only audit of `/home/yassine/data/platform/platform.db` (built by experiments/46_platform_db) and
`/home/yassine/data/marc/marc.db`. No paid calls. Every number below was measured with sqlite3 on those files today
(the queries are in the appendix). Scope: articles, journals, issues, publishers, catalogue records and ids (stem, rec,
999$c, 001, DOI, ISSN), titles / translated titles / printed forms (D33), dates, pages, languages, abstracts,
keywords and subjects, runs and article versions (`article_runs`), and how the current version is chosen.
Citations, people and institutions are other auditors' areas; they appear here only where they touch these tables.

## In one paragraph

The 46 schema works for 354 articles, but it treats four different things as one: **the scanned file (stem)**, **the
catalogue record (999$c)**, **the publication** and **one run's reading of it**. They are not one-to-one. A thesis is
one catalogue record split over about 10 PDFs; 15 stems point at 2–3 different records; 87,396 catalogued articles
have no file, and 13,680 files have no record. Each bibliographic value is stored once, in a fixed column, with no
pointer to the ink it was read from, even though the blocks table already has the box. There are also real defects:
the translated title is empty for all 354 articles, 19 articles have a hijri year stored as their gregorian
`pub_year`, French abstracts are labelled English, and citation targets are keyed on `rec`, which is only the record's
position in the XML export. Our edge over Web of Science is that we hold several readings of every value (the printed
page, Azure, Gemini, the catalogue, a person), each one pointing back at its ink. v2 should store each value as a set
of **assertions**, each with its evidence, and pick one as the display value. It should not keep one column per
reading.

## Problems (with evidence)

### P1 (high). File, record, publication and run are one row, keyed by `stem`
- `articles.stem` is the primary key, and `rec`, `c999` and `record_id` are columns on it, which assumes one file is
  one record is one publication.
- In marc.db, `pdf_ids` has 3,196,220 rows. 1,807,389 of them are **thesis part PDFs**, and one record has up to
  ~13 stems. For example, rec 504556 (one thesis) has `9802-001-009-0299-T` (صفحة العنوان), `-A` (المستخلص),
  `-C`, `-F`, `-1`…`-4` (الفصل), `-O` (الخاتمة) and `-R` (المصادر والمراجع). 168,179 records have an «المصادر والمراجع»
  part, which is a reference list in its own PDF.
- 15 stems point at 2 or 3 *different* records (catalogue errors). For example, `9800-001-001-0015-0` is under both
  «تعارض أحكام الإمام محمد بن حبان…» and «أثر الحوافز التشجيعية…». The loader keeps one, chosen by title similarity
  (`is_primary`), and drops the other without a trace.
- Experiment 44: 87,396 catalogue articles have no file, 301,187 are legacy PDF only (no Azure), and 13,680 main
  documents have no catalogue record. None of these can be a row today, because an `articles` row exists only when a
  run's masters exist.
- Fix: split them into `publications` (the work, W id), `documents` (one file or part, with stem and S3 state),
  `catalogue_records` (keyed by 999$c) and `publication_versions` (one per run). See the proposed tables below.

### P2 (high). The translated title is never loaded
- `articles.title_en` is empty in all 354 rows. 54 masters have a `<trans-title-group>`, and `blocks` holds 59
  `title-en` blocks with boxes.
- Cause: `parse46.py` line 205 looks for `am.find("trans-title-group/trans-title")` under `<article-meta>`, but the
  element sits inside `<title-group>`, so the path should be `title-group/trans-title-group/trans-title`.
- The column name is also wrong. For an English article the translated title is Arabic (`0260-050-081-007`:
  English title, `trans-title-group xml:lang="ar"`). The catalogue-disagreement check on `title_en` therefore never
  runs, and 3 D33 changes to "translated title" have no column to land in.
- Fix: store titles as language-tagged assertions (P6). Fix the XPath in the v2 loader.

### P3 (high). Hijri years stored as gregorian `pub_year`
- 19 articles have `pub_year` between 1397 and 1446. For example, `0418-000-136-002` has 1446 where the catalogue
  has 2025, and `0011-005-014-013` has 1404 where the catalogue has 1985 (hijri 1405).
- `article_dates` has 22 articles with **two** `pub` rows, one gregorian and one hijri (`0260-000-008-013`: «آب 1977»
  and 1397), and no column says which calendar each row uses.
- Any year facet, citation window or journal metric would place these 19 in the 15th century.
- Fix: dates get `calendar` (gregorian | hijri), `precision`, `month_printed`, a converted counterpart and evidence.
  `pub_year` becomes a derived gregorian year with its derivation recorded.

### P4 (high). Citation targets keyed on `rec`, which is not an identifier
- marc.db's own comment: `rec INTEGER PRIMARY KEY -- order in the XML (1-based)`. A new catalogue export renumbers
  every record.
- `citation_links.target_rec` holds 478 links (320 records), and `catalogue_records` / `catalogue_authors` key on
  `(stem, rec)`. All of these break on the next export.
- In marc.db, 999$c is unique: 1,558,415 distinct values for 1,558,415 records. 001 is not: 1,541,987 distinct, so
  16,428 duplicate rows. For example, 001 `0075810` is both «الدين والمجتمع والسياسة في عالم متبدل» and a thesis on
  video compression. Some 001s are empty.
- Fix: 999$c is the catalogue key everywhere. `rec` is kept only as `(export_id, rec)` for tracing back to the XML.

### P5 (high). "Current version" is just whichever run loaded last, and other versions keep only a sha
- `article_runs`: 655 rows over 354 stems. v33_300 has 299 rows with 0 current, v33_300_final has 300 with 300
  current, and v2_55 has 55 with 54 current. The rule is in the code (`--current always`: the last run to load a
  changed version wins), not in the data. There is no `current_reason` or `chosen_by`.
- A non-current version keeps only its `sha`, `made` and `loaded`. Its titles, pages and D33 changes are deleted on
  reload (`DELETE … WHERE stem = ?`). For example, v33_300 had 5 metadata changes; the db now holds only the 171 from
  v33_300_final. Their files still exist, but the database cannot compare versions or show the correction history
  across runs.
- `runs.n_articles` is "articles this run currently holds", not "articles in the run". It reads 299 for v33_300, which
  is stale: v33_300 holds 0 now. `v33_300_judged` reads 1, but its folder holds 77 masters.
- The stamp's `run` field says `v33_300` for the v33_300_final masters (`*.stamp.json`), so files and db disagree
  about which run made them.
- `sha` covers JATS + metachanges + patches sidecars, but not ALTO or the PDF. A changed ALTO (boxes) is not seen as
  a new version.
- v2_55 articles are **partial**: 24 of 54 have ≤ 5 scanned pages, and 12 have a page range longer than the scan
  (`0041-002-005-008`: pages 213–249, 5 pages scanned). Nothing marks them incomplete. They will show as complete
  articles beside the full ones.
- Fix: a `publication_versions` table holding all per-run values, including coverage (`pages_covered`, `complete`);
  an explicit current-choice rule stored per row (`current_reason`: rule name, or `person`); and `runs` with stable
  counts and every stamp hash.

### P6 (medium). One column per reading, no pointer to the ink
- `articles` has `title` (corrected), `title_printed`, `title_metadata` and `title_en`. `catalogue_records` has
  `title`, `subtitle` and `title_en`. Gemini's 174,138 `.gemini.title.json` files (title + authors) are not in the db.
- `title_printed` is NULL in 25 articles. `title_metadata` is set in 63. Only 2 have title ≠ title_printed
  (`0728-040-010-005` «ودورة» → «ودوره», `1058-005-993-021`).
- Pages: `fpage`/`lpage` hold the corrected value. The printed value exists only in `metadata_changes.printed`
  (171 rows: lpage 132, fpage 37, plus title 2 and translated title 3), as free text with `change_source` like
  "catalogue (its range spans the scan's pages)".
- No bibliographic value says where on the page it was read, although `blocks` already has the title (327 of 354
  stems), title-en (59), abstract (261), keywords (96) and front-matter (280) blocks, each with ALTO line ids and a
  box. Nothing joins `articles.title` to its `block_id`.
- `catalogue_disagreements` (393 rows) is a precomputed snapshot. It is not recomputed when a person patch changes a
  value.
- Fix: a `metadata_assertions` table (below). `articles` becomes a view of the chosen assertions, D33 changes become
  assertions with a reason, and disagreements become a view.

### P7 (medium). Journals: overwritten by the last article loaded, ISSNs not validated
- `journals` is one row per journal code, and `title_catalogue`, `issn`, `publisher` and `country` are overwritten by
  whichever article loaded last (`load_article`: `UPDATE journals SET …`).
- `title_masters` is likewise last-wins. Journal titles change over time. In marc.db, code 0663 is
  «دراسات إقتصادية إسلامية» (1993–2014) and «دراسات اقتصادية إسلامية» (2009–2020), and 24 codes carry more than one
  title.
- `issn`: 114 of 261 journals have an empty string, stored as `''`, not NULL, so `count(issn)` says 261.
- Across the catalogue there are 1,779 distinct ISSN strings:
  - **63 fail the check digit** (23,062 records). Code 0820 has both `6018-1110` and `1110-6018`; 0882 has
    `1319-8000` and `1319-0008`.
  - **42 are malformed** (13,211 records): `0851-025`, `1112-1511X`, `0581 - 6073`, `001858-6104`.
  - 29 codes have more than one ISSN, mostly truncations (`2356-9`) or case differences (`1994-473x`).
- There is no print/online distinction and no ISSN-L. `publisher` is a free-text column, not an entity (example:
  «وزارة الاوقاف والشؤون الاسلامية»).
- Fix: `journals` (J id, code), `journal_titles` (with years and form), `journal_issns` (raw, normalised,
  check-digit result, kind, ISSN-L), `publishers` + `journal_publishers`. Invalid ISSNs go to the catalogue report.

### P8 (medium). Issues: mixed printed and normalised values, and joint/special issues are strings
- `issues` is rebuilt as `max(coalesce(a.volume, cr.volume))` and `max(coalesce(a.issue, cr.issue))`, so one column
  mixes the masters' printed form with the catalogue's padded code. Examples:
  - `0418-000-136`: issue «١٣٦»;
  - `0408-002-010`: volume «002», issue «010»;
  - `0200-000-140`: volume «000».
- `articles.volume` is NULL in 258 of 354 rows and `articles.issue` in 183. Where set, it is printed text:
  `special`, «الأول+الثاني», «رمضان وشوال», «مارس ٢٠٠٣».
- Joint issues are `003,004` strings: 42 of 354 stems carry a comma, and 4.9% of the bucket does. «عدد خاص» is coded
  `999`.
- `issues.year` takes `max(catalogue, masters)`. `year_hijri` is `''` in 223 of 353.
- At scale the catalogue has 96,007 (journal, volume, issue) combinations, and we cannot say how many articles of an
  issue are scanned, read, or missing.
- Fix: `issues` with `volume_raw` / `issue_raw` (printed), `volume_num`, `is_special`, `issue_numbers` (rows for joint
  issues), both calendars, and coverage counts from catalogue, bucket and runs.

### P9 (medium). Language codes and abstract languages
- `catalogue_records.language` is ISO 639-2 (`ara`, `fre`, `eng`), while `articles.language` is 639-1 (`ar`, `fr`,
  `en`). The disagreement check therefore compares different code sets; it found 2 real ones (`0484-049-291-001`:
  catalogue ara, masters fr).
- Catalogue abstracts get their language from the script (`"ar" if Arabic letters else "en"`). At least 7 of 63
  "en" catalogue abstracts are French. For example, `0310-000-089-011`: «Si vous voulez vivre paisiblement…».
- 041 can hold several languages (marc.db joins them with ','), but `articles.language` holds one.
- Fix: a languages lookup (639-1 ↔ 639-2 ↔ name ar/en), `publication_languages` (role: text | abstract | title),
  and language detection with the method recorded.

### P10 (medium). Keywords and subjects keyed by stem, duplicated, ar/en pairs not linked
- `keywords`: 1,179 rows. The catalogue rows use `seq` 1000+ to avoid colliding with the masters' rows. 371
  (stem, term) pairs appear from both sources as separate rows, so a "keyword count" counts them twice.
- No term entity. «مصر» is a term_key in 4 articles, with nothing to group them beyond the string.
- `subjects`: 773$4 (Arabic field of study, 467 rows) and 773$6 (English, 465 rows) are the same facet in two
  languages, stored as unrelated rows. `catalogue_records.fields_of_study` holds the same values again, pipe-joined
  («الادب | العلوم الإنسانية ، متعددة التخصصات»).
- Subjects are keyed by stem, but they belong to the catalogue record (999$c). A thesis's 10 parts would each copy
  them.
- Fix: `subject_terms` (scheme, ar, en, one row per pair) + `record_subjects` (by c999); `keyword_terms` +
  `publication_keywords` with form (printed | catalogue | person), evidence block and source.

### P11 (medium). DOIs: one printed column, Mandumah-minted and publisher DOIs not told apart
- `articles.doi` is set in 4 rows (printed). `catalogue_records.doi` is set in 41. Neither is resolved into one
  column.
- In marc.db, 296,884 records have a DOI, and 185,769 of them end in the stem pattern. These are Mandumah's own DOIs
  (`10.34120/0382-016-063-013`, `10.35270/0011-005-014-013`, joint issue as `10.71219/0135-025-001.002-002`). The
  others are publisher DOIs (`10.21608/JAAUTH.2017.48128`, `10.33899/edusj.2020.165298`). Both can be correct for one
  article, and they mean different things.
- Fix: `external_ids` (scheme doi | c999 | 001 | qdrant_doc | s3 | issn…, value, `assigned_by` mandumah | publisher,
  source, evidence).

### P12 (low). Denormalised copies and paths on `articles`
- `articles` repeats the run's `prompt`, `prompt_hash`, `rules_hash` and `model`, and it carries 15 counters
  (`n_blocks` … `flags_low`) that go stale when a patch changes content.
- `jats_path`, `alto_path` and `pdf_path` are absolute paths to the laptop's repo
  (`/home/yassine/inkscript/experiments/43_rehearsal/out/v2_55/masters/…`), so the db is not portable to the server
  or S3.
- `patches_applied` is free text («j-2048-p1-1 split_block (judge)»), not a link to `patches`.
- There is no cost per article. Usage sits in `out/<run>/raw/<stem>_cNNN.json` and `gemini_spend.jsonl`
  (v33_300: $28.46 over 3,508 pages), but nothing in the db. The stamp holds more hashes (rules43, masters43,
  evidence43, judge prompt) than `runs` stores.
- Fix: these move to `publication_versions` and `runs`. Paths become a root + relative path. Counters become views.

### P13 (low). Naming: `works` already means "cited work"
- The brief proposes W ids for publications (OpenAlex works), but platform.db's `works` table holds parsed
  *citations* (4,775 rows, ids like `<stem>|note:<fn>|<n>`). In v2, archive items should be `publications` (W id) and
  the cited side `cited_works` / `citations` (the citations auditor's area), so "work" is never ambiguous.

## What makes our bibliographic layer different from Web of Science's

These are features the proposed tables enable. None of the systems in the brief has them.

1. **Every metadata value shows its ink.** Each title, page number, date or keyword assertion can carry
   `block_id → ALTO lines → box on the page image`. "Why is the year 1977?" opens the crop of «آب 1977» on page 1,
   beside the catalogue's value and the D33 reason. This is already possible for 327 titles, 59 translated titles,
   261 abstract blocks and 96 keyword blocks.
2. **Several readings side by side, with a chosen one.** For each field we can show printed (masters), catalogue
   (MARC), Gemini title file (174k documents), Azure line (OCR confidences), corrected (D33 rule) and person (patch).
   Choosing is a rule (person > judge > rule > printed > catalogue > gemini), not an overwrite. A value can therefore
   carry a **trust score**: the number of independent readings that agree, plus the flags and judge findings on its
   block.
3. **A catalogue-error report for Mandumah**, as data. In marc.db today: 105 bad ISSNs (36,273 records),
   15 stems under 2–3 records, 16,428 duplicate 001s, 13,680 files with no record, and 87,396 records with no file.
   On our pages: 142 page ranges, 11 years and 5 titles (393 disagreement rows). Each entry has evidence (our crop or
   the MARC field) and a status (reported → fixed in export N), so the next catalogue export can be checked against
   the report.
4. **Coverage per issue and per journal**: catalogued, in the bucket (Azure), legacy PDF only, read by a run,
   complete or partial. Neither WoS nor OpenAlex can show which articles of an issue exist on paper but not in their
   index. We can, because the stem encodes journal-volume-issue-sequence and the catalogue lists every article.
5. **Both calendars as first-class dates.** We keep the printed «جمادي الأولى / أكتوبر 1964» and «ربيع الثاني 1407»,
   each tagged with its calendar, plus the converted pair. Search and facets work by either calendar.
6. **Theses as structured publications**: title page, abstract, contents, chapters, conclusion and «المصادر والمراجع»
   as typed parts (`documents.part_label`) of one W. The reference-list part is a ready citation source for 168,179
   theses. The scanned parts are not in the bucket today (experiment 44), but the catalogue knows them.
7. **Semantic search tied to the record.** Qdrant `mandumah_v2` points carry `doc_id` (the stem). `documents.stem`
   joins them to W, J and the catalogue. The vectors stay in Qdrant; only the join key and the collection name live
   in the db.

## Proposed tables

Types are SQLite. "→" is a foreign key. Every table read from a run has `run → runs`, and every asserted value has
`source` (masters | catalogue | gemini-title | azure | judge | person | rule:<name> | link47) plus `created`.

| table | role (plain words) | columns | replaces |
|---|---|---|---|
| `publications` | One row per scholarly item (article, thesis, review, editorial…), whether we have its scan or only its catalogue entry. | `pub_id TEXT PK` ('W'+999$c, or 'WS'+stem if uncatalogued), `c999 TEXT → catalogue_records` NULL-able, `journal_id → journals`, `issue_id → issues`, `seq_in_issue INT`, `type TEXT` (from 336, normalised: article, thesis, conference, book-review, thesis-review, editorial, literary-text, bibliography, legislation, fatwa, other), `type_catalogue TEXT`, `current_version → publication_versions`, `status` (catalogued-only, scanned, read, read-partial) | `articles` (the identity part) |
| `documents` | One row per file in the archive: an article PDF, or one part of a thesis; tells where it is and what we have for it. | `stem TEXT PK`, `pub_id → publications`, `part_label TEXT` (NULL, or صفحة العنوان, المستخلص, 1 الفصل, المصادر والمراجع…), `part_kind` (title-page, abstract, contents, chapter, conclusion, references, first-pages), `part_seq INT`, `in_main_bucket INT`, `has_azure_json INT`, `has_html INT`, `has_gemini_title INT`, `legacy_only INT`, `scan_pages INT`, `pdf_sha TEXT`, `qdrant_doc_id TEXT` | `articles.stem`, `articles.pdf_path`, `pdf_ids` use |
| `catalogue_exports` | Each MARC file we built marc.db from, so a record can be traced to the export it came from. | `export_id TEXT PK`, `file`, `sha256`, `records INT`, `built`, `latest_995d` | `marc.db meta` (copied) |
| `catalogue_records` | Mandumah's catalogue entry for a publication or a cited item, keyed by the stable 999$c. | `c999 TEXT PK`, `export_id → catalogue_exports`, `rec INT` (position in that export only), `record_id_001 TEXT` (not unique), `title`, `subtitle`, `title_en`, `parallel_titles`, `language_raw`, `year_raw`, `year_int`, `year_hijri`, `month`, `pages_raw`, `page_first`, `page_last`, `type`, `journal_code`, `journal_raw`, `issn_raw`, `volume_raw`, `issue_raw`, `issue_printed`, `article_seq`, `doi`, `databases`, `added`, `thesis_json`, `n_pdfs`, `in_platform INT` | `catalogue_records` (stem, rec); `citation_links.target_rec` |
| `catalogue_record_documents` | Which files the catalogue says belong to a record (a thesis has ~10). | `c999 → catalogue_records`, `stem → documents`, `seq INT`, `label TEXT`, PK `(c999, stem)` | marc.db `pdf_ids` (for loaded items) |
| `publication_versions` | One row per reading of a publication by a run: what that run produced, at what cost, how complete it is, and whether it is the one shown. | `pub_id → publications`, `run → runs`, `stem → documents`, PK `(pub_id, run)`; `jats_sha`, `alto_sha`, `pdf_sha`, `sidecars_sha`, `made`, `loaded`, `pages_covered TEXT` (e.g. '1-5'), `pages_expected INT`, `complete INT`, `cost_usd REAL`, `tokens_in INT`, `tokens_out INT`, `n_chunks INT`, `retries INT`, `is_current INT`, `current_reason TEXT` (rule name or 'person'), `chosen_by TEXT`, `masters_rel TEXT` (path relative to the run root) | `article_runs`; run columns of `articles` |
| `version_patches` | Which patches were applied to one version (a link, not a string). | `pub_id`, `run`, `patch_run`, `patch_id`, `status`; FK `(pub_id, run) → publication_versions`, `(patch_run, patch_id) → patches` | `articles.patches_applied` |
| `runs` | One processing run: its purpose, what it ran with, what it cost. | `run TEXT PK`, `purpose` (sample, exam, base, judged-copy, final), `base_run → runs`, `root_dir` (relative), `prompt`, `prompt_hash`, `rules_hash`, `rules43_hash`, `masters43_hash`, `evidence43_hash`, `judge_prompt_hash`, `model`, `thinking`, `mode` (batch/online), `cost_usd`, `pages`, `n_in_run INT` (stable), `first_loaded`, `last_loaded`, `note` | `runs` (extended); `n_current` becomes a view |
| `metadata_assertions` | Every value anyone has given for a bibliographic field (printed, catalogue, Gemini, corrected, a person's), with where on the page it was read; one is marked as the one we show. | `assert_id INTEGER PK`, `pub_id → publications`, `field` (title, subtitle, title_translated, fpage, lpage, volume, issue, pub_date, language, doi, journal_title…), `value TEXT`, `value_norm TEXT`, `lang TEXT`, `script TEXT`, `form` (printed, corrected, catalogue, gemini-title, azure, person), `source`, `run`, `c999`, `block_id`, `page INT`, `alto_lines TEXT`, `box TEXT`, `confidence REAL`, `reason TEXT`, `rule TEXT` (D33 rule), `supersedes → metadata_assertions`, `is_chosen INT`, `created` | `articles.title*`, `fpage/lpage` printed vs corrected, `metadata_changes`, title parts of `catalogue_records`, Gemini title files |
| `publication_dates` | Every date of a publication (published, received, accepted…) in the calendar it was printed in, with its converted pair. | `pub_id`, `date_type`, `calendar` (gregorian, hijri), `year INT`, `month INT`, `day INT`, `precision` (year, month, day, range), `printed TEXT`, `month_name_printed`, `pair_id → publication_dates` (the converted twin), `source`, `run`, `block_id`, `box` | `article_dates`, `articles.pub_year`/`pub_date` (derived) |
| `journals` | One row per journal (Mandumah's journal code). | `journal_id TEXT PK` ('J'+code), `code TEXT UNIQUE`, `country`, `databases TEXT`, `fields_of_study`, `first_year`, `last_year`, `n_catalogued INT`, `n_in_bucket INT`, `n_read INT` | `journals` |
| `journal_titles` | Every name a journal has had or been printed under, in which years, from which source. | `journal_id → journals`, `title`, `lang`, `form` (printed, catalogue, catalogue-en, romanised, person), `from_year`, `to_year`, `n INT`, `source`, `is_chosen INT` | `journals.title_*` |
| `journal_issns` | Every ISSN string seen for a journal, cleaned and checked. | `journal_id`, `issn_raw`, `issn` (normalised NNNN-NNNC), `valid_check INT`, `kind` (print, online, unknown), `issn_l`, `n_records INT`, `source`, `note` | `journals.issn` |
| `publishers` / `journal_publishers` | Publishers as entities, and which published a journal when. | `publisher_id PK`, `name`, `name_en`, `country`, `inst_id → institutions` (when a university or ministry); link: `journal_id`, `publisher_id`, `from_year`, `to_year`, `source` | `journals.publisher` text |
| `issues` | One issue of a journal, with its printed label and numbers, both calendars, and how much of it we hold. | `issue_id TEXT PK` (journal-volume-issue from the stem), `journal_id`, `volume_raw`, `volume_num INT`, `issue_raw`, `issue_printed`, `is_special INT`, `year_greg INT`, `year_hijri INT`, `date_printed`, `n_catalogued`, `n_in_bucket`, `n_legacy`, `n_read`, `n_complete` | `issues` |
| `issue_numbers` | The issue numbers one physical issue covers (a joint issue 3,4 has two rows). | `issue_id → issues`, `number INT`, PK `(issue_id, number)` | the `003,004` string |
| `languages` | Code list: ISO 639-1, 639-2 and names in Arabic and English. | `code1 PK`, `code2b`, `code2t`, `name_ar`, `name_en` | none (fixes P9) |
| `publication_languages` | Which languages a publication is in, by role. | `pub_id`, `lang → languages`, `role` (text, abstract, title, summary), `source`, `method` (catalogue-041, xml:lang, detected), `share REAL` | `articles.language` |
| `abstracts` | Abstracts as printed and as catalogued, with the true language and the ink. | `pub_id`, `lang`, `lang_method`, `seq`, `text`, `form` (printed, catalogue), `source`, `run`, `block_id`, `page`, `box` | `abstracts` (language fixed) |
| `keyword_terms` / `publication_keywords` | Author keywords as terms that can be counted across the archive, and which publication carries each (printed or catalogue form). | terms: `term_id PK`, `term_key`, `display`, `lang`; link: `pub_id`, `term_id`, `seq`, `printed TEXT`, `form`, `source`, `run`, `block_id` | `keywords` |
| `subject_terms` / `record_subjects` | The catalogue's subject headings and fields of study, each Arabic/English pair as one term. | terms: `subject_id PK`, `scheme` (653, field-of-study), `term_ar`, `term_en`, `term_key`; link: `c999`, `subject_id`, `seq`, `source` | `subjects`, `catalogue_records.fields_of_study` |
| `external_ids` | Every outside identifier of a publication or journal, with who assigned it. | `entity_kind` (W, J), `entity_id`, `scheme` (doi, c999, 001, issn, issn-l, qdrant-doc, s3-key, handle), `value`, `assigned_by` (mandumah, publisher, crossref), `source`, `block_id` (when printed) | `articles.doi`, `c999`, `record_id` |
| `merged_ids` | When two ids turn out to be the same thing, the old one points to the survivor, so links never break. | `old_id PK`, `new_id`, `kind`, `merged`, `reason`, `source` | none |
| `catalogue_reports` | Problems found in Mandumah's catalogue, with evidence and status, to hand to them and recheck on the next export. | `report_id PK`, `c999`, `stem`, `field`, `catalogue_value`, `our_value`, `kind` (invalid-issn, stem-on-several-records, duplicate-001, page-range, year, title, author-count, missing-keywords…), `severity`, `evidence` (our block/box or MARC field), `found_in_export`, `status` (open, reported, fixed, rejected), `fixed_in_export`, `run` | `catalogue_disagreements` (becomes a view over assertions + this table) |

Views, never stored: `articles` (the chosen assertion per field plus ids, which keeps Datasette queries and canned
queries working), `catalogue_disagreements_v`, `article_counts` (n_blocks …, from content tables), `runs_current`
(n_current per run), `issue_coverage`, `journal_coverage`.

What stays in files: page images, the scan PDF / ink, crops (`*.crops`), the ALTO and JATS themselves (the db holds
ids, boxes and hashes and points at the file), Azure JSON (S3), Qdrant vectors, raw Gemini answers. Reason: they
are large, immutable, and already addressable by stem + page + line id, which is all a value needs to point at.

## How the current version should be chosen

The rule is stored in the data and applied in this order:
1. a person's choice (`chosen_by = person`);
2. complete over partial (`complete = 1`);
3. by run purpose: final > judged-copy > base > exam > sample;
4. later `made`.

`current_reason` records which step decided it. Loading a run never silently displaces a version a person chose.
v33_300b (the exam, 300 different stems, 0 overlap with v33_300_final, checked) loads as purpose=exam with no
conflicts.

## Migration notes

- Build into a new file, `/home/yassine/data/platform_v2/platform_v2.db`, from the same sources (masters of every
  run, `marc.db` read-only, run folders). Do not migrate from platform.db; it is a derived layer. Reuse `parse46.py`'s
  readers (with the trans-title path fixed) through a 47 loader. Keep platform.db as it is for comparison.
- Order:
  1. `catalogue_exports` and `languages`;
  2. `journals`, `journal_titles`, `journal_issns`, `publishers` and `issues` from **marc.db for all 5,306 journal
     codes / 96,007 issues** (cheap; this gives coverage from day one);
  3. `catalogue_records` only for records we load or link to (≈ 354 + 320 now), keyed by 999$c, with `pub_id` for
     every catalogued article created lazily (`publications.status = catalogued-only`) when a journal or issue page
     needs it;
  4. `documents` from experiment 44's id lists;
  5. per run: `publication_versions`, then the assertions of the current version (other versions' assertions are
     kept too, tagged by run, so versions can be compared);
  6. `catalogue_reports` from the ISSN check, the stem → several records list and the disagreement rules.
- Size at 1M: `metadata_assertions` ≈ 15 fields × 3–4 readings ≈ 50M rows. That fits SQLite with
  `(pub_id, field)` and `(field, value_norm)` indexes, but it is the table to partition first if we move to Postgres.
  `publications` ≈ 1.56M rows (catalogue) + 13,680 uncatalogued. `documents` ≈ 3.2M (thesis parts included).
- Id rule check: W ids from 999$c are stable because 999$c is unique in the catalogue and does not depend on export
  order. A scan-only `WS<stem>` that later gets a record is merged into `W<c999>` through `merged_ids`.
- Keep column names Datasette's canned queries use (`stem`, `title`, `journal_id`) in the `articles` view, so
  metadata46.json's ten queries can be ported with small edits.
- Before the v2 loader goes in, fix the hijri `pub_year` case (19 rows) and the trans-title path; both are loader
  bugs, not schema questions. They are not fixed in 46 here, because 46 is off-limits for this audit.

## Open questions for the owner

1. **The W id basis.** Should it be 999$c (stable, but absent for 13,680 files), or a new running number with 999$c
   as an external id? The proposal uses 'W'+999$c with a 'WS'+stem fallback.
2. **Thesis parts.** Should parts (chapters, «المصادر والمراجع») be separate searchable units, or pages of one thesis?
   None of the parts are in the bucket yet.
3. **Precedence for the display value.** Is it person > judge > D33 rule > printed > catalogue > gemini-title for
   every field? For example, should the journal title display the catalogue's form or the printed one?
4. **How many partial versions to show.** v2_55's partial articles: show them as partial, or hide them until a full
   run exists?
5. **The catalogue-error report.** Should it go to Mandumah as a file per export, and who records "fixed"?

## Appendix: the queries behind the numbers

```
P=file:/home/yassine/data/platform/platform.db?mode=ro ; M=file:/home/yassine/data/marc/marc.db?mode=ro
sqlite3 $P "select count(*), sum(nullif(title_en,'') is not null) from articles"                       -- 354, 0
grep -l trans-title experiments/43_rehearsal/out/v33_300_final/masters/*.jats.xml | wc -l               -- 54
sqlite3 $P "select stem,pub_year from articles where pub_year<1500"                                    -- 19 rows
sqlite3 $P "select run,count(*),sum(current) from article_runs group by run"
sqlite3 $P "select run,sum(scan_pages<=5),sum(cast(lpage as int)-cast(fpage as int)+1>scan_pages) from articles group by run"
sqlite3 $M "select count(*),count(distinct c999),count(distinct record_id) from records"               -- 1558415,1558415,1541987
sqlite3 $M "select n,count(*) from (select stem,count(*) n from pdf_ids group by stem) group by n"     -- 2:14, 3:1
sqlite3 $M "select label,count(*) from pdf_ids group by 1 order by 2 desc limit 10"
sqlite3 $M "select count(*) from records where doi like '%-___-___-___'"                               -- 185774
ISSN check digit: python over `select issn,count(*) from records group by issn` (63 bad check, 42 malformed)
```

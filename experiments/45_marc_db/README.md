# Experiment 45: the MARC catalogue as a local database

**Question** (owner, 2026-10-19): the owner copied Mandumah's MARC XML (`metadata_final.xml`, 7.67 GB) onto this
machine. Make it a local, fast, queryable database: every field kept, the main fields flattened, PDF ids, people,
keywords and subjects in their own tables, full-text search that forgives Arabic spelling variants.

**Answer (2026-10-20).** `~/data/marc/marc.db` (SQLite, **10.16 GB**), built in **22 min 07 s** with **257 MB** peak
memory (streamed with lxml `iterparse`, each record cleared). 1,558,415 records, 3,196,204 PDF ids, 68,231,364
subfields, 2,217,503 people, 12,016,575 subject terms / fields of study, 1,836,873 keyword pairs. A lookup by PDF
id, record number, 999 $c or authority, or a record's raw fields, takes 0.004–0.03 ms warm (the CLI answers in
0.06–0.4 s, mostly Python start-up).

The XML is **byte for byte the dump the masters already use**: its sha256 (`4bd30433…6f1e`) equals that of the
decompressed `~/.cache/inkscript/catalogue/metadata_final.xml.gz` (2026-08-27, experiment 29), so this is the same
catalogue, now queryable. The XML states no dump date (no 005, no attribute on `<collection>`); 995 $d (date
added to a database) exists on 248,864 records only, all in 2014.

## Checks (`check45.py` → `~/data/marc/check45.json`)

| | marc.db | bucket map (exp. 44) | masters' index (exp. 29) |
|---|---|---|---|
| records | 1,558,415 | 1,558,415 | 1,558,415 |
| distinct PDF ids | 3,196,204 | 3,196,204 | 3,196,204 |
| PDF id → record rows | 3,196,220 (15 ids in 2–3 records) | — | 16 duplicates dropped (the first record kept) |
| masters' ids missing here / here missing there | 0 / 0 | | |

**200 random PDF ids, field by field** (the masters' `Catalogue.get` against the tables here: id, title, subtitle,
English title, people with role / Latin form / authority, publisher, year (both calendars), month, pages, type,
thesis, notes, abstracts, subject terms, keywords, journal fields, databases, DOI, language, country): **0
differences** in 200. Expected, as the flattening is the masters' own reader (`inkscript.enrich.catalogue.parse_record`).

**Things the data say that a user of the database must know**

- **001 is not unique.** 15,184 record numbers are shared by 31,612 records (5 records have none): 11,095 pairs
  are an article and a dissertation, 2,834 pairs two non-dissertation records (e.g. 0075810 is both a 1998 article,
  `0080-026-002-002`, and a 2013 thesis, `9805-007-012-0019-*`). **999 $c is unique** (1,558,415 values). The
  database's key is `rec` (the record's order in the XML); `records.record_id` is indexed but not unique.
- 15 PDF ids belong to two or three records (all dissertation files, `98xx-…`); `pdf_ids` keeps every pair.
- 692 keywords pair Arabic $a with English $b by position, and the catalogue sometimes has one more English term
  than Arabic, so pairs can be shifted (2382-005-003-001: «الدول العربية النفطية» beside "Environmental
  Degradation"). As the masters read it; the raw subfields are in `fields`.
- 773's subfields are not the textbook ones: $s is the journal's title, $t / $e its English title, $o the journal
  code, $v / $l volume and issue, $m the printed form; there is no $g (experiment 29's table).

**The two examples**

- `0355-000-002-006` → 001 0525299, 999 $c 129547: «أثر التطور الاجتماعي على تطور الأشكال الفنية في القصة المصرية
  الحديثة», أوراق جديدة (0210-0045), ع 2, 1979, pp. 50–73, author «الشوني، يوسف» (authority 130243). That authority
  has this one record; «الشاروني، يوسف» (authority 124101) has 136, among them a 1975 essay «أثر التطور الاجتماعي على
  التطور الفني : في القصة المصرية خاصة», so «الشوني» is very probably a misspelled duplicate of Yusuf al-Sharouni (a question for the catalogue's
  owners, not something the database changes).
- `2382-005-003-001` → 001 2058215, 999 $c 1299730: «الفقر والنمو الاقتصادي والتدهور البيئي : دليل تجريبي من الدول
  العربية النفطية», مجلة الدراسات التجارية والاقتصادية المعاصرة (2661-7153), مج5 ع3, 2022, pp. 497–505, «الحويج، حسين
  فرج» / Alhwij, Hussen Faraj (401869), DOI 10.55624/2382-005-003-001, EcoLink, abstracts $a (Arabic) and $b (English).

## Disk and memory

C: (which holds WSL's disk) had 49 GiB free after the copy (`df -h`), 45 GiB at the lowest during the build, 52
then 50 GiB after (space was freed on C: by something else during the build; the database itself is 9.5 GiB).
A first slice (100,000 records: 548 MB, 66 s, 200 MB of memory) projected 10.8 GB by bytes read, too close to the
38 GiB floor, so the abstracts (1.7 GB of text) are stored once, in `fields`, and read through views; the build
then came to 10.16 GB (the slice had few abstracts). `diskwatch45.sh` pauses the build (SIGSTOP) below 38 GiB;
the build itself stops below `--min-free`. It never triggered.

Size by table: `fields` 7.41 GB, `records` 0.96, `subjects` 0.58, `authors` 0.29 (+0.10 name index), FTS 0.28,
`pdf_ids` 0.18 (+0.09), `keywords` 0.10, other indexes 0.16.

## Schema

| table | one row per | columns |
|---|---|---|
| `records` | record | `rec` (key: order in the XML), `record_id` (001), `leader`, `title`, `subtitle` (245 $a $b), `title_en`, `subtitle_en` (242, else a Latin 246), `parallel_titles` (every 246, ' \| '), `language` (041), `country` (044 $b), `year` (260 $c), `year_int`, `year_hijri` (260 $m), `month` (260 $g), `publisher`, `place` (260 $b $a), `pages`, `page_first`, `page_last` (300 $a), `type`, `type_en` (336), `journal`, `journal_en`, `journal_romanised`, `journal_code`, `issn`, `volume`, `issue`, `issue_printed`, `article_seq` (773 $s $t\|$e $f $o $x $v $l $m $c), `fields_of_study` (773 $4), `databases` (995 $a), `added` (995 $d), `abstract_codes` (520 codes present), `doi` (024 $3), `thesis` (502 as JSON), `c999`, `d999`, `n_pdfs`, `n_authors` |
| `fields` | subfield | `rec`, `fseq` (field's place in the record), `sseq`, `tag`, `ind1`, `ind2` (NULL = blank), `code` ('' for control fields), `value` (verbatim): nothing is lost |
| `pdf_ids` | PDF × record | `stem` (`0355-000-002-006`, from 856 $u without `.pdf`), `rec`, `record_id`, `seq`, `label` (856 $y: «صفحة العنوان»…) |
| `authors` | person or body | `rec`, `seq` (100/110 first, then 700/710 in order), `tag`, `name`, `name_folded`, `latin` ($g/$q), `role` ($e), `authority_id` ($9), `is_org` |
| `keywords` | 692 pair | `rec`, `seq`, `ar`, `en` |
| `subjects` | term | `rec`, `seq`, `source` ('653' subject term, '773$4' field of study, '773$6' its English), `term` |
| `abstracts` (view) | 520 subfield | `rec`, `seq`, `code` (a author's Arabic, b English, d French/other, e Mandumah's Arabic, f Mandumah's English), `text` |
| `records_v` (view) | record | `records` + `abstract` (the first 520) |
| `fts` | record | contentless FTS5, rowid = `rec`; `title` (245, 242/246), `authors` (names and Latin forms), `keywords` (653 + 692), all folded |
| `tag_stats` | tag / subfield code | `records` having it, `occurrences` |
| `meta` | key | source path, size, mtime, sha256 (first 100 MB and whole file), build date and times, counts, the folding |

Folded form (`build45.fold`, used for both the index and the query): diacritics, Quranic marks and tatweel removed;
أ إ آ ٱ → ا, ؤ → و, ئ → ي, ى → ي, ی → ي, ة → ه, ک → ك, Arabic-Indic digits → 0–9, lower case.

Indexes: `pdf_ids(stem)` (primary key), `pdf_ids(rec)`, `records(record_id)`, `records(c999)`, `records(issn)`,
`records(year_int)`, `records(journal_code, volume, issue)`, `authors(authority_id)`, `authors(name_folded)`;
`fields`, `authors`, `keywords`, `subjects` are clustered on `rec`. `fields` has no index by tag: count with
`tag_stats`, search with `fts`, or scan (~1 min).

## Use

```
P=.venv/bin/python; Q=experiments/45_marc_db/marcq.py
$P $Q stem 0355-000-002-006 [--raw]     # one PDF's record (--raw: every field as stored)
$P $Q record 0525299                    # by 001 (can return several records); also: c999 129547
$P $Q author "الشاروني"                  # people (folded; every word must match)
$P $Q authority 124101                  # one authority's records
$P $Q search "القصه المصريه الحديثه"      # title + people + keywords, ranked
$P $Q sql "SELECT journal_code, count(*) FROM records GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
```

Example SQL:

```sql
-- the articles of one issue, in order
SELECT p.stem, r.pages, r.title FROM records r JOIN pdf_ids p USING (rec)
 WHERE r.journal_code = '0355' AND r.volume = '000' AND r.issue = '002' ORDER BY r.article_seq;
-- every file of a thesis, with its label
SELECT stem, label FROM pdf_ids WHERE rec = (SELECT rec FROM pdf_ids WHERE stem = '9805-007-012-0019-A');
-- an exact MARC subfield anywhere (scan): records whose 856 has a publisher link
SELECT rec, value FROM fields WHERE tag = '856' AND code = 'n' LIMIT 10;
-- full text, folded query
SELECT r.record_id, r.title FROM fts JOIN records r ON r.rec = fts.rowid
 WHERE fts MATCH 'title: (الطاقه AND الذريه)' ORDER BY rank LIMIT 20;
```

## Build

```
.venv/bin/python experiments/45_marc_db/build45.py [--xml ~/data/marc/metadata_final.xml] [--db ~/data/marc/marc.db] \
    [--limit N] [--full-sha] [--min-free 38]          # writes <db>.part, renames at the end; progress in <db>.log
experiments/45_marc_db/diskwatch45.sh &               # optional: pauses the build below 38 GiB free on C:
.venv/bin/python experiments/45_marc_db/fix_parallel45.py   # one-off, already applied (see below)
.venv/bin/python experiments/45_marc_db/check45.py          # -> ~/data/marc/check45.json
```

`fix_parallel45.py`: the first build joined 246 $a and $b without trimming $a's ISBD " :" ("…Degradation: :
Empirical…"); `build45.py` now trims it, and the script recomputed `parallel_titles` in place for the 488,986
records with a 246 (42 s), so the database matches what the current code would build.

Files outside git: `~/data/marc/metadata_final.xml` (moved from the repo root; 7,666,455,049 bytes, mtime
2026-10-19 23:34), `marc.db`, `marc.log`, `marc.time` (`/usr/bin/time -v`), `diskwatch.log`, `check45.json`,
`tablesizes.txt`, `slice/` (the 30k / 100k test builds, 1.1 GB, can go).

**What it changed.** Nothing in the pipeline: the masters keep reading `~/.cache/inkscript/catalogue/catalogue.sqlite`
(same dump). `docs/moving-to-a-server.md` lists the new data.

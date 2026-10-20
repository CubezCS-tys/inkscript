# Experiment 46 — the platform database (first version)

**Question.** Can the masters of experiment 43 (JATS + ALTO) and Mandumah's MARC catalogue (experiment 45) be one
database of entities — journals, issues, articles, people, institutions, keywords, blocks, notes, figures, references
and their links, and the quality record (flags, judge findings, patches, fixes, misprints, D33 changes, catalogue
disagreements) — that a new run can be added to tonight, and that shows what a Web-of-Science-style platform on the
archive would look like?

**Answer (2026-10-20, $0, no paid calls).** Yes: `/home/yassine/data/platform/platform.db` (SQLite, 57 MB), served
read-only by Datasette at **http://127.0.0.1:8002/platform** with ten canned queries. 353 articles (the 300 of run
`v33_300` and the 55 of `v2_55`; one article is in both and is kept from `v33_300`), 50,916 blocks, 4,083 notes,
4,775 parsed works, 394 people (346 with a catalogue authority id), 301 institutions; 109 works linked with confidence
to a catalogue record and 303 of 544 «المرجع السابق»/ibid. notes resolved to the work they point back to. Hand check of
54 links: 22 right, 3 near and 0 wrong among the confident catalogue links; 19 right and 6 wrong among the resolved
back references. The loader takes 12 s for the 354 masters (83 MB memory) and is idempotent.

Data lives outside the repo: `/home/yassine/data/platform/` (`platform.db`, `datasette.log`). Sources are never
edited: the masters are read, `marc.db` is opened read-only.

## The schema

```
                          journals ── issues ── articles ─┬─ article_dates, abstracts (masters + catalogue 520)
  (journal code, ISSN,              (stem j-v-i) (stem;    ├─ keywords (printed + catalogue), subjects (catalogue)
   printed + catalogue names)                    rec,c999,├─ article_authors ── people ── person_names
                                                 DOI,     │      (order, printed name, email,   (authority id or folded name;
                                                 titles   │       catalogue name, match)         printed / catalogue / Latin)
                                                 printed/ │      └─ affiliations ── institutions ── institution_variants
                                                 corrected│          (printed; org/faculty/dept keys)  (organisation > faculty > department)
                                                 /metadata├─ blocks (page, kind, order, text, ALTO line ids, box)  + blocks_fts
                                                 , pages, ├─ notes ── note_calls          figures (figure / table / equation / inline)
                                                 stamps)  ├─ works ── work_authors  ┐
                                                          ├─ back_references        ├─ citation_links → article | catalogue record | earlier work
                                                          │                         ┘   (score, method, best, evidence)  + link_checks
                                                          ├─ catalogue_records, catalogue_authors   (marc.db's view, source = catalogue)
                                                          └─ quality: flags · judge_findings · patches · fixes · misprints ·
                                                                      metadata_changes (D33) · catalogue_disagreements
  runs ── article_runs (every article × run ever loaded; `current` = the run whose masters fill the content tables)
```

The full definitions, with a comment on every non-obvious column, are in [schema46.sql](schema46.sql). Provenance:
every row has `source` (masters | catalogue | judge | person | gemini-retry | flags43 | link46) and rows read from a
run have `run`. Masters and catalogue values sit side by side and are never merged into one column (e.g. `articles.title`
is the print with D33 corrections, `articles.title_printed` the print as it is, `catalogue_records.title` the catalogue's).

Tables and what fills them:

| table | rows | from |
|---|---|---|
| articles | 353 | `<article-meta>`: ids (stem, catalogue rec / 999 $c / 001, printed DOI), titles (corrected, printed, metadata form, English), volume/issue/year/pages, abstracts, counts, the run's prompt/rules/model stamps, applied patches |
| journals / issues | 260 / 352 | journal code (stem's first part, `<journal-id>`), printed name, catalogue name/ISSN/publisher |
| article_dates | 454 | pub-date and history (received, revised, accepted, published, online) |
| abstracts | 364 | printed `<abstract>`/`<trans-abstract>` paragraphs and the catalogue's 520 |
| keywords / subjects | 1,175 / 3,001 | printed `<kwd>` (label «الكلمات المفتاحية:» stripped, printed form kept) and catalogue keywords; catalogue 653 / 692 / 773 $4 subjects |
| article_authors / people / person_names | 412 / 394 / 878 | contribs matched to the catalogue's 100/700 by name (Arabic printed form against «surname، given», Latin against the Latin form); one person per authority id, else per folded name |
| affiliations / institutions | 246 / 301 | `<aff>` (tagged orgname/dept/city/country and the untagged rest) → organisation > faculty > department |
| blocks | 50,916 | every element with a block id (`p<page>b<n>`, table cells `p<page>t<n>c<rc>`) in document order: kind, section, language, text as printed, ALTO line ids, box (ALTO TextBlock, else the union of its lines) |
| notes / note_calls | 4,083 / 4,035 | footnotes and endnotes with their calls (the block each call is in) |
| figures | 1,908 | figures (caption, alt-text ar/en, text-in-figure, crop), tables (cells), display and inline equations (LaTeX, MathML), pictures in a line |
| works / work_authors | 4,775 / 4,619 | every `<element-citation>`: in a `<ref>` (with its printed `<mixed-citation>`) or in a note's parsed citations (with the note's text) |
| back_references | 544 | notes with «المرجع السابق», «المصدر نفسه/ذاته», «مرجع سابق», ibid., op. cit., loc. cit. (497 of them have no parsed citation) |
| citation_links / link_checks | 779 / 54 | link46.py; the hand check |
| fixes / misprints / metadata_changes | 11,029 / 1,796 / 5 | the masters' reader-fixes notes (Azure's reading → the print), suspected-misprints notes (D30), `<stem>.metachanges.json` (D33) |
| flags | 790 | `out/<run>/flags.json` (flags43) |
| judge_findings | 79 | `out/judge/answers/<model>/<run>/<stem>_pNNN.json` (judge43.py), one row per named problem (or one "none" row per page) |
| patches | 1 | `out/<run>/patches/<stem>.json` (patches43.py) with the status from the masters' `<stem>.patches.json` |
| catalogue_records / catalogue_authors | 353 / 428 | marc.db, by `pdf_ids.stem` (the primary record = the best title match when a stem has several) |
| catalogue_disagreements | 393 (237 articles) | masters vs catalogue, field by field (below) |

The judge tables follow docs/ideas.md "A judge with authority, through patches": a finding has id, run, article, page,
type (with the judge's subtype), targets (blocks, lines, box), confidence, evidence, action, route (auto = two keys
and applied | proposed | retry | human | none), the patch made of it and its status, the model and the answer file.
A patch has id, run, article, page, action, targets, payload, source (person | judge | gemini-retry), confidence,
evidence, reason, apply, status (applied | skipped | overridden | proposed | not-built) and the run it was built into.
Judge answers are read for the base run (`v33_300_judged` → `v33_300`).

## How to load a run

```
.venv/bin/python experiments/46_platform_db/load46.py --run v33_300            # masters in experiments/43_rehearsal/out/v33_300/masters
.venv/bin/python experiments/46_platform_db/load46.py --run <second 300 run>    # tonight's second 300
.venv/bin/python experiments/46_platform_db/load46.py --run v33_300_judged     # a judged/fixed copy: its articles become current
.venv/bin/python experiments/46_platform_db/load46.py --run v2_55 --current if-new   # never displace an article another run holds
.venv/bin/python experiments/46_platform_db/load46.py --run v33_300 --stem <stem> --force   # reload one article
.venv/bin/python experiments/46_platform_db/link46.py                          # link what was loaded since the last linking
```

- **Idempotent and incremental.** An article whose JATS, D33 sidecar and patches sidecar are unchanged since that run
  was loaded is skipped (sha in `article_runs`); a new or changed one is re-read and its rows replaced (delete by stem,
  insert). Flags, patches and judge findings of the run are re-read on every call (they are small), so new judge or
  flag files are picked up by running the same command again. `link46.py` without arguments links only articles
  loaded after their last linking. Re-running both on unchanged data changes nothing.
- **Which run fills an article.** The run that last loaded a new or changed version wins (`--current always`, the
  default): load a judged or fixed copy after its run; re-running the unchanged run does not take the article back
  (use `--stem … --force` for that). `--current if-new` records the run in `article_runs` but leaves articles another run holds.
- Options: `--masters DIR`, `--flags FILE`, `--patches DIR` (repeatable) when a run's files are not in the usual places.
- People, institutions, journals and issues are rebuilt from the article rows on every load (deterministic, < 1 s).
- Serving: `setsid nohup .venv/bin/datasette serve /home/yassine/data/platform/platform.db -h 127.0.0.1 -p 8002
  --metadata experiments/46_platform_db/metadata46.json --setting sql_time_limit_ms 10000 --setting max_returned_rows 2000 &`
  (not `--immutable`, so loads show at once; Datasette opens the file read-only). Canned queries
  ([metadata46.json](metadata46.json)): articles by author (any spelling), who cites whom, most cited catalogue records,
  catalogue disagreements (list and counts), judge findings by type, flags per article, one article beside the
  catalogue, institution clusters, full-text search. All return 200.

## Citation linking (link46.py)

Each parsed work is matched to (a) the articles in the database (title against printed, corrected and catalogue titles,
+ author surname, + year), (b) the catalogue: FTS5 on the 6 (then 4, 3) longest folded title words, then title
similarity, author surname as a whole word of a catalogue name, year (a hijri year compared after conversion), and
(c) back references are resolved inside the article. A link is kept with its score, method and evidence (the
catalogue title, authors, **authority ids**, year, type); `best = 1` marks a confident one. Source rows are never
changed.

| | links | confident (`best`) |
|---|---|---|
| work → catalogue, title + author/year agree | 109 works (89 records) | 109 — journal 74 of 852 journal citations, thesis 19 of 150, book 6 of 3,222, other 10 |
| work → catalogue record that is a review of the cited book (`عروض كتب`) | 82 | 0 |
| work → catalogue article about the cited book (book cited, journal article found) | 176 | 0 |
| work → part / edition of it (a long subtitle such as «… دراسة وتحقيق» the citation lacks) | 42 | 0 |
| work → catalogue, title only | 61 | 0 |
| work → article in this database | 6 (all «كشف الظنون», the book vs an article of that name) | 0 |
| back reference → earlier work: by author | 98 | 98 |
| … by author and title words (an author with several works) | 80 | 80 |
| … the work cited just before (ibid., نفسه, ذاته), following earlier back references | 109 | 109 |
| … by title words (short notes only) | 16 | 16 |

303 of 544 back references are resolved; the rest are left on purpose: an «op. cit.» naming an author with no
earlier parsed work, or an ibid. after a note we could not parse, is left rather than guessed. Books are the bulk of
what is cited (3,222 of 4,775) and the catalogue holds articles and theses, not books: a book's title in the
catalogue is mostly a review or a study of it, which is why those are kept as candidates and not as links.

**Hand check** (`sample46.py`, seed 2026, read one by one; verdicts in [checks46.py](checks46.py),
`sample46_checked.json` and the `link_checks` table):

| method | checked | right | near | wrong |
|---|---|---|---|---|
| catalogue (confident) | 25 | 22 | 3 (thesis behind a book; conference paper later in a journal; a thesis cited, its article linked) | 0 |
| catalogue-about (withheld) | 4 | 4 rightly withheld | | |
| backref-author | 6 | 5 | | 1 (Pincus's «Economic Aid» → his C.N.U.C.E.D. paper) |
| backref-author-title | 6 | 5 | | 1 («Land Evaluation Part II» → Part I) |
| backref-previous | 8 | 7 | | 1 (ibid. after an unparsed court judgment) |
| backref-title | 5 | 2 | | 3 (op. cit. of a book → another chapter of it; two long notes matched by chance) |

After the check, title matching for back references was limited to short notes (≤ 12 words besides the marker): of
the five checked, the three long-note ones (1 right, 2 wrong) are no longer made; 16 title links remain. Two earlier
rounds of checking (not counted above) found what the rules now handle: reviews and studies of a book linked as the
book, edition-parts of classical works, «حسن» matched inside «محسن», «op. cit. Lois Mai Chan» with the author after
the marker, ibid. falling back to the reference list.

## Institutions

Affiliations are cut at «-», «،», «/», «.» and before «كلية/جامعة/College of/University of», each piece classed by its
head word (organisation: جامعة, University, وزارة, مركز, معهد, هيئة, مجمع, الأزهر…; faculty: كلية, College, Faculty,
Faculté; department: قسم, شعبة, دائرة, Department; a known country), after a leading role is cut («مدرس»,
«الأستاذ بـ», «عميد», «Lecturer at»…). The key is the folded name without spaces, «ال» or «of/the»; keys of ≥ 8
letters with ratio ≥ 0.92 in the same script are one institution; an Arabic and a Latin organisation are one when the
same person is printed in both scripts in one article (7 pairs: جامعة تكريت = Tikrit University, جامعة بغداد =
University of Baghdad, جامعة القاهرة = Cairo Unverssity, جامعة بابل = Université de Babylon, جامعة صلاح الدين,
جامعة الإدارة والتكنولوجيا, مؤسسة إيهيا).

Result: 246 affiliations → 202 with an organisation, 108 with a faculty, 84 with a department, 28 with none (a
country, a city, «ناقد وباحث»). 134 organisations (107 Arabic, 27 Latin), 89 faculties, 77 departments; 12
organisations gather more than one printed form (جامعة القاهرة ‖ جامعة القاهره ‖ Cairo Unverssity; الجامعة الأردنية ‖
الجامعة الاردنية; جامعة البصرة ‖ جامعة البصره; جامعة الإسكندرية ‖ جامعة الاسكندرية; جامعة قسنطينة ‖ جامعة قسنطينة 2 …).
**Check of 30 affiliations** (read): 24 right, 4 partly (a «Faculté» as organisation, a region as a department,
«دائرة» missed, «بالمعهد» with its «ب») — the last three fixed after the check, 2 wrong (an OCR-garbled
«١ ـمعة الإسلامية العاية»; «المراقب المساعد للبحوث … بالأزهر» not reduced to الأزهر). Arabic↔English names of
different people are not joined (no dictionary yet): «جامعة الملك سعود» and «King Saud University» stay two rows
unless one person carries both.

## Catalogue disagreements (the list for Mandumah)

393 rows on 237 of 353 articles: `catalogue_disagreements_summary` / `catalogue_disagreements_list` at :8002.

| field | kind | n |
|---|---|---|
| pages | the catalogue's range fits the scan's page count, the masters' does not | 142 (lpage 112, fpage 30) |
| pages | neither fits / masters fit | 27 / 2 |
| title | spelling (ratio ≥ 0.9) / one contains the other / different | 32 / 39 / 5 |
| authors | count differs | 24 (e.g. 0939: 7 printed authors, 5 in the catalogue; 0085, 0128, 0310, 0345: the catalogue adds a second name, often the thesis supervisor) |
| author n | name differs / printed author not in the catalogue | 17 / 15 |
| year | differs (a hijri print converted is not counted) | 11 (1608: 2022 vs 2023; 0700: 1991 vs 1997) |
| issue / volume / language | differs | 9 / 2 / 2 |
| missing in the catalogue | keywords / Arabic abstract / English abstract | 36 / 15 / 15 |

Two findings for the pipeline, not the catalogue: **the masters' page range is the wrong one in 142 articles** (the
catalogue's range has exactly the scan's page count; e.g. 1058-005-993-021 printed 450–459, catalogue 450–469, 20
pages scanned) — Argon seems to read the range printed on the first page or stop at the Arabic part; and 3 of the 5
"different" titles are the masters' (0355 «أثر التـ عَلى تطـ فنى القـ», a cut-off line; French section titles
«II. - JURISPRUDENCE», «REVUE DES LIVRES» where the catalogue has the article's own title). Of the other two, 0484 is
a French article catalogued under its Arabic title, and 0944 is the catalogue's («الأداء والرفض» for the printed
«الإباء والرفض»).

## Files

| file | what |
|---|---|
| [schema46.sql](schema46.sql) | the tables, with comments |
| [load46.py](load46.py) | `--run` loader (catalogue lookups, author matching, disagreements, flags, patches, judge findings, rebuilds) |
| [parse46.py](parse46.py) | one master → rows (JATS + ALTO + sidecars) |
| [inst46.py](inst46.py) | affiliations → institutions |
| [link46.py](link46.py) | citation linking |
| [common46.py](common46.py) | paths, experiment 45's Arabic folding, similarity |
| [sample46.py](sample46.py), [checks46.py](checks46.py), sample46.json, sample46_checked.json | the hand-checked sample |
| [metadata46.json](metadata46.json) | Datasette title, descriptions, canned queries |
| progress.md | the run log |

## What it changed / next

- The second 300 can be added with one command and linked with another; a judged or fixed copy is loaded after its run.
- For experiment 43: the masters' `<fpage>/<lpage>` should come from the catalogue (or be checked against the scan's
  page count) — 142 of 353 are off.
- Next for the platform: cited authors → people (the catalogue authority ids are already in the link evidence);
  Arabic↔English institution names from a small dictionary or from the catalogue's Latin names; a work-identity table
  so the same book cited in many articles is one row (now each citation is its own work); books from a book
  catalogue (Mandumah holds articles and theses).

# 29 · The front matter from Mandumah's library catalogue, tied to the ink

**Question.** Experiment 28 found the JATS front matter weakest where the page alone decides: without a Gemini title
file the layout's title was right in 79 of 129 documents, an author in half. Mandumah's own catalogue (MARC 21,
1.56 million records, made by people from each article) already says what every article is called, who wrote it,
where and when it was published. Can every JATS file take its front matter from the catalogue — properly mapped,
fast and offline — and still point at the printed words, and does the catalogue ever describe the wrong article?

**Answer (2026-10-07).** Yes. 204 of the 205 documents of experiment 28's set have a record (`1548-011-001-031`
has none). With the catalogue first:

| documents (of 205) whose JATS has… | before (the page alone) | after |
|---|---|---|
| a title | 194 (171 of 204 matching the catalogue) | **205** |
| … tied to its printed words (word ids) | 194 | **202** |
| authors | 147 (the page found 132 of the catalogue's 214 names) | **205** |
| … with a name on the ink | 147 | **172** (195 of 214 names found) |
| an affiliation (from the page) | 26 contribs | **50** |
| the journal's title | 101 (right in about half, exp. 28) | **205** |
| ISSN | 0 | **89** |
| a year | 66 | **205** (Hijri too: 10 → 76) |
| volume or issue | 199 (from the id) | 199 (catalogue; the id agrees) |
| pages | 165 (printed numbers) | **205** |
| an abstract | 0 | **34** |
| keywords / subject terms | 0 | **204** |
| a DOI | 0 | **15** |
| valid: JATS 1.4 Archiving / ALTO 4.4 | 205 / 205 | **205 / 205** |

The honorific printed before a name is the name's `<prefix>` (97 names: «الدكتور», «للأستاذ», «د.», «الأستاذ
دكتور»…), never part of it; the catalogue's form of the name is the name (surname and given names apart, the Latin
form beside it when the record has one) and the page's printed form is kept as a `string-name`. Every element says
where it came from (`specific-use="catalogue"` / `"page"`, custom-meta `title-source`, `author-n-source`,
`front-sources`, `catalogue-check`).

**No record looked like the wrong one.** 197 records agree with their page (title found, backed by the names or the
page count); 1 agrees on the ink while Gemini's title file names another title (the catalogue used the rubric); 3
"partly" — the catalogue names the article by its **rubric** («كلمة العدد», «البيت المسلم», «الادب ورسالته الروحية» for
a page headed «أدب وفن») and the page does not print it; 3 "doubtful" that are right records (a title Azure misread,
«كيف خقد العرب» for «كيف ننقذ الغرب»; a review of 3 reviewers in a 7-page PDF catalogued as 3 pages; a paraphrased
title). To know whether the check would notice a wrong record, each document was given its **neighbour's record**
(the next id: mostly the next article of the same issue — the hardest case, same journal, same year, often the same
page): **0 of 204 accepted**, 27 "disagrees", 146 "doubtful", 31 "partly" (`wrong_record.py`). Before the rule was
tightened, 12 of 204 neighbours' records had been accepted on a weak title match (a phrase of the text, a table of
contents) — the rule now asks a match under 0.75 to be backed by a name or the page count.

What the catalogue does that the page could not: the rubric/subtitle split («ديوان العرب» : «في مرابع الصبا» —
the ink is the subtitle's, found), corporate authors («هيئة التحرير», «لجنة الفتوى»), translators («ترجمة: د. حمدي
الزيات» at the foot of the page, found there), names the page abbreviates («جعفر العبد» for «جعفر عبدالمجيد العبد»),
both calendars and the months («يونيو / جمادى الاولى» → month 6 Gregorian, 5 Hijri).

## The catalogue, and the index

The MARC XML (`s3://mandumah-source-docs/metadata/metadata_final.xml.gz`, 1.17 GB, 1,558,415 records, 3,196,204 PDF
ids — theses list several PDFs — 16 PDFs in two records) is fetched once (63 s) into `~/.cache/inkscript/catalogue/`
and indexed into one SQLite file: **1.10 GB**, records stored as compact JSON compressed 64 at a time (a zlib stream
per record made 2.33 GB). Building: 7 min 15 s alone, 18 min beside a 3-worker run; at most **0.47 GB** of memory
(streamed with lxml `iterparse`). Opening: **29 ms, 18 MB**; a lookup **1.1 ms**; nothing is loaded into memory, so
3-4 workers cost nothing extra. Why the cache and not the repo: the data are Mandumah's, 1 GB, and rebuildable
from the bucket; the cached schemas already live there (D20). See `docs/moving-to-a-server.md`.

    python -m inkscript.enrich.catalogue build            # the cached XML, else the bucket
    python -m inkscript.enrich.catalogue show 0048-002-007-009
    inkscript native ... --xml [--catalogue FILE.sqlite|FILE.xml.gz|none]   # default: the cache if it exists

## What each MARC field is, and where it goes

Read on all 1.56M records (field counts in `src/inkscript/enrich/catalogue.py`'s docstring) and on the 204 records
of the set:

| MARC | what Mandumah puts there | JATS |
|---|---|---|
| 001 | record number | `article-id pub-id-type="custom" custom-type="mandumah-record"` |
| 024 $3 | DOI (297k records; 15 of the set) | `article-id pub-id-type="doi"` |
| 041 $a | language (ara 201, eng 2, fre 1 in the set) | custom-meta `catalogue-language` (the article stays `xml:lang="ar"`; Latin paragraphs carry their own) |
| 044 $b | country | `publisher-loc` (with 773 $d) |
| 100 / 700 $a | "Surname، Given" | `contrib` › `name-alternatives` › `name` (surname, given-names), `xml:lang="ar"` |
| 100 / 700 $g, $q | the name in Latin script | a second `name`, `xml:lang="en"` |
| 100 / 700 $e | role: مؤلف, م. مشارك (co-author), مترجم, مشرف (supervisor), عارض (presenter / book reviewer) | `@contrib-type` author / translator / supervisor / presenter, `role` |
| 100 / 700 $9 | authority number | `contrib-id contrib-id-type="mandumah-authority"` |
| 110 $a | a body ("هيئة التحرير", 68k) | `contrib` › `collab` |
| — | affiliation: **no record has one** (no 100 $u) | from the page: the page's byline reading, or the line(s) under the name opening with جامعة/كلية/قسم/أستاذ/مدرس… (`aff specific-use="page"`) |
| 245 $a, $b | title, subtitle (ISBD " :" at the end of $a) | `article-title`, `subtitle` |
| 242, 246 $a $b | English title (246 also other variants) | `trans-title-group xml:lang="en"` |
| 260 $b | publisher | `journal-meta/publisher` |
| 260 $c, $m, $g | year Gregorian (all), Hijri (454k), month or season | `pub-date calendar="gregorian"` / `"islamic"` with `month` (Arabic month names, Levantine and Maghrebi too, mapped to numbers) or `season` |
| 300 $a | "184 - 238" | `fpage`, `lpage content-type="catalogue"`; the print's own first number noted when it differs |
| 336 $a $b | بحوث ومقالات / Article, Book Review, Conference Proceedings, Literary Text, Other | `subj-group subj-group-type="mandumah-type"` |
| 500 / 502 / 995 | note / thesis (degree, university, faculty, country) / database (HumanIndex, EduSearch…) | custom-meta |
| 520 $a $b $d $e $f | abstracts: author's Arabic / English / French-or-other; Mandumah's Arabic / English | one `abstract` in the article's language (the author's before Mandumah's), the rest `trans-abstract`, `abstract-type="author"` / `"mandumah"`; an "abstract" equal to the title is dropped |
| 653 $a | subject terms (~5.5 a record) | `kwd-group kwd-group-type="subject-terms"` |
| 692 $a $b | keywords, Arabic with English | two `kwd-group kwd-group-type="keywords"` |
| 773 $s, $t/$e, $f | journal title, English title, romanised | `journal-title`, `trans-title`, `abbrev-journal-title abbrev-type="romanised"` |
| 773 $x | ISSN (906k) | `issn` |
| 773 $v, $l, $m | volume, issue ("071,072" = a double issue → 71-72), as printed ("مج34, ع390", "س 33, ع 4") | `volume`, `issue content-type="catalogue"`; the printed form in custom-meta |
| 773 $4, $6 | field of study, Arabic / English | `subj-group subj-group-type="field"` |
| 773 $c, $o | article's place in the issue, journal code | custom-meta; `journal-id` (already from the id) |
| 856 $u, $y, $n | the PDF(s) and their labels; the publisher's page | the index key; custom-meta for theses' files; `self-uri` |
| 930, 999, 555 | internal flags and counters | not used |

## How the front matter is decided (`catalogue.front`, called from `structure._front`)

1. The page is read as before (Gemini's title file, else the layout) — kept for the comparison and the affiliation.
2. The catalogue's title (with its subtitle, then alone) is aligned to the first pages' words (the same aligner as
   Gemini's file); a title repeated as a running head is looked for in page 1's furniture too. A match under 0.75
   counts only among page 1's first 60 words or on the page's own title (a 0.62 match deep in the text, «الأديب
   التي» for «الادب ورسالته الروحية», was refused this way). When the page's own title reads as the catalogue's title
   or subtitle but sits elsewhere than the match, the page's words win (the match was a mention in the text).
3. The page is read again with the catalogue in Gemini's place: the title's words given, the names aligned after it
   (in the order the ink matches best — given names first, the catalogue's order, or first name + surname), the
   rubric (short lines above the title) found against the right title.
4. A name must match at **0.75** letter similarity (0.6, Gemini's level, let «العربى عام» pass for «عصام العياش»),
   a short form at 0.85. A name not found in the text is looked for, at 0.85, in what was set aside: a byline at the
   foot, a note, the title's own line («الحقيقة والسياسة حنة آرندت»: the name is then taken off the title's words).
5. The honorific/byline words just before the name are its prefix («بقلم» is dropped, as before); the affiliation is
   the page's reading of the byline, else the line(s) under the name that open with an institution or a post.
6. The check (title match, names found, page count) gives the verdict written in `catalogue-check`.

The catalogue's title is the article-title even where the page does not print it (precedence catalogue > Gemini's
title file > layout); then the JATS has no title-words, and its alt-title / custom-meta keep what the ink says.

## Fifteen documents by eye

Every 14th of the 205 in id order (`out/report.html` shows each title page with the boxes and both front matters;
`spotcheck.json` holds the notes). All 15 titles right and on the right ink; names right where printed. Problems
seen: (1) two authors are not printed on page 1 (0331, 0955) — listed from the catalogue with no ink, correctly;
(2) a second author found in a box about the authors instead of the byline under the first (1036: the byline reads
«وهلموت» with the و glued, the box's spelling matches exactly — still his printed name); (3) an author's post
printed at the foot of the next column is not taken as his affiliation (0701); (4) the catalogue's name may add a
name the page does not print (0005, «… الدسوقي إبراهيم»). Before the fixes measured above, the look found a false name
match (0331), a false title match (0549-021-248-007), a mention in the text beating the page's own title (0357), a
double issue written «071,072», and «(*)» taken as an affiliation — each fixed and re-measured.

## Files

- `run.py` — writes the 205 JATS + ALTO files without (`before`) and with (`after`) the catalogue from experiment 28's
  builds (read only), validates them, summarises each front matter → `out/before.json`, `out/after.json`.
- `summarize.py` → `out/summary.json` (the table above); `wrong_record.py` → `out/wrong_record.json` (neighbours'
  records); `names_missed.py` → `out/names_missed.txt` (each catalogue name not found and the closest words);
  `inspect_front.py`, `show.py` — one document's alignment / front matter as text.
- `report.py` → `out/report.html` (the owner's page; `--look` also writes `out/look/<id>.jpg`).
- Code: `src/inkscript/enrich/catalogue.py`; tests `tests/test_catalogue.py`.

**What it changed.** D25; `inkscript native --xml` takes the front matter from the catalogue whenever the index
exists (`--catalogue`); docs/pipeline.md, STATUS, ideas.

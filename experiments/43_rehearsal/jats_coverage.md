# JATS coverage of the masters (experiment 43, 2026-10-18)

Which parts of a JATS 1.4 journal article our masters fill, how often, where each comes from, and what stays empty
and why. Counted by `coverage43.py count` (XPath per slot over every `<stem>.jats.xml` of a folder; "a / n" = articles
that have it / occurrences). Folders:

* **before** — `out/v2_55/masters`: the run of the 55 (prompt v2 answers) with the code of the owner's review (commit
  736b19d).
* **now** — `out/v3_test/v2_now`: the same v2 answers through today's code (`jats43.py`, no new calls). All 55 JATS
  DTD-valid and ALTO XSD-valid.
* **v3** — `out/v3_test/masters`: the paid test, 6 articles answered with prompt v3 (see the README section "Prompt v3
  and JATS coverage"); its column is in the README's table, not here (6 articles do not make a rate).

Sources: **print** = the page, through Gemini's answer (block types, metadata) and Azure's text; **catalogue** =
Mandumah's MARC record (experiment 29's merged JATS, `experiments/29_catalogue/out/merged/<stem>.jats.xml`, made by
`src/inkscript/enrich/catalogue.py`; the index `~/.cache/inkscript/catalogue/catalogue.sqlite`, 1.56M records);
**code** = computed. 41 of the 55 have a catalogue record (the others are windows or were not in experiment 29's set).

## Front matter (`front/article-meta`, `journal-meta`)

| slot | before | now | source | notes |
|---|---|---|---|---|
| `article-id[@pub-id-type=doi]` | 4 / 4 | 4 / 4 | catalogue 024 $3 | 297k of 1.56M records have a DOI (10.34120/…, Mandumah's own) |
| `article-id` catalogue record | 41 / 41 | 41 / 41 | catalogue 001 | |
| `article-categories/subj-group` | 41 / 132 | 41 / 132 | catalogue 336, 773 $4/$6 | record kind, field of study (ar + en) |
| `journal-meta` title / ISSN / publisher | 41; ISSN 23 | same | catalogue 773, 260 | ISSN in 906k records |
| `article-title` (printed lines, ids → ALTO) | 42 / 42 | 42 / 42 | print | 13 windows / title-less pages take the catalogue's title text |
| `subtitle` | 14 / 14 | 14 / 14 | print (metadata) / catalogue 245 $b | |
| **`trans-title-group` printed** (`specific-use="printed"`, `trans-title` with the printed lines' ids, `trans-subtitle` split off when it matches the catalogue's) | 0 | **1 / 1** (2382) | print: v3 title block `"translated": true`; older answers: a Latin block on p1 matching the catalogue's translated title | owner's decision (b): printed wins |
| `trans-title-group` catalogue (`specific-use="catalogue"`) | 5 / 5 | 4 / 4 | catalogue 242 / 246 | dropped when the printed one says the same (2382: same words, the catalogue capitalises); else kept as `alt-title[@alt-title-type="catalogue-translation"]` (0 in the 55) |
| `contrib` (string-name as printed) | 52 / 62 | 52 / 62 | print | |
| **`contrib-id`, `name-alternatives/name` (ar + en), `role`** | 0 | **39 contribs** | catalogue 100 / 700 ($9 authority, $g/$q Latin name, $e role) | attached when the printed name matches the catalogue's printed-on-the-page string or Arabic name; the printed string-name is kept inside `name-alternatives` |
| `contrib/email` | 4 / 7 | 4 / 7 | print | |
| `contrib/aff` (printed string) | 32 / 36 | 32 / 36 | print | catalogue records hold no affiliation |
| **`aff/institution[@content-type=dept\|orgname]`, `aff/country`, `aff/addr-line[city]`, `aff/email`** | 0 | **dept 16 / 21, orgname 22 / 25, country 7 / 7** | print: v3 `aff_parts` (exact substrings); older answers: a country list and institution words (كلية / قسم / Faculty → dept; جامعة / معهد / University → orgname) | tagged in place: the printed string is unchanged, its parts are elements. City and e-mail inside the aff: none printed that way in the 55 (e-mails sit in `contrib/email`) |
| `pub-date` (catalogue year, Gregorian / Hijri) | 55 / 68 | 55 / 69 | catalogue 260 $c/$m/$g, else print | |
| **`pub-date` with day and month as printed** | 0 | **1 / 1** | print «تاريخ النشر» | after the catalogue's (the edition reads the first); the DTD has no `specific-use` on pub-date |
| **`history/date[@date-type]`** (`received`, `reviewed`, `revised`, `accepted`, `published`, `online`; day / month / year, `@iso-8601-date`, `string-date` as printed) | 0 | **4 / 9** (2382, 1147, 1148, 0767) | print: v3 `history`; older answers: the labels on the first and last page (تاريخ الاستلام / الإستقبال / التحكيم / القبول / النشر، مقبول للنشر بتاريخ، Received, Accepted…) followed directly by a date | a body block that is only dates goes to the front as a printed front-matter block (2382, 1147): out of the article's running text, still drawn where printed |
| `volume`, `issue`, `fpage`, `lpage` | 35; 55 | same | catalogue 773 / 300, else print | |
| **`abstract` / `trans-abstract[@xml:lang]` (printed)** | 0 (20 abstract paragraphs in the body of 9 articles) | **8 + 6** (all 20 paragraphs; 0 left in the body) | print: blocks "abstract", or paragraphs whose lines the metadata lists as an abstract | `abstract-type="printed"`; the heading «الملخص:» / «Abstract:» above becomes its `title` (8). The paragraphs keep their ids: the Layout view still draws them where printed; `inkscript edition` prints them once, from the front |
| `abstract` (catalogue) | 0 | 0 | catalogue 520 (ar 569k, en 474k, Mandumah-written 184k) | **not copied, on purpose**: the printed abstract is the article's own text with ink; the catalogue's is often rewritten by Mandumah, and an edition would print two abstracts. Owner to decide whether to add it for articles that print none (marked `specific-use="catalogue"`) |
| **`kwd-group[@kwd-group-type="author-printed"]`** (title = the printed label, one `kwd` per keyword) | 0 (8 keywords paragraphs in the body) | **7 articles, 10 groups, 52 kwd** | print: "keywords" blocks; else the metadata's keywords strings (2) | printed before the catalogue's groups |
| `kwd-group` catalogue (`specific-use="catalogue"`: subject-terms, keywords) | 41 / 48 | 41 / 48 | catalogue 653, 692 | told apart by `specific-use` |
| `counts/page-count` | 55 | 55 | code | |
| `custom-meta` front-matter-block (printed bylines that are not one author, the dates block) | 29 / 31 | 29 / 33 | print | |
| `permissions` (`copyright-statement`, `license`) | 0 | 0 | — | **no catalogue field** (MARC 540 / 542 absent from the export); copyright lines printed on pages are rare and not asked for. Needs a rights source from Mandumah |
| `self-uri` | 0 | 0 | catalogue 856 $n (74k: the publisher's landing page) | not copied yet; cheap, from the catalogue |
| `funding-group` | 0 | 0 | print | not asked for; a funding sentence sits in acknowledgements, rare in this corpus |
| `author-notes` (corresponding author) | 0 | 0 | print | not asked for |
| `product` (the book a review is about) | 0 | 0 | print / catalogue 336 "Book Review" | not filled; a book review's reviewed book would go here |

## Body

| slot | before | now | source | notes |
|---|---|---|---|---|
| `sec` / `title` (nested by heading level) | 47 / 362 | 46 / 349 | print | 13 sections emptied by the moves above (an abstract or endnotes heading) are removed |
| `p` | 53 / 2363 | 54 / 2333 | print | |
| `list` / `list-item` | 24 / 512 | same | print | owner's rule (a): a list of the author's works is a list (v3 says so) |
| `disp-quote` | 4 / 9 | same | print (quote blocks) | v3 asks for every set-apart quotation / Quran verse; the 55 hold **no** paragraph that is only a Quran verse; 37 paragraphs quote a verse inline (﴿…﴾) |
| `named-content[@content-type=quran]` (inline Quran) | 0 | 0 | — | **not filled**: an inline verse often crosses line breaks (the `<target>` of each printed line), so wrapping it needs a span-aware pass; `inkscript edition` already reads it. Next candidate |
| `verse-group` / `verse-line` | 8 / 306 | same | print | |
| `table-wrap` (XHTML table) | 13 / 47 | same | print | |
| `fig` (`graphic` = scan crop, `caption`) | 12 / 51 | same | print | |
| `fig/alt-text` | 12 / 51 | same; `@xml:lang` set when not the article's language (32 English) | print (Gemini's description) | owner's decision (c): **v3 asks for Arabic and English**, stored as two `alt-text` (`xml:lang` on the one not in the article's language; JATS allows repeated alt-text). v2 answers have one (mostly English) |
| `fig/p[@content-type=text-in-figure]` | 6 / 26 | same | print | |
| `disp-formula` / `inline-formula` (MathML + LaTeX) | 6 / 77; 2 / 88 | same | print | |
| **`boxed-text`** | 0 | 0 (v2 has no type for it; v3 test: 3 in 0493) | print: v3 block type "boxed", one box = same "box" number on a page | the Layout view draws it as a tinted box |
| `xref[@ref-type=fn]` (note calls) | 30 / 483 | same | print | |
| `named-content[@content-type=sic]` | 45 / 212 | same | print (D30) | |
| `def-list`, `glossary`, `statement`, `code`, `chem-struct`, `supplementary-material`, `media` | 0 | 0 | — | not met in the 55 |

## Back matter

| slot | before | now | source | notes |
|---|---|---|---|---|
| `fn-group[@content-type=footnotes]/fn` | 31 / 547 (endnotes mixed in) | 26 / 347 | print | |
| **`fn-group[@content-type=endnotes]/fn`** | 0 | **6 / 200** (0355, 1769, 0767, 0781, 0049, …) | print: v2/v3 endnote blocks (ids en-…) | ids and calls unchanged (still linked); the heading above the run (هوامش البحث …) becomes the group's `title` (5) |
| `ref-list/ref/mixed-citation` | 10 / 186 | same | print | the printed reference, untouched |
| `element-citation` (parsed: person-group, year, article-title, source, volume, fpage…) | 0 | 0 | — | **plan only** (README "Structured references") |
| **`ack`** | 0 | 0 (no such heading in the 55) | print: a section headed شكر وتقدير / Acknowledgements | moved to `back`; `inkscript edition` now reads it after the body (one-line change in `src/inkscript/edition/model.py`) |
| **`app-group/app`** | 0 | 0 (none in the 55) | print: a section headed ملحق / الملاحق / Appendix | same |
| `notes[@notes-type=reader-fixes]`, `[suspected-misprints]` | 54 / 988; 45 / 212 | same | code | |
| `bio`, `sig-block` | 0 | 0 | — | a closing signature stays a paragraph `content-type="byline"` |

## How each moved element still reaches the ink

Every element moved out of the body keeps its `id`; the ALTO TextBlock's `xlink:href` still points at it, so the
Layout view (`views43.py`, which reads element kinds through `mread`) draws an abstract, a keywords line, a
translated title, an endnotes heading or a dates block where the page prints it. In the editions (`inkscript
edition`), abstracts, keywords and translated titles come from the front only, so nothing prints twice.

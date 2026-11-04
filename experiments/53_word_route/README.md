# Experiment 53: the Word route

**Question** (owner, approved 2026-10-22, run beside gate 1 without touching it). Many years of a journal exist only
as S3 `legacy/` PDFs (308,593 documents, PDF only, no Azure reading), which were made from the publishers' **Word
files** with LibreOffice + Amiri. The Word originals themselves are on this server
(`/home/adminuser/ai_data/{journals,ai_batch2,ai_batch3}/docs`, read only). Can we build the **same masters** (JATS
1.4, valid against the DTD) from them that the scan pipeline builds, cheaply, so that a journal can be complete?
Test case: journal 0130 مجلة الطفولة العربية, 2009–2016 (the years gate 1 cannot cover: they are not in the main
bucket).

**Answer.** Yes. In code only, with no model, **all 139 articles build and validate**.

The Word files are the journal's own typeset files. Every one of them numbers its first page with the catalogue's
first page. Their abstracts match the catalogue's word for word (90 of 90 Arabic abstracts overlap by 95% or more).
So we get the text with **no reading errors**, plus:
- real footnotes, linked to their calls;
- real tables (764 tables, 42k cells);
- Word's own list numbers;
- about 33 references an article, 97% of them split into fields.

What code cannot do well:
- heading roles and levels: about 10% of the headings are wrong (sentences that introduce a list, for example);
- reference fields: about half of them need a small fix;
- the enrich fields;
- **the printed page numbers.**

A **text-only** Gemini call for the uncertain parts would cost about **$0.01 (Flash) to $0.03 (Argon) an article
now**, and double that after the price rises. The scan route costs about $0.12–0.18.

There is one caution for the 308k legacy documents: a Word file can be **another article** under the stem's name. On
the 23 documents that also have a scan, 17 Word files were another text. A cheap test caught all 17: the Word file's
first page number differs from the catalogue's first page.

## Method ($0: no Gemini call; read-only outside this folder; no installs)

1. **Finding the files.**
   - Stems come from `marc.db` (`journal_code='0130'`, `type='بحوث ومقالات'`, years 2009–2016): **139**.
   - Exp 44's `ids_legacy.txt` holds **137** of them. 0130-011-043-003 and 0130-017-066-003 are in neither bucket.
   - The Word originals sit in flat folders, named `<stem>.doc` / `<stem>.docx`. All 139 have a file, all of them old
     binary `.doc`: 137 in `journals/docs`, 2 in `ai_batch2/docs`.
   - `inkscript fetch` has no `legacy/` prefix, so `fetch53.sh` copies `s3://mandumah-source-docs/legacy/<stem>/<stem>.pdf`
     with the aws CLI (read only, 107 MB).
   - The `.doc` files are copied to `out/doc/` and converted by `soffice` 24.2 (already installed; no new install)
     to `out/docx/`. It runs in batches of 20, at a peak of 0.49 GB and about 2 s a file.
2. **The Word structure.**
   - [inspect53.py](inspect53.py) → `out/inspect.json`;
   - [docx53.py](docx53.py) is the reader. It handles paragraphs, runs (bold, italic, superscript, the complex-script
     font and size), Word's numbering (`numbering.xml` → the label Word draws), footnotes, tables (`gridSpan` /
     `vMerge`), images, text boxes (LibreOffice's duplicate `mc:Fallback` copy is dropped), headers, and
     `pgNumType` / `pgSz`.
3. **Masters by code**: [build53.py](build53.py).
   - **Front matter.** The catalogue is read through `inkscript.enrich.catalogue`, imported, not edited. It gives the
     title, the people with authority ids, the journal, the date, the volume / issue and the pages. Beside it go the
     file's first lines (D33):
     - the printed title, kept as `alt-title[@alt-title-type="printed"]` when its words differ, with the change logged
       in `<stem>.metachanges.json`;
     - the printed names, as `string-name[@specific-use="printed-on-the-page"]`;
     - the affiliations under each name (columns split at tabs or runs of spaces, or at honorifics);
     - the rubric;
     - abstracts and keywords, found by experiment 43's `jats43` regexes;
     - the English title and abstract, wherever they sit;
     - any other printed line, kept as a `front-matter-block`.
   - **Body**:
     - headings from the heading font (PT Bold Heading …), all-bold short lines, short colon lines and Word heading
       styles;
     - levels from alignment, size and numbering;
     - lists from Word's numbering;
     - footnotes as `fn` + `xref`;
     - notes called from the front → `author-notes`;
     - tables as `table-wrap`, with the «جدول (n)» caption and the * / المصدر notes in `table-wrap-foot`;
     - figures with their media copied;
     - acknowledgements and appendices.
   - **References**:
     - one `ref` / `mixed-citation` per paragraph after a references heading;
     - fields by a code parser for APA and comma styles, written by experiment 43's `refs43.citation`. It was
       imported, not edited: `sys.dont_write_bytecode`, so nothing is written into experiment 43's folder. It keeps
       a value only if it is a substring of the printed reference.
   - **Source marks**: `custom-meta` text-source "publisher's Word file (no scan) …", structure-source,
     metadata-source, printed journal and issue (from the running head), the Word page numbering, and "ink".
   - **Validation**: `inkscript.enrich.schemas.validate_jats`, the same JATS 1.4 Archiving MathML3 DTD the masters
     use.
   - **What replaces ALTO**: `<stem>.pdfmap.json`. For each block it holds the page and box in the legacy PDF (found
     by text after dropping the stray Latin letters that LibreOffice's justification leaves inside Arabic words) and
     an estimated printed page.
4. **Measures**:
   - [refcompare53.py](refcompare53.py): references, headings, notes and tables per article, against the scan
     route's v3.3 masters of EduSearch research articles, 2000 or later (gate 1 has no 0130 masters yet; its first
     raw answers hold the first 10 pages only);
   - [abscheck53.py](abscheck53.py): the catalogue's abstract against the Word file's;
   - [compare53.py](compare53.py): the 23 documents that have a scan, a legacy PDF and a Word file (Word text
     against Azure's reading of the print, page numbering, page estimates; `--breaks` uses Word's own
     `lastRenderedPageBreak`);
   - [price53.py](price53.py): the cost;
   - [outline53.py](outline53.py): an outline used for the hand look.

Commands (each process ≤ 0.4 GB; one at a time):
```
experiments/53_word_route/fetch53.sh                                  # legacy PDFs (read only)
.venv/bin/python experiments/53_word_route/inspect53.py
.venv/bin/python experiments/53_word_route/build53.py [stem ...]      # ~3 min for the 139
.venv/bin/python experiments/53_word_route/refcompare53.py; …/abscheck53.py; …/price53.py
.venv/bin/python experiments/53_word_route/compare53.py [--breaks]    # needs out/ground/ (23 docs)
```

## Results (2026-10-22)

**Files.**

| | count |
|---|---|
| 0130 research records 2009–2016 | 139 (19, 18, 19, 18, 17, 14, 17, 17 by year) |
| with a Word original | **139** (all `.doc`; none `.docx`) |
| with a legacy PDF | 137 |
| both / Word only / neither | 137 / 2 / 0 |
| built / valid against the DTD | **139 / 139** |

The legacy PDFs are born digital: LibreOffice 24.2, made 2026-09-03, US Letter pages. Their text layer is good, but
justified lines carry stray Latin letters inside Arabic words, as in «معرفZة» or «الفونولAوجي» (the kashida
glyphs). The masters take the Word text, so this does not reach them; the map to the PDF ignores those letters.

**What the Word files hold** (`inspect53.py`):
- Styles are almost all "Normal": there are no heading styles, and outline levels appear in 4 files only.
- Headings are told apart by font (PT Bold Heading), bold, size and centring.
- Real footnotes: 98 in 38 files. There are no endnotes, and no typed «الهوامش» sections with numbered notes (two
  headings carry that name but have no numbered notes under them).
- References are APA-style lists, one paragraph each.
- Real tables: 797 in 100 files.
- Auto-numbered paragraphs: 6,205.
- Pictures: 261 drawings in 56 files. Text boxes: 178 in 10 files.
- Body text in Traditional Arabic; Times New Roman for Latin.
- The running head gives «مجلة الطفولة العربية … العدد الثامن والثلاثون».

**What the code builds**, over 139 articles:

| part | result |
|---|---|
| title | found in the file's first lines in 137 / 139 (122 every word). Matches the catalogue exactly in 83; the same words spelt as printed in 38 (the catalogue drops hamzas: «الاطفال»), so the printed spelling is used and the catalogue's kept as alt-title; other words in 16, kept as printed alt-title and logged (Word misprints such as «العرفية» for «المعرفية» or «تدير» for «تقدير», a Symbol-font bracket «÷نقاط الدخول×», catalogue rewordings) |
| people | 200 contribs, **all 200 with Mandumah authority ids**; the printed name found and attached to 151; affiliations tagged on 141 |
| abstracts | printed Arabic 90, English 85 (8 at the end of the article); the catalogue's abstract stands in where none is printed (24) |
| headings | 3,676 (26 / article, median 22). Signals: heading font 1,863, all-bold 1,555, Word style 187, colon 61, centring 10. Levels 1/2/3: 646 / 2,635 / 395 |
| lists | 1,071 lists, 4,368 items with Word's own labels |
| footnotes | all **98** Word notes written: 79 in the body's notes, 19 author notes called from the title or byline. **95 calls linked** (76 in the body, 19 in the front); 3 notes have no call |
| tables | **764** real tables (plus 33 byline tables read as lines), 42,155 cells with col/rowspans; **629 captioned** (82%), 117 table notes |
| figures | 178 (media copied); only 41 captioned |
| references | **4,613** in 118 articles with a list (the other 21 are reports and book reviews); **39 per article** (median 38); 4,465 with an `element-citation` (96.8%), 4,408 with author + year + title (95.6%); types: book 2,394, journal 1,250, thesis 277, web 123, other 421 |
| the legacy PDF map | 23,932 of 25,031 blocks found on their legacy page (95.6%; whole span 72.8%) |
| time and memory | 188 s for the 139 (1.4 s an article, including the PDF map); peak ~0.4 GB |

**References against the scan route.** The scan route's v3.3 masters of EduSearch research articles (59 articles,
2000 or later, none of them 0130) have 19.8 references an article that has a list. Gate 1 has no 0130 masters yet.
The Word route gives 39.1. This is not over-counting: 0130 is a psychology / education journal with long APA lists.
Before two fixes, 439 entries had no year; tables and stray paragraphs after a list had become references, and both
causes are fixed. The 156 left without a year are mostly real web entries or lists of institutions.

**The hand look.**

Five articles were read beside their legacy PDF pages (`out/look/*.png`) and outlines:

| article | verdict | what was wrong |
|---|---|---|
| 0130-010-039-001 | **minor** | the English byline was swallowed into the English title (fixed); typed «_» bullets left as paragraphs |
| 0130-012-045-001 | **minor** | two list lead-ins became headings; the terms under «مصطلحات البحث» one level too high (levels fixed for «أولاً / ثانياً» parts) |
| 0130-013-049-001 | **serious → minor** | the author was not matched (the catalogue's surname is «محمد»; fixed); 83 headings, some of them lead-ins, a poem title and restarted ordinal series, so the outline misleads in places |
| 0130-015-060-003 | **minor** | the second title line and the author missed (the joined «و» in «وبعض»; fixed); 4 tables without their caption |
| 0130-016-064-003 | **minor** | lead-in sentences as headings; a URL split from its reference; the English byline kept as a printed block |

The text itself was right in all five, because the Word text *is* what the legacy PDF shows. Footnotes and tables
were right.

A random sample of **60 headings**: 54 are headings; 6 are not (two lead-ins, a quotation, a source line, a reference
left in the body, a book-review «دار النشر:» line). About 1 in 10 levels looks wrong.

A random sample of **40 references** (before the last parser fix):
- **18 right**;
- **17 minor**: a missing university for a thesis, an unsplit place or publisher, a subtitle lost, a journal not
  recognised in comma style;
- **5 wrong**: 3 printed quotes in place of brackets («"2011"») and 1 Hijri year with no هـ, all fixed since; 1 run-on
  «Family Relations 44:170-176».

**What code cannot do, and Gemini would have to:**
- heading roles where the signals disagree (lead-ins, quotations, poem titles) and levels in deep or restarted
  outlines (about 10%);
- reference fields beyond the APA patterns: theses, conference papers, comma styles, translators and editors, and
  references split over two paragraphs;
- document type: all 139 are catalogued «بحوث ومقالات», yet some are reports and book reviews, whose «دار النشر /
  سنة النشر» lines should become a reviewed-book `product`;
- the English bylines matched to people (445 printed lines kept as blocks);
- figure kinds and the text inside the 178 pictures (an image call, not a text one);
- the rest of exp 51's enrich fields (corresponding author, conference, translation, note kinds).

**The cost of the Gemini step** (`price53.py`; no calls):
- Tokens follow the project's estimating rule: characters ÷ 2.6, input × 1.117.
- The text is the real text of the 139 articles: on average 46k characters and 33 references an article, with about
  15 weak-signal headings and run-in heads.
- References are priced at 239 characters of JSON each, the mean of exp 43's 1,718 parsed ones.
- *Lean* sends a short text-only prompt with only the uncertain blocks (with neighbours), the captions, the front
  lines and the reference list. *Full* sends a v3.5b-sized prompt with the whole article.

| | tokens in / out | Argon Batch now | Argon from 1 Dec | Flash 3.8 Batch now | Flash from 1 Jan 2027 |
|---|---|---|---|---|---|
| lean | 9.2k / 3.7k | **$0.028** ($28 per 1,000) | $0.056 | **$0.010** | $0.021 |
| full | 30k / 4.0k | $0.050 | $0.100 | $0.019 | $0.038 |
| scan route (gate 1) | ~29k in a 10-page chunk / 6.2k out | **$0.18** expected (dry run, 0130 2010–2025, 19 pp an article); $0.06 per 10-page chunk billed; ~$0.12 the owner's figure | ×2 | — | — |

For the 308,593 legacy documents:
- the lean call costs **$8.6k** with Argon now, $17k after 1 December, and $3.2–6.5k with Flash;
- the scan route would cost about $37–55k now if they were scans;
- the code part costs nothing but time: about 2 s a `.doc` conversion (167k files) and 1.4 s a build (303k), so about
  210 process-hours in all, or about 3 days on 3 workers off-peak.

**The cautions, measured.**

1. **Does the Word text differ from the print?**
   - **For 0130, the evidence says no.** All 139 files number their first page with the catalogue's first page (they
     are the typeset files). The catalogue's Arabic abstracts, typed from the published article, match the Word
     abstracts word for word: median overlap 1.000, 90 of 90 at 95% or more. The 2 below are English-language
     articles, where the catalogue holds the Arabic abstract.
   - **On the 23 documents that also have a scan** (Azure's reading of the print):
     - in the 6 where the Word file's first page equals the catalogue's, 92–97% of printed words are in the Word
       file and 95–99% of Word words are in print. The remainder is OCR noise, running heads and page numbers. One
       exception, 1644-000-009-004, is at 65%: the print has more;
     - in the **17 where they differ** (16 of journal 2044, 1 of 2253), the Word file is **another article**: overlap
       0.11–0.47, which is just common words. The first-page test caught all 17 and raised no false alarm on the 6.
       The legacy PDFs of those stems are made from the same wrong files.
2. **Printed page numbers.** The Word file gives the first printed page exactly (139 of 139). It does not give the
   other pages:
   - The legacy PDF has 1.42× the print's pages (median; 4,143 against 3,006), because it is set in Amiri on Letter
     pages, and its footers number pages from the first printed page. Legacy page 22 of 0130-010-039-001 says «29»,
     though in print that text is on about page 23. **A reader citing the legacy PDF's pages cites wrong pages.**
   - On the 23 ground documents, estimating the printed page of a scan page's first line works as follows:
     - from its share of the text: right 11–41% of the time (within one page 32–88%);
     - from its legacy-PDF page scaled to the print: right 4–26% (within one 22–94%);
     - from Word's own page marks (`lastRenderedPageBreak`, in native `.docx` only; 0130's are `.doc`): 13 of 17
       right on the best document and 1 of 64 on the worst (within one page 17/17 down to 3/64).

     These ranges are over the 5 good ground documents where lines were found.
   - So a cited «ص» into these articles, and our own `fpage` for anything but the first page, can only be an
     estimate. The pdfmap gives a `printed_page_est` per block and says so.
3. **Where the Word route is weaker than the scan route:**
   - no printed pagination (above);
   - no ink: the legacy PDF is a re-setting, not the print, so "show me the ink" becomes "show me the place in the
     legacy PDF" (95.6% of blocks found);
   - the file under a stem can be another article (17 of 23 on the ground set; cheap to detect);
   - characters lost or re-coded when the old `.doc` was converted: «(?)» marks in 11 articles, Symbol-font brackets
     in 2;
   - any last-minute change made in print and not in Word is invisible; for 0130 we found none;
   - pictures are only pictures, and 77% of them have no caption linked;
   - the scan route's judgment about the page (show-through, stamps, handwriting) does not apply, which is mostly a
     relief.
4. **Where it is stronger:**
   - **no reading errors at all**: the text, diacritics, digits and table numbers are the author's own;
   - footnotes are linked by Word itself;
   - tables come with their real cells;
   - italics in references point to the source.

## What it means

- **For gate 2.** Wherever a journal's missing years are in `legacy/`, the Word route can complete it: here 0130
  2009–2016, and the same files exist for 2020–2022. The masters come out in the same JATS, marked as coming from a
  Word file. Bridges and citations can use them at once. The one field they lack is exact page numbers for pages
  after the first.
- **For the 308k legacy set**:
  - 302,961 of the 308,593 stems (98.2%) have a Word original: 136k `.docx`, 167k `.doc` only (`out/word_files_all.txt`);
  - the first-page test should run on all of them before anything else;
  - native `.docx` files also carry Word's page marks, so their page estimates will be better than 0130's;
  - building costs only time; a lean text-only call costs ~$9k with Argon now, ~$3k with Flash.

## What waits for the owner

1. **Page numbers.** Choose one:
   - accept estimated pages, flagged;
   - find the print (scans or the journal's PDFs) for the years cited by page;
   - allow a test with the original fonts: Traditional Arabic and PT Bold Heading are Windows / commercial fonts and
     are not on the server; installing them is an install, so this needs your permission. The test would re-render
     the 6 good ground documents and measure page breaks.
2. **A paid text-only test after gate 1.** About 20 articles, lean call, Flash against Argon, under $1, to measure
   what the model fixes in headings and references.
3. **Gate 2 and the 308k.** Whether to run the first-page test (free) and the code build over the whole legacy set,
   and what to do with stems whose Word file is another article (the 17 here also have scans; the legacy PDF is
   wrong for them).
4. The AI-Search legacy corpus serves those 17 stems with another article's text. Nothing here was changed; it is
   for the AI-Search owner to decide.

Outputs (gitignored, private data, on this server only), all under `out/`:
- `masters/` (JATS, metachanges, pdfmap, media);
- `build.json` and `build.log`;
- `inspect.json`, `compare.json`, `compare_breaks.json`, `abscheck.json`, `refcompare.json`, `price.json`;
- `gate1_raw_counts.json`;
- `look/` (legacy pages used in the hand look);
- `doc/`, `docx/`, `legacy_pdf/`, `ground/`.

**Owner's decision (2026-10-22, D36):** page numbers in Word-route articles are estimates, flagged as estimates
(option a). The first printed page and the catalogue's range stay as fact; the scan route is preferred wherever a scan
exists. Next for this route, after gate 1: a paid text-only test of about 20 articles (under $1).

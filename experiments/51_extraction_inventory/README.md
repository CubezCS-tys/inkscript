# Experiment 51: the "extract everything" inventory

**Question** (owner, 2026-10-22). A Gemini read of a million articles costs about $106k, and Gemini's prices double
on 1 December. So each article should be read **once**, and that read should take everything worth having. What is
worth extracting from a scanned article? Which of those things need the model's eyes or judgment and must go into the
one big read (**group A**)? Which can our code derive later, for free, from Azure's words and Gemini's structure, which
we keep forever (**group B**)? And where does the live prompt v3.3 stand on each one today?

Terms follow the glossary. A **reference** is what this article cites (outgoing, WoS "Cited References", CR). A
**citation** is another article citing this one (incoming).

## Method ($0, no model calls, read-only outside this folder)

1. Read what the pipeline asks for and what it writes:
   - the prompt (`43_rehearsal/prompt43.py`, v3.3 live);
   - the JATS slots (`jats_coverage.md`);
   - the code that adds things (`rules43`, `masters43`, `jats43`, `meta43`, `refs43`);
   - the platform (`47_platform_v2/DESIGN.md`);
   - what linking lacked (`48_linking_probe`);
   - the faithful-text rules (D30–D35).
2. Wrote the list of everything worth extracting. It was drawn up the way Web of Science, JATS/PMC, Crossref, ORCID,
   ROR, OpenAlex and an Arabic scholarly edition would each see an article.
3. Counted real occurrences in the 600 masters (`43_rehearsal/out/v33_300_final/masters` and
   `.../v33_300b_fix3/masters`):
   - [count_masters.py](count_masters.py): about 90 regular expressions over the printed text of every block, each
     tagged with its context (front, heading, body, footnote, endnote, reference, table, figure, caption, abstract),
     plus counts of JATS elements. It writes `out/master_counts.json`.
   - [count_answers.py](count_answers.py): what the 600 v3.3 answers hold (metadata keys, block types, the fields of
     each parsed work). It writes `out/answer_counts.json`.
   - [count_alto.py](count_alto.py): the ALTO roles (running heads, page numbers, other article, show-through,
     ornaments). It writes `out/alto_counts.json`.
   - [snip.py](snip.py): pulls up real snippets for a pattern, which is how the examples were checked.
4. [build_inventory.py](build_inventory.py) writes [inventory.json](inventory.json). The items are written by hand.
   Their evidence counts and examples are filled in from the three count files.
5. [build_page.py](build_page.py) writes `out/inventory.html`, the owner's page. A copy is served by the Desk at
   http://127.0.0.1:8004/inventory/ (local only: the examples are Mandumah's text).

Each item has these fields:
- `group`, `field`;
- `why` (Web-of-Science index, RAG, reader, corrections, exports);
- `wos_tag`, `jats`;
- `needs` (A or B);
- `today` (extracted-well, extracted-partly, kept-as-text-only, not-extracted);
- `evidence`, `example` (stem, page, printed text of at most 200 characters), `note`;
- `prompt_priority`, for group-A gaps only.

Counts read "A articles / N", meaning A of the 600 articles and N occurrences.

**Limits.** The counts are regular expressions over the text. They are good for "how often does this exist", but they
are not a precision study: hadith grading and some reference patterns have false hits, which the item notes say.
"Today" is judged from the prompt, the code and the counts, not from a hand check of each value.

## Result (2026-10-22)

**235 items in 12 groups.**

| state today | all | group A (eyes / judgment) | group B (code, later) |
|---|---|---|---|
| extracted well | 88 | 73 | 15 |
| extracted partly | 47 | 34 | 13 |
| kept as text only | 43 | 3 | 40 |
| not extracted | 57 | 39 | 18 |
| **total** | **235** | **149** | **86** |

By group (well / partly / text only / not):

| group | items | well | partly | text only | not |
|---|---|---|---|---|---|
| metadata | 32 | 17 | 4 | 6 | 5 |
| authors-and-affiliations | 25 | 7 | 10 | 1 | 7 |
| references | 35 | 13 | 8 | 5 | 9 |
| body-structure | 25 | 9 | 2 | 10 | 4 |
| Arabic-and-Islamic | 23 | 8 | 2 | 9 | 4 |
| tables-figures-math | 20 | 7 | 6 | 2 | 5 |
| document-level | 17 | 4 | 4 | 1 | 8 |
| page-furniture | 14 | 7 | 5 | 0 | 2 |
| RAG-specific | 14 | 9 | 3 | 0 | 2 |
| visual-and-styling | 13 | 2 | 3 | 0 | 8 |
| rights-and-funding | 10 | 1 | 0 | 7 | 2 |
| notes | 7 | 4 | 0 | 2 | 1 |

What v3.3 already captures well is the core of the article:
- title, translated titles, authors, e-mails, affiliations split into parts;
- the history dates;
- abstracts and keywords in each language;
- sections, lists, quotations, verse with its hemistichs;
- footnotes and endnotes with their calls;
- tables with spans, figures with Arabic and English descriptions, equations;
- every reference and every work cited in a note, with author, title, source, year, volume, issue, pages, publisher,
  place, series and DOI;
- the page furniture and the other article on a shared page, kept out of the text.

### Group A, missing or partial: the list to add to the prompt before the big run

There are 76 group-A gaps: 39 not extracted, 34 partly, 3 kept as text only. Each has a priority:

- **1** (37 items): add before the big run. They are cheap keys or enums with high value.
- **2** (17 items): add if a small paid test shows they are cheap and reliable.
- **3** (22 items): leave. They are rare here, expensive in output, or code can do them.

**Priority 1, in plain words** (the prompt lines to write):

1. **What kind of document this is**: research, review, editorial, book review, report, conference paper, thesis
   summary, interview, news, translation, obituary, poem, or issue front matter (contents, editorial board).
   Today every one of the 600 masters says `research-article`. A review flag comes with it, for the RAG.
2. **About the article itself:**
   - Conference papers: the conference's name, place and dates. Today these land in `subtitle`, e.g. «الكويت ٢٠
     -٢٥ نوفمبر ١٩٧٦».
   - Thesis summaries: degree, university and year.
   - Book reviews: the reviewed book.
   - Translated articles: the original title, author and source.
   - Articles in a series: the part number, e.g. «المدارس النموذجية فى الميزان (٤)».
3. **Authors:**
   - The corresponding-author mark (printed in 10 articles; not asked).
   - ORCID and other ids (one bare ORCID in the 600; common after 2020).
   - A Latin byline marked as the same person as an Arabic author (`same_as`). Experiment 48 found these doubled as
     extra authors in 11 articles.
   - Several affiliations per author, matched through the superscripts.
   - A `faculty` key apart from `department`. Today «كلية التربية» goes into department.
   - The starred author note on page 1 (79 articles) recognised as an author note, not a footnote.
4. **The parts of each cited work that are missing today** (the biggest gap, and where experiment 48 found linking
   fails):
   - the editor of the text (تحقيق / تح: 89 articles, 438 uses);
   - the translator (75 articles);
   - the edition (ط٢: 101 articles, 641);
   - the author's death date (ت ٧٥١هـ: 12 articles, 73), which tells classical authors apart;
   - the calendar of each year (Hijri years in 93 articles, 876);
   - the cited page kept apart from the work's page range (ص: 218 articles, 3,555);
   - the access date of web sources (28 articles);
   - a thesis's degree and university;
   - a conference's name and place;
   - a manuscript's library, shelfmark and folio (21 articles). Manuscript, conference, law, Quran and hadith also
     need types of their own; today they fall into `other`.
5. **Notes under tables and figures:**
   - Table notes (* p < 0.05, ملاحظة) and source lines (المصدر: … in 21 articles, 136 lines) as their own block,
     tied to the table. Today they become paragraphs, and `table-wrap-foot` is empty in all 600.
   - Each note's kind: the author's, the translator's or the editor's.
6. **Each figure's kind**: chart, photograph, map, diagram, manuscript facsimile, logo, stamp, portrait, cartoon,
   table-as-image. Today there is only a free-text description, so no one can ask for "every manuscript facsimile in
   the archive".
7. **On the page:**
   - Library stamps, readers' handwriting and marginalia, kept apart from the text.
   - Scan problems: a cut-off edge, blur, a missing, doubled or out-of-order page.
8. **Rules for the text that only eyes can apply:**
   - An honorific ligature (ﷺ ﷻ) printed as a symbol is fixed to its Unicode glyph.
   - v3.4's two content lines: inline formulas inside Arabic sentences, and letters Azure drops in fully vowelled
     lines.

**Priority 2** (test first):
- italic, bold, superscript, subscript as spans (Azure gives no styles: 0 in the 600);
- the publisher as printed;
- contributor roles mapped to a fixed list;
- equal contribution and deceased marks;
- author bio or photo;
- the closing signature;
- an article that starts or ends outside the scan;
- glossaries, as definition lists;
- jumps to a non-adjacent page («بقية ص»);
- interview turns;
- advertisements as a block type;
- archival documents cited;
- the voice of a passage (the author's own claim, or a quotation).

Styling is the costly one. It should be scoped (for example, italics only in references) and measured on a small paid
test before it goes into the big read.

**Priority 3** (leave):
- underline, small caps, colour;
- chart data, sub-figures, rotated tables, chemistry, code;
- table and figure numbers as labels (code);
- joint and special issues, month names (code);
- reprints, epigraphs, drop caps, logos, signatures;
- language per block (code can detect it).

### Group B: what can wait for code (86 items)

Each is already in what we store: Azure's words with their boxes, Gemini's block types, and the parsed works.

- **Metadata from the printed text**: the article DOI (26 articles print one), ISSN (6), copyright and licence lines
  (18), JEL and other classification codes (7), the "how to cite this article" box (4), ISBN, e-locator, Hijri and
  Gregorian conversion.
- **Funding, conflicts of interest, ethics, data availability**: almost absent in this archive (no real funding
  statement found in the 600). When present they are plain sentences.
- **Section roles from headings**: introduction (174 articles), problem and questions (77), previous studies (36),
  method (88), results (103), conclusion (122), recommendations (72), definitions (16). Section numbering labels
  (219 articles).
- **Linking inside the article**:
  - in-text author-year citations to the reference list (89 articles; `xref bibr` 0 today);
  - numbered [12] citations (11 articles);
  - back references «المرجع السابق» / «نفسه» (91 articles) and ibid. / op. cit. (43), which platform v2 already
    resolves;
  - mentions of tables and figures in the text.
- **Arabic and Islamic**:
  - inline Quran ﴿…﴾ (28 articles, 268) and printed sura:aya references (21), to match against a Quran text;
  - hadith sources and numbers;
  - verse metre;
  - Hijri dates and death dates in the text;
  - honorific phrases, foreign words in Latin script (205 articles);
  - digits and tatweel folded for search.
- **For the RAG**: the section path, the prior-studies flag, tables as text rows, passage language and trust,
  statistics (51 articles), people, places and organisations named in the text.
- **Name parts and ids**: the parts of an Arabic name, Mandumah authority ids, ROR and OpenAlex institution ids,
  ISO country codes, an author's position or rank split out of the affiliation string (166 articles).

### Surprising

- **Azure's Persian look-alike letters in the masters.** 190 of the 600 articles hold words written with ی
  (U+06CC) or ک (U+06A9) in place of Arabic ي / ى / ك: 1,889 words, e.g. «المدمنیین الرسمی» (0013 p2).
  `src/inkscript/text.py` already has `fold_letters` for exactly this, but experiments 41 and 43 do not call it. So
  search for «الرسمي» misses «الرسمی», and Gemini's metadata (which writes ي) disagrees letter by letter with the
  ALTO. This is free to fix in code (group B), but it touches D30 (the text as printed), so it is the owner's call.
- **Every master is `article-type="research-article"`.** The 600 include news pages, a book's documents, thesis
  summaries and translations.
- **Rights and funding are almost empty in this archive.** No real funding statement and no conflict-of-interest
  statement were found in the 600. Three articles have acknowledgements and three an ethics statement. These Web of
  Science fields (FU, FX) will be empty for most of Mandumah, so they are not worth prompt tokens.
- **ORCID is printed in 1 article of the 600**, and e-mails in 64. Corresponding-author marks are in 10.
- **The reference gaps are mostly fields the model already reads but has no key for:** editor, edition, translator,
  death date, cited page. Adding them to W costs a few output tokens per work. These are the fields experiment 48
  found missing.

## What it changed

Nothing in `src/` or experiment 43. This is an inventory. Proposed for the owner's decision:
- the priority-1 prompt additions above, as a prompt v3.5 candidate, to be tested on a small paid set before the
  big run;
- folding ی/ک in code (owner's call under D30).

## In the platform database (2026-10-22)

Experiment 47's field audit (`../47_platform_v2/audit_fields47.py` → `out/field_audit.md`, `.json`) counts each item's
slot in the 726 masters (the 600 `_lettersfix` and journal 0130's 126) and says where platform v2 holds it. `homes.py`
reads it: `out/homes.json` gains `in_platform`, `platform_where` and `masters_filled` per item, and `out/homes.html` a
column "In the platform db" (copied to `../49_correction_desk/web/public/inventory/homes.html`). **124 items have a
filled slot and all 124 are in the platform database**; the other 111 have no filled slot in any master yet
("slot empty") or no slot of their own.

## Files

- `inventory.json`: the 235 items.
- `count_masters.py`, `count_answers.py`, `count_alto.py`, `snip.py`, `build_inventory.py`, `build_page.py`.
- `out/master_counts.json`, `out/answer_counts.json`, `out/alto_counts.json`: the counts, with examples (gitignored).
- `out/inventory.html`: the owner's page; copy at `../49_correction_desk/web/public/inventory/index.html`.
- `progress.md`: the working log.

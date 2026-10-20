# Audit: citations in platform.db (experiment 47)

Area: `works`, `work_authors`, `back_references`, `citation_links`, `link_checks`, `link_runs`
(built by `experiments/46_platform_db/parse46.py` and `link46.py`). Read-only inspection of
`/home/yassine/data/platform/platform.db` and `/home/yassine/data/marc/marc.db` on 2026-10-20. No paid calls.
Every number below came from a query against those files on that date.

## What is there today

| table | rows | what a row is |
|---|---|---|
| works | 4,789 (all run v33_300_final: 2,742 from notes in 127 articles, 2,047 from reference lists in 85) | one `<element-citation>`: a *place* where something is cited, stored as if it were the cited work |
| work_authors | 4,638 (3,334 distinct name keys) | one author of that place |
| back_references | 544 (80 from v2_55, 464 from v33_300_final) | one note holding «المرجع السابق / نفسه / ibid. / op. cit.» |
| citation_links | 790 | 304 backref→work, 478 work→catalogue, 6 work→article |
| link_checks | 54 | agent-46 hand checks: 41 right, 6 wrong, 3 near, 4 withheld-ok |
| link_runs | 354 | one timestamp per article |

## Problems

### P1. `works` mixes two things: a mention and a work (high)
A row is created for every parsed citation in every note, so a book cited 34 times in one article is 34 "works".
- 556 groups of rows in the same article with the same first-author key and title hold 1,574 rows. **1,018 of 4,789
  "works" (21%) are repeats in the same article**, e.g. `1875-005-020-001` «الديوان» ×34, `0117-043-170-003`
  «تلخيص الخطابة» ×28, `1693-000-012-015` الجرجاني «أسرار البلاغة» ×18 (once in the reference list `r2`, 17 times in notes).
- Mention-level facts sit in work columns: in 2,104 note-origin rows, `fpage`/`page_range` is the **page cited**
  («ص: ٨» in `fn-p11-1` becomes `fpage=8`), not the book's page range. `printed` is the whole note text, not the
  citation's own span. The cited volume («ج ١») has no column.
- Across articles nothing is grouped: «لسان العرب» is split into 5 articles under `ابن منظور` and 3 more with an
  empty author key. Only 47 title+author groups span more than one article (108 rows). 1,012 rows (21%) have no
  `first_author_key`, mostly short forms («الديوان», «المسند»), which never group with their full citation.

Result: "times cited" cannot be computed. Counting `citation_links` per catalogue record counts repeats inside one
article (18 of 94 linked records have more than one link, and 17 of those come from a single article).

### P2. Back references resolve to *a* row, often not the first full citation (high)
`link46.link_backrefs` resolves `op. cit.` to the **most recent** earlier work by that author (`reversed(seen)`), and
`ibid.` to `last`. Chains do collapse, because a backref's target is always a `works` row and never another backref.
But since the repeats in P1 are separate rows, **128 of 306 backref targets are a repeat** of a citation printed
earlier in the same article, not the first full citation the owner asked for.
- Resolution goes into `citation_links` as fake `backref → work` links (304 rows, `target_kind='work'`). That is
  resolution inside one article, not a link, and the owner ruled it out.
- Cardinality: `parse46` keeps only the first marker in a note (`BACKREF.search`). 23 notes hold two or more markers
  (e.g. «المرجع نفسه … وانظر: المصدر السابق»), and the second is lost. The id `stem|note_id` cannot hold two.
- 47 notes have both a back reference and parsed works (`has_parsed=1`). They are modelled as one or the other, not
  as several mentions in reading order.
- The 80 back references from v2_55 (54 current articles) can never resolve, because v2_55 masters have no parsed
  citations (`n_works = 0` for all 54). They sit unresolved with no reason recorded. 238 of 544 back references
  have no resolution at all, and none of them says why.
- Precision is unknown at scale. Agent hand checks of backref links: 19 right, 6 wrong. The wrong ones were an
  author with two works, «Part II» resolved to Part I, ibid. after an unparsed court judgment, one chapter against
  another of the same book, and two long notes matched by chance title words.

### P3. `citation_links` mixes real links, relations and rejected candidates (high)
| method | rows | best | what it really is |
|---|---|---|---|
| backref-* | 306 | 1 | resolution inside the article (P2), not a link |
| catalogue-fts | 114 | 1 | real link → catalogue record |
| catalogue-about | 175 | 0 | relation: the record *studies* the cited book |
| catalogue-review-of | 83 | 0 | relation: the record *reviews* the cited book (catalogue type عروض كتب) |
| catalogue-part-of | 43 | 0 | relation: part or edition |
| catalogue-title-only | 63 | 0 | rejected candidate (title only, author and year not confirmed) |
| article-title-only | 6 | 0 | rejected candidate → archive article |

So **114 of 790 rows (14%) are real accepted links**. There are no accepted links to archive articles at all.
`from_kind/target_kind/from_id/target_id` as TEXT is a polymorphic key, and the typed FK columns repeat it.
Who asserted a link is always `source='link46'`. There is no way for a person or the judge to assert or reject one.

### P4. The catalogue key is wrong (high, breaks at the next MARC export)
`target_id`/`target_rec` store `records.rec`, the **order of the record in the XML file** (marc.db's own comment).
The stable key 999$c lives only inside `evidence` JSON (`target_rec=1001857`, `c999=1079058`). A re-export of the
catalogue renumbers `rec`, and every catalogue link then points at a different record without any error.

### P5. Book citations have nowhere to land (high, the biggest gap in the design)
`marc.db` holds articles (بحوث ومقالات 1,219,026), theses (رسائل جامعية 169,600), conference papers (59,954),
literary texts, book **reviews** (عروض كتب 27,423) and editorials. **It holds no book records.** Of 3,224 cited
books, 6 have an accepted link. Journals do far better (76 of 856), and theses 22 of 154. Most of the citation index
for Arabic humanities will be books that exist only as cited works, so the cited work has to be a first-class entity
with its own times-cited count (Web of Science's "cited reference" index). Today it is not an entity at all.
The 83 review-of and 175 about rows already give a book something no index has: "reviewed in / studied in" Mandumah
records. They are stored as rejected links, though.

### P6. Evidence does not reach the ink (medium)
A works row carries `page` only. The masters do place each note line on the page: `<target id="p11b2l1"/>` inside
`<fn>` (8,446 note lines in v33_300_final). Neither `notes` nor `works` keeps them, so a citation cannot be shown
as its crop of the scan. Those same line ids are where the quality signals live:
- **1,047 Azure-misreading fixes and 153 suspected misprints (D30) fall on note lines**, i.e. inside citations.
  Nothing connects them to the citation. A title used for matching may carry a fixed misreading or a printed misprint.
  Both readings should be tried, and the link should say which one matched.
- `flags.lines` uses a different scheme (`"2:1"`, page:line), so 0 of 876 flags join to note lines by id. The flag
  owner needs to settle this. It has to be resolved before trust scores can be computed per mention.

### P7. Authors: no Arabic name structure, no person link (medium)
- `work_authors` holds surname, given and `name_key = given + surname`. So «ابن جني» and «أبو الفتح عثمان ابن جني» are
  two keys. Kunya, nisba, laqab and honorifics (د.، الشيخ، أ.) are not separated: `0461-000-122-013` has surname
  «محمد», given «أ. محمد حسن».
- There is no `person_key`. The catalogue authority ids of a matched record exist (478 links carry them in
  `evidence.authority_ids`) but are never lifted onto the cited work's authors.
- So **self-citation cannot be computed**. A surname-in-byline test finds 36 works in 20 articles. About 10 of the
  first 12 are real (Askari, بوبوش, أبو الفتح… أحمد أبو الوفا, فكتور الكك), and the rest are false hits on the names
  «محمد» or «محمود». Person ids are needed; surnames do not work for Arabic names.

### P8. Years: hijri and gregorian are conflated (medium)
`year_int` keeps the printed number: 1420 for «1420ه». The calendar is not stored, although 136 rows show «هـ».
`link46.year_hit` guesses that any year below 1500 is hijri. A printed misprint such as «(١٤٩٤) هـ»
(`0013-002-001-005|ref:r1`) stays as year 1494 with nothing to show it.

### P9. Ids and provenance will not hold across runs or at 1M documents (medium)
- `work_id = stem|note:fn-p11-1|0` depends on the note ids and parse order of one Gemini run. v33_300b will renumber
  some of them. `link46` deletes and rewrites links per stem, and checks keyed by the old ids are orphaned without
  notice: **4 of 54 link_checks already match no link**.
- `link_runs` stores a timestamp only. It does not record the linker version, thresholds, rules hash or MARC
  snapshot, so no link can be reproduced or explained after a rebuild.
- Scale: about 16 parsed citations per article (4,789 / 300) means about 16M mentions at 1M articles. TEXT
  composite keys like `stem|note:fn-p26-33|0`, repeated in every link, check and index, are wasteful. Integer
  surrogate keys should be used inside the database, with stable text ids exported.

### P10. Quran and other canonical sources are treated as books (low now, unique later)
42 works are «القرآن الكريم», and 98 notes contain «سورة» or «الآية». The Quran is cited by sura and aya, not by
page. Hadith collections behave the same way («المسند» ×14 in `1453-025-001-008`, cited by number). Treating these as
book citations to a page, and grouping them with other books, distorts times-cited and loses a Quran citation index
that no other database has.

## Proposed tables

The pattern: **mention → (in-article) full citation → cited work cluster → real links**. Raw values are never
overwritten, every inferred value carries method, score and asserted_by, and every mention points at the ink.

### `citation_mentions` (replaces `works` as a row-per-place and `back_references`)
Role: *each place on a page where an article cites something*: a full citation, a short form, or an
«المرجع السابق»/ibid. It records where on the scan it is printed and which first full citation it counts for.
```
mention_pk      INTEGER PRIMARY KEY
mention_id      TEXT UNIQUE      -- 'M:' stem ':' page ':' sha1(folded printed span)[:10] ':' k  (stable across runs while the ink is the same)
stem            TEXT FK articles, run TEXT FK runs
container_kind  TEXT             -- note | reference | inline
container_id    TEXT             -- fn-p11-1 / r2 (run-local, kept for the masters)
reading_ord     INTEGER          -- order in reading order across the whole article (refs list first, as link46 does)
seq_in_container INTEGER         -- 2nd mention in the same note
kind            TEXT             -- full | short | ibid | op_cit | loc_cit | see_also(«انظر») | quran | hadith
marker          TEXT             -- the printed back-reference marker, if any
printed         TEXT             -- the citation's own span as printed (D30), not the whole note
printed_fixed   TEXT             -- the same span after Azure-misreading fixes, when different
parsed          TEXT JSON        -- the element-citation exactly as the master gives it (raw, never edited)
cited_locator   TEXT, cited_volume TEXT, cited_pages TEXT   -- «ج ١، ص ٦٥»: belongs to the mention, not the work
page INTEGER, alto_lines TEXT JSON, box TEXT, block_id TEXT -- the ink: one click to the crop
n_fixes_on_lines INTEGER, n_misprints_on_lines INTEGER, max_flag TEXT, trust REAL   -- quality signals on its lines
full_mention_pk INTEGER FK citation_mentions  -- the FIRST full citation it counts for (self for a full one; chains collapsed at load)
resolve_method  TEXT, resolve_score REAL, resolve_evidence TEXT JSON, resolved_by TEXT  -- link47 | person | judge
unresolved_why  TEXT             -- 'no parsed citations in run v2_55', 'named author not cited before', …
```
Rule at load: an ibid. takes the `full_mention_pk` of the mention just before it. An op. cit. takes that of the
earliest full mention by the named author, or by matching title words. A short form takes the earliest full mention
with the same author and title key. **No row ever points at another non-full mention**, so chains are always one
step. Several markers in one note become several rows (`seq_in_container`).

### `cited_works` (new: the WoS cited-reference index, books included)
Role: *one book, article, thesis or source cited anywhere in the archive*, the same entity whichever articles cite it
and however they spell it. It carries times-cited even when the work is not in Mandumah.
```
cited_work_pk INTEGER PRIMARY KEY, cited_work_id TEXT UNIQUE ('C' + base32)
pub_type TEXT, title TEXT, title_key TEXT, first_author_key TEXT, year_printed TEXT, year_calendar TEXT (hijri|gregorian|both),
year_hijri INTEGER, year_greg INTEGER, edition_note TEXT (ط٧، تح عبد السلام هارون), lang TEXT,
canonical_kind TEXT              -- ordinary | quran | hadith_collection | diwan | dictionary
target_stem TEXT FK articles, target_c999 TEXT, doi TEXT, isbn TEXT, worldcat TEXT, wikidata TEXT   -- best accepted link, copied from citation_links
n_mentions INTEGER, n_full INTEGER, n_articles INTEGER   -- recomputed per release
built TEXT, method TEXT          -- clustering method + version
```

### `cited_work_members` (new)
Role: *which full citations were grouped into each cited work, why, and by whom*. A person can merge or split groups
here.
```
full_mention_pk INTEGER FK citation_mentions (kind='full'), cited_work_pk INTEGER FK cited_works,
method TEXT (same-key | catalogue-same-c999 | fuzzy-title+author | person), score REAL, evidence TEXT JSON,
asserted_by TEXT (link47 | person | judge), patch_id TEXT FK patches, PRIMARY KEY (full_mention_pk)
```

### `cited_work_authors` (replaces `work_authors`)
Role: *the authors of a cited work as printed, split into the parts of an Arabic name, and tied to a person where the
catalogue identifies them*.
```
cited_work_pk INTEGER FK, seq INTEGER, printed TEXT, honorific TEXT (د.|الشيخ|أ.), kunya TEXT, ism TEXT, nasab TEXT,
nisba TEXT, laqab TEXT, shuhra TEXT (ابن منظور), latin TEXT, name_key TEXT, person_key TEXT FK people,
authority_id TEXT, match_method TEXT, match_score REAL, PRIMARY KEY (cited_work_pk, seq)
```

### `citation_links` (rebuilt: real links only)
Role: *a cited work found in the archive (an article we hold) or in Mandumah's catalogue (a 999$c), or later an
external id*. Each link records how sure it is and who said so.
```
link_pk INTEGER PRIMARY KEY
cited_work_pk INTEGER FK cited_works
via_mention_pk INTEGER FK citation_mentions   -- the full citation whose text matched (evidence → ink)
target_kind TEXT (article | catalogue | doi | isbn | wikidata)
target_stem TEXT FK articles, target_c999 TEXT, target_ext TEXT    -- never records.rec
status TEXT (accepted | candidate | rejected), best INTEGER
score REAL, method TEXT, evidence TEXT JSON (title ratio, author, year, authority ids, which reading matched: printed|fixed)
asserted_by TEXT (link47 | person | judge), link_run_id INTEGER FK link_runs, created TEXT
UNIQUE (cited_work_pk, target_kind, target_stem, target_c999, target_ext)
```
`catalogue-title-only` and `article-title-only` become `status='candidate'`. `backref-*` rows leave the table and
become `citation_mentions.full_mention_pk`.

### `work_relations` (new: from the 301 relation rows)
Role: *a typed relation between a cited work and another record*: «reviewed in», «studied in», «part of / edition
of», «translation of». Each relation is stored with its reverse.
```
relation_pk INTEGER PRIMARY KEY, subject_cited_work_pk INTEGER FK, relation TEXT (is_reviewed_by | is_studied_by | has_part | is_edition_of | is_translation_of),
inverse TEXT, object_kind TEXT (catalogue | article | cited_work), object_c999 TEXT, object_stem TEXT, object_cited_work_pk INTEGER,
score REAL, method TEXT, evidence TEXT JSON, asserted_by TEXT, link_run_id INTEGER
```
This answers "which Mandumah records review the book this article cites", which Web of Science cannot answer.

### `link_reviews` (replaces `link_checks`)
Role: *a person's or agent's verdict on one link or resolution, kept even after the links are rebuilt*.
```
review_pk INTEGER PRIMARY KEY, subject_kind TEXT (link | relation | resolution | membership), subject_pk INTEGER,
snapshot TEXT JSON (mention_id, cited_work_id, target, method, score at check time), verdict TEXT (right|wrong|near|withheld-ok),
note TEXT, checked_by TEXT, checked TEXT, is_gold INTEGER
```
After a rebuild, reviews re-attach by `snapshot` (mention_id + target). Any that cannot re-attach are listed instead
of disappearing silently. Today 4 of 54 checks have already gone silently.

### `link_runs` (rebuilt)
Role: *one pass of the linker: which code, which rules and which catalogue*, so that any link can be reproduced.
```
link_run_id INTEGER PRIMARY KEY, linker TEXT (link47), code_hash TEXT, thresholds TEXT JSON, marc_snapshot TEXT (marc.db meta load date),
started TEXT, finished TEXT, n_stems INTEGER, n_links INTEGER
link_run_stems(link_run_id, stem, linked TEXT, PRIMARY KEY (link_run_id, stem))
```

### `quran_citations` (new, unique)
Role: *every place an article quotes or cites the Quran, by sura and aya*, so it can be searched like a verse index.
```
mention_pk INTEGER FK citation_mentions (kind='quran') or block_id + alto_lines for inline quotations,
sura INTEGER, aya_from INTEGER, aya_to INTEGER, printed_ref TEXT («سورة البقرة، الآية ٢٥٥»), quoted_text TEXT, method TEXT, score REAL
```
The same shape later serves hadith (collection, number) and poetry («البيت مجهول القائل»: poet, diwan, hemistich lines).

### Views (computed, never stored; brief rec. 6 and 14)
- `times_cited`: per cited work, the count of mentions (all, full only), distinct citing articles, and distinct
  articles without self-citations, with the time window and document types stated.
- `self_citations`: author self-citation where a citing article author's `person_key` equals a cited-work author's
  `person_key` (trusted only when it comes from an authority id). Journal self-citation where the linked target
  article or catalogue record has the same `journal_id` / ISSN-L as the citing article.
- `journal_citation_pairs`: citing journal × cited journal counts, for spotting citation stacking.
- `catalogue_link_report`: catalogue records reached by citations whose catalogue author, year or title disagrees
  with the printed citation. A report Mandumah can use to find errors in its catalogue.

## Uses of our extra data no index offers
- **Ink behind every citation.** `alto_lines` and `box` on each mention, and `via_mention_pk` on each link, mean any
  "times cited" number expands to a page of scan crops. A reviewer checks a link by looking at the print.
- **Trust per citation.** A citation lying on lines with an Azure fix, a misprint or a high flag gets a lower trust.
  The linker tries the printed and the fixed reading, and says which one matched.
- **Books and their reviews.** Cited books cluster as cited works. Mandumah's 27,423 book reviews and 5,791 thesis
  reviews attach to them as `is_reviewed_by` relations.
- **Authority ids.** The cataloguer's authority id on a matched record propagates to the cited work's authors, then
  to everyone who cites them, so person-level self-citation becomes reliable.
- **Footnote reading order.** ibid. and op. cit. resolve by the citation-style position rule, which reference-list
  databases cannot apply.
- **Qdrant (`mandumah_v2`, 15.7M vectors with title, journal, year and author payloads).** It is a candidate
  generator for matching cited works (title embedding → nearest catalogue records), checked by the same
  author/year rules. It stays outside SQLite. Only the chosen target and `method='qdrant+rules'` are stored.

## What stays in files
JATS + ALTO masters (the source), the page images and scan PDFs (only ALTO line ids and boxes are copied), the full
MARC subfields (only 999$c and the fields used for a match are copied into evidence), and Qdrant vectors.

## Migration notes
1. Build in `/home/yassine/data/platform_v2/` from the masters, not from platform.db. `parse46` already discards the
   note line `<target>` ids and the second marker in a note. A parse47 has to read them from the JATS.
2. Mentions: one row per element-citation and one per marker, in reading order. Classify each as full or short. A
   repeat (same first-author key and title key as an earlier full one, or no author with a known title) is short.
   Then set `full_mention_pk` with the position rule. Check the result against the 25 agent-checked backref links:
   the six wrong cases are the test set.
3. Cluster full mentions into cited works. Use exact keys first (folded title + Arabic name key with ال/ابن/أبو
   normalised and honorifics stripped), then the same accepted c999 or stem, then fuzzy matching within a block.
   Write each step's members with its method.
4. Relink at the cited-work level. Use 999$c, never `rec`. Map today's `target_rec` to `records.c999`, since all
   478 rows carry it in evidence and it can be verified against marc.db. Keep the old link46 rows as
   `status='candidate'`, `asserted_by='link46'` for comparison.
5. Port `link_checks` into `link_reviews` with snapshots. Report the 4 orphans to the owner rather than dropping them.
6. v2_55 articles have no parsed citations. Their 80 back references load as mentions with
   `unresolved_why='run v2_55 has no parsed citations'` until a v3.x run covers them.
7. Hijri years: store the printed year, the calendar from «هـ/ه/م» and the converted year. Keep year_hit's
   "below 1500" guess only as a method with a lower score.
8. `flags.lines` ("page:line") must be mapped to ALTO line ids before trust scores join. This belongs to the
   quality-area audit.

# Audit: content (blocks, notes, figures, full-text search, ink)

Experiment 47, 2026-10-20, database engineer for the content area. Read-only on
`/home/yassine/data/platform/platform.db` (354 articles, 51,791 blocks, 4,084 notes, 4,024 note calls, 1,910 figures),
`experiments/46_platform_db/` (schema46.sql, parse46.py, load46.py, common46.py) and the masters in
`experiments/43_rehearsal/out/<run>/masters`. No paid calls. Every number below was counted on 2026-10-20 with the
query or script given beside it (sqlite3 on `file:...platform.db?mode=ro`, or short Python on the masters).

## The short version

What platform.db holds for content today is a **text table with a box**. One row per JATS element that has a block id,
plus its printed text, a folded copy, a JSON list of ALTO line ids and one rectangle. That is enough for full-text search
and for a "go to page" link. It is not enough for the thing nobody else has, which is **"show me the ink behind this
value"**: every citation, name, fix, misprint, note call, figure and search hit pointing at the exact place on the
scan, with the reading behind it (Azure's text and confidence, Argon's fix, the printed misprint) and with how much to
trust it.

Web of Science, Scopus and OpenAlex keep no body text at all. PMC and Europe PMC keep JATS full text and index it
by section, but they have no page image coordinates, no OCR readings and no correction history. Our masters already
hold all of that: ALTO with 1,189,069 words, word confidences, 11,662 Azure alternatives, 1,415 figure, formula and
table boxes, and 7,245 left-out regions. The loader throws most of it away (`read_alto` reads only TextBlock and
TextLine boxes). The gaps that matter:

1. **There is no page entity**, and the database mixes **three coordinate and line-id systems with no crosswalk**.
   Blocks use 300-dpi pixels (x,y,w,h) and ALTO line ids. Flags, patches, judge findings and fixes use Azure "P:N"
   line labels and 0–1000 boxes (x0,y0,x1,y1). Words exist only in ALTO. So no SQL query can put a flag, a patch or a
   fix on its block, or draw two of them on one page.
2. **No id survives a new run.** Block ids, ALTO line ids and even ALTO word ids move between runs of the same
   article, and `blocks.id` is renumbered on every reload. A link, a person patch or a bookmark made against one run
   points at the wrong ink in the next.
3. **The full-text search does not fold the query** and ignores Arabic clitics. Searching «الإسلام» finds 0 blocks,
   while the folded form finds 377 and a substring search finds 1,015.
4. Notes, calls, figures, sections, verses and table cells are **flattened**: their structure is in the JATS and
   ALTO, but the rows cannot be joined to it.

## Problems, with evidence

### P1 (high) A block that runs across pages keeps only its first page's box
`parse46.py` takes `ablocks.get(block_id)`, which is the first page's TextBlock. 1,733 of 51,791 blocks (3.3%) have
`page <> last_page`. Example: `0005-012-004-007` `p1b9` has page 1, last_page 2, lines `p1b9l1, p1b9l2, p2b1l1…p2b1l4`
and box `338.9, 2334.7, 1223 × 133.9`, which covers only page 1. The page-2 part (ALTO `p2b1`, `IDNEXT` chain,
`flow.continued`) has no box in the db. A crop of the evidence for anything in the continuation draws the wrong place.
**Fix:** `block_parts` (one row per page part, from ALTO `IDNEXT` / `flow.continued`).

### P2 (high) No pages table, and boxes that cannot be compared
- There is no row per scanned page. ALTO has 3,523 `<Page>` elements in the 300, each with WIDTH and HEIGHT (for
  example 1808 × 2729 for `0005-012-004-007` p1). The page image `out/pages/0005-012-004-007_p001.jpg` is
  **1812 × 2730**. So every box needs its page's own size to be drawn on the image, and the db stores neither.
- Two box conventions sit side by side: `blocks.hpos/vpos/width/height` in 300-dpi pixels, and `flags.box`
  `[104, 43, 817, 836]` as 0–1000 x0,y0,x1,y1 (rules43 `"b" (0-1000 box)`). Nothing in the schema says which is
  which.
- The printed page number of each scan page is not stored, although ALTO marks 1,664 `role.pageNumber` blocks.
  "p. 32" in a citation and "scan page 4" cannot be translated, so a cited page cannot be opened on the scan.
**Fix:** `pages` (below). Store every box in one convention: page pixels, x,y,w,h, plus the page's size.

### P3 (high) Three line-id schemes and no crosswalk
- `blocks.alto_lines` uses ALTO line ids (`p1b5l5`).
- `flags.lines` (`["2:1","2:5",…]`), `patches.targets` (`{"lines":["4:2",…]}`), `judge_findings.targets` and
  `fixes.line_label` / `misprints.line_label` use Azure "P:N" labels.
- Word ids (`p1w0001`) exist only in ALTO.
- The mapping is held by the masters builder in memory (`41_azure_structure/masters.py` `self.tl_of`). It is written
  out only for fixes and misprints, as the `alto-line` named-content.
So "which block does this flag or patch touch?" has no SQL answer. Of the 124 patches, the targets are Azure lines or
block ids depending on the action.
**Fix:** `ink_lines` crosswalk (below), built by the loader from ALTO plus the Azure JSON that sits beside the masters
(`out/fetch/<stem>/<stem>.json`).

### P4 (high) Nothing in the content tables has an id that survives a new run
- **Block ids:** between `v33_300` and `v33_300_final`, the list of block ids differs in 18 of 299 articles (for
  example `0368-000-003-003`: 119 blocks, then 127).
- **ALTO line ids** are derived from block ids (`p<page>b<n>l<k>`). In `0368-000-003-003`, only 1,185 of 1,290 are
  shared between the two runs.
- **ALTO word ids** are numbered in output order (`masters.py`: `p{lp}w{self.wn[lp]:04d}`), not in Azure's order.
  Matching words by position, 5,963 of 1,178,199 words changed id between the two runs, in 14 of 299 articles.
- **`blocks.id`** (INTEGER PRIMARY KEY, also the FTS rowid) is reassigned on every delete-and-insert reload.
- **Inline equations** get positional ids `inline-formula<k>` (`inline-formula1` appears in 14 articles). A reread
  that adds one formula renumbers all the rest.
The only thing that never changes is Azure's reading: the S3 JSON is fixed input. Patches already target Azure "P:N"
lines for this reason.
**Fix:** make the **ink address** the stable anchor. An ink address is a stem, a page, and a span of Azure word
ordinals in Azure's JSON order. Block, line and word ids become per-run labels resolved through `ink_lines` and
`ink_anchors`. `blocks` gets a key that never collides: (stem, run, block_id).

### P5 (high) Full-text search does not work the way an Arabic reader searches
`blocks_fts` is `fts5(text_folded, content='blocks', tokenize='unicode61 remove_diacritics 2')`. The canned query is
`WHERE blocks_fts MATCH :q`, so the query string is not folded.

| query | blocks matched |
|---|---|
| `الإسلام` (as typed, with hamza) | **0** |
| `الاسلام` (folded) | 377 |
| `text_folded LIKE '%الاسلام%'` | 1,015 |
| `والاسلام OR بالاسلام OR للاسلام OR فالاسلام` | 63 |
| `مدرسة` (as typed) | **0** |
| `مدرسه` (folded) | 78 |

- unicode61 strips the harakat but does not unify alef forms or ة/ه. Only the stored text is folded (`common46.fold`).
- Arabic attaches و ف ب ك ل and ال to the word, so a whole-token index misses about 60% of the substring hits.
- `snippet()` returns the folded text (`…بذلك ايضا في [الاسلام] . يضاف الي هذه الفصاحه…`), not the print.
- Only blocks are indexed. Figure alt-text (735 Arabic, 519 English), text inside figures (430), equation LaTeX and
  the parsed citations are not.
- Every load runs `INSERT INTO blocks_fts(blocks_fts) VALUES ('rebuild')`, which re-indexes the whole corpus. That
  is fine at 354 articles and impossible at 1M.
**Fix:** fold the query with the same `fold()`, registered as an SQL function by a small Datasette plugin, so the
query reads `MATCH fold(:q)`. Add a second indexed column with clitics stripped (a light stemmer, no model). Map the
snippet back to the printed words: fold keeps the word count, so token offsets carry over. Index search units beyond
blocks. Update the index per article by delete and insert, with no rebuild.

### P6 (medium) Notes and calls cannot be joined to the ink
- `notes` has no block id, line or box. Its 4,084 rows and the 4,084 blocks of kind footnote or endnote line up only
  by guessing.
- `note_calls` has **no primary key**. 54 calls (in 13 articles) have `note_id NULL`, because the xref has no `rid`.
  fk46 reports 0 orphans, because a NULL is not an orphan. Example: `0702-015-058-007` calls (٢٩)…(٣٣) in
  `p7b4`/`p7b5` lead nowhere.
- A call that names several notes, such as `(٤، ٩)` or `(٥،٢، ٨)` in `0049-001-999-012`, is one row pointing at one
  note.
- 158 notes in 49 articles have no call.
- A call stores its block but not its line, word or position in the text. The call mark cannot be shown on the scan,
  and nothing can tell which sentence a citation supports.
This matters for citations. The owner's «المرجع السابق» rule resolves in note reading order, so the citation index
(see audit_citations.md) depends on notes and calls being exact.
**Fix:** `note_calls` gets a sequence key, an ink anchor and a character offset in its block, and is split into calls
and call targets. `blocks.note_id` links each note's paragraphs. Unresolved calls are kept with
`status='no-target'`, not with a NULL key.

### P7 (medium) Figures, tables and equations have no box, no place in the text and no cells
- ALTO holds 857 `Illustration TYPE="figure"`, 185 `Illustration TYPE="formula"` and 373
  `ComposedBlock TYPE="table"`, each with a box and an `xlink:href` to the JATS id. `read_alto` ignores them, so
  `figures` has no box at all.
- `page` is NULL for all 329 inline equations and all 36 inline pictures.
- There is no link from a figure to its caption block. Caption `p3b6` sits inside `table-wrap p3t1`, but nothing in
  the db says so. There is also no link to the block it sits after in the reading flow.
- **Tables are not data.** Their 18,895 cells are blocks (36% of all block rows, 9 characters on average) with no
  table id, row, column, rowspan or colspan. The cell id encodes row and column (`p3t1c0201` = row 2, column 1) and
  the JATS has `rowspan` / `colspan`, but a table cannot be rebuilt from the db.
- The `figures.graphic` crop path is relative (`<stem>.crops/p1f1.jpg`), but the crop's own box is not stored.
**Fix:** `figures` gains box, page parts, `caption_block_id`, `anchor_block_id`, `crop_key` and the stable id. A
`table_cells` table holds table, row, column, spans, header flag and block id. Display equations keep LaTeX and
MathML. Inline equations get an ink anchor instead of a positional id.

### P8 (medium) Content rows carry no per-value provenance or trust
- `blocks.source` is `masters` for all 51,791 rows and `figures.source` is `masters` for all 1,910. Yet 10 articles
  were built with patches that change content, for example `j-0484-p1-1 set_kind (judge)`, `j-0590-p2-1
  fix_picture_box (judge)` and `r-0368-p11-1 replace_page_blocks (gemini-retry)`. Those changes are recorded only as
  a text list in `articles.patches_applied`.
- Azure's word confidence (WC) is in ALTO for 1,171,970 words and unused. It is a real signal. Words that Argon fixed
  have a mean WC of **0.61** and 34% of them are below 0.5. Across all words the mean is **0.947** and 2.2% are below
  0.5.
- Nothing per block says how many fixes, misprints, flags or judge findings touch it.
**Fix:** blocks get `kind_source` / `text_source` (masters | judge | person | gemini-retry), `patch_ids`, `n_words`,
`mean_wc`, `min_wc`, `n_low_wc`, `n_fixes`, `n_misprints`, `n_flags` and a derived `trust`. A per-block rollup is
cheap. Per-word values stay in ALTO.

### P9 (medium) The ink the article left out is not in the db
7,245 ALTO TextBlocks have no JATS link, and 591 of 13,369 `fixes` point at their lines (for example
`0041-002-005-008` `p1b2l1`, a `role.pictureText` block). The 300 alone have:

| role | blocks |
|---|---|
| pageHeader | 2,230 |
| pageNumber | 1,664 |
| pageFooter | 1,214 |
| noise | 855 |
| pictureText | 416 |
| pictureJunk | 302 |
| formulaInk | 185 |
| ornament | 174 |
| showThrough | 112 |
| otherArticle | 93 |

This is unique evidence. Running heads and page numbers are printed metadata: the journal, the issue and the
page. "Noise" and "other article" are the decisions a person checks when text goes missing. Today the db shows none
of it.
**Fix:** a `page_regions` table (role, text, box, lines, which decision made it: Argon, judge or person).

### P10 (medium) Mixed concepts in `blocks` and flattened structure
- `kind` mixes reading roles (paragraph, footnote, caption) with JATS element names (`contrib` 37, `keywords` 96;
  both have no lines) and metadata copies (`title` 327, `title-en` 59, `abstract` 261, `byline` 154). There are 2,231
  `reference` blocks for 2,028 refs.
- `section` is just an id (`s86`; ids are per article). There is no section table with heading text, level and
  parent, although the JATS has `heading-level-2/3`. 1,773 of 14,973 paragraphs have no section.
- **Verse** is flattened. 2,494 verse-group blocks join their 3,875 `verse-line`s (hemistichs, each with its own id)
  with " / ", and the call digits sit inside the line: «وأنت الذي رَبَّيت ذا الملك مُرْضَعًا وليس / له أُمٌّ سواك
  ولا أب (١٧٠)».
- **Quran** quotations are not marked at all. 144 blocks contain ﴿ … ﴾ and 55 contain «سورة …» references. The JATS
  has no markup for them.
**Fix:** `sections`, `verse_lines`, and a derived `quran_quotes` table (below). Keep `kind` to a closed list of
reading roles, and put metadata blocks under `role='front'` with a pointer to the metadata field.

### P11 (low) File locators are local absolute paths, and many are broken
- `articles.pdf_path` exists on disk for 54 of 354 articles. The 300-run masters symlink to
  `experiments/41_azure_structure/out/native_in/<stem>/<stem>.pdf`, which is not there.
- The page images that exist (`experiments/43_rehearsal/out/pages`, 6,927 jpg for 600 stems, 4.2 GB) are not
  referenced at all.
- At 1M documents, the scan lives at S3 `mandumah-source-docs/<id>/<id>.pdf` (with the Azure JSON beside it).
**Fix:** store storage keys, not paths (`scan_key`, `azure_key`, `alto_key`, `jats_key`, `page_image_key`), plus a
`storage_roots` row per environment.

### P12 (low) Fixes and misprints are tied to a line but not to a word or a block
`fixes` (13,369) and `misprints` (1,798) carry `alto_line` and `line_label`, but no block id, word id or character
offset. ALTO marks the fixed words themselves (`TAGREFS="fix.argon"`, `<ALTERNATIVE PURPOSE="azure">`), so the exact
word is known in the files but lost in the db.
**Fix:** one `readings` ledger (below).

### P13 (low) Size at 1M documents
- 59 MB holds 354 articles: blocks 37.7 MB, FTS 5.9 MB. A linear projection gives ~165 GB for 1M structured
  articles, ~105 GB of it blocks.
- `text_folded` duplicates `text` (7.38M of 7.42M characters).
- Words: 1.19M for 300 articles, so ~4 billion at 1M, and ALTO lines ~540M. **Words never go in the db.** Lines go in
  only for structured articles.
For years most of the 1M documents will be Azure-only (no Gemini structure), so the db needs a processing level per
article.

## How the big databases do it, and where we go further

- **WoS, Scopus, OpenAlex:** no body text, only metadata, abstracts and references. OpenAlex keeps raw strings beside
  resolved values (brief §1). We copy that: the printed form, Azure's reading and the correction are all kept.
- **PMC / Europe PMC:** full JATS, indexed by section, with figures as objects that have captions. This is the right
  model for `sections`, `figures` and `table_cells`. They have no coordinates and no OCR, so nothing in them points
  back to the page.
- **Library OCR collections** (ALTO / METS, e.g. national-library newspaper archives) keep word boxes in ALTO and
  link hits to the page image. That is the pattern for `pages` + `ink_anchors`: words stay in the files, and the db
  keeps the anchors values need.
- **Beyond all of them:**
  - every value (citation, author name, misprint, fix, search hit, metadata change, flag) is an ink anchor you can
    open as a crop in one click;
  - there are two readings with a confidence, and an auditable correction ledger;
  - trust scores per block and page;
  - a verse index and a Quran-quotation index;
  - the page-number translation that lets a citation's "ص ٣٢" open the right scan page.

## Proposed tables

Columns are listed with type and key. ⟶ = foreign key. Every row read from a run carries `run` ⟶ runs and `source`.

**pages.** *One row per scanned page: its size, its image, the printed page number, and how good its reading is.*
`stem ⟶ articles, page INTEGER (scan order), PK(stem,page); printed_page TEXT (from role.pageNumber), printed_page_int,
width_px REAL, height_px REAL (ALTO), image_w, image_h, dpi INTEGER, scan_key TEXT, page_image_key TEXT,
running_head TEXT, n_words, mean_wc REAL, n_low_wc, n_fixes, n_misprints, n_flags, n_noise_regions, level TEXT
(azure-only|structured|judged|final), run, source`.

**block_parts.** *Where each piece of a block sits on each page it spans.*
`stem, run, block_id, part INTEGER, PK(stem,run,block_id,part); page, alto_block_id, x, y, w, h (page px),
first_line_id, last_line_id`. This takes over from blocks' single box. Keep `blocks.hpos…` as part 1 for
compatibility.

**blocks (revised).** *The article's text in reading order, one row per paragraph, heading, cell, note paragraph or
verse group, as printed.*
`stem, run, block_id, PK(stem,run,block_id)`; `uid INTEGER UNIQUE` (FTS rowid, never reused); `ord, page, last_page,
role` (closed list); `section_id ⟶ sections, note_id ⟶ notes, figure_id ⟶ figures, table_cell` flag, `lang, text,
kind_source, text_source, patch_ids TEXT, n_words, mean_wc, min_wc, n_low_wc, n_fixes, n_misprints, n_flags, trust
REAL, first_anchor ⟶ ink_anchors`. Content of non-current runs is not kept in the db. `article_runs` and the
masters files hold it.

**sections.** *The article's headings as a tree, so a hit can say "in section 3.2, Method".*
`stem, run, section_id, PK(stem,run,section_id); parent_id, level INTEGER, heading_block_id, heading TEXT, ord`.

**ink_lines.** *The translation between Azure's line numbers ("4:2"), the run's ALTO line ids and the blocks, so
flags, patches and fixes land on the right text.*
`stem, run, alto_line_id, PK(stem,run,alto_line_id); azure_line TEXT ("P:N"), UNIQUE(stem,run,azure_line); page,
block_id, region_id ⟶ page_regions, x,y,w,h, first_word INTEGER, last_word INTEGER (Azure word ordinals on the page)`.
Only for structured articles (~540 lines per article). Words stay in ALTO.

**ink_anchors.** *A pointer to an exact place on the scan (page and word span) that any value can cite as its
evidence: "show me the ink".*
`anchor_id TEXT PK` (`<stem>|p<page>|w<first>-<last>`, Azure word ordinals, stable across runs); `stem, page,
first_word, last_word, x,y,w,h, text_printed, text_azure`; `owner_kind TEXT, owner_id TEXT` (note_call | work |
backref | author_name | fix | misprint | metadata_change | flag | finding | patch | figure | quran_quote | search
hit). The many-to-many form is `anchor_links(anchor_id, owner_kind, owner_id, role)`. Crops are rendered on demand
from `pages.page_image_key` + box and never stored.

**page_regions.** *Ink on the page that is not part of the article text (running heads, page numbers, noise,
show-through, another article, text inside pictures), kept so every leave-out can be checked.*
`stem, run, region_id (ALTO TextBlock id), PK(stem,run,region_id); page, role, text, x,y,w,h, alto_lines TEXT,
decided_by (argon|rules|judge|person), patch_id`.

**readings (the corrections ledger).** *Every word where the readings differ, in one list: Azure's reading, what is
printed, and for a misprint the proposed correction, each with who said so and why.*
`reading_id TEXT PK (<stem>|<run>|<fix_id or sic_id>); stem, run, kind (azure-misread | misprint), anchor_id ⟶
ink_anchors, block_id, char_start, char_end, azure_reading, azure_wc REAL, printed, proposed (misprint only, D30),
why, asserted_by (argon|judge|person), patch_id, status (applied|proposed|rejected)`. This replaces `fixes` and
`misprints`, which stay as views for Datasette. D33 metadata changes stay in `metadata_changes` (metadata area) but
gain `anchor_id`.

**note_calls (revised) + note_call_targets.** *Each call mark in the text, where it is on the page, and the note or
notes it opens.*
- `note_calls`: `stem, run, call_seq INTEGER, PK(stem,run,call_seq); call_text, block_id, char_offset, anchor_id,
  status (ok|no-target|multi)`.
- `note_call_targets`: `stem, run, call_seq, note_id ⟶ notes, PK(stem,run,call_seq,note_id)`.
- `notes` gains `first_block_id, anchor_id, label_int` (the number on the label, for checking order).

**figures (revised) + table_cells.** *Each picture, table and equation as an object with its box, caption and place in
the text; tables as cells you can rebuild.*
- `figures`: `stem, run, figure_id (JATS id; inline formulas: anchor-based id), PK(stem,run,figure_id); kind, page,
  x,y,w,h, alto_id, caption_block_id, anchor_block_id, label, caption, alt_ar, alt_en, text_in_figure, crop_key, tex,
  mathml (TEXT, not a flag), specific_use, source`.
- `table_cells`: `stem, run, figure_id ⟶ figures, row INTEGER, col INTEGER, PK(stem,run,figure_id,row,col); rowspan,
  colspan, is_header, block_id ⟶ blocks, text`.

**verse_lines.** *Each printed verse line or hemistich, so poetry can be searched and cited line by line.*
`stem, run, verse_id (verse-line id), PK(stem,run,verse_id); group_block_id, seq, text (call marks removed), call_ids,
anchor_id`.

**quran_quotes** (derived by code, $0). *Every Quran quotation in the archive with its sura and aya, for a citation
index of the Quran no other index has.*
`quote_id PK, stem, run, block_id, anchor_id, quoted_text, sura INTEGER, aya_from, aya_to, printed_ref (as printed,
e.g. «[البقرة: ٢٥٥]»), method (bracket+match | ref-only | match-only), score, checked_by`. It is built by matching the
folded text inside ﴿ ﴾ and «سورة» references against a public Quran text (an open question: which text, and its
licence).

**search_units + search_fts.** *One searchable piece of text per row (block, alt-text, text in figure, equation,
verse line, printed citation), so one search covers everything and a hit always opens its ink.*
- `search_units`: `uid PK, stem, run, unit_kind, unit_id, text (printed), lang, anchor_id`.
- `search_fts`: `fts5(folded, stemmed, content='search_units', content_rowid='uid')`, updated per article.
- Queries use `MATCH fold(:q)` (a plugin function), and snippets are mapped to the printed text.

**vector_chunks** (links only). *A pointer from each existing Qdrant point (mandumah_v2) to the article and, where
offsets allow, the blocks it covers, so a semantic hit opens the page.*
`point_id PK, collection, doc_id (= stem), section, block_from, block_to, method, score`. Only links are stored. The
vectors stay in Qdrant.

**storage_roots.** *Where files live in each environment (laptop, server, S3), so the db holds keys and not broken
paths.*
`root_id PK, kind (local|s3), base TEXT, note`. The `*_key` columns are relative to a root.

## What stays in files, and why

- **Words, word boxes, every alternative reading:** ALTO (193 MB for 300 articles, ~4B words at 1M). The db keeps
  per-block and per-page rollups, plus the anchors that values actually cite.
- **The JATS tree itself** (inline markup, MathML, named-content): the masters remain the record. The db holds what is
  queried, and rebuilds come from the files.
- **Page images, crops, the ink PDF:** in object storage, rendered on demand from the key and the box.
- **Content of non-current runs:** only `article_runs` (sha, made) in the db. Diffs between runs come from the masters.
- **Azure JSON for the 1M Azure-only documents:** an Azure-level search across 1M documents belongs in a search engine
  fed from S3, not in this SQLite file. The db gets `pages` rows (level `azure-only`) and only the anchors that
  values need.

## Migration notes

1. Build v2 in `/home/yassine/data/platform_v2/` from the same masters. Do not alter platform.db. Loader
   `experiments/47_platform_v2/`.
2. Read ALTO fully: Page size, TextBlock with `IDNEXT`/`TAGREFS`, Illustration, ComposedBlock, String WC/TAGREFS/
   ALTERNATIVE. Roll WC up to block and page, emit `block_parts`, `page_regions`, `figures` boxes and `ink_lines`
   (Azure "P:N" from `out/fetch/<stem>/<stem>.json` by word box overlap, the same match rules43 uses).
3. Convert flag and patch boxes from 0–1000 to page pixels with `pages.width_px/height_px`, keeping the raw value in
   `box_raw`.
4. `readings` from the `reader-fixes` / `suspected-misprints` notes, plus the ALTO words tagged `fix.argon`. Check
   that the counts match: 11,662 ALTERNATIVE in ALTO against 12,389 fix rows for the 300. The difference is fixes on
   words without their own box, to be explained before trusting the join.
5. Equivalence check: v2 `blocks` text = v1 `blocks` text for every (stem, block_id) of the current run, and
   `fixes`/`misprints` views = v1 tables row for row.
6. FTS: a Datasette plugin with `fold()` (copy of `common46.fold`) and a light clitic stripper. Measure on the table
   above (الإسلام, مدرسة, والاسلام…) before and after.
7. Load v33_300b when it is done, as a new run of the same articles where stems overlap. `ink_anchors` ids must come
   out identical between runs. That is the test of P4.

## Open questions

- Should verse lines be split into hemistichs (ṣadr/ʿajuz) as separate rows? The masters have one `verse-line` per
  printed line, and sometimes that is a full bayt.
- Which Quran text to match against (Tanzil Uthmani or simple), and is its licence fine for a commercial platform?
- Do Qdrant `mandumah_v2` chunks carry character offsets into Azure's content? If not, `vector_chunks` can only link
  to the document and section.
- Should table cells stay in `blocks` (for search) as well as in `table_cells`? This proposal keeps them in both.

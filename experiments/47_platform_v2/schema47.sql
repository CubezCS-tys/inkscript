-- schema47.sql — platform v2 target schema (experiment 47, 2026-10-20). Design and reasons: DESIGN.md.
--
-- Conventions
--   * Built in SQLite now; written in portable SQL (TEXT/INTEGER/REAL, JSON as TEXT, partial indexes) so the same
--     tables move to PostgreSQL later. Only search_fts (FTS5) is SQLite-specific.
--   * `-- @group:` and `-- @role:` comments are read by schema_doc47.py to write the schema section of DESIGN.md.
--   * Every inferred value carries method / score / asserted_by; every read value carries source + run (via
--     version_id) and, where it was read off a page, anchor_pk (its place on the scan).
--   * asserted_by / source vocabulary: person > judge > gemini-retry > reader (Argon/Gemini masters) > rule > link47
--     > catalogue > azure. Corrections are patches; nothing printed is ever overwritten (D30, D33).
--   * Catalogue records are keyed by 999$c (c999) everywhere; marc.db `rec` survives only as a trace column.
--   * Boxes are page pixels of the ALTO page (x, y, w, h); a raw box in another convention is kept beside it as JSON.
PRAGMA foreign_keys = ON;

-- ====================================================================================================== provenance
-- @group: Provenance and identity — where every row came from, and ids that never break

-- @role: A place files live (local disk, an S3 bucket), so the database stores keys relative to it, never absolute paths.
CREATE TABLE storage_roots (
  root_id TEXT PRIMARY KEY,            -- e.g. 'local-43', 's3-source-docs', 's3-legacy'
  kind TEXT NOT NULL,                  -- local | s3
  base TEXT NOT NULL,                  -- path or s3://bucket/prefix in this environment
  note TEXT
);

-- @role: One processing run (a Gemini/Argon reading, a judge pass, a final rebuild, an exam): what it ran with and what it cost.
CREATE TABLE runs (
  run TEXT PRIMARY KEY,                -- v2_55, v33_300, v33_300_judged, v33_300_final, v33_300b
  kind TEXT NOT NULL,                  -- sample | base | judged | final | exam | replay
  parent_run TEXT REFERENCES runs(run),-- the run whose readings this one builds on
  model TEXT, thinking TEXT, mode TEXT,
  prompt_hash TEXT, rules_hash TEXT, rules43_hash TEXT, masters43_hash TEXT, evidence43_hash TEXT,
  judge_prompt_hash TEXT, code_commit TEXT,
  started TEXT, finished TEXT,
  usd REAL, tokens_in INTEGER, tokens_out INTEGER, pages INTEGER,
  root_id TEXT REFERENCES storage_roots(root_id), root_rel TEXT,   -- the run folder
  note TEXT
);

-- @role: One execution of the loader or linker, so every row can be traced to the load that wrote it.
CREATE TABLE load_events (
  load_id INTEGER PRIMARY KEY,
  started TEXT NOT NULL, finished TEXT,
  tool TEXT NOT NULL,                  -- load47 | link47 | people47 | report47 | rebuild47
  tool_hash TEXT, run TEXT REFERENCES runs(run), export_id TEXT REFERENCES catalogue_exports(export_id),
  args TEXT, n_loaded INTEGER, n_unchanged INTEGER,
  rows_by_table TEXT                   -- JSON
);

-- @role: Every paid model call ever made for a run (from gemini_spend.jsonl, raw chunk files, judge answers), so the cost of any page, article or verdict adds up.
CREATE TABLE model_calls (
  call_pk INTEGER PRIMARY KEY,
  called TEXT, model TEXT, job TEXT,   -- job: read | retry | judge | title | numbers ...
  run TEXT REFERENCES runs(run), stem TEXT, page INTEGER, chunk INTEGER, mode TEXT,
  tokens_in INTEGER, tokens_out INTEGER, tokens_think INTEGER, usd REAL, finish TEXT,
  root_id TEXT REFERENCES storage_roots(root_id), file_key TEXT, sha TEXT
);

-- @role: Who (which person, agent, model or code rule) made an assertion, a patch or a review.
CREATE TABLE actors (
  actor_id TEXT PRIMARY KEY,           -- 'person:owner', 'agent:link47', 'model:gemini-3.8-flash', 'rule:d33-pages'
  kind TEXT NOT NULL,                  -- person | agent | model | rule
  name TEXT, note TEXT
);

-- @role: The append-only register of public ids (A persons, I institutions, C cited works), so a rebuild gives every entity the same id again.
CREATE TABLE id_registry (
  public_id TEXT PRIMARY KEY,          -- 'A000123', 'I000045', 'C0001234'
  kind TEXT NOT NULL,                  -- person | institution | cited_work
  natural_key TEXT NOT NULL,           -- 'auth:111978' | 'mention:<mention_id>' | 'founder:<mention_id>' | 'cat-corp:2631'
  created_load INTEGER REFERENCES load_events(load_id),
  UNIQUE (kind, natural_key)
);

-- @role: When two ids turn out to be one thing (or one splits), the retired id points to the survivor so no link or bookmark breaks.
CREATE TABLE merged_ids (
  old_id TEXT PRIMARY KEY,
  new_id TEXT NOT NULL,
  kind TEXT NOT NULL,                  -- publication | person | institution | cited_work | journal
  relation TEXT NOT NULL,              -- merged-into | split-from
  merged TEXT, reason TEXT,
  asserted_by TEXT,                    -- person | judge | link47 | catalogue
  patch_key TEXT REFERENCES patches(patch_key)
);

-- ====================================================================================================== ink
-- @group: The ink layer — the scan and Azure's reading, fixed per document and the same for every run

-- @role: One file in the archive (an article PDF or one part of a thesis): where it is and how far it has been processed.
CREATE TABLE documents (
  stem TEXT PRIMARY KEY,               -- S3 id, e.g. 0005-012-004-007 or 9802-001-009-0299-R
  pub_id TEXT REFERENCES publications(pub_id),
  part_label TEXT,                     -- thesis part suffix: T A C F 1..n O R
  part_kind TEXT,                      -- article | title-page | abstract | contents | chapter | conclusion | references
  part_seq INTEGER,
  level TEXT NOT NULL,                 -- legacy-pdf | azure | structured | judged | final | person-checked
  in_main_bucket INTEGER, legacy_only INTEGER,
  has_azure_json INTEGER, has_html INTEGER, has_gemini_title INTEGER,
  scan_pages INTEGER, pdf_sha TEXT, azure_sha TEXT,
  root_id TEXT REFERENCES storage_roots(root_id),
  scan_key TEXT, azure_key TEXT, html_key TEXT, gemini_title_key TEXT, scan_pdf_key TEXT,  -- scan_pdf = inkscript ink PDF
  qdrant_doc_id TEXT,                  -- = stem in mandumah_v2 payloads
  first_load INTEGER REFERENCES load_events(load_id)
);
CREATE INDEX documents_pub ON documents(pub_id);
CREATE INDEX documents_level ON documents(level);

-- @role: One scanned page: its size, image, printed folio and running head, and Azure's own confidence on it.
CREATE TABLE pages (
  stem TEXT NOT NULL REFERENCES documents(stem),
  page INTEGER NOT NULL,               -- scan page, 1-based
  width_px REAL, height_px REAL,       -- ALTO page size (the box convention)
  image_w INTEGER, image_h INTEGER, dpi INTEGER,
  page_image_key TEXT,
  printed_folio TEXT, printed_folio_int INTEGER,   -- from the role.pageNumber region (evidence for page ranges)
  running_head TEXT,                   -- from role.pageHeader (evidence for journal / issue)
  n_words INTEGER, wc_mean REAL, wc_min REAL, n_low_wc INTEGER,   -- Azure word confidences, run-independent
  angle REAL,
  PRIMARY KEY (stem, page)
);

-- @role: One line as Azure read it (its "P:N" label), with its box and the span of Azure word numbers on it; kept only for structured documents.
CREATE TABLE azure_lines (
  stem TEXT NOT NULL, page INTEGER NOT NULL,
  line_no INTEGER NOT NULL,            -- N in the 'P:N' labels of flags, patches, judge targets and fixes
  x REAL, y REAL, w REAL, h REAL,
  first_word INTEGER, last_word INTEGER,  -- Azure word ordinals on the page
  n_words INTEGER, wc_min REAL,
  text TEXT,                           -- Azure's reading of the line
  PRIMARY KEY (stem, page, line_no),
  FOREIGN KEY (stem, page) REFERENCES pages(stem, page)
);

-- @role: An exact place on the scan (a page and a span of Azure words, or a box) that any value can cite as its evidence: "show me the ink".
CREATE TABLE ink_anchors (
  anchor_pk INTEGER PRIMARY KEY,
  anchor_key TEXT NOT NULL UNIQUE,     -- '<stem>|p<page>|w<first>-<last>' (stable across runs) or '<stem>|p<page>|b<x>,<y>,<w>,<h>'
  stem TEXT NOT NULL, page INTEGER NOT NULL,
  first_word INTEGER, last_word INTEGER,
  x REAL, y REAL, w REAL, h REAL,
  text_azure TEXT, wc_min REAL,
  method TEXT NOT NULL,                -- words | line | box | page  (how precisely the value was placed)
  FOREIGN KEY (stem, page) REFERENCES pages(stem, page)
);
CREATE INDEX anchors_page ON ink_anchors(stem, page);

-- @role: Extra evidence places for a value that needs more than one (a citation running across two pages, a name printed twice).
CREATE TABLE anchor_links (
  anchor_pk INTEGER NOT NULL REFERENCES ink_anchors(anchor_pk),
  owner_kind TEXT NOT NULL,            -- citation_mention | byline_mention | assertion | correction | flag | finding | patch | quran | figure ...
  owner_key TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'evidence',
  seq INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (anchor_pk, owner_kind, owner_key, role)
);
CREATE INDEX anchor_links_owner ON anchor_links(owner_kind, owner_key);

-- ====================================================================================================== readings
-- @group: The reading layer — one transparent sheet per run laid on the ink: text, structure, corrections

-- @role: One reading of one document by one run; every content and quality row belongs to one of these, and one per document is shown.
CREATE TABLE versions (
  version_id INTEGER PRIMARY KEY,
  version_key TEXT NOT NULL UNIQUE,    -- 'V:<stem>@<run>'
  stem TEXT NOT NULL REFERENCES documents(stem),
  run TEXT NOT NULL REFERENCES runs(run),
  stamp_run TEXT,                      -- what the stamp file says (it can disagree with the folder)
  made TEXT, load_id INTEGER REFERENCES load_events(load_id),
  jats_sha TEXT, alto_sha TEXT, pdf_sha TEXT, sidecars_sha TEXT, inputs_sha TEXT,
  pages_covered TEXT, pages_expected INTEGER, complete INTEGER,   -- v2_55: 24 of 54 are partial
  usd REAL, tokens_in INTEGER, tokens_out INTEGER, n_chunks INTEGER, n_retries INTEGER,
  content_in_db INTEGER NOT NULL DEFAULT 1,   -- 0 = retired to files; the row and its hashes stay
  is_current INTEGER NOT NULL DEFAULT 0,
  current_reason TEXT,                 -- person | complete | purpose:final>judged>base>exam>sample | newest
  chosen_by TEXT,
  masters_key TEXT,                    -- under the run's root
  UNIQUE (stem, run)
);
CREATE UNIQUE INDEX versions_one_current ON versions(stem) WHERE is_current = 1;

-- @role: Translation between a run's ALTO line ids and Azure's lines, so a flag, patch or fix given as "4:2" lands on the right block.
CREATE TABLE line_map (
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  alto_line_id TEXT NOT NULL,          -- p3b6l1
  page INTEGER NOT NULL,
  azure_line_no INTEGER,               -- NULL when the ALTO line has no Azure source (rare)
  block_id TEXT, region_id TEXT,       -- exactly one of them is set
  x REAL, y REAL, w REAL, h REAL,
  map_method TEXT,                     -- tag | box-overlap
  PRIMARY KEY (version_id, alto_line_id)
);
CREATE INDEX line_map_azure ON line_map(version_id, page, azure_line_no);

-- @role: The article's headings as a tree, so a search hit or a citation can say which section it sits in.
CREATE TABLE sections (
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  section_id TEXT NOT NULL,
  parent_id TEXT, level INTEGER, ord INTEGER,
  heading_block_id TEXT, heading TEXT,
  PRIMARY KEY (version_id, section_id)
);

-- @role: The text in reading order exactly as printed (D30), one row per paragraph, heading, cell, note paragraph or verse group, with its quality roll-up.
CREATE TABLE blocks (
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  block_id TEXT NOT NULL,              -- the run's JATS/ALTO id, e.g. p1b9
  uid INTEGER NOT NULL UNIQUE,         -- never reused; the search rowid
  ord INTEGER NOT NULL,
  page INTEGER, last_page INTEGER,
  role TEXT NOT NULL,                  -- closed list: title | title-translated | byline | affiliation | abstract | keywords | heading | paragraph | list-item | footnote | endnote | ref | caption | table-cell | verse-group | quote | front-matter | back-matter
  section_id TEXT, note_id TEXT, figure_id TEXT,
  lang TEXT, text TEXT,
  role_source TEXT, text_source TEXT,  -- reader | rule | patch:<source>:<patch_key> (source = person | judge | gemini-retry)
  n_words INTEGER, wc_mean REAL, wc_min REAL, n_low_wc INTEGER,
  n_fixes INTEGER, n_misprints INTEGER, n_flags INTEGER,
  trust REAL,                          -- derived (see v_block_trust); stored per release
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  PRIMARY KEY (version_id, block_id)
);
CREATE INDEX blocks_ord ON blocks(version_id, ord);

-- @role: Where each piece of a block sits on each page it spans (1,733 blocks cross a page).
CREATE TABLE block_parts (
  version_id INTEGER NOT NULL, block_id TEXT NOT NULL, part INTEGER NOT NULL,
  page INTEGER NOT NULL, alto_block_id TEXT,
  x REAL, y REAL, w REAL, h REAL,
  first_line_id TEXT, last_line_id TEXT,
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  PRIMARY KEY (version_id, block_id, part),
  FOREIGN KEY (version_id, block_id) REFERENCES blocks(version_id, block_id)
);

-- @role: Ink on the page that is not article text (running heads, page numbers, noise, show-through, the next article, picture text), kept so every leave-out can be checked.
CREATE TABLE page_regions (
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  region_id TEXT NOT NULL,             -- the ALTO TextBlock id
  page INTEGER NOT NULL,
  role TEXT NOT NULL,                  -- pageHeader | pageNumber | pageFooter | noise | pictureText | pictureJunk | formulaInk | ornament | showThrough | otherArticle
  text TEXT, x REAL, y REAL, w REAL, h REAL,
  decided_by TEXT,                     -- reader | rule | judge | person
  patch_key TEXT REFERENCES patches(patch_key),
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  PRIMARY KEY (version_id, region_id)
);

-- @role: One footnote or endnote, with its printed label and its place on the page.
CREATE TABLE notes (
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  note_id TEXT NOT NULL,
  kind TEXT,                           -- footnote | endnote
  label TEXT, label_int INTEGER,
  ord INTEGER, page INTEGER,
  first_block_id TEXT, text TEXT,
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  PRIMARY KEY (version_id, note_id)
);

-- @role: Each call mark in the running text, where it is, and whether it found its note.
CREATE TABLE note_calls (
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  call_seq INTEGER NOT NULL,
  call_text TEXT, block_id TEXT, char_offset INTEGER,
  status TEXT NOT NULL,                -- ok | no-target | multi
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  PRIMARY KEY (version_id, call_seq)
);

-- @role: The note or notes one call opens ("(٤، ٩)" opens two).
CREATE TABLE note_call_targets (
  version_id INTEGER NOT NULL, call_seq INTEGER NOT NULL, note_id TEXT NOT NULL,
  PRIMARY KEY (version_id, call_seq, note_id),
  FOREIGN KEY (version_id, call_seq) REFERENCES note_calls(version_id, call_seq),
  FOREIGN KEY (version_id, note_id) REFERENCES notes(version_id, note_id)
);

-- @role: Each picture, table and equation as an object: its box, crop, caption, Arabic and English descriptions, text inside it, LaTeX and MathML.
CREATE TABLE figures (
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  figure_id TEXT NOT NULL,             -- JATS id; inline formulas get an anchor-based id
  kind TEXT NOT NULL,                  -- figure | table | equation | inline-equation | inline-picture
  page INTEGER, x REAL, y REAL, w REAL, h REAL, alto_id TEXT,
  caption_block_id TEXT, anchor_block_id TEXT,
  label TEXT, caption TEXT, alt_ar TEXT, alt_en TEXT, text_in_figure TEXT,
  tex TEXT, mathml TEXT, specific_use TEXT,
  crop_key TEXT,
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  PRIMARY KEY (version_id, figure_id)
);

-- @role: Tables as data: every cell with its row, column and spans, so a table can be rebuilt, exported or queried.
CREATE TABLE table_cells (
  version_id INTEGER NOT NULL, figure_id TEXT NOT NULL,
  row INTEGER NOT NULL, col INTEGER NOT NULL,
  rowspan INTEGER DEFAULT 1, colspan INTEGER DEFAULT 1, is_header INTEGER DEFAULT 0,
  block_id TEXT, text TEXT,
  PRIMARY KEY (version_id, figure_id, row, col),
  FOREIGN KEY (version_id, figure_id) REFERENCES figures(version_id, figure_id)
);

-- @role: Each printed verse line, or hemistich where the print separates them, as printed with its vowels, so poetry can be searched and cited line by line.
CREATE TABLE verse_lines (
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  verse_id TEXT NOT NULL,
  group_block_id TEXT, seq INTEGER,
  part TEXT NOT NULL DEFAULT 'line',   -- line | sadr | ajuz
  text TEXT,                           -- vowelled, call marks removed
  text_bare TEXT,                      -- vowels stripped, for search
  call_ids TEXT,
  poet_hint TEXT,                      -- as printed near the verse («قال المتنبي»), not resolved
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  PRIMARY KEY (version_id, verse_id)
);

-- @role: The text-correction ledger: every word where Azure's reading, the print and a proposed correction differ (Azure misreadings fixed in the text; suspected misprints kept as printed, D30), with who said so and why.
CREATE TABLE text_corrections (
  corr_pk INTEGER PRIMARY KEY,
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  xml_id TEXT NOT NULL,                -- fixN | sicN in the masters
  layer TEXT NOT NULL,                 -- azure-misread | misprint
  block_id TEXT, char_start INTEGER, char_end INTEGER,
  azure_reading TEXT, azure_wc REAL,   -- what Azure read, and how sure it was
  printed TEXT,                        -- what the paper says (the text shown)
  proposed TEXT,                       -- misprint only: the suggested correction, never applied to the text
  applied_to_text INTEGER NOT NULL,    -- 1 for azure-misread, 0 for misprint
  why TEXT,
  asserted_by TEXT,                    -- reader | rule | judge | person
  actor_id TEXT REFERENCES actors(actor_id),
  patch_key TEXT REFERENCES patches(patch_key),
  status TEXT NOT NULL DEFAULT 'open', -- open | confirmed | rejected (by a review)
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  anchor_method TEXT,                  -- word | contains | line-only | none
  UNIQUE (version_id, xml_id)
);
CREATE INDEX corrections_block ON text_corrections(version_id, block_id);

-- @role: One searchable piece of text (block, figure description, picture text, equation, verse line, printed citation), so one search covers everything and every hit opens its ink.
CREATE TABLE search_units (
  uid INTEGER PRIMARY KEY,             -- = blocks.uid for blocks; its own range for the rest
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  unit_kind TEXT NOT NULL,             -- block | alt-text | figure-text | equation | verse | citation
  unit_id TEXT NOT NULL,
  lang TEXT,
  text TEXT,                           -- as printed (snippets come from here)
  folded TEXT,                         -- hamza/alef/ya/ta-marbuta/tatweel/diacritics folded
  stemmed TEXT,                        -- folded, with clitics و ب ل ف ك ال stripped
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  UNIQUE (version_id, unit_kind, unit_id)
);
-- Search runs on the current versions only: the loader inserts/deletes per version (no corpus-wide rebuild).
CREATE VIRTUAL TABLE search_fts USING fts5(folded, stemmed, content='search_units', content_rowid='uid');

-- ====================================================================================================== bibliographic
-- @group: Bibliographic layer — publications, the catalogue, every reading of every metadata value

-- @role: Each MARC export marc.db was built from, so every catalogue value can be traced to its export and rechecked on the next one.
CREATE TABLE catalogue_exports (
  export_id TEXT PRIMARY KEY,          -- e.g. 'marc-2026-09'
  file TEXT, sha256 TEXT, records INTEGER, built TEXT, latest_995d TEXT
);

-- @role: Mandumah's catalogue entry, keyed by the stable 999$c, as it stands in one export.
CREATE TABLE catalogue_records (
  c999 TEXT PRIMARY KEY,
  export_id TEXT REFERENCES catalogue_exports(export_id),
  rec INTEGER,                         -- position in that export only (trace back to the XML)
  record_id_001 TEXT,                  -- not unique (16,428 duplicates)
  type TEXT,                           -- 336 / Mandumah type: بحوث ومقالات | رسائل جامعية | بحوث المؤتمرات | عروض كتب
  title TEXT, subtitle TEXT, title_en TEXT, parallel_titles TEXT,
  language_raw TEXT, year_raw TEXT, year_int INTEGER, year_hijri INTEGER, month TEXT,
  pages_raw TEXT, page_first INTEGER, page_last INTEGER,
  journal_code TEXT, journal_raw TEXT, issn_raw TEXT,
  volume_raw TEXT, issue_raw TEXT, issue_printed TEXT, article_seq INTEGER,
  doi TEXT, databases TEXT,            -- HumanIndex, EduSearch, ...
  added TEXT,
  thesis_json TEXT,                    -- 502: degree, university, year
  n_pdfs INTEGER
);
CREATE INDEX catrec_journal ON catalogue_records(journal_code, year_int);

-- @role: Which files the catalogue says belong to a record (a thesis has about ten parts); files may be absent from the bucket.
CREATE TABLE catalogue_record_documents (
  c999 TEXT NOT NULL REFERENCES catalogue_records(c999),
  stem TEXT NOT NULL,                  -- not a key into documents: 87,396 catalogued files are missing
  seq INTEGER, label TEXT,
  PRIMARY KEY (c999, stem)
);
CREATE INDEX crd_stem ON catalogue_record_documents(stem);

-- @role: One scholarly item (article, thesis, conference paper, book review, editorial), whether we hold its scan or only its catalogue entry; the target of every real citation link.
CREATE TABLE publications (
  pub_id TEXT PRIMARY KEY,             -- 'W'+c999, or 'WS'+stem for an uncatalogued file (merged later via merged_ids)
  c999 TEXT UNIQUE REFERENCES catalogue_records(c999),
  journal_id TEXT REFERENCES journals(journal_id),
  issue_id TEXT REFERENCES issues(issue_id),
  seq_in_issue INTEGER,
  type TEXT,                           -- article | thesis | conference-paper | book-review | editorial | interview | report
  type_catalogue TEXT,
  status TEXT NOT NULL,                -- catalogued-only | pdf-only | azure | structured | judged | final | person-checked
  title_shown TEXT, year_shown INTEGER,  -- denormalised from the chosen assertions, refreshed per release
  current_version INTEGER REFERENCES versions(version_id)
);
CREATE INDEX pubs_issue ON publications(issue_id, seq_in_issue);

-- @role: Every value anyone gave for a bibliographic field (as printed, as corrected under D33, catalogue, Gemini title file, Qdrant payload, a person), with its place on the page; exactly one per field is chosen to show.
CREATE TABLE metadata_assertions (
  assert_pk INTEGER PRIMARY KEY,
  pub_id TEXT NOT NULL REFERENCES publications(pub_id),
  field TEXT NOT NULL,                 -- title | title_translated | subtitle | pages | volume | issue | year | doi | journal_title | language ...
  value TEXT, value_norm TEXT, lang TEXT, script TEXT,
  form TEXT NOT NULL,                  -- printed | corrected | catalogue | gemini-title | qdrant-payload | html-view | azure | person
  source TEXT NOT NULL,                -- masters | catalogue | s3-gemini-title | qdrant | judge | person | rule
  version_id INTEGER REFERENCES versions(version_id),
  export_id TEXT REFERENCES catalogue_exports(export_id),
  block_id TEXT,
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  confidence REAL,
  rule TEXT, reason TEXT,              -- D33: why the corrected form differs from the printed one
  alternatives TEXT,
  supersedes INTEGER REFERENCES metadata_assertions(assert_pk),   -- a correction points at the printed form it corrects
  actor_id TEXT REFERENCES actors(actor_id),
  patch_key TEXT REFERENCES patches(patch_key),
  is_chosen INTEGER NOT NULL DEFAULT 0,
  chosen_rule TEXT,                    -- person > judge > D33-corrected > printed > catalogue > gemini-title > qdrant
  created TEXT, load_id INTEGER REFERENCES load_events(load_id)
);
CREATE INDEX assertions_field ON metadata_assertions(pub_id, field);
CREATE UNIQUE INDEX assertions_one_chosen ON metadata_assertions(pub_id, field, lang) WHERE is_chosen = 1;

-- @role: Every date of a publication in the calendar it was printed in, paired with its converted twin, and where it was read.
CREATE TABLE publication_dates (
  date_pk INTEGER PRIMARY KEY,
  pub_id TEXT NOT NULL REFERENCES publications(pub_id),
  date_type TEXT NOT NULL,             -- published | received | accepted | defended | issue
  calendar TEXT NOT NULL,              -- gregorian | hijri
  year INTEGER, month INTEGER, day INTEGER,
  precision TEXT,                      -- year | month | day | season
  printed TEXT, month_name_printed TEXT,   -- 'آب 1977', 'رمضان وشوال'
  pair_pk INTEGER REFERENCES publication_dates(date_pk),   -- its twin in the other calendar
  derivation TEXT,                     -- read | converted | catalogue
  assert_pk INTEGER REFERENCES metadata_assertions(assert_pk),
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk)
);
CREATE INDEX dates_year ON publication_dates(calendar, year);

-- @role: The language code list (ISO 639-2/B as key, with 639-1 and names in Arabic and English).
CREATE TABLE languages (
  code TEXT PRIMARY KEY,               -- ara | fre | eng | ...
  code1 TEXT, code2t TEXT, name_ar TEXT, name_en TEXT
);

-- @role: Which languages a publication is in, by role (text, abstract, title), and how we know.
CREATE TABLE publication_languages (
  pub_id TEXT NOT NULL REFERENCES publications(pub_id),
  lang TEXT NOT NULL REFERENCES languages(code),
  role TEXT NOT NULL,                  -- text | abstract | title | summary
  source TEXT, method TEXT,            -- catalogue-041 | script-share | detector:<name>
  share REAL,
  PRIMARY KEY (pub_id, lang, role)
);

-- @role: An abstract as printed or as catalogued, with its detected language and its place on the page.
CREATE TABLE abstracts (
  abstract_pk INTEGER PRIMARY KEY,
  pub_id TEXT NOT NULL REFERENCES publications(pub_id),
  lang TEXT REFERENCES languages(code), lang_method TEXT,
  seq INTEGER, text TEXT,
  form TEXT NOT NULL,                  -- printed | catalogue
  version_id INTEGER REFERENCES versions(version_id),
  export_id TEXT REFERENCES catalogue_exports(export_id),
  block_id TEXT,
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk)
);

-- @role: An author keyword as a term that can be counted across the archive.
CREATE TABLE keyword_terms (
  term_id INTEGER PRIMARY KEY,
  term_key TEXT NOT NULL UNIQUE,       -- folded
  display TEXT, lang TEXT
);

-- @role: Which publication carries which keyword, as printed and from which source.
CREATE TABLE publication_keywords (
  pub_id TEXT NOT NULL REFERENCES publications(pub_id),
  term_id INTEGER NOT NULL REFERENCES keyword_terms(term_id),
  source TEXT NOT NULL,                -- masters | catalogue
  seq INTEGER, printed TEXT,
  version_id INTEGER REFERENCES versions(version_id),
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  PRIMARY KEY (pub_id, term_id, source)
);

-- @role: A catalogue subject heading or field of study, its Arabic and English forms as one term.
CREATE TABLE subject_terms (
  subject_id INTEGER PRIMARY KEY,
  scheme TEXT NOT NULL,                -- 653 | field-of-study | database
  term_ar TEXT, term_en TEXT, term_key TEXT NOT NULL,
  UNIQUE (scheme, term_key)
);

-- @role: Which subjects the catalogue gives a record.
CREATE TABLE record_subjects (
  c999 TEXT NOT NULL REFERENCES catalogue_records(c999),
  subject_id INTEGER NOT NULL REFERENCES subject_terms(subject_id),
  seq INTEGER,
  PRIMARY KEY (c999, subject_id)
);

-- @role: One journal (Mandumah's journal code) with its country and the databases it is indexed in.
CREATE TABLE journals (
  journal_id TEXT PRIMARY KEY,         -- 'J'+code
  code TEXT NOT NULL UNIQUE,
  country_code TEXT,                   -- ISO 3166-1
  databases TEXT,
  first_year INTEGER, last_year INTEGER
);

-- @role: Every name a journal has had or been printed under, in which years, from which source.
CREATE TABLE journal_titles (
  journal_id TEXT NOT NULL REFERENCES journals(journal_id),
  title TEXT NOT NULL, lang TEXT,
  form TEXT NOT NULL,                  -- printed | running-head | catalogue | catalogue-en | romanised | person
  from_year INTEGER, to_year INTEGER, n INTEGER,
  source TEXT, is_chosen INTEGER DEFAULT 0,
  PRIMARY KEY (journal_id, title, form)
);

-- @role: Every ISSN string seen for a journal, cleaned and check-digit tested, with its ISSN-L.
CREATE TABLE journal_issns (
  journal_id TEXT NOT NULL REFERENCES journals(journal_id),
  issn_raw TEXT NOT NULL,
  issn TEXT, valid_check INTEGER, kind TEXT,  -- print | online | unknown
  issn_l TEXT, n_records INTEGER, source TEXT, note TEXT,
  PRIMARY KEY (journal_id, issn_raw)
);

-- @role: A publisher (a university, society, ministry or press) as an entity.
CREATE TABLE publishers (
  publisher_id TEXT PRIMARY KEY,       -- 'P...'
  name TEXT, name_en TEXT, country_code TEXT,
  inst_id TEXT REFERENCES institutions(inst_id)
);

-- @role: Which publisher published a journal, in which years.
CREATE TABLE journal_publishers (
  journal_id TEXT NOT NULL REFERENCES journals(journal_id),
  publisher_id TEXT NOT NULL REFERENCES publishers(publisher_id),
  from_year INTEGER, to_year INTEGER, source TEXT,
  PRIMARY KEY (journal_id, publisher_id)
);

-- @role: One physical issue of a journal, with its printed label, numbers, special/joint marks and both calendars.
CREATE TABLE issues (
  issue_id TEXT PRIMARY KEY,           -- 'J<code>/<volume_raw>/<issue_raw>'
  journal_id TEXT NOT NULL REFERENCES journals(journal_id),
  volume_raw TEXT, volume_num INTEGER,
  issue_raw TEXT, issue_printed TEXT,
  is_special INTEGER DEFAULT 0, is_joint INTEGER DEFAULT 0,
  year_greg INTEGER, year_hijri INTEGER, date_printed TEXT
);

-- @role: The issue numbers one physical issue covers (a joint issue "3,4" has two rows).
CREATE TABLE issue_numbers (
  issue_id TEXT NOT NULL REFERENCES issues(issue_id),
  number INTEGER NOT NULL,
  PRIMARY KEY (issue_id, number)
);

-- @role: Every outside identifier of a publication, journal, person, institution or cited work, and who assigned it.
CREATE TABLE external_ids (
  entity_kind TEXT NOT NULL,           -- W | J | A | I | C
  entity_id TEXT NOT NULL,
  scheme TEXT NOT NULL,                -- doi | c999 | 001 | issn-l | isbn | orcid | viaf | wikidata | ror | qdrant-doc | s3-key
  value TEXT NOT NULL,
  assigned_by TEXT,                    -- mandumah | publisher | crossref | person | link47
  source TEXT,
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),   -- a DOI printed on the page
  PRIMARY KEY (entity_kind, entity_id, scheme, value)
);
CREATE INDEX extids_value ON external_ids(scheme, value);

-- ====================================================================================================== people
-- @group: People and institutions — printed mentions, entities, and the links between them

-- @role: The controlled list of contributor roles (author, co-author, translator, reviewer of a book, editor, supervisor...).
CREATE TABLE role_codes (
  code TEXT PRIMARY KEY,               -- author | coauthor | translator | reviewer | editor | supervisor | interviewer | compiler | original-author | editor-of-text (محقق)
  name_ar TEXT, name_en TEXT,
  counts_as_author INTEGER NOT NULL DEFAULT 1
);

-- @role: One real person, with an id that never changes across rebuilds.
CREATE TABLE persons (
  person_id TEXT PRIMARY KEY,          -- 'A...' from id_registry
  status TEXT NOT NULL,                -- active | provisional | merged
  preferred_name_ar TEXT, preferred_name_lat TEXT,
  birth_year_h INTEGER, birth_year_g INTEGER, death_year_h INTEGER, death_year_g INTEGER,
  source TEXT,                         -- catalogue-authority | cluster | person
  created_load INTEGER REFERENCES load_events(load_id)
);

-- @role: Which Mandumah authority ids belong to a person (a cataloguer's decision, our highest-trust identity signal); two when the catalogue has a duplicate.
CREATE TABLE person_authorities (
  authority_id TEXT PRIMARY KEY,       -- never ''
  person_id TEXT NOT NULL REFERENCES persons(person_id),
  heading TEXT, n_records INTEGER,
  relation TEXT NOT NULL DEFAULT 'same',   -- same | duplicate-in-catalogue
  asserted_by TEXT, reason TEXT
);

-- @role: Every way a person's name is written (printed, catalogue heading, Latin form, cited form, initials), split into its Arabic name parts.
CREATE TABLE person_names (
  name_pk INTEGER PRIMARY KEY,
  person_id TEXT NOT NULL REFERENCES persons(person_id),
  full_form TEXT NOT NULL, script TEXT, lang TEXT,
  form_type TEXT NOT NULL,             -- printed | catalogue-heading | catalogue-latin | cited | transliteration | initials | pseudonym
  ism TEXT, nasab TEXT, nisba TEXT, laqab TEXT, kunya TEXT, family TEXT,
  name_key TEXT,                       -- folded, for matching (never an identity)
  n_seen INTEGER, source TEXT,
  UNIQUE (person_id, full_form, form_type)
);
CREATE INDEX person_names_key ON person_names(name_key);

-- @role: Arabic↔Latin name-token pairs learned from the catalogue's own Latin headings (232k authority ids), used to match Latin bylines and citations and to search across scripts.
CREATE TABLE translit_pairs (
  arabic TEXT NOT NULL, latin TEXT NOT NULL,
  n INTEGER NOT NULL, share REAL,
  source TEXT NOT NULL DEFAULT 'catalogue-latin',
  PRIMARY KEY (arabic, latin)
);

-- @role: A name exactly as printed in one version's byline, with its titles («د.», «الشيخ») kept and its box on the scan; never changed by matching.
CREATE TABLE byline_mentions (
  mention_pk INTEGER PRIMARY KEY,
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  byline_pos INTEGER NOT NULL,
  printed TEXT NOT NULL,               -- whole printed string
  titles TEXT,                         -- د. | أ.د. | الشيخ | الدكتور ... (kept, not thrown away)
  name_text TEXT, script TEXT, email TEXT,
  block_id TEXT,
  min_word_conf REAL, reader_fixes TEXT,
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  UNIQUE (version_id, block_id, byline_pos, script)
);

-- @role: Every contributor heading on a catalogue record (100/110/700), with its normalised role and authority id.
CREATE TABLE catalogue_contributors (
  c999 TEXT NOT NULL REFERENCES catalogue_records(c999),
  seq INTEGER NOT NULL,
  tag TEXT, name TEXT, latin TEXT,
  role_raw TEXT, role_code TEXT REFERENCES role_codes(code),
  authority_id TEXT,                   -- NULL, never ''
  is_org INTEGER DEFAULT 0, life_note TEXT,   -- «ت. 1973 م»
  PRIMARY KEY (c999, seq)
);
CREATE INDEX catcontrib_auth ON catalogue_contributors(authority_id);

-- @role: One person's (or body's) part in one publication: role, position, and how we know who they are.
CREATE TABLE authorships (
  authorship_pk INTEGER PRIMARY KEY,
  pub_id TEXT NOT NULL REFERENCES publications(pub_id),
  position INTEGER NOT NULL,
  role_code TEXT NOT NULL REFERENCES role_codes(code), role_raw TEXT,
  person_id TEXT REFERENCES persons(person_id),
  inst_id TEXT REFERENCES institutions(inst_id),   -- corporate byline (اللجنة الوطنية ...)
  c999 TEXT, catalogue_seq INTEGER,
  is_corresponding INTEGER DEFAULT 0,
  method TEXT,                         -- exact | token-subset | transliteration | script-twin | corporate | initials | catalogue-only | person
  score REAL,                          -- NULL when nothing was compared
  asserted_by TEXT NOT NULL,           -- link47 | judge | person | catalogue
  evidence TEXT,                       -- JSON
  from_version INTEGER REFERENCES versions(version_id),
  patch_key TEXT REFERENCES patches(patch_key),
  FOREIGN KEY (c999, catalogue_seq) REFERENCES catalogue_contributors(c999, seq),
  UNIQUE (pub_id, position, role_code)
);
CREATE INDEX authorships_person ON authorships(person_id);

-- @role: Joins the printed forms of a name (an Arabic and a Latin byline of the same author) to the one authorship they belong to.
CREATE TABLE authorship_mentions (
  authorship_pk INTEGER NOT NULL REFERENCES authorships(authorship_pk),
  mention_pk INTEGER NOT NULL REFERENCES byline_mentions(mention_pk),
  PRIMARY KEY (authorship_pk, mention_pk)
);

-- @role: An affiliation exactly as printed, split into position, department, faculty, organisation and place, with its box.
CREATE TABLE affiliation_mentions (
  aff_pk INTEGER PRIMARY KEY,
  mention_pk INTEGER NOT NULL REFERENCES byline_mentions(mention_pk),
  seq INTEGER NOT NULL,
  printed TEXT NOT NULL,
  position_title TEXT,                 -- «مدرس القانون الدولي العام» (kept)
  org_text TEXT, faculty_text TEXT, dept_text TEXT, city TEXT,
  country_printed TEXT, country_code TEXT,
  kind TEXT,                           -- institution | position-only | place-only
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  UNIQUE (mention_pk, seq)
);

-- @role: Which institution(s) a printed affiliation was matched to, with method, score and who said so.
CREATE TABLE affiliation_links (
  aff_pk INTEGER NOT NULL REFERENCES affiliation_mentions(aff_pk),
  inst_id TEXT NOT NULL REFERENCES institutions(inst_id),
  level TEXT,                          -- org | faculty | dept
  method TEXT, score REAL, asserted_by TEXT NOT NULL, evidence TEXT,
  PRIMARY KEY (aff_pk, inst_id)
);

-- @role: One university, faculty, department, ministry or centre, with a stable id and its parent.
CREATE TABLE institutions (
  inst_id TEXT PRIMARY KEY,            -- 'I...' from id_registry (never a path)
  kind TEXT,                           -- university | faculty | department | ministry | centre | society | press | committee
  parent_id TEXT REFERENCES institutions(inst_id),
  country_code TEXT, city TEXT,
  status TEXT NOT NULL DEFAULT 'active',   -- active | renamed | merged | closed | provisional
  catalogue_authority_id TEXT,         -- corporate authority «مصر. جامعة القاهرة. كلية الحقوق»
  source TEXT
);

-- @role: All names of an institution in Arabic, Latin and French, each typed; no single "primary" name (ROR style).
CREATE TABLE institution_names (
  inst_id TEXT NOT NULL REFERENCES institutions(inst_id),
  name TEXT NOT NULL, lang TEXT, script TEXT,
  type TEXT NOT NULL,                  -- label | alias | acronym | printed | catalogue-heading | dissertation-502c
  name_key TEXT, n_seen INTEGER, source TEXT,
  PRIMARY KEY (inst_id, name, type)
);
CREATE INDEX inst_names_key ON institution_names(name_key);

-- @role: How institutions relate over time: part of, renamed to, successor of.
CREATE TABLE institution_relations (
  from_id TEXT NOT NULL REFERENCES institutions(inst_id),
  to_id TEXT NOT NULL REFERENCES institutions(inst_id),
  relation TEXT NOT NULL,              -- parent | successor | predecessor | related
  start_year INTEGER, end_year INTEGER, source TEXT, reason TEXT,
  PRIMARY KEY (from_id, to_id, relation)
);

-- @role: Who supervised whose thesis, where and when: the Arab world's academic family tree, from the catalogue.
CREATE TABLE supervisions (
  c999 TEXT NOT NULL REFERENCES catalogue_records(c999),
  supervisor_person_id TEXT NOT NULL REFERENCES persons(person_id),
  student_person_id TEXT REFERENCES persons(person_id),
  degree TEXT, inst_id TEXT REFERENCES institutions(inst_id), country_code TEXT,
  year_greg INTEGER, year_hijri INTEGER,
  source TEXT NOT NULL DEFAULT 'catalogue',
  PRIMARY KEY (c999, supervisor_person_id)
);

-- ====================================================================================================== citations
-- @group: Citations — every place something is cited, the works cited, and real links only

-- @role: Each place on a page where an article cites something (full citation, short form, «المرجع السابق»/«نفسه»/ibid./op. cit., Quran, hadith), with its ink and the first full citation it counts for.
CREATE TABLE citation_mentions (
  mention_pk INTEGER PRIMARY KEY,
  mention_id TEXT NOT NULL UNIQUE,     -- '<stem>|p<page>|w<first>-<last>|<n>': built on Azure word numbers, so it survives a new run
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  container_kind TEXT NOT NULL,        -- note | ref-list | body
  container_id TEXT,                   -- note_id / ref id / block_id
  reading_ord INTEGER NOT NULL,        -- order of the citation in the article's reading (note stream order)
  seq_in_container INTEGER NOT NULL,
  kind TEXT NOT NULL,                  -- full | short | ibid | op_cit | loc_cit | see_also | quran | hadith
  marker TEXT,                         -- the back-reference words as printed
  printed TEXT,                        -- the citation's own span, as printed
  printed_fixed TEXT,                  -- the same span with Azure misreadings fixed (what the linker also tries)
  parsed TEXT,                         -- JSON: authors, title, source, place, publisher, year, edition ...
  cited_volume TEXT, cited_pages TEXT, -- the locator: the page cited, not the work's pages
  page INTEGER,
  block_id TEXT,
  n_fixes_on_lines INTEGER, n_misprints_on_lines INTEGER, max_flag TEXT,
  trust REAL,
  full_mention_pk INTEGER REFERENCES citation_mentions(mention_pk),
      -- for kind full: itself; for a back-reference: the FIRST full citation of that work in the article (chains collapsed)
  resolve_method TEXT,                 -- self | previous-mention | same-author-earliest | title-words | person
  resolve_score REAL, resolve_evidence TEXT,
  resolved_by TEXT,                    -- link47 | judge | person
  unresolved_why TEXT,                 -- no-earlier-full | ambiguous-author | no-parse | ...
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  CHECK (kind <> 'full' OR full_mention_pk IS NULL OR full_mention_pk = mention_pk)
);
CREATE INDEX cm_version ON citation_mentions(version_id, reading_ord);
CREATE INDEX cm_full ON citation_mentions(full_mention_pk);

-- @role: One book, article, thesis, diwan or manuscript cited anywhere in the archive, the same whichever articles cite it, with its own times-cited even when it is not in Mandumah (most cited books are not).
CREATE TABLE cited_works (
  cited_work_pk INTEGER PRIMARY KEY,
  cited_work_id TEXT NOT NULL UNIQUE,  -- 'C...' from id_registry
  pub_type TEXT,                       -- book | article | thesis | chapter | conference-paper | manuscript | diwan | web | quran | hadith-collection
  title TEXT, title_key TEXT, first_author_key TEXT,
  year_printed TEXT, year_calendar TEXT, year_hijri INTEGER, year_greg INTEGER,
  edition_note TEXT, place TEXT, publisher TEXT, lang TEXT,
  status TEXT NOT NULL DEFAULT 'active',   -- active | merged
  method TEXT, built_load INTEGER REFERENCES load_events(load_id)
);
CREATE INDEX cw_key ON cited_works(first_author_key, title_key);

-- @role: Which full citations were grouped into each cited work, why, and by whom; a person can move one with a patch.
CREATE TABLE cited_work_members (
  full_mention_pk INTEGER PRIMARY KEY REFERENCES citation_mentions(mention_pk),
  cited_work_pk INTEGER NOT NULL REFERENCES cited_works(cited_work_pk),
  method TEXT, score REAL, evidence TEXT,
  asserted_by TEXT NOT NULL,
  patch_key TEXT REFERENCES patches(patch_key)
);
CREATE INDEX cwm_work ON cited_work_members(cited_work_pk);

-- @role: The authors of a cited work split into the parts of an Arabic name, tied to a person where the catalogue identifies them.
CREATE TABLE cited_work_authors (
  cited_work_pk INTEGER NOT NULL REFERENCES cited_works(cited_work_pk),
  seq INTEGER NOT NULL,
  printed TEXT,
  honorific TEXT, kunya TEXT, ism TEXT, nasab TEXT, nisba TEXT, laqab TEXT, shuhra TEXT,  -- «ابن جني» is shuhra
  latin TEXT, name_key TEXT,
  person_id TEXT REFERENCES persons(person_id),
  authority_id TEXT,
  match_method TEXT, match_score REAL,
  PRIMARY KEY (cited_work_pk, seq)
);
CREATE INDEX cwa_person ON cited_work_authors(person_id);

-- @role: One pass of the linker: its code, thresholds and catalogue export, so any link can be reproduced.
CREATE TABLE link_runs (
  link_run_id INTEGER PRIMARY KEY,
  linker TEXT NOT NULL, code_hash TEXT, thresholds TEXT,
  export_id TEXT REFERENCES catalogue_exports(export_id),
  started TEXT, finished TEXT, n_versions INTEGER, n_links INTEGER
);

-- @role: Which versions one linker pass covered.
CREATE TABLE link_run_versions (
  link_run_id INTEGER NOT NULL REFERENCES link_runs(link_run_id),
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  PRIMARY KEY (link_run_id, version_id)
);

-- @role: A REAL link only: a cited work found as a publication of the archive or catalogue (or an outside id), with status, score, method, evidence and who said so. No back-reference, no relation, no self-link.
CREATE TABLE citation_links (
  link_pk INTEGER PRIMARY KEY,
  cited_work_pk INTEGER NOT NULL REFERENCES cited_works(cited_work_pk),
  via_mention_pk INTEGER REFERENCES citation_mentions(mention_pk),   -- the full mention whose text matched
  target_kind TEXT NOT NULL,           -- publication | external
  target_pub_id TEXT REFERENCES publications(pub_id),   -- scanned or catalogued-only: both are publications
  target_scheme TEXT, target_value TEXT,   -- doi / isbn / wikidata when external
  status TEXT NOT NULL,                -- accepted | candidate | rejected
  best INTEGER NOT NULL DEFAULT 0,
  score REAL, method TEXT,             -- catalogue-fts+validate | article-fts+validate | doi | person
  matched_on TEXT,                     -- printed | printed_fixed
  evidence TEXT,
  asserted_by TEXT NOT NULL,           -- link47 | judge | person
  link_run_id INTEGER REFERENCES link_runs(link_run_id),
  created TEXT,
  CHECK ((target_kind = 'publication' AND target_pub_id IS NOT NULL) OR (target_kind = 'external' AND target_value IS NOT NULL)),
  UNIQUE (cited_work_pk, target_kind, target_pub_id, target_value)
);
CREATE INDEX links_target ON citation_links(target_pub_id, status);
CREATE UNIQUE INDEX links_one_best ON citation_links(cited_work_pk) WHERE best = 1;

-- @role: A typed relation between a cited work and another item (reviewed in, studied in, part of, edition or translation of), stored with its reverse, separate from citations.
CREATE TABLE work_relations (
  relation_pk INTEGER PRIMARY KEY,
  subject_cited_work_pk INTEGER NOT NULL REFERENCES cited_works(cited_work_pk),
  relation TEXT NOT NULL,              -- is_reviewed_in | is_studied_in | is_part_of | is_edition_of | is_translation_of
  inverse TEXT NOT NULL,               -- reviews | studies | has_part | has_edition | has_translation
  object_pub_id TEXT REFERENCES publications(pub_id),
  object_cited_work_pk INTEGER REFERENCES cited_works(cited_work_pk),
  score REAL, method TEXT, evidence TEXT, asserted_by TEXT NOT NULL,
  link_run_id INTEGER REFERENCES link_runs(link_run_id)
);

-- @role: A reference text of the Quran (sura, aya, text) to match quotations against; source and licence recorded.
CREATE TABLE quran_ayat (
  sura INTEGER NOT NULL, aya INTEGER NOT NULL,
  text_uthmani TEXT, text_simple TEXT, text_key TEXT,
  sura_name_ar TEXT,
  source TEXT NOT NULL, licence TEXT,
  PRIMARY KEY (sura, aya)
);

-- @role: Every place an article quotes or cites the Quran, by sura and aya: a Quran citation index no other index has.
CREATE TABLE quran_citations (
  qc_pk INTEGER PRIMARY KEY,
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  source_kind TEXT NOT NULL,           -- inline-quote (﴿…﴾) | note-ref («سورة البقرة، الآية ٢٥٥») | both
  mention_pk INTEGER REFERENCES citation_mentions(mention_pk),
  block_id TEXT,
  quoted_text TEXT, printed_ref TEXT,
  sura INTEGER, aya_from INTEGER, aya_to INTEGER,
  method TEXT,                         -- bracket+match | ref-only | match-only | person
  score REAL, checked_by TEXT,
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  FOREIGN KEY (sura, aya_from) REFERENCES quran_ayat(sura, aya)
);
CREATE INDEX qc_aya ON quran_citations(sura, aya_from);

-- ====================================================================================================== quality
-- @group: Quality — flags, judge, patches, reviews, catalogue reports: the trust behind every value

-- @role: Each automatic check that raises flags, with its code version and thresholds, so "resolved" can be told from "new detector".
CREATE TABLE flag_detectors (
  detector_id TEXT PRIMARY KEY,        -- '<kind>@<code_hash8>'
  kind TEXT NOT NULL, code_hash TEXT, thresholds TEXT, introduced TEXT
);

-- @role: One warning raised by a code check on one version's page, tied to the detector that raised it and to its ink.
CREATE TABLE flags (
  version_id INTEGER NOT NULL REFERENCES versions(version_id),
  flag_id TEXT NOT NULL,               -- natural id, stable across runs
  detector_id TEXT REFERENCES flag_detectors(detector_id),
  kind TEXT NOT NULL, severity TEXT,
  page INTEGER, block_id TEXT,
  lines_raw TEXT, box_raw TEXT,        -- as in the flag file ('2:1', 0-1000 box)
  reason TEXT, extra TEXT,
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  PRIMARY KEY (version_id, flag_id)
);

-- @role: One look by one judge model and prompt at one page, kept even when it found nothing, with its cost.
CREATE TABLE judge_calls (
  call_id TEXT PRIMARY KEY,            -- '<run>|<stem>|p<page>|<model>|<prompt_version>'
  run TEXT NOT NULL REFERENCES runs(run),
  version_id INTEGER REFERENCES versions(version_id),   -- the version that was judged
  stem TEXT NOT NULL, page INTEGER,
  model TEXT, prompt_version TEXT, view TEXT, mode TEXT,
  usd REAL, tokens_in INTEGER, tokens_out INTEGER, finish TEXT,
  verdict TEXT,                        -- clean | problems | failed
  root_id TEXT REFERENCES storage_roots(root_id), file_key TEXT, sha TEXT
);

-- @role: One problem a judge named on a page, with its route (auto, retry, human) and its ink.
CREATE TABLE judge_findings (
  finding_pk INTEGER PRIMARY KEY,
  call_id TEXT NOT NULL REFERENCES judge_calls(call_id),
  k INTEGER NOT NULL,
  type TEXT, subtype TEXT, confidence REAL,
  question TEXT, answer TEXT, evidence TEXT, code_check TEXT,
  action TEXT, route TEXT,             -- auto | retry | human
  targets_raw TEXT,
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  UNIQUE (call_id, k)
);

-- @role: One proposed correction (structure, text, metadata, who-is-who, citation grouping) from a person, the judge or a retry; never changed after it is made.
CREATE TABLE patches (
  patch_key TEXT PRIMARY KEY,          -- '<run>|<stem>|<patch_id>' (upstream ids collide across a journal's articles)
  run TEXT REFERENCES runs(run), stem TEXT, patch_id TEXT NOT NULL,
  domain TEXT NOT NULL,                -- content | metadata | entity | citation | catalogue
  op TEXT NOT NULL,                    -- split_block | set_kind | replace_page_blocks | merge | split | assign-mention | set-parent | move-member | not-a-person ...
  page INTEGER, targets TEXT, payload TEXT,
  source TEXT NOT NULL,                -- person | judge | gemini-retry | rule
  priority INTEGER NOT NULL,           -- person 1 > judge 2 > gemini-retry 3 > rule 4
  actor_id TEXT REFERENCES actors(actor_id),
  finding_pk INTEGER REFERENCES judge_findings(finding_pk),
  confidence REAL, evidence TEXT, reason TEXT,
  apply INTEGER NOT NULL DEFAULT 1,
  created TEXT, root_id TEXT REFERENCES storage_roots(root_id), file_key TEXT, sha TEXT,
  payload_copy TEXT                    -- only for person patches (they cannot be regenerated)
);
CREATE INDEX patches_stem ON patches(stem);

-- @role: What happened to a patch in each build or rebuild that saw it (applied, skipped, overridden).
CREATE TABLE patch_applications (
  patch_key TEXT NOT NULL REFERENCES patches(patch_key),
  version_id INTEGER,                  -- content patches: the version built; NULL for entity/citation patches
  load_id INTEGER NOT NULL REFERENCES load_events(load_id),
  status TEXT NOT NULL,                -- applied | skipped | overridden | proposed
  why TEXT,
  PRIMARY KEY (patch_key, load_id),
  FOREIGN KEY (version_id) REFERENCES versions(version_id)
);

-- @role: Every human or agent verdict on anything (a link, a resolution, a grouping, a finding, a flag, a correction, a page, a gold item): the ground truth trust scores are calibrated on.
CREATE TABLE reviews (
  review_pk INTEGER PRIMARY KEY,
  subject_kind TEXT NOT NULL,          -- link | relation | resolution | membership | authorship | finding | flag | correction | assertion | page | article
  subject_key TEXT NOT NULL,           -- stable id (mention_id, link fingerprint, flag_id ...)
  subject_fingerprint TEXT,            -- hash of what was seen, so a verdict re-attaches after rebuilds or is marked stale
  verdict TEXT NOT NULL,               -- right | wrong | partly | unsure
  note TEXT,
  actor_id TEXT REFERENCES actors(actor_id),
  checked TEXT,
  is_gold INTEGER NOT NULL DEFAULT 0,
  source_file TEXT                     -- judge_verdicts43.json, judge_truth43.json, gold/, handcheck/, link_checks
);
CREATE INDEX reviews_subject ON reviews(subject_kind, subject_key);

-- @role: A problem found in Mandumah's catalogue (or a print-vs-catalogue disagreement), with who is right, its evidence on the page, and whether Mandumah was told and fixed it in a later export.
CREATE TABLE catalogue_reports (
  report_pk INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,                  -- invalid-issn | stem-on-several-records | duplicate-001 | duplicate-authority | missing-author | name-differs | role-wrong | corporate-as-person | page-range | year | hijri-as-gregorian | title | language | author-count | missing-file | missing-record
  field TEXT,
  c999 TEXT REFERENCES catalogue_records(c999),
  pub_id TEXT REFERENCES publications(pub_id),
  stem TEXT, version_id INTEGER REFERENCES versions(version_id),
  authority_ids TEXT, mention_pk INTEGER REFERENCES byline_mentions(mention_pk),
  catalogue_value TEXT, our_value TEXT,
  who_is_right TEXT NOT NULL DEFAULT 'unknown',   -- print | catalogue | both-wrong | unknown
  severity TEXT, evidence TEXT,
  assert_pk INTEGER REFERENCES metadata_assertions(assert_pk),   -- the D33 correction it rests on
  anchor_pk INTEGER REFERENCES ink_anchors(anchor_pk),
  found_in_export TEXT REFERENCES catalogue_exports(export_id),
  status TEXT NOT NULL DEFAULT 'open', -- open | sent | accepted | rejected | fixed
  batch TEXT, fixed_in_export TEXT REFERENCES catalogue_exports(export_id),
  load_id INTEGER REFERENCES load_events(load_id), note TEXT
);
CREATE INDEX catreports_kind ON catalogue_reports(kind, status);

-- ====================================================================================================== outside
-- @group: Ties to what Mandumah already runs — semantic search and users' feedback

-- @role: A link from each existing Qdrant point (mandumah_v2) to its document and, where offsets allow, its blocks, so a semantic hit opens the page and its payload counts as one more metadata reading.
CREATE TABLE vector_points (
  collection TEXT NOT NULL,            -- mandumah_v2
  point_id TEXT NOT NULL,
  stem TEXT,                           -- payload doc_id; not a key: points exist for documents we have not loaded
  section TEXT,
  version_id INTEGER REFERENCES versions(version_id),
  block_from TEXT, block_to TEXT,
  map_method TEXT,                     -- doc-only | section | text-overlap
  map_score REAL,
  PRIMARY KEY (collection, point_id)
);
CREATE INDEX vp_stem ON vector_points(stem);

-- @role: Users' feedback on Mandumah's AI search (from the ai_search_feedback MySQL dumps), as query/document judgements without user identities.
CREATE TABLE search_feedback (
  feedback_pk INTEGER PRIMARY KEY,
  dump TEXT NOT NULL,                  -- the nightly dump it came from
  source_row TEXT,                     -- its id in the dump
  query TEXT, stem TEXT,
  verdict TEXT,                        -- as the dump records it (columns fixed once the dump is inspected)
  given TEXT,
  user_hash TEXT                       -- salted hash only; never names or emails
);
CREATE INDEX sf_stem ON search_feedback(stem);

-- ====================================================================================================== derived
-- Views: computed, never stored. At scale the heavy ones are materialised per release (same names, `_m` suffix),
-- with the release's load_id, window and document types written next to each number.

-- Back-compat: the v46 `articles` row, shown for the current version of each document.
CREATE VIEW v_articles AS
SELECT d.stem, p.pub_id, p.c999, p.journal_id, p.issue_id, p.type, p.status, d.level,
       v.run AS current_run, v.version_id, v.complete, v.usd,
       (SELECT value FROM metadata_assertions a WHERE a.pub_id = p.pub_id AND a.field = 'title' AND a.is_chosen = 1 LIMIT 1) AS title,
       (SELECT value FROM metadata_assertions a WHERE a.pub_id = p.pub_id AND a.field = 'title' AND a.form = 'printed' AND a.version_id = v.version_id LIMIT 1) AS title_printed,
       p.year_shown AS pub_year
FROM documents d
LEFT JOIN publications p ON p.pub_id = d.pub_id
LEFT JOIN versions v ON v.stem = d.stem AND v.is_current = 1;

-- Back-compat: fixes and misprints of v46 are two slices of the ledger.
CREATE VIEW v_fixes AS
SELECT v.stem, v.run, c.xml_id AS fix_id, c.azure_reading, c.printed AS print, c.why, c.azure_wc, c.block_id, c.anchor_pk
FROM text_corrections c JOIN versions v USING (version_id) WHERE c.layer = 'azure-misread';
CREATE VIEW v_misprints AS
SELECT v.stem, v.run, c.xml_id AS sic_id, c.printed, c.proposed, c.why, c.block_id, c.anchor_pk, c.status
FROM text_corrections c JOIN versions v USING (version_id) WHERE c.layer = 'misprint';

-- D33 log: each corrected value beside the printed one it corrects.
CREATE VIEW v_metadata_changes AS
SELECT c.pub_id, c.field, p.value AS printed, c.value AS corrected, c.source AS change_source, c.reason, c.rule,
       c.alternatives, c.actor_id, c.version_id, p.anchor_pk AS printed_anchor
FROM metadata_assertions c JOIN metadata_assertions p ON p.assert_pk = c.supersedes
WHERE c.form IN ('corrected', 'person');

-- Print vs catalogue, recomputed from the assertions (no stale snapshot).
CREATE VIEW v_catalogue_disagreements AS
SELECT pr.pub_id, pr.field, pr.value AS printed_value, ca.value AS catalogue_value, pr.anchor_pk
FROM metadata_assertions pr
JOIN metadata_assertions ca ON ca.pub_id = pr.pub_id AND ca.field = pr.field AND ca.form = 'catalogue'
WHERE pr.form = 'printed' AND coalesce(pr.value_norm, pr.value) <> coalesce(ca.value_norm, ca.value);

-- Each citation counted where it belongs: every mention (full or back-reference) of a work in one article.
CREATE VIEW v_mention_work AS
SELECT m.mention_pk, m.version_id, v.stem, d.pub_id AS citing_pub_id, m.kind,
       coalesce(m.full_mention_pk, m.mention_pk) AS full_mention_pk, w.cited_work_pk
FROM citation_mentions m
JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
JOIN documents d ON d.stem = v.stem
LEFT JOIN cited_work_members w ON w.full_mention_pk = coalesce(m.full_mention_pk, m.mention_pk)
WHERE m.kind NOT IN ('quran', 'hadith');

-- Times cited per cited work: citing publications (WoS headline) and all mentions incl. «المرجع السابق».
CREATE VIEW v_times_cited AS
SELECT cited_work_pk, count(DISTINCT citing_pub_id) AS n_citing_pubs, count(*) AS n_mentions,
       sum(kind = 'full') AS n_full, sum(kind IN ('ibid', 'op_cit', 'loc_cit', 'short')) AS n_backrefs
FROM v_mention_work WHERE cited_work_pk IS NOT NULL GROUP BY cited_work_pk;

-- Times cited per archive/catalogue publication, through accepted best links only.
CREATE VIEW v_pub_times_cited AS
SELECT l.target_pub_id AS pub_id, count(DISTINCT mw.citing_pub_id) AS n_citing_pubs, count(*) AS n_mentions
FROM citation_links l JOIN v_mention_work mw ON mw.cited_work_pk = l.cited_work_pk
WHERE l.status = 'accepted' AND l.best = 1 AND l.target_kind = 'publication'
GROUP BY l.target_pub_id;

-- True self-citation: an author of the citing publication is an author of the cited work (shared person id).
CREATE VIEW v_author_self_citations AS
SELECT DISTINCT mw.citing_pub_id, mw.cited_work_pk, au.person_id
FROM v_mention_work mw
JOIN authorships au ON au.pub_id = mw.citing_pub_id AND au.person_id IS NOT NULL
JOIN cited_work_authors ca ON ca.cited_work_pk = mw.cited_work_pk AND ca.person_id = au.person_id;

-- Journal self-citation and journal pairs (citation stacking), through accepted links.
CREATE VIEW v_journal_citation_pairs AS
SELECT cp.journal_id AS citing_journal, tp.journal_id AS cited_journal,
       count(DISTINCT mw.citing_pub_id) AS n_citing_pubs, count(*) AS n_mentions,
       cp.journal_id = tp.journal_id AS is_self
FROM v_mention_work mw
JOIN citation_links l ON l.cited_work_pk = mw.cited_work_pk AND l.status = 'accepted' AND l.best = 1
JOIN publications cp ON cp.pub_id = mw.citing_pub_id
JOIN publications tp ON tp.pub_id = l.target_pub_id
WHERE cp.journal_id IS NOT NULL AND tp.journal_id IS NOT NULL
GROUP BY cp.journal_id, tp.journal_id;

-- Trust of a block, from evidence (starting formula; calibrated on `reviews` per release):
-- start at 1, x0.6 if any Azure word < 0.5, x0.9 per fix (max 3), x0.8 if a flag, x0.7 if patched by retry, floor 0.05.
CREATE VIEW v_block_trust AS
SELECT b.version_id, b.block_id,
       max(0.05, 1.0
           * (CASE WHEN coalesce(b.wc_min, 1) < 0.5 THEN 0.6 ELSE 1.0 END)
           * (CASE min(coalesce(b.n_fixes, 0), 3) WHEN 0 THEN 1.0 WHEN 1 THEN 0.9 WHEN 2 THEN 0.81 ELSE 0.729 END)
           * (CASE WHEN coalesce(b.n_flags, 0) > 0 THEN 0.8 ELSE 1.0 END)
           * (CASE WHEN b.text_source LIKE 'patch:gemini-retry:%' THEN 0.7 ELSE 1.0 END)
       ) AS trust
FROM blocks b;

-- Judge precision per model / prompt / finding type, against reviews: tells how far to trust an auto route.
CREATE VIEW v_judge_precision AS
SELECT c.model, c.prompt_version, f.type, count(r.review_pk) AS n_reviewed,
       sum(r.verdict = 'right') AS n_right, 1.0 * sum(r.verdict = 'right') / nullif(count(r.review_pk), 0) AS precision
FROM judge_findings f JOIN judge_calls c ON c.call_id = f.call_id
LEFT JOIN reviews r ON r.subject_kind = 'finding' AND r.subject_key = f.call_id || '|' || f.k
GROUP BY c.model, c.prompt_version, f.type;

-- Flag lifecycle between two versions of one document, comparing only detectors present in both.
CREATE VIEW v_flag_lifecycle AS
SELECT a.version_id AS old_version, b.version_id AS new_version, a.flag_id,
       CASE WHEN b.flag_id IS NULL THEN 'gone' ELSE 'kept' END AS fate
FROM flags a JOIN versions va ON va.version_id = a.version_id
JOIN versions vb ON vb.stem = va.stem AND vb.version_id <> va.version_id
LEFT JOIN flags b ON b.version_id = vb.version_id AND b.flag_id = a.flag_id
WHERE a.kind IN (SELECT f2.kind FROM flags f2 WHERE f2.version_id = vb.version_id);

-- Holdings per issue: catalogued vs in the bucket vs read — the map of what exists on paper but not in the index.
CREATE VIEW v_issue_coverage AS
SELECT i.issue_id, i.journal_id, count(p.pub_id) AS n_catalogued,
       sum(p.status <> 'catalogued-only') AS n_with_file,
       sum(p.status IN ('structured', 'judged', 'final', 'person-checked')) AS n_read
FROM issues i LEFT JOIN publications p ON p.issue_id = i.issue_id GROUP BY i.issue_id;

-- Quran citation index: how often each aya is quoted or cited, by how many publications.
CREATE VIEW v_quran_index AS
SELECT q.sura, q.aya_from, q.aya_to, count(*) AS n_places, count(DISTINCT v.stem) AS n_documents
FROM quran_citations q JOIN versions v ON v.version_id = q.version_id AND v.is_current = 1
GROUP BY q.sura, q.aya_from, q.aya_to;

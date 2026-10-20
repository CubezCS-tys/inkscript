-- Experiment 46: the platform database (first version). Every row says where it came from: `source`
-- (masters | catalogue | judge | person | gemini-retry | link46) and, for values read from a run's masters, `run`.
-- Rows read from a run are replaced when that run (or one article of it) is loaded again; nothing else is overwritten.
--
-- Foreign keys (2026-10-20) are DECLARED for Datasette (clickable links, "Links from other tables") and as
-- documentation; they are NOT enforced: the loaders run with `PRAGMA foreign_keys=OFF` (children may be inserted
-- before their parents, and catalogue / run rows may point at articles another run holds). Orphans are counted by
-- fk46.py. Datasette follows single-column keys only; the compound ones (note_calls → notes, …) are documentation.
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);

-- ------------------------------------------------------------------ runs and articles
CREATE TABLE IF NOT EXISTS runs (
  run TEXT PRIMARY KEY, masters_dir TEXT, prompt TEXT, prompt_hash TEXT, rules_hash TEXT, model TEXT,
  first_loaded TEXT, last_loaded TEXT, n_articles INTEGER, note TEXT);
-- every (article, run) ever loaded; `current` = the run whose masters fill the content tables for that article
CREATE TABLE IF NOT EXISTS article_runs (
  stem TEXT REFERENCES articles(stem), run TEXT REFERENCES runs(run), sha TEXT, made TEXT, loaded TEXT,
  current INTEGER, PRIMARY KEY (stem, run));

CREATE TABLE IF NOT EXISTS journals (
  journal_id TEXT PRIMARY KEY,           -- Mandumah journal code (773 $o; first part of the stem)
  title_masters TEXT,                    -- <journal-title> in the masters
  title_catalogue TEXT, title_en_catalogue TEXT, title_romanised TEXT, issn TEXT, publisher TEXT, country TEXT,
  n_articles INTEGER);
CREATE TABLE IF NOT EXISTS issues (
  issue_id TEXT PRIMARY KEY,             -- journal-volume-issue part of the stem, e.g. 1058-005-993
  journal_id TEXT REFERENCES journals(journal_id), volume TEXT, issue TEXT, issue_printed TEXT, year INTEGER,
  year_hijri TEXT, n_articles INTEGER);

CREATE TABLE IF NOT EXISTS articles (
  stem TEXT PRIMARY KEY, run TEXT REFERENCES runs(run), journal_id TEXT REFERENCES journals(journal_id),
  issue_id TEXT REFERENCES issues(issue_id),
  rec INTEGER, c999 TEXT, record_id TEXT,           -- catalogue: rec (marc.db row), 999 $c (unique), 001 (not unique)
  doi TEXT,                                         -- printed DOI (pub-id); the catalogue's is in catalogue_records
  language TEXT,                                    -- xml:lang of the article
  title TEXT,                                       -- <article-title>: the print, with D33 corrections applied
  title_printed TEXT,                               -- as printed (alt-title printed, else the article-title block)
  title_metadata TEXT,                              -- alt-title metadata (short form chosen for metadata)
  title_en TEXT, subtitle TEXT,
  volume TEXT, issue TEXT, pub_year INTEGER, pub_date TEXT, fpage TEXT, lpage TEXT, scan_pages INTEGER,
  abstract_ar TEXT, abstract_en TEXT,
  n_blocks INTEGER, n_notes INTEGER, n_refs INTEGER, n_works INTEGER, n_figures INTEGER, n_tables INTEGER,
  n_equations INTEGER, n_fixes INTEGER, n_misprints INTEGER,
  flags_high INTEGER, flags_medium INTEGER, flags_low INTEGER,
  prompt TEXT, prompt_hash TEXT, rules_hash TEXT, model TEXT, made TEXT, patches_applied TEXT,
  jats_path TEXT, alto_path TEXT, pdf_path TEXT, source TEXT DEFAULT 'masters', loaded TEXT);
CREATE TABLE IF NOT EXISTS article_dates (
  stem TEXT REFERENCES articles(stem), date_type TEXT, iso TEXT, year INTEGER, printed TEXT, source TEXT,
  run TEXT REFERENCES runs(run));
CREATE TABLE IF NOT EXISTS abstracts (                -- masters (printed) and catalogue (520)
  stem TEXT REFERENCES articles(stem), lang TEXT, seq INTEGER, text TEXT, block_id TEXT, source TEXT,
  run TEXT REFERENCES runs(run));

-- ------------------------------------------------------------------ the catalogue's view of each article (marc.db, read only)
CREATE TABLE IF NOT EXISTS catalogue_records (
  stem TEXT REFERENCES articles(stem), rec INTEGER, c999 TEXT, record_id TEXT, is_primary INTEGER, title TEXT,
  subtitle TEXT, title_en TEXT,
  language TEXT, year INTEGER, year_hijri TEXT, pages TEXT, page_first INTEGER, page_last INTEGER,
  journal TEXT, journal_en TEXT, journal_code TEXT, issn TEXT, volume TEXT, issue TEXT, issue_printed TEXT,
  article_seq TEXT, doi TEXT, type TEXT, publisher TEXT, country TEXT, fields_of_study TEXT, n_authors INTEGER,
  source TEXT DEFAULT 'catalogue', PRIMARY KEY (stem, rec));
CREATE TABLE IF NOT EXISTS catalogue_authors (
  stem TEXT REFERENCES articles(stem), rec INTEGER, seq INTEGER, name TEXT, latin TEXT, role TEXT,
  authority_id TEXT, is_org INTEGER, source TEXT DEFAULT 'catalogue', PRIMARY KEY (stem, rec, seq),
  FOREIGN KEY (stem, rec) REFERENCES catalogue_records(stem, rec));

-- ------------------------------------------------------------------ people and institutions
CREATE TABLE IF NOT EXISTS people (
  person_key TEXT PRIMARY KEY,           -- 'auth:<catalogue authority id>' or 'name:<folded name, no spaces>'
  authority_id TEXT, display_name TEXT, latin_name TEXT, n_articles INTEGER, source TEXT);
CREATE TABLE IF NOT EXISTS person_names (
  person_key TEXT REFERENCES people(person_key), name TEXT, name_key TEXT, form TEXT, n INTEGER, source TEXT,
  PRIMARY KEY (person_key, name, form));                                    -- form: printed | catalogue | latin
CREATE TABLE IF NOT EXISTS article_authors (
  stem TEXT REFERENCES articles(stem), seq INTEGER, printed_name TEXT, email TEXT,
  person_key TEXT REFERENCES people(person_key),
  catalogue_seq INTEGER, catalogue_name TEXT, authority_id TEXT, name_score REAL, match TEXT,
  source TEXT, run TEXT REFERENCES runs(run), role TEXT, PRIMARY KEY (stem, seq));
CREATE TABLE IF NOT EXISTS affiliations (
  stem TEXT REFERENCES articles(stem), author_seq INTEGER, seq INTEGER, printed TEXT, orgname TEXT, dept TEXT,
  city TEXT, country TEXT,
  org_key TEXT REFERENCES institutions(inst_key), faculty_key TEXT REFERENCES institutions(inst_key),
  dept_key TEXT REFERENCES institutions(inst_key), source TEXT, run TEXT REFERENCES runs(run),
  PRIMARY KEY (stem, author_seq, seq),
  FOREIGN KEY (stem, author_seq) REFERENCES article_authors(stem, seq));
CREATE TABLE IF NOT EXISTS institutions (
  inst_key TEXT PRIMARY KEY, level TEXT,  -- organisation | faculty | department
  name TEXT, parent_key TEXT REFERENCES institutions(inst_key), country TEXT, script TEXT, n_affiliations INTEGER,
  n_variants INTEGER, source TEXT);
CREATE TABLE IF NOT EXISTS institution_variants (
  inst_key TEXT REFERENCES institutions(inst_key), variant TEXT, n INTEGER, PRIMARY KEY (inst_key, variant));

-- ------------------------------------------------------------------ keywords and subjects
CREATE TABLE IF NOT EXISTS keywords (
  stem TEXT REFERENCES articles(stem), seq INTEGER, lang TEXT, term TEXT, term_printed TEXT, term_key TEXT,
  source TEXT, run TEXT REFERENCES runs(run));
CREATE TABLE IF NOT EXISTS subjects (
  stem TEXT REFERENCES articles(stem), seq INTEGER, scheme TEXT, term TEXT, term_key TEXT,
  source TEXT DEFAULT 'catalogue');

-- ------------------------------------------------------------------ content
CREATE TABLE IF NOT EXISTS blocks (
  id INTEGER PRIMARY KEY, stem TEXT REFERENCES articles(stem), block_id TEXT, page INTEGER, last_page INTEGER,
  ord INTEGER, kind TEXT,
  section TEXT, lang TEXT, text TEXT, text_folded TEXT, alto_lines TEXT, hpos REAL, vpos REAL, width REAL,
  height REAL, source TEXT, run TEXT REFERENCES runs(run));
CREATE INDEX IF NOT EXISTS blocks_stem ON blocks(stem, ord);
CREATE TABLE IF NOT EXISTS notes (
  stem TEXT REFERENCES articles(stem), note_id TEXT, kind TEXT, page INTEGER, label TEXT, text TEXT,
  n_calls INTEGER, n_works INTEGER, ord INTEGER, source TEXT, run TEXT REFERENCES runs(run),
  PRIMARY KEY (stem, note_id));
CREATE TABLE IF NOT EXISTS note_calls (
  stem TEXT REFERENCES articles(stem), note_id TEXT, call_text TEXT, block_id TEXT, page INTEGER, source TEXT,
  run TEXT REFERENCES runs(run),
  FOREIGN KEY (stem, note_id) REFERENCES notes(stem, note_id));
CREATE TABLE IF NOT EXISTS figures (
  stem TEXT REFERENCES articles(stem), xml_id TEXT,
  kind TEXT,                             -- figure | table | equation | inline-equation | inline-picture
  page INTEGER, label TEXT, caption TEXT, alt_ar TEXT, alt_en TEXT, text_in_figure TEXT, graphic TEXT, tex TEXT,
  has_mathml INTEGER, specific_use TEXT, n_cells INTEGER, source TEXT, run TEXT REFERENCES runs(run),
  PRIMARY KEY (stem, xml_id, kind));

-- ------------------------------------------------------------------ references and citations
CREATE TABLE IF NOT EXISTS works (
  work_id TEXT PRIMARY KEY,              -- <stem>|ref:<r id>|<n>  or  <stem>|note:<fn id>|<n>
  stem TEXT REFERENCES articles(stem),
  origin TEXT,                           -- reference (ref-list) | note (a note's parsed citations)
  container_id TEXT, seq INTEGER, ord INTEGER, pub_type TEXT, authors TEXT, first_author TEXT, first_author_key TEXT,
  article_title TEXT, chapter_title TEXT, source_title TEXT, year TEXT, year_int INTEGER, volume TEXT, issue TEXT,
  fpage TEXT, lpage TEXT, page_range TEXT, publisher TEXT, place TEXT, doi TEXT, url TEXT, series TEXT,
  extra TEXT, printed TEXT, page INTEGER, source TEXT, run TEXT REFERENCES runs(run));
CREATE INDEX IF NOT EXISTS works_stem ON works(stem, ord);
CREATE TABLE IF NOT EXISTS work_authors (
  work_id TEXT REFERENCES works(work_id), seq INTEGER, surname TEXT, given TEXT, name_key TEXT,
  PRIMARY KEY (work_id, seq));
-- notes that point back («المرجع السابق», «المصدر نفسه», ibid., op. cit.) — resolved by link46.py
CREATE TABLE IF NOT EXISTS back_references (
  backref_id TEXT PRIMARY KEY, stem TEXT REFERENCES articles(stem), note_id TEXT, ord INTEGER, marker TEXT,
  hint TEXT, printed TEXT, has_parsed INTEGER, page INTEGER, source TEXT, run TEXT REFERENCES runs(run),
  FOREIGN KEY (stem, note_id) REFERENCES notes(stem, note_id));
-- links never change the source rows; one row per candidate kept, `best` marks the chosen one per (from, kind).
-- from_id / target_id are polymorphic (by from_kind / target_kind); link46 also writes them into typed columns so
-- Datasette can follow them: from_work_id | from_backref_id, and target_stem | target_rec | target_work_id
-- (target_rec is a marc.db row, mostly not in catalogue_records, so it is not declared as a key).
CREATE TABLE IF NOT EXISTS citation_links (
  from_kind TEXT, from_id TEXT, target_kind TEXT,  -- from_kind: work | backref; target_kind: article | catalogue | work
  target_id TEXT, score REAL, method TEXT, best INTEGER, evidence TEXT, linked TEXT, source TEXT DEFAULT 'link46',
  from_work_id TEXT REFERENCES works(work_id), from_backref_id TEXT REFERENCES back_references(backref_id),
  target_stem TEXT REFERENCES articles(stem), target_rec INTEGER, target_work_id TEXT REFERENCES works(work_id),
  PRIMARY KEY (from_kind, from_id, target_kind, target_id));
CREATE TABLE IF NOT EXISTS link_checks (               -- hand checks of links (read, judged right/wrong)
  from_kind TEXT, from_id TEXT, target_kind TEXT, target_id TEXT, verdict TEXT, note TEXT, checked_by TEXT, checked TEXT);
CREATE TABLE IF NOT EXISTS link_runs (stem TEXT PRIMARY KEY REFERENCES articles(stem), linked TEXT);  -- link46.py

-- ------------------------------------------------------------------ quality
CREATE TABLE IF NOT EXISTS flags (
  flag_id TEXT, run TEXT REFERENCES runs(run), stem TEXT REFERENCES articles(stem), kind TEXT, severity TEXT,
  page INTEGER, lines TEXT, box TEXT, reason TEXT,
  extra TEXT, made TEXT, source TEXT DEFAULT 'flags43', PRIMARY KEY (run, flag_id));
CREATE TABLE IF NOT EXISTS judge_findings (
  finding_id TEXT, run TEXT REFERENCES runs(run), stem TEXT REFERENCES articles(stem), page INTEGER, type TEXT,
  question TEXT, answer TEXT, targets TEXT,
  confidence TEXT, evidence TEXT, code_check TEXT, action TEXT, route TEXT,   -- route: auto | retry | human
  patch_id TEXT, status TEXT, model TEXT, created TEXT, raw TEXT, source TEXT DEFAULT 'judge', file TEXT,
  PRIMARY KEY (run, finding_id),
  FOREIGN KEY (run, patch_id) REFERENCES patches(run, patch_id));   -- patch ids are unique per run only
CREATE TABLE IF NOT EXISTS patches (
  patch_id TEXT, run TEXT REFERENCES runs(run), stem TEXT REFERENCES articles(stem), page INTEGER, action TEXT,
  targets TEXT, payload TEXT,
  source TEXT,                           -- person | judge | gemini-retry
  confidence TEXT, evidence TEXT, reason TEXT, route TEXT, apply INTEGER,
  status TEXT,                           -- applied | skipped | overridden | proposed (from the masters' sidecar)
  status_why TEXT, built_run TEXT REFERENCES runs(run), created TEXT, raw TEXT, file TEXT,
  PRIMARY KEY (run, patch_id));
CREATE TABLE IF NOT EXISTS fixes (       -- Azure misreadings fixed by Argon (masters' reader-fixes notes)
  stem TEXT REFERENCES articles(stem), fix_id TEXT, azure_reading TEXT, print TEXT, why TEXT, alto_line TEXT,
  line_label TEXT, page INTEGER, source TEXT, run TEXT REFERENCES runs(run), PRIMARY KEY (stem, fix_id));
CREATE TABLE IF NOT EXISTS misprints (   -- suspected misprints (D30: kept as printed, correction proposed)
  stem TEXT REFERENCES articles(stem), sic_id TEXT, printed TEXT, proposed TEXT, why TEXT, alto_line TEXT,
  line_label TEXT, page INTEGER, source TEXT, run TEXT REFERENCES runs(run), PRIMARY KEY (stem, sic_id));
CREATE TABLE IF NOT EXISTS metadata_changes (   -- D33 corrections of metadata
  stem TEXT REFERENCES articles(stem), seq INTEGER, field TEXT, printed TEXT, corrected TEXT, change_source TEXT,
  reason TEXT, alternatives TEXT, rule TEXT, source TEXT, run TEXT REFERENCES runs(run), PRIMARY KEY (stem, seq));
CREATE TABLE IF NOT EXISTS catalogue_disagreements (    -- masters vs catalogue: the list for Mandumah
  stem TEXT REFERENCES articles(stem), rec INTEGER, c999 TEXT, field TEXT, masters_value TEXT, catalogue_value TEXT,
  kind TEXT, severity TEXT, note TEXT, run TEXT REFERENCES runs(run), PRIMARY KEY (stem, field, kind));

-- ------------------------------------------------------------------ indexes
CREATE INDEX IF NOT EXISTS links_target ON citation_links(target_kind, target_id);
CREATE INDEX IF NOT EXISTS flags_stem ON flags(stem);
CREATE INDEX IF NOT EXISTS findings_stem ON judge_findings(stem);
CREATE INDEX IF NOT EXISTS patches_stem ON patches(stem);
CREATE INDEX IF NOT EXISTS backrefs_stem ON back_references(stem);
CREATE INDEX IF NOT EXISTS authors_person ON article_authors(person_key);
CREATE INDEX IF NOT EXISTS names_key ON person_names(name_key);
CREATE INDEX IF NOT EXISTS affs_org ON affiliations(org_key);
CREATE INDEX IF NOT EXISTS keywords_stem ON keywords(stem);
CREATE INDEX IF NOT EXISTS dates_stem ON article_dates(stem);
CREATE INDEX IF NOT EXISTS abstracts_stem ON abstracts(stem);
CREATE INDEX IF NOT EXISTS subjects_stem ON subjects(stem);
CREATE INDEX IF NOT EXISTS calls_stem ON note_calls(stem);

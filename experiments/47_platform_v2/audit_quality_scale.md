# Audit: quality record, provenance, rebuilds and scale (platform.db, experiment 46)

2026-10-20. Auditor role: database engineer, area *quality_scale*. Read-only on
`/home/yassine/data/platform/platform.db`, `marc.db`, `experiments/43_rehearsal` and `experiments/46_platform_db`.
No paid calls. Every number below comes from a query or a file read made today. The commands are short and can
be repeated with `sqlite3 'file:/home/yassine/data/platform/platform.db?mode=ro'`.

## What is already right (keep it)

- **The rebuild works.** The FK rebuild re-made all 35 tables from the masters and they equalled the old db. The
  loader is a pure function of (masters, run files, marc.db), and that is the main reproducibility property.
- **Raw and resolved values sit side by side.** `title` / `title_printed` / `title_metadata`, `fixes.azure_reading`
  / `fixes.print`, `misprints.printed` / `proposed`, `metadata_changes.printed` / `corrected`. Nothing is
  overwritten in place.
- **Flag ids are natural keys** (`<stem>|<kind>|p<page>|<first line>`). They stay the same across runs, so a
  flag can be followed from run to run (see P6). This is better than most systems have.
- **Every quality row keeps its source file** (`judge_findings.file`, `patches.file`, `raw`).

## Problems, with evidence

### P1 (high). Content and corrections exist only for the "current" run, so runs cannot be compared

`load_article` deletes every content table `WHERE stem = ?` before inserting (load46.py:299-301). Only one run's
blocks, fixes, misprints, metadata changes and disagreements survive per article:

```
fixes:     v33_300_final 12,389 rows / v2_55 980 rows; v33_300 0 rows (299 of its articles were loaded, then replaced)
article_runs: v33_300 299 rows current=0, sha equal to v33_300_final for 0 of 299
```

The exam run `v33_300b` (200 masters on disk now, being built) re-reads the same 300 articles with a new
configuration. The whole point of an exam or an A/B is comparing two readings of the same page. With
`--current always` it would erase `v33_300_final`'s content. With `--current if-new` its content would never be
loaded at all, only an `article_runs` row. Either way "how did fixes, misprints and flags change between
v33_300_final and v33_300b" cannot be asked in SQL. The same is true of the D30/D33 history across runs.
**Fix:** key content and correction rows by an *article version* `(stem, run)` and not by `stem`. "Current" is a
pointer, not a deletion (proposed `article_versions`). This is OpenAlex's "one work, many locations".

### P2 (high). Judge patch ids collide across articles: one patch is already lost and 5 findings point at the wrong article's patch

patches43 makes ids `j-<first 4 characters of stem>-p<page>-<n>`, which is the journal code, not the article.
`patches` has PK `(run, patch_id)` and `INSERT OR REPLACE`:

```
patch files in out/v33_300_final/patches: 125 patches, 124 distinct ids
  j-1677-p1-1 is used by 1677-010-002-041 AND 1677-010-002-023  → one silently replaced; platform.db has 124
judge findings joined to a patch of a DIFFERENT article: 5, e.g.
  gemini-3.8-flash|0368-000-013-009|p11|1 → j-0368-p11-1 (patch of 0368-000-003-003, set_kind, proposed)
  gemini-3.8-flash_v2|1016-054-623-033|p5|1 → patch of 1016-054-618-013
patch ids shared by findings from 2–3 judge models: 11 (load_judge maps finding k of EVERY model to j-…-k)
articles that share a journal code with another article: 153 of 354
```

At 1M documents nearly every journal has many articles, so collisions become the norm and not a rare event.
The retry ids (`r-0368-p11-1`) have the same shape. Person ids (`h-0744-p1-mvg55i280`) are safe.
**Fix:** the patch key becomes `(run, stem, patch_id)` in the db. The finding→patch link is stored as the
patch's own back-reference (the decide step knows which finding it came from) and is not re-derived from
`k`. Upstream (patches43, not ours to edit) should use the full stem. Until then the loader must refuse a
duplicate id with two articles instead of replacing.

### P3 (high). The full-db rebuild steps on every load make loading quadratic

After every load, load46.py:572-576 runs `rebuild_people`, `rebuild_journals_issues`, `inst46.rebuild` (each
`DELETE` and re-derive from *all* rows) and `INSERT INTO blocks_fts(blocks_fts) VALUES ('rebuild')`, which
re-indexes all 51,791 blocks. It takes 12 s today. At ~160 M blocks (below) each incremental load becomes
hours of re-indexing work that has nothing to do with the new articles. "Idempotent" holds, but
"incremental" does not.
**Fix:** FTS rows are written per block on insert and delete (external-content triggers, or Postgres
`tsvector` per row). People, institutions and journals are re-derived only for the keys the loaded versions
touch, and a full re-derive becomes a separate, explicit command.

### P4 (high). Keys that will not hold at scale or across rebuilds

| key | evidence | breaks when |
|---|---|---|
| `citation_links.target_id` for catalogue = `rec` | `rec` = "order in the XML (1-based)" (marc.db schema comment); `catalogue_records` rec 1284200 ↔ 999$c 1370909 | Mandumah sends a new MARC export: every catalogue link and every hand check of one points at another record |
| `blocks.id` INTEGER surrogate | min 45,978, max 98,306 for 51,791 rows: ids move on every reload | anything outside the db (Datasette bookmarks, FTS rowids, exports) that holds a block id |
| `works.work_id` = `<stem>|note:<fn id>|<n>` (positional) | 4 of 54 `link_checks` already match no current link (the hand verdict "wrong" on `0368-000-003-003|fn-p14-14` → `…|note:fn-p14-4|0` has nothing left to suppress) | a new run parses a note into a different number of citations: person verdicts attach to the wrong citation |
| absolute paths | `articles.jats_path` = `/home/yassine/inkscript/experiments/43_rehearsal/out/v33_300_final/masters/…`; also `runs.masters_dir`, `patches.file`, `judge_findings.file` | the move to a server or S3 |

**Fix:** catalogue links use `c999`, with `rec` only as a cache. Blocks are keyed by `(version_id, block_id)`.
Every human verdict is stored against a *content fingerprint* (stem + note id + folded printed text of the
citation) as well as the id, so it can be re-attached after a reparse. Paths are relative URIs under a
`storage_root` (local folder | `s3://…`), plus a sha.

### P5 (high). Judge rows mix two things, and the judge calls themselves (cost, model, prompt version) are missing

```
judge_findings 634 rows: 415 are type='none' ("page judged, no problem named"), 219 are problems
model column: 'gemini-3.8-flash' for both answers/gemini-3.8-flash and answers/gemini-3.8-flash_v2 (the prompt
  version lives only in the finding_id prefix)
the answer file holds usd, tin, tout, mode=batch, finish, and the page view the judge saw; none of it is loaded
113 of 219 problem findings have no target at all (no blocks, no lines, no box): nothing to point at on the page
```

A page that was judged and found clean is a *call*, not a *finding*. Calibration ("how often is Flash v2 right
on wrong_order?") needs calls, cost and the human verdicts below.
**Fix:** `judge_calls` (one per model × prompt version × page, with cost and verdict) and `judge_findings`
(only problems, with an FK to the call). `type` and `subtype` become separate columns.

### P6 (medium). The flag record cannot tell "resolved" from "detector added", and the detector version is missing

```
flags v33_300 731 / v33_300_final 876; same flag_id in both 676, gone in final 55, new in final 200
new in final by kind: letters_lost_vowelled 114, guillemets_unsure 47, show_through 23, …
```

Most "new" flags come from detectors added between the two flag runs, not from worse pages. `flags.made` is
the run date, and nothing records the flags43 code or rules version. "55 gone" mixes fixed pages with detectors
whose thresholds changed. `articles.flags_high/medium/low` hold only the current run's counts (a precomputed
copy, which goes stale if flags are reloaded without the article).
**Fix:** `flags` keyed by `(version_id, flag_id)` plus `detector_version`. Lifecycle (open → resolved by patch X
→ reappeared) becomes a view over versions of the same stem, and it compares only flags whose detector existed
in both versions.

### P7 (medium). A patch can be built into several runs, but only one build status is kept

`patches` PK `(run, patch_id)` with `built_run` and `status` as columns; `load_patches` deletes
`WHERE built_run = ?`. Patch `run` is the run the patch was *made against* (all 124 have `run = v33_300`), while
`v33_300_judged` (77 patch files) and `v33_300_final` (77 files) both built them. Today all 124 rows say
`built_run = v33_300_final`, so the judged build's statuses are gone. The exam `v33_300b` will need the same
patches applied again. `articles.patches_applied` is a free-text copy ("r-0368-p11-1 replace_page_blocks
(gemini-retry)"). Person patches (`source: person`, from correct43) carry no *who* (no person id, only a
browser timestamp).
**Fix:** split `patches` (the proposal: immutable) from `patch_applications` (patch × built version →
applied | skipped | overridden, why). Add `actor_id` for person patches.

### P8 (medium). Fixes and misprints point at a line, not a word, and Azure's confidence is not used

The ALTO has `WC` on every word (`<String ID="p1w0001" CONTENT="المدارس" WC="0.916" …>`). Measured on 40 articles
of v33_300_final:

```
all words 181,829: median WC 0.992, share with WC < 0.5 = 2.1%
words Argon fixed (matched by Azure's reading inside the fix's ALTO line) 1,299: share with WC < 0.5 = 26.4%  (12× more)
fix/misprint rows that could not be matched to a word at all: 553 of 2,101
```

So Azure's confidence is a real trust signal for exactly the corrections we keep. But the db cannot use it,
because a fix names only its `alto_line`, and 26% of rows cannot be placed on a word afterwards (Azure split or
joined the words differently).
**Fix:** the masters writer (future, not ours to edit) should emit word ids. Until then, `text_corrections`
stores the matched word id, its WC, and `anchor_method` (exact | contains | line-only).

### P9 (medium). Two address systems for the same line, and no table joins them

Flags, judge targets and patches use *line labels* `page:n` (`"4:2"`), while blocks, fixes and misprints use
*ALTO ids* (`p3b6l1`). The `page` number has different meanings: judge finding `0089-006-005-006|p3` targets
lines `4:2…4:6`, and the judge's own view lists them inside block `p3b6` of page 3 with `line_box = null`.
No table maps a label to an ALTO line and its box, so "show me the scan behind this flag" needs the JSON views
of experiment 43.
**Fix:** a `pages` table and a `lines` table (label ↔ ALTO id ↔ box ↔ block, per version). Every quality row
points to one `anchors` row instead of carrying its own JSON `lines`/`box`.

### P10 (medium). Human checks and gold sit outside the db, so no trust score can be calibrated

Loaded: `link_checks` (54, `checked_by = agent-46`). Not loaded: `judge_verdicts43.json` (the human look at
every calibration finding: real / debatable / false), `judge_truth43.json` (known problems per calibration page),
`gold/` (5 owner hand checks, e.g. 0747 183/183), `out/<run>/handcheck/` (9 pages), and the correction tool's
exports. These are the only ground truth we have. Without them in the db, "judge precision by type and model"
or "how much to trust an auto-applied patch" cannot be computed.
**Fix:** one `reviews` table for every human or agent verdict on anything (link, finding, flag, page, article),
with checker and date.

### P11 (medium). Catalogue disagreements have no outcome and use the unstable key

`catalogue_disagreements` 253 rows (179 articles): PK `(stem, field, kind)`, no `run` in the key, so only the
current run's list survives. There is no "who is right" (print, catalogue, both wrong), no status
(sent to Mandumah / accepted / rejected), and no pointer to the printed evidence (page and box of the printed
title or folio). In 20 rows the same field also has a D33 change. 80 of the 174 D33 changes took the *catalogue's*
page range because it fits the scan. Those are print errors that the catalogue confirms, not catalogue errors.
None of this is separated today. This list is a product for Mandumah ("catalogue-error report"), and a product
needs states.
**Fix:** `catalogue_reports` with verdict, status, evidence anchor and `c999`.

### P12 (low). Run-level stamps are partly wrong or stale

- `runs.n_articles` is written at load time: `v33_300` says 299 but holds 0 current articles, `v33_300_judged`
  says 1 and holds 0.
- `runs.prompt/model/rules_hash` come from the *first* `*.stamp.json` in the folder (load46.py:540). The per-article
  stamps disagree inside one folder: in `v33_300_final`, 223 stamps say `"run": "v33_300"` (copied forward)
  and 77 say `v33_300_final`. Run lineage (final ← judged ← v33_300) appears only in a regex (`base_run`).
- Cost is not in the db, although it exists in the files: `summary.json` has `usd/tin/tout` per article
  (the 300 cost $28.64), `raw/<stem>_cNNN-NNN.json` has the cost and the batch job id per chunk,
  `gemini_spend.jsonl` has 1,798 calls, and judge answers have usd per page.
- `meta` holds one row (`schema`). There is no load log: which loader code, when, how many rows changed.

### P13 (low). Raw JSON blobs are duplicated into the db

`judge_findings.raw` (0.17 MB), `patches.raw` (105 KB): small now. At 1M documents with several judge models
they become many gigabytes of copies of files that stay on disk anyway. Keep `file` + `sha` + the parsed
columns. Copy the blob only for person patches, because they are the only ones that cannot be regenerated.

## Scale: what the numbers say

Measured: 3,866 pages in `blocks`, 57 MB db, so **~14.7 KB per page for one content version** (blocks 36 MB of
it, FTS 5.6 MB). Per page: 13.4 blocks, 3.5 fixes, 0.47 misprints, 0.25–0.45 flags. 344 words per page (300 run:
1,213,332 words over 3,523 pages). Linear extrapolation to 12 M pages:

| thing | rows at 12 M pages | where it lives |
|---|---|---|
| words (with WC and box) | ~4.1 billion | **files only** (ALTO in S3). Never rows. Reached through `lines` + byte offsets, or read per page |
| lines (label ↔ ALTO id ↔ box) | ~360 M (≈30/page) | db, partitioned. The bridge that every evidence click needs |
| blocks | ~160 M | db, partitioned. FTS in a search engine, not in SQLite |
| fixes + misprints | ~48 M per version | db (`text_corrections`) |
| flags | ~3–5 M per flag run | db |
| works / citation occurrences | ~13.5 M parsed works, ~50 M citation occurrences (given) | db |
| one content version | ~175 GB in SQLite form | — |

**SQLite or PostgreSQL.** SQLite stays right for *building* a unit: one file per run or per shard, written by
one loader, rebuilt from sources, diffable, and fine for the 300, the exam and the first tens of thousands of
articles. For the published platform at 1M documents it is the wrong home: one writer at a time, a 175 GB+
single file per version, FTS rebuilt whole (P3), no partition pruning, and Datasette reading the same file the
loader writes. Recommendation:

1. **Build layer:** per-shard SQLite (shard = journal code, ~hundreds of articles each), produced by an
   idempotent per-article loader. A shard is the unit of rebuild and the unit that gets diffed.
2. **Serve layer:** PostgreSQL. Big tables (`blocks`, `lines`, `text_corrections`, `citation_occurrences`) are
   hash-partitioned by `stem` (or list-partitioned by journal). Quality tables (`flags`, `judge_*`,
   `patch_applications`) are list-partitioned by run, because runs are added and dropped whole. Search goes to
   OpenSearch (or the existing Qdrant for meaning); Postgres has no good Arabic stemmer.
3. **Analytics layer:** a Parquet export per release (DuckDB) for the metrics and the corrections ledger at
   full scale.

**Indexes needed at scale** (today only `flags_stem`, `findings_stem`, `patches_stem` exist): `(version_id)` on
every content table; `(stem, page)` on flags, judge_findings, text_corrections, anchors; `(kind, severity)` on
flags; `(c999)` on catalogue links; `(status)` on catalogue_reports; `(detector_version, kind)` on flags.

**Precompute per release (materialised, stamped with release id and the time window):** `page_quality`
(mean and low-WC share, fixes per 100 words, open flags by severity, judge verdict, reviewed?);
`article_quality` (the same rolled up, plus cost); trust per block and per citation link; judge precision by
(model, prompt, type) from `reviews`; flag lifecycle between consecutive versions; times-cited and journal
metrics (citation area). Do not precompute in base rows (`articles.flags_*`, `n_fixes`, `patches_applied`):
those are view columns.

## Proposed tables

Ids: `V:<stem>@<run>` = article version. All tables carry `source` (masters | catalogue | judge | person |
gemini-retry | code-rule | link47) and the version or run they were read from.

| table | role (plain words) | columns | replaces |
|---|---|---|---|
| `runs` | One row per processing run: how it was made, from what, and at what cost. | run PK, kind (build\|judged\|final\|exam\|replay), parent_run FK→runs, prompt, prompt_hash, rules_hash, model, thinking, code_commit, started, finished, usd, tin, tout, n_articles (view), storage_root, note | runs |
| `article_versions` | One reading of one article by one run. Every content and quality row belongs to one. | version_id PK, stem FK→articles, run FK→runs, sha_inputs, made, stamp_run, usd, tin, tout, n_chunks, n_retries, loaded, load_id FK→load_events, is_current | article_runs |
| `pages` | One scanned page of an article: the image, its ALTO, and its quality summary. | page_id PK (`stem:page`), stem FK, scan_page, printed_folio, image_uri, alto_uri, width, height, n_words, wc_mean, wc_low_share | — (new) |
| `lines` | One printed line: links the two names a line has (`3:21` and `p3b6l1`) to its box on the page. | version_id FK, line_label, alto_line_id, page_id FK, block_id, hpos, vpos, width, height, wc_min, PK(version_id, line_label) | — (new; today only in exp 43's JSON views) |
| `anchors` | "Where on the page": a reusable pointer that any value, flag, finding, correction or citation can cite as evidence. | anchor_id PK, version_id FK, page_id FK, line_labels JSON, alto_line_ids JSON, word_ids JSON, box, anchor_method (exact\|contains\|line-only\|none) | flags.lines/box, judge targets, patches.targets |
| `text_corrections` | Every word-level change between what Azure read, what is printed, and what a correction proposes: misreadings fixed (applied) and suspected misprints (D30: never applied to the body). | corr_id PK, version_id FK, xml_id (fix1/sic3), layer (azure-misread\|misprint), before, after, applied_to_text (bool), why, anchor_id FK, azure_wc, actor_kind (reader-model\|code-rule\|judge\|person), actor_id, rules_hash | fixes, misprints |
| `metadata_changes` | Every D33 correction of metadata: the printed form, the corrected one, where the evidence is, who decided. | version_id FK, seq, field, printed, corrected, change_source, reason, alternatives, rule, anchor_id FK, actor_id, created, PK(version_id, seq) | metadata_changes (+version, anchor, who) |
| `flag_detectors` | Each automatic check that raises flags, and its version. | detector_id PK, kind, code_hash, thresholds JSON, introduced | — (new) |
| `flags` | A code check's warning on a page, tied to the detector version that raised it. | version_id FK, flag_id, detector_id FK, kind, severity, anchor_id FK, reason, extra, PK(version_id, flag_id) | flags |
| `judge_calls` | One look by one judge model (and prompt version) at one page, even when it found nothing. | call_id PK, run FK, stem, page, model, prompt_version, mode, usd, tin, tout, finish, verdict, file, sha | the 415 'none' rows of judge_findings |
| `judge_findings` | One problem a judge named on a page. | finding_id PK, call_id FK, k, type, subtype, confidence, evidence, action, route, anchor_id FK | judge_findings |
| `patches` | One proposed correction of structure (from a person, the judge or a retry). Immutable once made. | patch_key PK (`run|stem|patch_id`), run FK, stem, patch_id, page, action, payload, source, actor_id, finding_id FK, confidence, evidence, reason, apply, created, file, sha | patches (proposal part) |
| `patch_applications` | What happened to a patch in each build that saw it. | patch_key FK, version_id FK, status (applied\|skipped\|overridden\|proposed), why, PK(patch_key, version_id) | patches.built_run/status, articles.patches_applied |
| `reviews` | Every human or agent verdict on anything: a link, a finding, a flag, a page, a gold item. | review_id PK, subject_kind, subject_key, subject_fingerprint, verdict, note, checker, checked, source_file | link_checks, judge_verdicts43.json, judge_truth43.json, gold/, handcheck/ |
| `catalogue_reports` | One disagreement between the print and Mandumah's catalogue, with who is right and whether Mandumah was told. | report_id PK, version_id FK, c999, field, masters_value, catalogue_value, kind, severity, who_is_right (print\|catalogue\|both-wrong\|unknown), evidence_anchor FK, d33_change FK, status (open\|sent\|accepted\|rejected), batch, note | catalogue_disagreements |
| `load_events` | One run of the loader: which code, when, what changed. Makes every row traceable to the load that wrote it. | load_id PK, started, finished, loader_hash, run, args, n_loaded, n_unchanged, rows_by_table JSON, db_file | meta (partly) |
| `model_calls` | Every paid model call with its cost, so the cost of any article, page or judge verdict can be added up. | call_id PK, when, model, tag, stem, chunk, mode, job, tin, tout, think, usd, finish, file | — (gemini_spend.jsonl, raw/*.json, summary.json) |

Views, not tables: `corrections_ledger` (union of text_corrections, metadata_changes and patch_applications,
ordered by time: the full auditable history of one article); `flag_lifecycle`; `page_quality`,
`article_quality`, `trust_*`; `judge_precision` (findings × reviews by model/prompt/type).

## What this enables that no existing index has

- **"Show me the ink."** Every flag, finding, correction, D33 change, catalogue report and citation (other
  area) resolves through `anchors` → `lines` → `pages.image_uri` to a crop of the scan.
- **A trust score built from evidence, not a guess.** Example: a block's trust = f(min Azure WC of its words,
  fixes per word, open flags on its lines, judge verdict on its page, whether a person reviewed it, judge
  precision for that finding type). The 12× enrichment of low-WC words among fixes (P8) shows the signal is
  real.
- **A public corrections ledger per article** (D30 + D33 + patches, each with who, why and where), and a
  catalogue-error report that Mandumah can act on.
- **Run-to-run comparison in SQL** (exam vs final): the A/B work of experiment 43 becomes queries instead of
  scripts.

## What stays in files (and why)

Words (4 B rows), page images, crops, ink PDFs, ALTO and JATS: they are the sources and the size of S3. The db
holds URIs + sha + the `lines` bridge. Raw model answers (`raw/`, judge answer files): pointer + sha. Copy
person patches into the db, because they cannot be regenerated.

## Migration notes

1. Write a new loader (`load47.py`) into `/home/yassine/data/platform_v2/`. Leave platform.db alone. Load
   v2_55, v33_300, v33_300_judged and v33_300_final as **four versions each** (no deletion). Later load v33_300b
   the same way. `is_current` reproduces today's choice (`final` > `judged` > `v33_300`; `v2_55` if new).
2. The loading unit is (article version). Delete and insert by `version_id`, inside one transaction per
   version. Update FTS per row. Re-derive people, institutions and journals only for the touched keys.
   Re-running on unchanged inputs writes nothing, except a `load_events` row.
3. Patch keys gain `stem`. On loading, a duplicate `(run, patch_id)` for two stems is an error and is logged,
   never replaced. Store the finding→patch link from the patch side.
4. Convert `citation_links` catalogue targets from `rec` to `c999` (join `marc.db records`). Re-key
   `link_checks` → `reviews` with a fingerprint. The 4 stale checks go into a "could not re-attach" list for a
   person.
5. Load `judge_verdicts43.json`, `judge_truth43.json`, `gold/`, `handcheck/` into `reviews`. Load
   `summary.json`, `raw/*.json` and `gemini_spend.jsonl` into `model_calls`.
6. Equality check, as in experiment 46: for the current versions every v46 table must be reproducible as a view
   over v47 (row counts and checksums). The only differences allowed are the listed fixes (the lost patch
   j-1677-p1-1 comes back, and 5 finding→patch links move).
7. Stay in SQLite until the exam and the second 300 are in. Then write the Postgres DDL with the partitioning
   above, and test it on a synthetic 1M-article load (repeat the 300, re-stemmed) before real data.

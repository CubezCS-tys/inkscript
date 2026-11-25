# Experiment 97 — an exam suite for extraction (reading + parsing)

**Status:** building (2026-11-10). Free and local: no Gemini calls, no GPU.

## Question

The owner (2026-11-10): "we need to separate our concerns properly and we need some way to test extraction,
reconciliation … test evals, because otherwise this is just useless." Until today nothing measured the Azure + Gemini
extraction on the product's own journals; the first number came from outside (the twin-journal table audit, see
`docs/ideas.md`). This experiment builds the exam for **extraction**: is the text what is printed (reading), and is
each piece labelled and joined correctly (parsing). Reconciliation (same person, same work) gets its own exam later.

## The exam set (locked)

- `LOCKED_EVAL.json`: 60 scan-read articles from release R20261104T151029, seed 97. Six from each of the seven
  journals read whole (0013, 0097, 0130, 0165, 0246, 0840, 1001) and 18 from 18 other journals. 1,443 pages.
- Exam pages per article: the first page; one random body page; and, where the article has them, one table page, one
  reference page, one footnote page. 214 pages: 60 front, 60 body, 38 references, 37 table, 19 notes.
- Known bias: table / reference / footnote pages were picked where **we** found one. The random body pages are the
  unbiased sample for pieces we missed.
- These articles are an exam, not training data: nothing may be tuned on them. A change is scored on them, never
  fitted to them.

## How the answer keys are made

- A key is written **from the page image**, never from our parsed output. Keyers get a neutral packet per article
  (`out/packets/<stem>/packet.json`): page images and Azure's raw lines (number, text, box). They may not open the
  release database, the Desk, the twin export or the Classic pages.
- Every key is written **twice by two agents that cannot see each other's work** (`out/keys/<part>/A/`, `/B/`).
  Where they agree, that is the key. Where they differ, a third agent settles it by eye and records why
  (`out/keys/<part>/final/`). Only items the third agent cannot settle go to the owner.
- Agreement between A and B is reported with every score: it is the ceiling a score can be trusted to.
- Keys use Azure line numbers as the common unit, so a key says "lines 12–15 are one paragraph", not "our block p3b4".

## The parts and their pass marks (fixed before any scoring)

The first run is a baseline; the marks say what "good enough to rely on" means, so a miss is a finding, not a failure
of the exam.

| Part | What is checked | Measure | Pass mark |
|---|---|---|---|
| R1 Reading | shown text against the printed line, 600 lines | wrong letters / wrong words | ≤ 0.5% letters, ≤ 2% words |
| R2 Nothing lost, nothing twice | every printed text line lands in exactly one block | lines lost / lines doubled | ≤ 0.5% / ≤ 0.2% |
| P1 Labels | each line's role: title, heading, paragraph, list item, footnote, reference, caption, table, header/footer, … | share of lines with the right role | ≥ 97% overall, ≥ 90% for every role with ≥ 30 lines |
| P2 Grouping | which lines form one paragraph / item / reference | F1 on line-pair "same piece" | ≥ 95% |
| P3 Reading order | order of the pieces on the page, two-column pages reported apart | share of adjacent pieces in the right order | ≥ 98%, two-column ≥ 95% |
| P4 Front matter | title(s), authors, affiliations, abstract(s), keywords, received/accepted dates, DOI, first page number | exact match per field after trimming | title ≥ 98%, authors ≥ 97%, others ≥ 95% |
| P5 Sections | headings found, their level, their parent (20-article subset, all pages) | headings found / invented; level right | found ≥ 97%, invented ≤ 3%, level ≥ 90% |
| P6 Footnotes | note text boundaries; note ↔ call mark in the text | notes right; calls linked right | ≥ 97% / ≥ 95% |
| P7 Tables | table found; rows × columns; header rows; caption and number; continuation of the previous page's table marked; cells on 40 tables | per-item | found ≥ 98%, shape ≥ 95%, continuation ≥ 90%, cells ≥ 99.5% |
| P8 Figures and equations | found, caption attached | per-item | found ≥ 95% |
| P9 References | where each reference starts and ends; fields (authors, year, title, source, volume, pages) | boundaries right; field exact match | boundaries ≥ 98%, each field ≥ 95% |

R1 uses three independent witnesses of every line (Azure's raw line, our own reader t91, the shown text). Lines where
all three agree are taken as right (a shared mistake is possible; 60 of those lines are checked by eye to measure how
often). Every line where they differ is settled from the line image by two blind agents.

**The ink is the map (owner, 2026-11-10).** Azure's lines are a convenient unit for the keys, but they are not
neutral: text Azure never saw has no line to label. So part **R0, the ink ledger**, starts from the page image itself:
every blob of printed ink on the 214 exam pages is assigned to the piece that claims it. Reported as shares of ink:
claimed once; claimed twice; seen by the reader but dropped by the parser; seen by nobody. Unclaimed text-like
regions are labelled by blind agents (printed text / picture / rule / stamp / noise). Pass mark: text ink seen by
nobody ≤ 0.3% of text ink; text ink dropped by the parser ≤ 0.2%. Output: `out/ink/` (overlay picture per page).
This replaces line counting as the main measure of R2. The ledger says whether ink was claimed, not whether it was
read correctly: R1 does that.

Not in this exam: citations linked to works, authors linked to persons, institutions (reconciliation); whether the
data gives better answers (the twin experiment).

## Files

- `sample97.py` — picks and locks the set, writes the packets (run once).
- `KEYER_RULES.md` — the rules every keyer follows; one section per part with the exact output format.
- `ink97.py`, `ink97_summary.py` — part R0, the ink ledger (resumable, one process); output and its write-up in
  `out/ink/` (`SUMMARY.md`, `summary.json`, `unclaimed_regions.jsonl` for the blind labellers, overlays, crops).
- `out/keys/<part>/{A,B,final}/` — the keys. `out/scores/` — scorer output. `score97.py` — the scorer.
- `extract97.py` — copies the pipeline's output for the 60 articles out of the release database once, read-only,
  into `out/cache/<stem>.json`; everything below works from that copy and never opens the database.
- `common97.py` — shared helpers: the explicit pipeline-role → key-role table, line → block / region lookup, and
  `tile_block`, which shares a block's shown text out among its Azure lines (alignment, boundaries snapped to spaces;
  lines re-ordered by best fit when the pipeline's line order is not the text order, e.g. table cells).
- `r1_reading.py` — R1: 600 lines (seed 97, 120 per page kind, 3+ characters), three witnesses (Azure, shown, t91 via
  the local reader service), crops in `out/reading/crops/`, `out/reading/lines.jsonl`, blind `out/reading/disputes.jsonl`
  (candidates shuffled, no witness names, 60 all-agree `control` lines), `out/reading/summary.json`. Which witness gave
  which candidate is in `out/reading/private/` — not for the blind agents.
- `r2_lines.py` — R2 mechanical: lines with no block / more than one block on the 214 pages → `out/scores/r2_lines.json`.
- `score97.py` — converts the pipeline into each key format and scores it with the same function that scores key A
  against key B (the ceiling); `scorecard.json` / `scorecard.md`, `pipeline_misses_<PART>.jsonl`,
  `disagreements_<PART>.jsonl` (A vs B, for the adjudicator). `selftest97.py` checks it on fake keys in `out/selftest/`.
- `page97.py` — builds the Desk page **/exam** ("The extraction exam", `desk/exam.py` + `web/pages/exam.tsx` in
  experiment 49): the scorecard (from `scorecard.json` `rows`) as bars with pass mark and keyer agreement, and real
  examples per group: ink overlays, disputed reading lines, key-vs-pipeline boxes per page, tables cell by cell,
  front-matter and reference misses, the triage's real errors. Writes only `out/page/` (exam.json, structure/,
  img/, ~120 MB). Rebuild after any re-score or key revision (the triage and REVISION_V2 notes are read live):
  `nice -n 19 ionice -c3 /home/appuser/inkscript/.venv/bin/python page97.py`. Screenshots: `out/page/screens/`.

## Result — Baseline v1 (keys rev 2), 2026-11-10

Release R20261104T151029, 60 articles, 214 exam pages. Full table with what a miss means per measure:
`out/scores/scorecard.md`; every miss in `out/scores/`; what is a real pipeline error and what was a scoring or key
artefact: `out/triage/TRIAGE.md`; key revisions: `out/keys/REVISION_V2.md`.

- **How far the exam can be trusted.** Two blind keyers agreed on 99.2–99.6% of line labels, 99.6–99.8% of grouping,
  100% of reading order, 99.7% of table cells, 517 of 518 reference boundaries, 96.6% of front-matter fields (99.2%
  folded). Controls on agreed items (60 + 60 lines, 40 cells, 40 references, 26 titles, 68 names): none wrong in both.
- **Passes.** Text ink seen by nobody 0.02%; lines lost 0%, doubled 0.2%; reading with deliberate rewrites set aside
  0.5% letters wrong; grouping F1 99.6%; order 99.1% (one column), 100% (two columns); footnotes 99.3%, calls linked
  96.4%; tables found 100%, shape 100%; reference boundaries 99.2%; reference year, volume, issue, pages 97–99%;
  source 95.7%; first printed page 98.2%.
- **Misses.** Label per line 95.7% (list items called paragraphs: 46 pieces; page numbers merged into the running
  head: all 56); table cells 98.5% folded and 90.1% exactly as printed (mark 99.5%); front matter: title 96.5% folded,
  authors 95.1%, abstract 90.9%, keywords 85.2%, affiliation 78.1%, received/accepted dates 72.2% (18 items), last
  printed page 86.4%; reference authors and title pass only when formatting is ignored; shown text as stored 0.7%
  letters wrong, because of 98 letters of deliberate rewriting (the printed «الكلمات المفتاحية:» label dropped, «،»
  turned into «؛»).
- **Reading.** The fix step beats Azure's raw line on 26 settled lines and loses on 3. Azure raw 0.8% letters wrong
  (exact), our reader t91 1.3%.
- **Ink ledger** (`out/ink/`): 99.975% of text ink claimed once; none of the unclaimed text-like regions is text.
- **Limits.** Table, reference and note pages were picked where the pipeline had found them, so "found" cannot fail;
  continuation can barely fail (the pipeline never links tables across pages); keyers saw Azure's lines; dates and DOI
  rest on 18 and 3 items; sections (P5) are not keyed yet.
- **What it changed.** Nothing in the pipeline yet: this is the baseline every later change is scored against.
  Found on the way: page images of 0529-004-007-007 with no body letters (font failed when the picture was made);
  a repository cover sheet read as page 1 (0246-021-003-004).

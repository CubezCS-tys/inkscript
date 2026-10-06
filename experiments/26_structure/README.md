# 26 · The article's structure, read as a reader reads the page

**Question.** The JATS file is only as credible as its structure, and experiment 24's position rules were its
weakest part: a title in 14 of 20 documents, an author in 8, an advertisement taken for a section ("1. إعلان" on
0656-014-010-014), footnote markers not linked, headings guessed. Can title, authors, headings, notes and their
markers be found from what a reader sees — size, bold ink, centring, space, numbering, repetition, place — and
from the Gemini title file already in the bucket, and how often is each right?

**Answer (2026-10-06).** Yes, measured against a truth I read on the page images (Arabic):

| element (10 documents, rules tuned on them) | before P / R | after P / R |
|---|---|---|
| title | 0.88 / 0.70 | **1.00 / 1.00** |
| authors (9) | 0.80 / 0.44 | **1.00 / 1.00** |
| rubric (3) | 0.67 / 0.67 | 1.00 / 0.67 |
| headings (27) | 0.00 / 0.00 | **0.96 / 1.00** |
| footnote links (31) | 0.67 / 0.13 | **1.00 / 0.97** |
| endnote links (15, one document) | – / 0.00 | **1.00 / 1.00** |
| running heads / page numbers left in the text | 15 | **0** |

**Held out** — 4 more documents (`truth/heldout.json`) read *after* the tuning: the first pass gave title 3/4,
authors 2/3, headings 0.83 / 0.71, footnote links 1.00 / 0.94, 2 furniture leaks (before: title 2/4, authors 2/3,
headings 0 / 0, links 1.00 / 0.81, 25 leaks). What they showed became three general rules (a title only slightly
larger than the text counts when a byline sits under it; an author's "*" note; a numbered heading over two lines
may be 16 words), after which: title 4/4, authors 3/3, headings 1.00 / 0.86, links 1.00 / 0.94, 0 leaks.

On the whole set of 20 (no truth needed): title found **20/20** (was 14), an author **16/20** (was 8); JATS 1.4
**20/20** and ALTO 4.4 **20/20** valid; every non-furniture ALTO block (2,806) points at an element of its JATS file.
The fixture still validates and its tests pass. Rebuilding the 20 files: 76 s, peak 0.8 GB. Gemini spend: **$0**
(only the title files already in the bucket; no check call was needed).

The owner's page: `out/report.html` — the precision/recall as bars, six documents with each page beside its
outline before and after, the boxes of title, author, rubric, headings, notes, markers and furniture drawn on the
page, and the 20-document table.

## What was built (in `src/`, see docs/pipeline.md, D22)

`src/inkscript/enrich/structure.py` — `read_meta(stem, dirs)` (Gemini's `<stem>.gemini.title.json` beside the
Azure JSON or in `--frontpage-dir`; the id's parts), `analyse(doc, meta, scan_pdf)`:

* **furniture**: digits alone at the top/bottom; short text at the top or bottom 16% that repeats on other pages
  (once more at the very edge, twice a little inside; never a numbered line); the journal's masthead; text on its
  side in the outer margin (a side tab); short text in the top 8% (not on page 1, where it may be the rubric) or
  bottom 6%.
* **notes**: the block of lines at the foot of a page whose letters are at most 86% of the body's, read upward
  until a body-size line; a raised number Azure returned as its own line is folded back into its note's line;
  a line opens a note when its first (or rightmost) word is a number — "(3)", "3)", "3 -", "3"; a block with one
  bare number counts only if a marker points at it.
* **markers**: in that page's text, the note's number glued to a word ("عاصم(٢).", "الأدب.٣"), in brackets alone,
  with one bracket ("٢)"), or bare and raised / alone on its line / after a full stop; never after الآية, رقم, ص…;
  in order after the previous note's marker. Notes gathered on the last pages (3+ per page, numbers not repeating)
  are endnotes, linked in order through the text.
* **title and authors**: Gemini's title aligned to Azure's words of the first pages (best contiguous run, letters
  similarity >= 0.6), the honorific words before a name joined to it as `<prefix>`; without a title file, the
  largest letters on page 1 before the text (>= 1.2x the body, or >= 0.95x with a byline under it), neighbouring
  lines of nearly the same size joined, a byline glued to the title line split off, an affiliation split from a
  name.
* **headings**: a paragraph of at most 2 lines and 16 words, narrower than the column, that is >= 1.2x the body,
  or bold (stroke width >= 1.2x the body's, measured on the scan: 2 x ink / outline), or numbered / opens with a
  section word / ends with a colon and is set apart by bold, space or centring; not a quotation, an invocation,
  the title or a name repeated over a later page (those are stripped and the rest judged), a table cell (words on
  its row), a note number beyond 40, or one of 3+ short numbered lines in a row (a list).

`jats.py` writes from it: Gemini's title with Azure's reading of the ink as `alt-title`, the ALTO word ids of the
title and each name in custom-meta, `<prefix>` and `<aff>`, the journal's name and year from the running heads,
volume/issue from the id, every note as an `<fn>` (one `<p>` per Azure paragraph it runs through) and each marker
as an `<xref ref-type="fn">` with the word's letters kept outside the link. `doc["roles"]` takes the new roles, so
`alto.py` (unchanged) tags its blocks the same way. `enrich()` gains `meta_dirs`; `cli.py` passes
`--frontpage-dir`.

**What the id spells** (`idparts.py`, 240 documents of experiment 19): journal-volume-issue-article. The printed
issue equals the id's on 62 of 70 documents that print one (the 8 others are the naive reading's mistakes — "عدد
(537)" in the text — a misprint, and one journal that puts العدد in the volume slot); the printed volume or
year-of-journal (السنة) on 33 of 37 (one journal is off by one). 000 = none (books; journals without volumes),
"041,042" = a double issue, 999 = a special issue. The fourth part is the article's order in the issue
(custom-meta), not a page.

## Method

* `fetch_gemini.py` — the title files in the bucket for the 20 documents: only **7 of 20** have one (titles and
  author names only; no rubric, journal or date).
* `render.py`, `dump.py`, `markers.py` — page images and Azure's paragraphs/markers, for reading by eye.
* `truth/truth.json` — 10 documents, the pages read (2–6 each), title, authors, rubric, every heading, every
  marker→note link, furniture strings; `truth/heldout.json` — 4 more, read after tuning. Borderline lines
  ("اما بعد", a plan's list) are "optional" and count neither way.
* `run_jats.py OUT` writes the JATS of the 20 documents with the code on `PYTHONPATH` (experiment 24's outputs
  read, never written): `out/before` was written with the code as it stood before this experiment, `out/after`
  with the new code. `evaluate.py [--truth heldout] DIR…` scores; matching is on normalised letters, ratio >= 0.6,
  honorifics removed from names.
* `reenrich.py` — the full `enrich` (JATS + ALTO, as `--xml` writes them) into `out/set/`, validated.
* `report.py` → `out/report.html`.

## Limits

* The 10 truth documents tuned the rules; the held-out numbers are the honest ones, on 4 documents.
* Without a Gemini title file the layout decides: an author printed *above* the title is taken for the rubric
  (1232-007-008-003); a rubric set in the title's size joins the title (1616: "دراسات قرآنية").
* A framed advertisement after the article's end ("إعلان", 0656) is still a section.
* Markers Azure never read (6934 p3: 5 of 9 raised numbers lost) cannot be linked; a misprinted marker (0792 p2: (٢)
  for note ٣) is not guessed.
* An English heading on an English abstract page was missed (2021 p4): the stroke and size cues are relative to
  the Arabic body.
* Stroke widths need the scan (the build has it); without it, bold is not a cue.

## Files

`fetch_gemini.py` · `render.py` · `dump.py` · `markers.py` · `idparts.py` · `run_jats.py` · `evaluate.py` ·
`reenrich.py` · `report.py` · `truth/truth.json` · `truth/heldout.json` · outputs (gitignored) in `out/`:
`gemini/`, `pages/`, `before/`, `after/` (JATS + `scores*.json`), `set/` (JATS + ALTO + `summary.json`),
`report.html`.

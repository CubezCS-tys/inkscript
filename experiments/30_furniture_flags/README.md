# 30 · Content taken for furniture, and flags that flood a page

**Question.** Experiment 28 found two failures in the product's reading layer on 205 documents. (1) **Content set
aside as page furniture**: 470 "lone" blocks in 105 documents were classed as running heads, footers or page
numbers, and 14 of 24 sampled were content (headings, captions, notes, table cells) missing from the JATS text.
(2) **Flags flood vowelled and handwritten pages**: documents over 50% vowelled had 60% of words flagged,
handwritten pages 68–91% — a flag on most words means nothing. Can furniture be told from content by more than
its place, and can the doubt be said once for a block or page, with word flags kept only where something points at
a word — without losing errors, and without letting running heads back into the text?

**Answer (2026-10-07).** Yes to both.

* **Furniture** — the rule now asks more than place: not in a table, not a note or caption, not ending with a
  colon, a repeat of the *same* text, the top/bottom band only when the text is the outermost on the page and set
  apart, a masthead only with مجلة or two masthead words, a side tab only outside the text's extent, a speck digit
  only alone on its line. On the 205 documents **9,815 → 6,742 blocks** are set aside; lone blocks with letters
  **470 → 267** (105 → 79 documents). On a hand-read sample of 140 old furniture blocks (tuning): **content kept
  56/60** (93%, 95% interval 84–97%; was 0/60), **furniture still set aside 71/78** (91%, 83–96%). **Held out** —
  60 blocks drawn afterwards from what the new rule changed: **released blocks that are content 33/38** (87%,
  73–94%; the 5 others a logo's lettering in one document and 2 specks), blocks still set aside by place that are
  furniture 12/15 (first pass 12/20; the bare-number note rule came from it). Experiment 26's truth unchanged:
  title 10/10, headings P 0.89 R 0.93, footnote links 30/31, endnote links 15/15, **furniture leaks 0**; held-out
  4 documents: 0 leaks.
* **Marks** — `trust.regions` marks a **handwritten** page (Azure's handwriting style on half its words at ≥ 0.9),
  **decorative** lettering (that style on a block of a printed page) and **vowelled** blocks (a third of the Arabic
  words vowelled). Inside, a word keeps its flag only for a Quran difference, Gemini's other reading, a Persian
  letter, a speck (not on handwritten pages), a Latin word, or a confidence under half its block's median *and*
  in the block's lowest tenth. On the 205 documents: over 50% vowelled **60.3% → 12.3%** flagged, 20–50% 15.8% →
  12.5%, handwritten pages **76.6% → 10.6%**, vowelled blocks 27.0% → 9.2%, decorative 23.5% → 9.0%; all words
  4.9% → 4.6%, documents under 5% vowelled unchanged (4.4%). On experiment 19's 2,935 judged words (61 errors):
  flagged 5.02% → 4.28% (weighted), errors flagged word by word 50 → 45 of 61 (82% [71–90] → 74% [62–83]),
  **errors flagged or inside a marked block 50 → 50**; in marked blocks (102 judged words, 8 errors) flagged 35 →
  11, errors flagged word by word 8 → 3 [14–69%], 1 flag in 3.7 a real error (was 4.4). Unflagged words outside
  marked blocks stay 0.42% wrong; inside them 5 of 91 unflagged judged words are wrong — what the block's mark
  says.

The owner's page: `out/report.html` — rescued content outlined on the scan, the two leaks, before/after flag maps
on a vowelled story, vowelled verse and a handwritten page, and the numbers as bars with their intervals.

## What changed in `src/`

* `enrich/structure.py` — the furniture part of `analyse` moved into `_furniture` (with `_segments`, `_band`,
  `CAPTION`, `MAST_WORD`, `LEAD_NUM`, `FURNITURE_TRACE` for experiments); the front matter (`_front` and its
  helpers) is untouched. Rules in its docstring and `docs/decisions.md` D23.
* `enrich/document.py` — each word carries `hw`, the confidence of Azure's handwritten-style span it sits in.
* `enrich/trust.py` — `regions`, `context`, `in_region`, `REGIONS`, `region_summary`, `region_meta`; `assess`
  applies them and stores `doc["regions"]`; `Mark.region`; `summary` counts words in marked blocks.
* `enrich/alto.py` — `OtherTag region.*` (TYPE reading-reliability), in each marked TextBlock's TAGREFS;
  `PAGECLASS="handwritten"` (ALTO 4.4 gives Page no TAGREFS; PAGECLASS is its user-defined class).
* `enrich/jats.py` — custom-meta `reading-vowelled` / `reading-handwritten` / `reading-decorative` (pages, counts,
  block ids, meaning) after the trust counts; `<p content-type="vowelled">` on body paragraphs.
* `enrich/trustpdf.py` — a third layer "Reading marks": a dashed blue outline per marked block and one note per
  page (English, top corner). The faithful bytes stay first; `trustpdf.check` passes (0657, 0408, 0679 rewritten).
* `enrich/__init__.py` — `res["regions"]` in the build report.
* `tests/test_furniture_flags.py` — table header vs running head, notes/masthead words, a cell vs a speck, the
  vowelled block, the handwritten page through ALTO, JATS and the trust PDF.

## Method

* **Census** (`census.py NAME`): `structure.analyse` on every one of experiment 28's 205 Azure readings (no
  scan: furniture does not use stroke widths), every block set aside with its rule, place, size → `out/census_*.json`.
* **Furniture truth** (`furniture_sample.py`): 140 of the old furniture blocks, stratified by the rule that set
  them aside (fuzzy repeats 40, exact repeats 30, top 8% 15, bottom 6% 12, side tabs 12, masthead 8, speck digits
  15, page numbers 8; seed 30), each cropped from the scan with its neighbourhood (`out/look/furniture_NN.png`),
  judged by me on the page: furniture / content / unsure → `truth/furniture_truth.json`. Old rule by stratum:
  fuzzy repeats 15 of 39 content, exact repeats 1/30, top 8% 13/14, bottom 6% 3/12, side 6/12, masthead 6/8,
  speck digits 15/15 (all table cells), page numbers 1/8 (a table's last row).
* **Tuning** on that truth (`evaluate_furniture.py`, trace per block); then **held out** (`heldout_sample.py`,
  seed 31): 30 released blocks with letters, 10 released numbers, 20 still set aside by place, judged the same
  way → `truth/heldout_truth.json`. One rule (a note that opens with a bare number) came from the held-out first
  pass; both passes are reported.
* **Experiment 26's truth** re-scored with its own scripts (`run_jats.py`, `evaluate.py`, `--truth heldout`).
* **Flags**: `judged_context.py` adds each judged word's block and page context (experiment 27's verdicts and
  signals; nothing paid); `flags_eval.py` scores variants (relative threshold 0–0.6 × median, with/without the
  lowest-tenth condition, ornament specific or not) with Wilson intervals; `flags_set.py` applies the rule to the
  build's own marks in experiment 28's ALTO files (205 documents, by kind and by mark).
* `handwriting_scan.py`: Azure's `styles` per page — the 9 manuscript pages of 0679 have 74–98% of words in a
  handwritten span at ≥ 0.9 (page median confidence 0.22–0.76); every printed page of 10 or more words is under 23% (most 0%).
  `look_marks.py`: contact sheets of the block-level marks, looked at — which is why a printed page's handwritten
  block is called *decorative* (script typefaces, calligraphic heads, a byline, one handwritten note, a screenshot)
  and why a vowelled block is never decorative (0412's vowelled verse is styled handwritten).
* `reenrich.py`: the full `enrich` + `verify` on 0657, 0408, 0679 into `out/reenrich/` (schemas valid, trust
  PDFs right). 0679 (78 pages): 62 s, peak 1.65 GB. `make_report.py` → `out/report.html`.

## Limits

* The furniture rule was tuned on 140 blocks I read; the held-out 60 are the honest check and are small.
* Still wrong: a logo's lettering that looks like a table (7894, every page), a calligraphic running head read
  differently on each page (1900), a table that starts at the very top of a page with nothing above it, a note
  whose number Azure reads at the end of the line, a rotated table's header at the page's foot.
* The judged sample holds only 102 words in marked blocks (8 errors): the intervals there are wide. The
  threshold (half the median, lowest tenth) was chosen for what the reader sees on the 205 documents, which the
  judged words cannot separate from 0.3–0.6.
* Words in a marked block that are not flagged carry `trust.agreed` with their block's region tag; "agreed" there
  means only that nothing points at the word.
* `test_docs.py::test_named_source_files_exist` fails in a fresh worktree (it names gitignored `out/` pages that
  exist only in the main checkout); it passes there.

## Files

`census.py` · `furniture_sample.py` · `evaluate_furniture.py` · `heldout_sample.py` · `handwriting_scan.py` ·
`look_marks.py` · `judged_context.py` · `flags_eval.py` · `flags_set.py` · `reenrich.py` · `make_report.py` ·
`truth/furniture_truth.json` · `truth/heldout_truth.json` · outputs (gitignored) in `out/`: `census_before.json`,
`census_after.json`, `furniture_sample.json`, `heldout_sample.json`, `furniture_eval_*.json`, `judged_context.json`,
`flags_eval.json`, `flags_set.json`, `handwriting_pages.json`, `look/`, `reenrich/`, `report.html`.

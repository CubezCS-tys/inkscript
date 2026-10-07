# Status

*Last updated 2026-10-07. Update this file whenever a headline number or a
"does / does not" changes; keep the date on every number.*

## What the PDFs do

| | Result | Measured on | Date |
|---|---|---|---|
| Words copy out intact in Chrome's engine | 99.99% (893,113 / 893,203) | 227 journals, 4,440 pages | 2026-09-20 |
| Lines come out in reading order | 99.95% (82,574 / 82,613) | same | 2026-09-20 |
| Words in which **every letter has its own selection box** | **97.8%** (711,485 / 727,514); typical document 98.4%, weakest tenth under 94.7% | the 193 scanned documents of the 227-journal set, rebuilt with the post-run fixes (3,465 pages) | 2026-09-22 |
| Lines in order, against other tools | ours 98–100%, Azure's own PDF 34–75%, ocrmypdf 2–16% | 3 documents (`experiments/07_engine_comparison`) | 2026-09-18 |
| Against the Azure PDFs being uploaded now | words 100.0% vs 97.9%, lines in order 100.0% vs 79.3%, letter boxes 5.88 vs 1.00 (Azure slices words evenly) | 10 random documents of the 21–22 Sep upload, 106 pages, 42,843 words (`experiments/14_vs_azure`) | 2026-09-22 |
| Test set of 30 documents | 34,959 / 34,959 words, 3,868 / 3,868 lines | `~/Desktop/native_pdfs` (built before the pen path; not rebuilt) | 2026-09-19 |
| 451-document sample | 99.98% words, ~99.9% lines (words only; no letters) | `docs/night-report-2026-09-18.md` | 2026-09-18 |
| Born-digital pages | detected and left alone (their junk-encoded fonts neutralised) | | 2026-09-18 |
| Reference document (the test fixture) | 1,246 / 1,246 words, 113 / 113 lines, 96.2% letter coverage, ~28 s, peak 0.85 GB | `tests/fixtures/0582-004-009-012` | 2026-09-20 |

An 81-page document builds in about 10 minutes at a peak of 1.6 GB.

| Letter highlight on the right letter (blind Gemini judge, strict) | 76.7% of letters on unseen pages after the alef fix (was 70.2%; Chrome's equal slicing 53.9%); fixture 62.2% (was 56.2%, equal slicing 58.2%) | 230 words, 981 letters (`experiments/18_boxes`, `21_better_boxes`) | 2026-10-06 |
| Azure's reading, judged on the ink | 1.55% of words wrong on scans [0.62–2.79], printed Arabic misread 0.61%; pre-2000 2.8%, after 0.65%; 42% of documents born-digital | 240 random documents, 2,971 words (`experiments/19_azure_map`) | 2026-10-06 |
| Reading from the pen path alone (the feeler) | 82.6% of unseen pieces read as Azure reads them (bigger reader, 97 books) | 4 books, held-out pages (`experiments/16_feel`) | 2026-10-06 |
| Document files beside the PDF (`--xml`): JATS 1.4 article + ALTO 4.4 page file | valid against the official schemas 20/20 + 20/20; title found 20/20 (was 14), author 16/20 (was 8), printed page range 18/20 | 20 scanned documents, 321 pages, 1960–2018 (`experiments/24_product`, `26_structure`) | 2026-10-06 |
| Article structure in the JATS, against a hand-read truth (precision / recall) | 10 documents (rules tuned on them): title 1.00/1.00 (was 0.88/0.70), authors 1.00/1.00 (0.80/0.44), headings 0.96/1.00 (0.00/0.00), footnote links 1.00/0.97 (0.67/0.13), endnote links 1.00/1.00 (–/0.00); running heads or page numbers left in the text 0 (was 15). 4 held-out documents, first pass: title 3/4, authors 2/3, headings 0.83/0.71, footnote links 1.00/0.94 | `experiments/26_structure` (`out/report.html`) | 2026-10-06 |
| Uncertain words marked (`--xml`/`--trust`, experiment 22's rule) | 7.9% of words flagged (pre-2000 prints 11.4%, from 2000 on 4.8%); on 22's judged sample the rule leaves 0.43% of unflagged words wrong | same set | 2026-10-06 |
| Uncertain words marked, with experiment 27's common-word refinement (now the rule) | **5.3%** of words flagged on the same set (was 7.9%); on 19's judged words 7.5% → 5.0% flagged, errors caught 50 → 50 of 61, 1 flag in 7.4 a real error (was 8.9), 0.42% of unflagged words wrong | same set; `experiments/27_corrections` | 2026-10-06 |
| Corrections from Quran verses (`inkscript fix`), judged on the ink by two blind judges | 194 proposed, 156 accepted, **147 written** into both PDFs' text, the ALTO, JATS and trust PDFs; the drawing pixel-identical; quotations equal to the verse 235 → 290 of 387; $0.80 for the set | same set (`experiments/27_corrections`) | 2026-10-06 |
| Quran quotations found and checked | 387, all linked to sura:verse; 235 equal to the verse, 152 differ (their words flagged) | same set | 2026-10-06 |
| `_trust.pdf` (hideable highlights, incremental update) | the original bytes first and the same text and character boxes in pdfium, 20/20; fixture 1,246/1,246 words, 113/113 lines on both copies | same set; `tests/test_enrich.py` | 2026-10-06 |
| **The whole product at scale** (`--vector --verify --xml --trust`, then `fix --apply`) | 205/205 built, 0 crashes, 0 timeouts; words intact 99.98% (868,741 / 868,897), lines in order 99.94%, letters selectable **97.75%** (median document 98.6%), flagged 4.89%, trust PDFs right 205/205, ALTO valid 205/205, JATS 204/205; title matching the MARC catalogue 148/204 (69/75 with a Gemini title file, 79/129 from the layout), catalogue authors found 107/214; 242 Quran quotations, 31 corrections proposed, 18 written, $0.125; 18.6 s a page (median document), peak 2.19 GB, 7 h 40 min on 3 workers | 205 scanned documents, 3,254 pages, 1932–2025, 172 journals, none of them tuning any rule (`experiments/28_scale`, `out/showcase.html`) | 2026-10-07 |
| Looking at the outputs (`inkscript view`, experiment 31) | the article's words linked to their box on the scan **99.85%** (900,130 / 901,457), non-furniture blocks placed in the article 46,525 / 46,525; a 48-page document opens in 0.9 s, a jump to page 40 in 0.2 s (Chromium, local server) | experiment 28's 205 documents | 2026-10-07 |
| Page furniture told from content (experiment 30) | blocks set aside on the 205 documents 9,815 → 6,742, "lone" ones with letters 470 → 267; on 140 old furniture blocks read by eye content kept 56/60 (93%, 84–97%), furniture still set aside 71/78 (91%, 83–96%); held out (60 blocks drawn afterwards) released blocks that are content 33/38 (87%, 73–94%); experiment 26's truth unchanged (0 furniture leaks) | experiment 28's 205 documents (`experiments/30_furniture_flags`) | 2026-10-07 |
| Block and page marks instead of flag floods (experiment 30: vowelled, handwritten, decorative) | flagged on documents over 50% vowelled 60.3% → 12.3%, handwritten pages 76.6% → 10.6%, all words 4.9% → 4.6% (under 5% vowelled unchanged); on 19's judged words flagged 5.0% → 4.3%, errors flagged word by word 50 → 45 of 61, flagged or inside a marked block 50 → 50; unflagged words outside marked blocks still 0.42% wrong | same 205 documents; 2,935 judged words (nothing paid) | 2026-10-07 |
| Selection in current Chrome (Chromium 153, real browser, scripted drag) | letter by letter in reading order, lines copy out exactly, once the PDF is marked right-to-left; unmarked it jumped word to word | `0618-021-002-004` p3 | 2026-10-05 |

## What they do not do (known gaps)

- **Found at scale (experiment 28, 2026-10-07; patches proposed in `experiments/28_scale/patches/`, not applied):**
  on scans that carry a typeset header or caption, the source font's text stays beside ours (23 of 205
  documents; copied twice, often garbled; 70% of the set's order inversions); without a Gemini title file the
  title is right in 79 of 129 documents; about 270 blocks of content (headings opening a page, captions,
  footnotes, table cells) are set aside as page furniture and missing from the JATS text; vowelled text, verse
  and handwriting flood the trust copy (over 50% vowelled: 60% of words flagged); `save(garbage=3)` is 65% of
  the slowest build; one JATS file had an empty `<fn-group>`. *(2026-10-07, experiment 30: furniture and the
  flag floods fixed — see the table above; still set aside wrongly: a logo's lettering read as a table, a table
  starting at the very top of a page, a calligraphic running head read differently on each page.)*

- **Latin-majority lines copy out with their words swapped** in current
  Chrome, the price of marking the document right-to-left (D18). Chromium also
  highlights the whole last line of a multi-line drag.

- **The text is Azure's reading** — since 2026-10-06 with every uncertain word
  marked (`--xml`/`--trust`; 5.3% of words on the product set since experiment
  27), and only words of Quran quotations corrected (`inkscript fix`: 147 on 20
  documents, each judged on the ink); everything else stays as Azure read it,
  and confident misreadings (an added hamza at 0.99) stay unmarked.
  "Words intact" means we preserved it, not
  that it is right. Page 1 is Gemini's. Making the text trustworthy is
  milestone 1 in [roadmap.md](roadmap.md). *First measurements, 2026-09-21
  (`experiments/12_gold`):* three sheets hand-marked word by word — `0005` p2
  (Azure, heavy clean face) **277 of 277 right**; `1110` p1, the set's weakest
  document, scored twice on the same ink: **Gemini 146 of 150** (the reading
  the PDF carries) against **Azure 149 of 150** (the reading Gemini replaces).
  D1 was kept unchanged all the same — [decisions.md](decisions.md), D16.
  Across the sheets 572 of 577 words are right, so the baseline any checker
  must beat — *change nothing* — is **99.1%**, and three of the five doubtful
  words were marked unsure from the ink itself, which no checker can settle
  either. Azure on the body text of a difficult face is still unmeasured.
- **Letter boxes: first measurement 2026-10-06 (experiment 18).** A blind Gemini judge (strict: accepts 49/60 boxes right by construction, 0/60 moved a letter) puts the cutter's highlight on the right letter for 70.2% of letters on unseen pages against 53.9% for Chrome's equal slicing, but not on the fixture (56.2% vs 58.2%); corrected for the judge's strictness about 83–86%. Weak spot: a joined final alef gets a sliver of a box (5/56 right). *Earlier:* **Letter boxes exist; their placement is not measured.** By eye about 85–90%
  of cuts sit right on the reference document; doubted cuts (about a third of
  them wrong) are still cut, because an uncut piece is no better. A
  hand-checked sample is milestone 2.
- Words carrying vowel marks are never cut into letters (pdfium reorders
  split vowelled words).
- Underlined words cut badly (the underline is glued to the ink).
- Fine slanted faces with overhanging kaf are weaker (`0690-012-001,012-028`).
- Tables: cells pdfium joins across rows. Firefox copies lines word-reversed
  at our 8 pt nominal size (`experiments/06`).
- `inkscript correct` cannot write a correction shorter than the word's glyph
  count in place (an empty ToUnicode reads back as the char code).
- *(Closed 2026-09-22.)* The fixes made after the first 227-journal run — the
  swapped `في`, alef splitting in a light face, hamza of a joined `أ`, dots
  under a swept-back tail — are now in `journals227_v3`. Letter coverage
  96.8% → **97.8%**; 29.4% of characters got a different box and 188 of 227
  documents moved by more than 5%, the biggest gainers being the faces the
  fixes were for (`0350` 91.4 → 96.1%, `0920` 87.5 → 94.6%, `1260` 92.7 → 98.1%).
  73 documents' page text string changed, all of it **where pdfium puts a line
  break** — a word that used to be split across one is now whole; words intact
  was identical old and new in every document sampled.

## In flight / where outputs are (this machine)

- **The scale run (2026-10-07)**: 205 documents built with everything on and fixed in
  `experiments/28_scale/out/set/w0..w2/`; numbers in `summary.json`, the owner's page
  `experiments/28_scale/out/showcase.html`. Nothing is running.

- **The product set (2026-10-06)**: 20 documents built with `--vector --verify
  --xml --trust` in `experiments/24_product/out/set/w0..w2/`; numbers in
  `summary.json`, the owner's page `experiments/24_product/out/showcase.html`.

- **The rerun of the 227 journals is running now** (started 2026-09-21,
  roadmap item 5): 3 workers into
  `experiments/09_pen_path/out/journals227_v3/`, watchdog up, `src/` must not
  be edited until it ends. It resumes by rerunning the same command
  (`experiments/09_pen_path/run_set.sh <azure> <frontpage> - <out> 3`, see
  [operations.md](operations.md)); when `summary.txt` ends `SET DONE`, compare
  the builds with `compare_boxes.py journals227 journals227_v3`.
- 227-journal run with letters (the "before" side of that comparison):
  `experiments/09_pen_path/out/journals227/` (`summary.txt`,
  `w0*/…_vector.pdf`, `w00/letter_coverage.json`); the first, pre-fix run is
  `journals227_first/`.
- Fonts built from two books are installed for the owner in
  `~/.local/share/fonts/` (Inkscript 0582 / 0565 Restored); sources in
  `experiments/11_typeface/out/`.
- Older deliverables: `~/Desktop/native_pdfs/` (30 documents),
  `~/Desktop/s3_native/` (47 documents) — built before pen-path letters.
- Storyboard artifact (version 4, published 2026-09-20; private to the owner until shared):
  https://claude.ai/artifact/MjTHoKev4bJLX6vHo4jdk3 — source `docs/storyboard/`, rebuilt by
  `docs/storyboard/rebuild.sh`, republished by passing that URL.

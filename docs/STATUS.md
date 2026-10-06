# Status

*Last updated 2026-10-05. Update this file whenever a headline number or a
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

| Selection in current Chrome (Chromium 153, real browser, scripted drag) | letter by letter in reading order, lines copy out exactly, once the PDF is marked right-to-left; unmarked it jumped word to word | `0618-021-002-004` p3 | 2026-10-05 |

## What they do not do (known gaps)

- **Latin-majority lines copy out with their words swapped** in current
  Chrome, the price of marking the document right-to-left (D18). Chromium also
  highlights the whole last line of a multi-line drag.

- **The text is Azure's reading.** "Words intact" means we preserved it, not
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

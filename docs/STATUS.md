# Status

*Last updated 2026-09-20. Update this file whenever a headline number or a
"does / does not" changes; keep the date on every number.*

## What the PDFs do

| | Result | Measured on | Date |
|---|---|---|---|
| Words copy out intact in Chrome's engine | 99.99% (893,113 / 893,203) | 227 journals, 4,440 pages | 2026-09-20 |
| Lines come out in reading order | 99.95% (82,574 / 82,613) | same | 2026-09-20 |
| Words in which **every letter has its own selection box** | **96.8%** (715,596 / 739,318); typical document 97.2%, weakest tenth under 92.7% | the 194 scanned documents of that set (3,511 pages we wrote) | 2026-09-20 |
| Lines in order, against other tools | ours 98–100%, Azure's own PDF 34–75%, ocrmypdf 2–16% | 3 documents (`experiments/07_engine_comparison`) | 2026-09-18 |
| Test set of 30 documents | 34,959 / 34,959 words, 3,868 / 3,868 lines | `~/Desktop/native_pdfs` (built before the pen path; not rebuilt) | 2026-09-19 |
| 451-document sample | 99.98% words, ~99.9% lines (words only; no letters) | `docs/night-report-2026-09-18.md` | 2026-09-18 |
| Born-digital pages | detected and left alone (their junk-encoded fonts neutralised) | | 2026-09-18 |
| Reference document (the test fixture) | 1,246 / 1,246 words, 113 / 113 lines, 96.2% letter coverage, ~28 s, peak 0.85 GB | `tests/fixtures/0582-004-009-012` | 2026-09-20 |

An 81-page document builds in about 10 minutes at a peak of 1.6 GB.

## What they do not do (known gaps)

- **The text is Azure's reading.** "Words intact" means we preserved it, not
  that it is right. Page 1 is Gemini's. Making the text trustworthy is
  milestone 1 in [roadmap.md](roadmap.md).
- **Letter boxes exist; their placement is not measured.** By eye about 85–90%
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
- Fixes made after the 227-journal run and **not yet in those files**: the
  swapped `في` in faces whose ya-tail runs back along the baseline; words of a
  light face not split at the alef; hamza of a joined `أ`; dots under a
  swept-back tail. A rerun with a per-document box comparison is the open task.

## In flight / where outputs are (this machine)

- 227-journal run with letters: `experiments/09_pen_path/out/journals227/`
  (`summary.txt`, `w0*/…_vector.pdf`, `w00/letter_coverage.json`); the first,
  pre-fix run is `journals227_first/`.
- Fonts built from two books are installed for the owner in
  `~/.local/share/fonts/` (Inkscript 0582 / 0565 Restored); sources in
  `experiments/11_typeface/out/`.
- Older deliverables: `~/Desktop/native_pdfs/` (30 documents),
  `~/Desktop/s3_native/` (47 documents) — built before pen-path letters.
- Storyboard artifact (published 2026-09-18, stale since):
  https://claude.ai/artifact/MjTHoKev4bJLX6vHo4jdk3 — source `docs/storyboard/`.

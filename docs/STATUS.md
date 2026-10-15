# Status

*Last updated 2026-10-14. Update this file whenever a headline number or a
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
| **JATS front matter from Mandumah's MARC catalogue, tied to the ink** (`--xml`, default when the index exists) | record for 204/205 documents; title 194 → **205** (on its printed words 194 → 202; the page alone matched the catalogue in 171/204), authors 147 → **205** (195 of 214 catalogue names found on the page; the page alone found 132), journal title 101 → 205, ISSN 0 → 89, year 66 → 205 (Hijri 10 → 76), pages 165 → 205, abstract 0 → 34, keywords 0 → 204, DOI 0 → 15, affiliations 26 → 50; honorifics as `<prefix>` (97); JATS 1.4 / ALTO 4.4 valid 205/205; no wrong record found, and of 204 neighbours' records given on purpose 0 were accepted; index 1.1 GB, 29 ms to open, 1.1 ms a lookup | the 205 documents of experiment 28 (`experiments/29_catalogue`) | 2026-10-07 |
| **The yardstick (gold set) for every reader** (experiment 34, D26) | 202 pages drafted and ready to correct: 185 documents, 159 journals, 1929–2025, 44 pages before 1970; tables 29, equations 14, Quran 22, vowelled 21, footnotes 43, mixed Latin 39, magazines 50; held out by journal 151 test / 51 dev; Gemini disagrees with Azure on 26% of 8,493 lines; correcting estimated at **13.6 h** (7.8–25); `inkscript view --gold`, `inkscript score`; nothing is gold until the owner corrects | `experiments/34_yardstick` (`out/report.html`), $12.40 | 2026-10-11 |
| **Derived editions from the master files** (`inkscript edition`, experiment 35): reading HTML, EPUB 3, layout-faithful PDF, one-column PDF, Markdown, dataset record | 205/205 built, 0 failures, 18 min on 2 workers, 0.63 GB a worker; printed words found, read back from the files: HTML/EPUB/Markdown/JSONL 99.99%, layout PDF 99.97% (every ALTO word, furniture too), one-column PDF 99.94% (digits aside: it renumbers notes); words in reading order in pdfium: layout 96.1%, one-column 93.6% (median document 99.3% / 99.0%; the rest mostly Latin lines in Arabic documents, D18); EPUB epubcheck-clean 21/21; Gemini judge on 36 pages, scan beside rebuild: same blocks 33 + 3 mostly, same order 36/36, overall 4/5 on 33 (planted faults: dropped paragraph 3/3, swapped 3/3, demoted heading 0/2); $0.39 | experiment 29's 205 masters, 3,254 pages (`experiments/35_edition`, `out/report.html`) | 2026-10-11 |
| **An open line reader of our own** (Kraken 7.1, fine-tuned; experiment 33) | born-digital lines: characters wrong 3.6% out of the box → **1.5%** (Kraken) / **1.3%** (PP-OCRv6), Azure 1.0%; scan-like copies 9.0% → 2.1% / 1.4%. Real scans, experiment 19's judged words wrong: 24.5% → **15.2%** / 15.5%, Azure 2.0% (body text 5.4% → 4.3%, Azure 1.1%); whole scanned pages against Azure's lines 13.4% → 8.2%, and **6.5%** with its line finder fine-tuned too (finds 95% of Azure's lines, was 93%; lines run together 2.4% → 0.6%). Owner's 2 gold pages (47 lines): Azure 0.8%, fine-tuned Kraken 2.7–2.8%. PaddleOCR-VL-0.9B (smoke test) reads lines about as well but invents and skips on pages | 4,089 born-digital test lines of 30 documents / 25 journals no training line came from; 2,894 judged words of 139 scanned documents; 139 scanned pages (`experiments/33_kraken`, `out/report.html`) | 2026-10-12 |
| **Our own parser on the hardest pages** (experiment 38, D29): Azure's words poured into dots.mocr's layout, tables, formulas and pictures, then JATS + ALTO and every edition | blind Gemini judge, scan beside old and new layout page: new preferred on **18 of 33** hard pages (55%, 38–70%), old 4, tie 11 (closeness 3.79 vs 3.36); a reviewer by eye on 44 pages: new 28, same 13, old 3; every Azure word placed once (13,481), none lost against Azure; gold word error order-free Azure 5.4%, new 5.5%; 15 pictures placed, 19 formulas checked on the crop and typeset (judged 3.89 vs dots' 3.47), 15 tables ruled but Azure's words in dots' grid judged 2.8 vs 3.4 for dots' own cells; **model correction off**: on gold 30 right, 34 wrong (word errors 85 → 89); JATS/ALTO valid 44/44; $3.08 | 35 hardest yardstick pages + 9 done gold pages (`experiments/38_parser`, `out/report.html`) | 2026-10-12 |
| Selection in current Chrome (Chromium 153, real browser, scripted drag) | letter by letter in reading order, lines copy out exactly, once the PDF is marked right-to-left; unmarked it jumped word to word | `0618-021-002-004` p3 | 2026-10-05 |

## What they do not do (known gaps)

- **Found at scale (experiment 28, 2026-10-07; patches proposed in `experiments/28_scale/patches/`, not applied):**
  on scans that carry a typeset header or caption, the source font's text stays beside ours (23 of 205
  documents; copied twice, often garbled; 70% of the set's order inversions); without a Gemini title file the
  title is right in 79 of 129 documents (since experiment 29 the catalogue gives it for 204 of 205); about 270 blocks of content (headings opening a page, captions,
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

- **Second branch, the open reading stack (started 2026-10-11)**, beside the ink-as-text
  work, which stays alive ([vision.md](vision.md), [roadmap.md](roadmap.md)). Research and plan:
  [experiments/32_open_stack](../experiments/32_open_stack/README.md) (plan page:
  https://claude.ai/artifact/4sMPMdfjjnrkttPTHsE1kM). Running, each on its own worktree branch,
  outputs in the main checkout's `experiments/3x_*/out/`:
  - 33: Kraken on Mandumah lines, then fine-tuned on born-digital lines. First numbers
    (2026-10-11, out of the box): Arabic character errors on clean born-digital lines are
    Kraken 4.1%, Azure 1.75%; 9.6% on the same lines degraded; about 7% on real scans
    (against Azure's readings, so silver truth).
  - 34: the yardstick, merged; the owner is correcting (`inkscript view --gold`).
  - 36: the VLM bake-off (2026-10-12, D28; owner's page
    `/home/yassine/inkscript/experiments/36_vlm_bakeoff/out/report.html`). **dots.mocr** is the main open reader: characters
    wrong on the owner's 6 done gold pages 3.0% [1.7–4.6] (Azure 0.9%, flattered), born-digital pages
    5.5% [3.0–9.2] (Azure 3.1%), 13.7% different from Azure on all 202 yardstick pages; invented
    0.9 words per 1,000 outside tables, dropped 15.2, no runaway or given-up page; two columns in
    order 86.5%; vowel marks kept 60% (Azure 89%); tables judged 3.44/5, equations 2.42/5;
    2,807 pages/h, $0.17 per 1,000 pages on one RTX 5090. amad-vlm6 reads plain text best (1.5% /
    3.6%) but gives no layout; PaddleOCR-VL reads two-column Arabic left column first and invents;
    Qwen3-VL gives up on 23% of pages or loops. Kraken as checker flags 92–100% of the VLMs'
    inventions (precision 9–13% on good readers). dots' licence agreement (no "unauthorized
    digitization of publications", limits on training from its outputs) is for the owner to clear.
    Spent $1.62 (GPU $1.06, Gemini judge $0.56).
  - 35: the native edition, merged (below).
  - 38: the parser (Azure's words in dots.mocr's layout) on the hardest pages, done 2026-10-12 (D29); owner's page
    `/home/yassine/inkscript/experiments/38_parser/out/report.html`, per-page masters and editions in
    `experiments/38_parser/out/pages/<pid>/`. Nothing is running.
  - 39: the layout model (DocLayout-YOLO on Gemini Flash line labels), round 2 done 2026-10-14: 87.8% of the 44
    test pages' lines named like the Pro referee (round 1 87.7%, dots.mocr 84.4%); equations 0% → 78%, lists 54% → 68%,
    but footnotes 95% → 67% and verse 96% → 61% (the new pages were 63% table lines); with dots for tables and
    equations 90.5% (round 1 92.1%). Not good enough to replace round 1. Owner's page
    `/home/yassine/inkscript/experiments/39_ink_geometry/out/layout_model.html`. Nothing is running.
  - 40: Gemini 4 (gemini-4-argon) alone as the reader, done 2026-10-14, $13.34
    ([README](../experiments/40_gemini4_vlm/README.md), https://claude.ai/artifact/54SBuWQZQQosVQqyqEpE31): block
    types right 96.8% (Azure 74%, our layout model 84%); text about Azure's level but not faithful (fixes misprints,
    adds hamzas). Led to D30: the print as printed, misprints flagged (`span.sic`).
  - 41: Azure's words with Gemini's structure as line ids, 55 articles / 399 pages, done 2026-10-15, $10.72
    ([README](../experiments/41_azure_structure/README.md), https://claude.ai/artifact/AiqhFTZTvMF2or8W9Bi4mp): no
    chunk failed; words wrong on 34 truth pages Argon 1.55%, Flash 1.77%, Azure 1.80%; Argon for the edition, Flash
    for training labels. A reader for the 55 articles is being built (`reader.py` → `out/reader/`). Waiting on the
    owner's hand-check of 5 articles (`out/handcheck/`). Gemini credit ran out 2026-10-15.
- **The editions (2026-10-11, experiment 35)**: every derived edition of the 205 documents in
  `experiments/35_edition/out/editions/<id>/` (513 MB), the hand-made table/maths tests in
  `out/testmasters/`, the owner's page `experiments/35_edition/out/report.html`. Nothing is running.

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

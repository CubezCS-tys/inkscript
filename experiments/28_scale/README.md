# 28 · The whole product on 205 scanned journal documents: what breaks?

**Question.** Experiments 24–27 built the product (faithful PDF + trust copy + JATS + ALTO + Quran checks and
corrections) and measured it on 20 documents, some of which tuned its rules. On ten times as many documents, from
every decade and 172 journals, what are its numbers, and what fails that the 20 did not show? "Every failure mode
so far was found this way, not by reasoning" (docs/roadmap.md).

**Answer (2026-10-07).** The build is solid at scale and the reading layer holds: 205 of 205 documents built with
everything on, no crash, no timeout, no lost page image, words intact 99.98%, lines in order 99.94%, letters
selectable 97.75%, trust PDFs right 205/205, ALTO valid 205/205, JATS valid 204/205. What breaks is around it:
**the source PDF's own text left beside ours** (23 documents), **titles and authors without a title file**
(title right in 79 of 129, an author in half), **content set aside as page furniture** (≈270 blocks), **flag floods
on vowelled text, verse and handwriting**, and **slow saves**. Four patches are proposed, each tested
(`patches/`); the owner's page is `out/showcase.html`.

## Numbers (205 documents, 3,254 pages, 1932–2025, 172 journals; built 2026-10-06/07)

| | set | before (experiment 24, 20 documents) |
|---|---|---|
| built end to end / crashed / timed out (90 min) | **205 / 0 / 0** | 20 |
| words intact in pdfium 5.12.1 | **868,741 / 868,897 (99.98%)** | 99.99% |
| lines in reading order | **82,664 / 82,717 (99.94%)**; 774 order inversions (542 of them in the 23 documents of failure 1) | 99.92% |
| words with every letter selectable (`coverage.py`) | **97.75%** (685,168 / 700,968); median document 98.6%, weakest tenth under 95.1% | 97.3% |
| words flagged to check | **4.89%** (43,085 of 881,793); median document 3.5%, 90th percentile 11.4% | 5.3% (after 27) |
| words verified | 2,529 | 4,946 |
| Quran quotations | **242** found; **185** equal to the verse after corrections (174 before) | 387; 290 |
| corrections (`inkscript fix`) | **31** proposed, 19 accepted, **18 written**, 1 declined (D13), 12 turned down on the ink; ink identical in every corrected PDF | 194 / 156 / 147 |
| Gemini spend | **$0.125** (cap set at $5 of the $15 budget) | $1.13 |
| JATS 1.4 / ALTO 4.4 valid | **204 / 205**, 205 / 205 (failure 7) | 20/20 |
| trust PDFs: same bytes first, same text in pdfium | **205 / 205** | 20/20 |
| title matches the MARC catalogue | **148 / 204** (with a Gemini title file 69/75; from the layout 79/129) | "found 20/20" |
| catalogue authors found in the JATS | **107 / 214**; names given right 106 / 124 | "16/20" |
| journal name from the running heads, when one is named | right in 53 of 101 | — |
| time | 7 h 40 min on 3 workers; 22.3 worker-hours; **18.6 s a page** median document (24.7 s mean), 78 s worst | |
| peak memory | median document 0.98 GB, **max 2.19 GB** (the 92-page 2025-067-002-007); watchdog never fired | 1.35 GB |
| pages left as born-digital | 45 (in 11 documents) | |

**By decade** (catalogue year; `out/set/summary.json` has every document, journal and decade):

| decade | docs | pages | letters selectable | flagged | title right |
|---|---|---|---|---|---|
| before 1960 | 14 | 92 | 97.2% | 8.4% | 14/14 |
| 1960s | 18 | 140 | 98.4% | 7.2% | 17/18 |
| 1970s | 23 | 250 | 98.7% | 7.1% | 19/23 |
| 1980s | 30 | 454 | 97.5% | 6.7% | 27/30 |
| 1990s | 38 | 655 | 97.5% | 4.3% | 29/38 |
| 2000s | 37 | 422 | 97.9% | 3.3% | 20/37 |
| 2010s | 29 | 729 | 97.0% | 4.4% | 14/29 |
| 2020s | 15 | 471 | 98.7% | 3.1% | 8/15 |

Old prints are flagged twice as often as recent ones (as experiment 22 predicted) but are no weaker in letters;
titles are found best on old, short articles (a large title alone at the top) and worst on 2000s–2010s articles,
whose page 1 crowds a masthead, a running head, a bilingual title and an abstract. In-sample (experiment 19's 127,
whose words helped build the common-word list) vs fresh 78: flagged 4.68% vs 5.21%, letters 97.5% vs 98.1% — the
fresh draw is older by design, so the gap is no evidence of overfitting.

## Failure modes (counts on the whole set; every kind looked at on rendered pages, `out/look/`)

1. **The source PDF's own text left beside ours — 23 documents, 412 pages, 9,218 words.** On a page rebuilt from the
   scan, a running head, caption or footnote the source had typeset in a real font keeps its text beside our glyphs
   for the same ink: copying gives it twice and often garbled ("جملة التواصل العدد التاسع واالربعون", presentation
   forms "اﻟﻤﺠﻠﺔ اﻟﻌﻠﻤﻴﺔ", "WO »UOG « WE("). 23 of the 26 `scan+real-font` documents; they hold 542 of the set's 774
   order inversions (Chrome reads that text after ours, back at the top). Cause: only fonts whose text extracts as
   symbols are neutralised (`native.py`); a broken lam-alef or presentation forms pass as text. New.
2. **Front matter without a title file.** 130 of 205 documents have no `<id>.gemini.title.json` in the bucket. From
   the layout the title matched the catalogue in 79 of 129: 37 got none, 13 the wrong line (an author, «المقدمة»,
   the masthead, «السلام عليكم»). Four causes, seen in `front_trace.py`: a running head repeating the title above it
   stops the search; Azure merged title + author + affiliation into one paragraph; the title repeats as a running
   head later and is classed as furniture; Azure's reading order puts the title last. Catalogue authors found 107/214.
   Experiment 26's 20/20 titles were in-sample; its 4 held-out documents (3/4) were the honest number.
3. **Content set aside as page furniture — 470 "lone" blocks in 105 documents; 14 of 24 sampled are content**
   (`furniture.py`, `lone_sheet.py`): a table caption, a heading opening a page («مراجع البحث», «(المادة الثالثة)»),
   a footnote, a reference, table cells, a column's last line — kept in the ALTO (tagged furniture) but missing from
   the JATS text. Repeated table headers ("درجات الحرية", "نوع العملية") and footnote phrases ("المرجع السابق")
   are taken for running heads — and then for the journal's name (right in 53 of 101).
4. **Flag floods on vowelled text and verse.** Documents under 5% vowelled words: 4.5% flagged; 20–50%: 15.8%
   (4 documents); over 50%: **60.3%** (2: a vowelled story, vowelled verse). Azure's confidence drops on vowel marks;
   a two-thirds-amber page tells the reader nothing.
5. **Handwritten pages** (manuscript facsimiles in 0679's appendix, pages 63–70): Azure reads them poorly, letters stay
   uncut, 68–91% of words flagged — right, but word by word it is noise.
6. **Slow saves.** The slowest document (92 pages, 82 min, 54 s a page) spends 4,613 of 7,065 profiled seconds in
   pymupdf's `save(garbage=3)` (pairwise duplicate search over ~10⁵ glyph streams); the letter cutter is 22%.
   Re-saving that PDF: garbage=3 519 s, garbage=1 0.8 s, same size.
7. **One invalid JATS** (1911-002-002-004): a «الهوامش» heading opened an `<fn-group>` that no note followed.
8. **Known gaps, now counted.** "pdfium joins lines" fired on 54 documents / 364 pages: 243 tables (a row's cells
   joined), 108 tightly-leaded prose, 13 lists — lines came out of order on 2 of those pages, so **no document lost
   lines**; the warning is mostly tables. Table rules touching text leave letters uncut (the underline gap: 1681 p46,
   39 of 155 words); sideways tiny-type forms give specks (0886: 48% flagged); a French article has no Arabic
   letters to cut (1140, "40%" of 5 words).

No crash, timeout, lost page image, reversed line, trust-PDF mismatch, or memory alarm in 205 documents.

## Proposed fixes (`patches/`, each tested here; not applied — the lead commits)

| patch | what it changes | tested |
|---|---|---|
| `native_leftover_text.patch` | on a page rebuilt from the scan, every non-Dummy font leaves the text (still drawn) | 0322-000-049-010 rebuilt: inversions 78 → 0, words intact and lines unchanged, 45/45 pages pixel-identical |
| `structure_title_fallback.patch` | when the layout rule finds no title, read page 1's lines top to bottom: lines over the byline, else the largest | all 205: titles matching the catalogue 149 → **171** / 204, catalogue authors 109 → **132** / 214, names right 88% (86%); acts only where nothing was found (22 right, 4 wrong of 30); tuned on the 7 documents traced, so 26's truth set should be rerun before merging |
| `native_save_garbage1.patch` | `save(garbage=1)` instead of 3 for both PDFs | 1548-011-001-031: 16.4 → 9.5 min, both PDFs pixel- and text-identical on 41/41 pages, 0.03–0.08% larger |
| `jats_empty_fn_group.patch` | an fn-group with no fn becomes a `notes-heading` custom-meta | 1911 rerun: valid |

Not patched (each needs a judged sample first): furniture (keep a lone block that is heading-sized, bold, numbered
as a note, inside a table frame or continuing a paragraph; a running head only outside the text frame); vowelled
text (judge flagged vowelled words on the ink and set their threshold from it); handwriting (a page-level
"handwritten" mark instead of word flags).

## What it means

The faithful PDF — the thing this repo exists for — held at 205 documents and 3,254 pages: words, lines, letters and
the trust copy are as good as on the 20, across seven decades. The weak parts are the newer layers, and only scale
showed them: structure rules tuned on 10 documents meet a different page 1 every few documents, and a scan with a
typeset header is a case the 20 did not contain. The Quran correction is cheap and safe at scale but rare in a random
archive (31 proposals in 205 documents, against 194 in the Quran-heavy 20). Next: apply the four patches, rerun
experiment 26's truth set, and give the furniture rule a hand-read truth.

## Method

* **Documents** (`out/azure/`, symlinks; 205): **127** — every scan of experiment 19's random sample of the archive
  (`scan` and `scan+real-font` kinds), **minus the 12 in experiment 24's product set** (experiments 26 and 27 tuned
  the structure rules and corrections on it); **78 fresh** (`catalogue.py` streams the MARC catalogue once,
  1,558,415 records; `draw.py` draws by decade, Arabic, one per journal, journals not in experiment 19; `classify.py`
  keeps scans by experiment 19's rule): before 1960 12, 1960s 12, 1970s 12, 1980s 10, 1990s 10, 2000s 10,
  2010s 8, 2020s 4 (36 drawn, nearly all born-digital). 177 fetched, 51 born-digital dropped. Not used: experiment
  16's books (the feeler's benchmark) and experiment 20's Quran-heavy picks.
* **Title files**: `fetch_titles.py` — 75 of 205 have one, passed as `--frontpage-dir out/gemini`. No page-1 Gemini
  readings. **Catalogue truth**: `catalogue_titles.py` (MARC 245, 100/700); a title or name is right at letters-only
  similarity ≥ 0.6, names in either order, honorifics dropped.
* **Memory first**: the 78-page 0679-000-014-004 alone under `/usr/bin/time -v`: 1.72 GB, 22 min.
* **Build** (`run_set.sh`): `inkscript native --vector --verify --xml --trust`, 3 workers, `nice`, longest first,
  90-minute limit a document, exit status and stderr kept, resumable; `09_pen_path/watchdog.sh` running.
* **Fix** (`run_fix.sh`): `inkscript fix --apply` on all 205, cap $5 (cumulative spend log), cache.
* **Numbers**: `summarize.py` (per document and page, letter coverage per page as `coverage.py`), `hunt.py`
  (rankings, joins-lines pages by kind), `leftover.py`, `furniture.py`, `lone_sheet.py`, `inversions.py`, `look.py`;
  front matter on all 205 without the build: `frontmatter.py` (+ `front_fix.py`, `front_trace.py`); timing:
  cProfile of 2025-067-002-007, `save_cost.py`. `showcase.py` → `out/showcase.html` (failures from `out/failures.json`).

## Files

Scripts above; outputs (gitignored) in `out/`: `set/w0..w2/` (every document's PDFs, trust PDFs, JATS, ALTO,
corrections), `set/summary.json`, `set/pages.json`, `hunt.json`, `leftover.json`, `furniture.json`,
`front_*.json`, `profile/`, `patchtest/`, `savetest/`, `spend.jsonl`, `judge_cache.jsonl`, `fix_set.log`, `look/`,
`showcase.html`. Patches in `patches/`.

## Progress log

* 2026-10-06 23:57 — set started (205 documents, 3,254 pages, 3 workers, watchdog up).
* 2026-10-07 02:50 — 19 documents built; front matter studied on all 205 without the build.
* 2026-10-07 07:37 — set done (205/205, exit 0 every one); 07:42 `fix` done ($0.125); analysis and showcase.

## Applied (2026-10-07)

All four patches are in `src/`. The title fallback was re-scored before merging: experiment 26's hand-read truth
title 9 → 10 of 10 (authors, footnote links unchanged; headings P 0.87 → 0.89, R 0.96 → 0.93), held-out set
unchanged; one guard added (a page that opens with body text has no title from the fallback — a synthetic test
had its chapter heading taken as the title); on all 205 documents titles matching the catalogue 171 / 204 and
catalogue authors 132 / 214 with the guard, as without it.


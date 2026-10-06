# 24 · The product: JATS + ALTO, trust marks and the trust PDF, built into `src/`

**Question.** Experiments 20 and 22 proved a Quran check, a per-word trust flag, a document-as-data file (TEI)
and a highlighted `_trust.pdf`. Can they become the product (`inkscript native --xml --trust`), in the XML
formats publishers and libraries use, and does a real set come out right end to end?

**Answer (2026-10-06).** Yes. 20 scanned documents (321 pages, 1960–2018) built with
`--vector --verify --xml --trust`: every JATS and ALTO file validates against the official schemas (20/20 each),
every trust PDF reads in pdfium exactly as its faithful PDF (20/20: the original bytes first, the same text and
character boxes on every page), and the faithful PDFs' own numbers are as before.

| | set of 20 |
|---|---|
| words intact (pdfium 5.12.1) | **83,842 / 83,853 (99.99%)** |
| lines in order | **7,568 / 7,574 (99.92%)**, 4 order inversions |
| words with every letter selectable (`coverage.py`) | **97.3%** |
| words flagged to check | **7.9%** (6,677 of 84,072): confidence 6,414, speck 291, Quran 244, Persian 46, Latin 32, ornament 27; pre-2000 prints 11.4%, from 2000 on 4.8% |
| words verified (equal to a Quran verse) | 4,946 |
| Quran quotations | **387** found, all linked to a verse; **235 equal** to the verse, **152 differ** |
| JATS 1.4 / ALTO 4.4 valid | **20/20 / 20/20** |
| trust PDFs identical in pdfium | **20/20** (both `_trust.pdf` and `_vector_trust.pdf`) |
| ALTO words linked to a glyph of the PDF | 87,795 of 88,407 Azure words (99.3%) |
| front matter found by the position rules | title 14/20, author 8/20, printed page range 18/20 |
| peak memory / time | 1.35 GB (the 53-page document, 14.5 min); the other 19 on 3 workers in 25 min |

The showcase for the owner is `out/showcase.html` (four documents: the page with its marks, the JATS as an
outline, the XML for one word; the per-document table).

## What was built (in `src/`, see docs/pipeline.md)

`src/inkscript/enrich/`: `document.py` (Azure's reading, word ids, roles), `quran.py` (experiment 20's matcher;
the Tanzil text ships in `src/inkscript/data/quran/`), `trust.py` (experiment 22's default rule), `jats.py`,
`alto.py`, `trustpdf.py`, `schemas.py`; CLI flags `--xml` and `--trust`; `tests/test_enrich.py`. The design and
why JATS + ALTO rather than TEI: docs/decisions.md D20. The trust copy's rules: docs/pdf-writing-rules.md.

One change outside `enrich/`: the build's `shapes.json` placements now carry their Azure word's span offset
(`off`), so a glyph is tied to its word exactly (the TEI prototype matched them by box overlap); `--xml` adds the
ALTO word id (`word`).

## Method

* **Documents** (`out/azure/`, symlinks): 12 scanned documents with catalogue years from experiment 19's random
  sample (`19_azure_map/out/docs`; 1960, 1961, 1974, 1978, 1981, 1983, 1996, 1998, 2001, 2008, 2018, 2018), each
  with Quran quotations, and 8 Quran-heavy scanned books from experiment 16 (`16_feel/out/books/raw`, years
  unknown). No Gemini page 1 (no frontpage dir): page 1 stays Azure's.
* **Memory first**: the longest document (1232-007-008-003, 53 pages) alone under `/usr/bin/time -v`: peak 1.35 GB.
  Then `run_set.sh` (3 workers, `--resume`, `/usr/bin/time` per document) with `09_pen_path/watchdog.sh` running;
  the watchdog never fired (available memory about 10 GB whenever checked).
* **Robustness before the set**: `enrich` alone (`--xml`, no build) over all 400 Azure readings on disk
  (16_feel books + 19_azure_map docs): no crash; 398 valid at once, the 2 others had footnote markers pointing at
  notes that had become references, fixed (a marker whose note is not a footnote stays text).
* **After the set**, the front-matter rules were tightened (no basmala, "Abstract" or section heading as author,
  a "بقلم :" byline takes the next line, a masthead naming مجلة/العدد/السنة with a number is a running head) and
  the XML and trust PDFs rewritten with `reenrich.py` (faithful PDFs untouched; numbers above are after it).
* `summarize.py` → `out/set/summary.json`; `showcase.py STEM…` → `out/showcase.html`.

## What it means, and limits

* The marks and the article structure now travel with every document, in two standard files, without touching
  the faithful PDF.
* **152 of 387 quotations differ from the verse** — mostly vowelled or Uthmani text, Azure's weak spot (experiment
  20: 20 of 24 such words were misreadings). Those words are flagged; nothing is corrected (D14).
* **Structure is guessed**: title found 14/20, author 8/20 (a two-line title, a byline glued to the name, a rubric
  that is really the masthead remain); sections are few (11 in 20 documents) because large short paragraphs are
  rare in these prints; footnotes 493, markers linked 149. A layout model (Azure `prebuilt-layout`) or the
  catalogue (MARC: title, author, year) would do better than position rules; ideas.md.
* `0652-000-001-004` (1981) has 22.7% of its words flagged: a poor scan where Azure is unsure, as experiment 22
  predicts for old prints.
* Gemini's page 1 is untested on the set (the fixture covers it: 2 flagged, 172 verified).
* The trust PDF was not re-checked in a real Chromium here; experiment 22 did that for the fixture (letters still
  select, notes pop up).

## Files

`run_set.sh AZURE OUT W [FIRST]` · `summarize.py [SET]` · `reenrich.py [SET]` · `showcase.py STEM[:PAGE]…` ·
outputs in `out/set/w0..w2/` (per document: `.pdf`, `_vector.pdf`, `_trust.pdf`, `_vector_trust.pdf`,
`.jats.xml`, `.alto.xml`, `.shapes.json`), `out/set/summary.json`, `out/set/memprobe.log`, `out/showcase.html`.

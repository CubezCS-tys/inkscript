# 34 · The yardstick: a hand-checked gold set and a scorer

**Question.** The owner wants our own open-source reading stack (experiment 32) and wants "most accurate" proven,
on public Arabic benchmarks and on Mandumah's own pages. What will every reader (Azure, Gemini, Mistral, open
models, our fine-tunes) be scored on, and how do we get the truth for it with as little of the owner's time as
possible?

**Answer (2026-10-11): 202 pages from 185 documents, drafted and waiting for the owner; a correction mode in
`inkscript view`; `inkscript score`.** Nothing is gold yet: the owner corrects next. Report with the pages and
the screens: `out/report.html` (main checkout).

```
cd /home/yassine/inkscript
.venv/bin/inkscript view --gold experiments/34_yardstick/out/gold      # then http://localhost:8766/ in Chrome
.venv/bin/inkscript score --gold experiments/34_yardstick/out/gold --pred PRED_DIR --name READER --out r.json
```

## Result (2026-10-11)

**The set.**

- 202 pages from 185 documents in 159 journals, 1929–2025.
- 44 pages are from before 1970.
- 8,493 draft lines.
- Held out: 151 test pages; 51 dev pages.

**The draft.**

- Gemini read 8,457 of the 8,493 lines. The other 36 came back blocked; they carry the flag `no-second`.
- Lines where the two readers differ:
  - 1,231 in their letters;
  - 845 in hamza, alef or ى/ي forms only;
  - 150 in vowel marks only, on vowelled pages.
- In all, 2,226 lines (26%) carry a disagreement.
- 827 other lines hold a word Azure gives under 0.6.
- 32 tables were drafted as grids (1,330 cells) and 31 equations as LaTeX.
- 2 table pages got no draft: Pro looped until its output was cut off. The owner draws those grids.

**The owner's time.** About **13.6 h expected (7.8–25 h)**, against the research's guess of 30–40 h. Section 6 explains the model.

**The scorer works end to end.**

- Azure scored against its own draft gives 0 errors, as it must.
- Gemini's line reading against Azure's draft differs by 3.2% of characters as printed and by 1.4% folded. It left 13 lines in 1,000 empty.
- These are disagreement rates, **not** accuracies. The real bar comes after the owner corrects the pages.
- Tests: `tests/test_gold_score.py` (9) and `tests/test_gold_view.py` (7).

## 1. Which pages (the sampling)

**Pool: 273 scanned documents** (`pool.py`, `out/pool.json`).

- 127 of experiment 28's random archive scans (experiment 19's random sample).
- Experiment 28's 78 "fresh" scans were drawn by decade. Their files were no longer on disk, so they were fetched again.
- 74 more were drawn for thin strata (`extra.py`, seed 34):
  - 16 from before 1960 and 8 from the 1960s;
  - 14 issues of the cultural monthlies (المعرفة, الموقف الأدبي, المجلة, الثقافة, الأديب, الآداب);
  - 24 from Economics, Management, Sport, Psychology and Geography, 1975–2009, to find equations;
  - 12 from Islamic studies, Quranic studies, Hadith and Poetry before 2000, for vowels and Quran.
- Of the 152 documents fetched, 146 are scans, 5 are missing on S3 and 1 is born-digital (put aside, experiment 19's rule).

**Newspapers.** Mandumah holds none:

- the catalogue has no such record type;
- no journal title says جريدة;
- every S3 prefix is an article id.

The cultural monthlies stand in for them. They have three or more columns, mixed blocks and pictures.

**Page features** (`features.py`, `out/features.*.jsonl`, one line per page). All come from Azure's reading and the build's own structure rules:

- footnote, heading and furniture lines;
- words in a Quran quotation matched to the verse;
- share of vowelled Arabic words;
- share of Latin words;
- Azure's handwriting style;
- lines that look like a formula;
- lines of numbers standing in columns;
- ruled lines on a 60 dpi render;
- text columns.

**Gemini's look** (`classify.py`): 814 candidate pages were sent, 4 thumbnails a request, gemini-3.8-flash, for $1.09. It answered yes/no on table, equation, footnotes, vowels, verse, mixed Latin, headings, handwriting, decorative lettering, columns and page type. The candidates were:

- the pages each feature guesses, up to a cap per kind;
- every usable page of the old and magazine documents, up to 4 a document;
- one random page of every document.

**Tags** (`select_pages.py`). These are the features confirmed by the look:

- tables, equations and handwriting need Gemini's yes;
- Quran needs 12+ words matched to the verse;
- covers, blank pages and contents pages are left out.

**Quotas** by primary kind. A page's primary kind is the rarest kind it holds; it keeps all its tags.

| kind | body | headings / first pages | footnotes | tables | equations | Quran | vowelled | mixed Latin | magazine | handwriting | decorative |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pages (primary) | 40 | 22 | 24 | 24 | 14 | 16 | 16 | 16 | 16 | 6 | 8 |
| pages holding it | 48 | 46 | 43 | 29 | 14 | 22 | 21 | 39 | 50 | 6 | 12 |

Within a kind, pages are taken in turn across decades: before 1960 first, then the 1960s, then the rest. At most one page comes from a document, two only where a kind ran short.

| decade | before 1960 | 1960s | 1970s | 1980s | 1990s | 2000s | 2010s | 2020s | ? |
|---|---|---|---|---|---|---|---|---|---|
| pages | 23 | 21 | 23 | 35 | 30 | 27 | 25 | 17 | 1 |

Handwriting is short: only 6 pages were confirmed in the pool. That is fine for a rate, but too few to tune on.

**Held out.** The split is by journal (the id's first four digits), so a typeface seen in tuning never appears in the test.

- 151 test pages and 51 dev pages. Journals were placed in dev by a hash of their code until dev held a quarter of the pages.
- `out/heldout.txt` lists the test journals and documents. `select_pages.heldout(stem)` is the guard.
- Nothing may be prompted, tuned or trained on a held-out journal: not the bake-off's prompts, not experiment 33's Kraken lines, not stage 2's training pairs.
- Report test scores; use dev for everything else.

## 2. The draft (pre-fill)

`build_gold.py` → `out/gold/<page_id>.json` + `.jpg` (`src/inkscript/gold/draft.py`). Each page holds:

- Azure's lines in its reading order, with boxes and its words with confidence;
- the blocks, with the build's kinds (title, heading, footnote, furniture…) and a column number each;
- the page as a 300 dpi grey JPEG.

**The second reading** (`second.py lines`): every line's crop, 12 a request, gemini-3.8-flash, blind. It never sees Azure's text. It is asked for the text exactly as printed: vowels, hamza forms, ى/ي and digits as printed, no kashida, no corrections.

**Tables and equations** (`second.py tables`): pages tagged table or equation went whole to gemini-3.1-pro-preview. It returned HTML tables (cells rightmost first, rowspan and colspan) and LaTeX equations, each with its box. Lines inside a table become kind `cell`; lines of a displayed equation become kind `equation`.

**Disagreements** (`second.py mark`). Words are aligned with vowels removed and alef/ya forms folded. Three kinds of difference are marked, in this order of importance:

1. `gemini-differs`: the letters differ.
2. `forms-differ`: only hamza, alef or ى/ي forms differ. This is Azure's commonest real fault on old prints (experiment 19).
3. `vowels-differ`: only the vowel marks differ. This is checked on vowelled pages only.

Each mark is a character span of the draft. `low-conf` marks a line holding a word Azure gives under 0.6.

## 3. The truth format (D26)

`src/inkscript/gold/format.py` holds the full description. The main points:

- **One JSON per page** (`inkscript-gold/1`), beside the page image. All boxes are in that image's pixels.
- **Lines** carry their box and polygon, the gold `text` exactly as printed, a status (`todo`, `ok`, `edited`, `added`, `deleted`, `unsure`), a kind and a language. They keep the drafts they were made from.
- **`order`** gives the reading order of the lines.
- **Blocks** (`regions`) carry their box, type, **column** and **article**, plus their own order. Following the owner's note, this keeps the layout, so a rebuilt print edition can keep its columns.
- **`tables`** are HTML: rows top to bottom, cells in reading order, rowspan and colspan.
- **`equations`** are LaTeX, with optional MathML.
- **`articles`** group blocks into articles on magazine pages.
- Every save keeps the earlier version (`.history/`). An integer `rev` stops two tabs from overwriting each other.

The text rules:

- Vowels, hamza and alef forms, ى/ي and digits stay as printed.
- ﷺ is one character when it is printed as a ligature.
- Tatweel is never typed.
- Persian code points are never used.
- Ink that is not text is marked `deleted`; ink nobody can read is marked `unsure`.

Why JSON and not ALTO? ALTO cannot hold the drafts, the statuses, the tables or the equations, and a JSON file is what the editor saves after every keystroke. `format.to_alto()` writes valid ALTO 4.4 for exchange (tested against the official schema). Tables and equations will go into JATS as XHTML and MathML when the product writes them (research/02_formats.md).

## 4. The correction mode

`inkscript view --gold DIR` (`src/inkscript/viewer/correct.py`, `app/correct.*`, `tests/test_gold_view.py`) works like this:

- **The line.** The scan's line is shown large, with its neighbours faded. The draft sits under it in a big right-to-left field. Yellow marks where the readers differ; blue marks your change; tinted words are ones Azure was unsure of.
- **Accepting.** Enter accepts and moves on. Alt+2 takes the second reading, Alt+1 goes back to Azure's, Alt+N jumps to the next marked line, Ctrl+Del marks a line as not text and Alt+U marks it unsure.
- **Keys and buttons.** Keys are read by their physical place, so they work with the Arabic keyboard on. A palette inserts vowel marks, hamza forms, ﷺ and Arabic digits.
- **Missing lines** are drawn on the page as boxes.
- **Reading order** is shown as numbers on the page. Alt+Shift+↑/↓ moves a line earlier or later.
- **Tables** are an editable grid (add, delete, merge and split cells). **Equations** are LaTeX source.
- **Blocks and articles.** Click blocks to group them into an article (keys 1–9). The column and order of each block can be set.
- **Saving.** Every accept saves the page, checked on the server. Closing the tab also saves.
- **Progress.** The start screen shows pages and lines done and the hours left. The estimate uses the owner's own pace once 30 lines are timed.

Measured in Chromium:

- 8 ms from Enter to the next line on screen;
- 9 ms for a save;
- the layout fits a 1366×657 window.

Screenshots: `out/shots/` (main checkout).

## 5. The scorer

`inkscript score` (`src/inkscript/gold/score.py`, `text.py`, `tests/test_gold_score.py`). The input is one file per page from the reader: `<page_id>.json` (lines with optional boxes, tables, equations) or `<page_id>.txt` (one line per line). It measures:

- **CER and WER** over the page in the reader's order, under two normalisations:
  - *faithful*: everything printed counts except tatweel;
  - *folded*: no vowels, alef/hamza/ى/ة folded, digits to ASCII, no punctuation.
- **Line CER**, independent of order. Reader lines are matched to gold lines by box, or else by text. Dropped and invented lines count in full.
- **Hallucination counts per 1,000 gold lines:**
  - **inserted**: invented lines;
  - **dropped**: skipped lines;
  - **repeated**: duplicates and loops.
- **Reading order**: the share of line pairs kept in the gold's order.
- **TEDS** for tables: Zhang–Shasha tree edit distance, with each cell's text compared by edit distance.
- **Equations**: similarity of the LaTeX tokens, plus exact match. This is not CDM.

Results come per kind, decade, split and line kind. The 95% intervals come from a bootstrap over documents.

Only pages marked done count. `--drafts` scores the drafts as a plumbing check, never as a result.

**Public benchmarks:** `benchmarks.md`, `bench.py` (KITAB-Bench, Misraj-DocOCR: where, licences, metrics, a runner stub).

## 6. Time the owner needs

`dryrun.py`, `estimate.py` → `out/estimate.json`.

**The dry run.** The agent, not the owner, judged 40 random disagreements from the dev pages against the ink (`out/dryrun/`):

| verdict | lines |
|---|---|
| Azure right | 20 |
| Gemini right | 12 |
| neither: typing needed | 4 (10%) |
| not text: one key | 3 |
| unclear | 1 |

What the dry run showed:

- **Most disagreements take one key.** Many are فى/في: old prints write فى, Azure keeps it, and Gemini modernises it. So on `forms-differ` lines the rule is usually "keep Azure".
- **Gemini catches what Azure gets wrong**: dropped hamza-less forms (اصبح, الاهداف), a Persian ی, ((…)) read where the print has «…», and misread words (كانها, نصفى).
- **Neither reader kept a printed shadda** on مجلّة.

**The model.** A keystroke-level model on the real counts, with seconds given as low / expected / high:

| action | seconds |
|---|---|
| agreeing line | 1.2 / 2 / 3.5 |
| decide a disagreement | 4 / 7 / 12 |
| type a fix (on 10% of disagreements) | 8 / 15 / 30 |
| page overhead | 20 / 35 / 60 |
| table cell | 3 / 5 / 10 |
| equation | 30 / 60 / 150 |
| magazine page (blocks and articles) | 20 / 40 / 90 |

**Every line looked at: 13.6 h (7.8–25.0 h).** About 2 h of that is the table grids. Looking only at disagreements and then glancing over each page saves little (12.9 h), because an agreeing line costs only an Enter. So the recommendation is to look at every line.

The correction mode starts from the same priors. After 30 timed lines it switches to the owner's own pace.

## Spend

**$12.40 of the $15 cap.** Every request is in `out/spend.jsonl`.

| task | model | cost |
|---|---|---|
| Gemini's look at 814 pages | gemini-3.8-flash | $1.09 |
| reading the 8,493 lines | gemini-3.8-flash | $6.27 |
| tables and equations on 39 pages | gemini-3.1-pro-preview | $5.05 |

Over half of the tables cost went on 2 pages that failed 6 times, each time with about 30k output tokens. **Lesson:** cap `max_output_tokens` near the size the answer needs, and do not retry a truncated JSON answer. Nothing was spent on the test pages beyond drafting them.

## Files

| file | what |
|---|---|
| `pool.py`, `extra.py` | the pool of scanned documents; the extra draws and their fetch |
| `features.py`, `classify.py`, `select_pages.py` | page features; Gemini's look; the choice, the tags and the held-out split |
| `build_gold.py`, `second.py` | drafts; second reading, tables, equations, disagreements |
| `gem.py` | Gemini calls: cache, spend log, the $15 cap |
| `dryrun.py`, `estimate.py` | the agent's dry run; the time model |
| `make_report.py` | `out/report.html` |
| `benchmarks.md`, `bench.py` | public benchmarks |

Run everything with `PYTHONPATH=<repo>/src` (and `experiments/34_yardstick` for `gem`).

## What it changed

- D26: the gold format.
- `inkscript score` and `view --gold`.
- The held-out rule binds experiment 33 and every later training set.
- The next step is the owner's: correcting the pages. Then Azure's real bar per stratum, then the bake-off (research/03_build.md stage 1).

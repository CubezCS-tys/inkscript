# Experiment 58 — Indra OCR 1.1: a fair local trial, and can it lift weight off Gemini?

**Question (owner, 2026-10-30).** Datalab announced Indra OCR 1.1: a ~1M-parameter OCR model, "44 pages/s on a 32-core
CPU, no GPU", "more accurate than Tesseract / PaddleOCR", 80+ languages, line and block boxes with labels and reading
order. "Give it a test but give it a good shot, don't try to dismiss it straight away." And (owner, same day): "maybe it
can lift some weight off Gemini." What can it do for us, where does it beat our pipeline (Azure words + Gemini 4 Argon
line roles + code rules), and where — if anywhere — does it fit?

**Status.** Done 2026-10-30. $0: no paid call, no hosted API, no Mandumah page left the machine (models downloaded from
GitHub / Hugging Face only; `HF_HUB_OFFLINE=1` while reading pages). Side-by-side page: `out/side/index.html` (8 pages),
`out/side/order_check.html` (6 pages where the reading orders differ most).

**Answer.**
* **Text: not a replacement for Azure on Arabic.** On our 34 hand-checked truth pages Indra gets **10.4% of words wrong
  against Azure's 1.80%** (Argon-fixed 1.55%). On the 14 born-digital pages, whose truth does not come from Azure,
  3.8% against 2.4%; on the 20 owner gold pages 15.6% against 1.4% (that truth was corrected from Azure's draft, which
  flatters Azure, but not by a factor of ten). Old print is where it fails: pre-1960 pages differ from Azure's words by
  19%, 1960s 17%, 2010s 4.4%, 2020s 3.0%. Every setting we tried (resolution 200–400 dpi, scaling, Otsu, CLAHE,
  sharpening, Azure's line boxes as crops) moved it by half a point at most. It writes Persian ی/ک (23 on the truth
  pages, Azure 9), drops hamza on alef (أ → ا, 62 times), keeps only ~75% of printed vowel marks, and reads
  Arabic-Indic digits in tables as Latin letters (٢ → Y, ٨ → A, ٧ → V).
* **On Latin-script pages it is close to Azure**: 834 English / French pages of the 300 articles differ from Azure's
  words by 1.8% (no truth there; Azure itself is ~1–2% wrong). Its English footnotes, headers and reading order on a
  clean page were right (`1136…_p012` on the side page).
* **Layout: good at the easy 85%, weak exactly where Gemini earns its money.** Against Gemini's line roles on 3,404
  pages (146,663 Azure lines of the proof pack's 300 articles): roles agree on **85.2%** of lines; body text recall
  95.7%; running heads / page numbers precision 97.8%, recall 77%; footnotes **precision 98%, recall 41%** (most
  Arabic footnotes become a list or body text); headings 54%; captions 21%; title 75% (as a heading); lists (and
  references) 60–78% (as a list); tables found on 400 of 433 but **cell structure poor** (TEDS structure 0.61, the same
  grid on 77 of 387). Reading order: 97.8% of line pairs in the same order, but the whole page in the same order on only
  68% of pages, and on only **42% of two-column pages** (we looked: on the pages where they differ most, ours is right —
  Indra reads a two-column glossary as one table row by row, and mixes the columns of an Arabic page under a picture).
  For comparison, Argon and Flash agreed with each other on 94.7% of line types and 99.5% of order pairs (exp 41).
* **Speed: true, even here.** 3,404 page images (300 dpi) in 508 s on 8 workers at `nice 19` on the shared server
  (6.7 pages/s; 1.17 CPU-seconds a page; 0.82 GB per worker; 0 errors). A million documents (15.9M pages) is about
  5,200 core-hours: about a week on this 32-core machine, or roughly $100–250 of rented CPU. Gemini's structure step on
  the same pages costs about $149k (v3.5b, Batch, $0.0094 a page).
* **Lifting weight off Gemini: real only on a small share of pages.** Skipping Gemini on every page after page 1
  that Indra calls plain (47% of pages) would save ~42% of the bill (~$63k per million documents now, ~$126k after
  1 December), but on those pages 10% of lines get another role, only 40% of the pages come out identical, footnotes
  are lost on 13% of them, and the skip drops **54% of all Argon's text fixes** and **34% of all note calls**. With
  free checks added (one column, no note marker low on the page, no note-call pattern such as «(١)», no side-by-side
  verse lines) the skip covers **7.4% of pages, saves ~6.6% (~$10k per million documents now, ~$20k after
  1 December)**, and costs 3.6% of lines a different role on those pages (headings and running heads mostly),
  footnotes missed on 3% of them, 5% of all Argon's fixes. Giving Gemini Indra's draft to correct saves at most ~17%
  and is untested.
* **Licence: a blocker to check before any production use.** Code Apache-2.0. Weights: modified OpenRAIL-M —
  commercial use is barred for an entity with more than $20M revenue in the prior year or more than $20M funding, or
  that offers a product competing with Datalab's (Datalab sells document parsing and "knowledge for agents"); the
  licence applies share-alike to the **Output** (s.8) and requires attribution with any Output (s.7); training a model
  on its outputs makes that model a Derivative (s.1(e)). Mandumah needs a reading by its lawyer, and probably a
  commercial licence, before Indra's output enters a master.

**Recommendation.** Do not swap Azure or Gemini for Indra.

*On letting plain body-text pages skip Gemini* (the owner: "if it seems like an option why not"): **not now.** The only
rule that is safe enough — **R2b**: not page 1; every Indra block is body text, a heading or a running head; one column
(Azure's boxes); no two lines side by side; no line in the lower 45% of the page starting with a note marker; no
note-call pattern in Azure's text — covers 7.4% of pages and saves about **$10k per million documents** (about $20k
after Argon's price doubles on 1 December), against ~$149k (~$299k) for the whole Gemini step. On those pages it would
introduce: 3.6% of lines with another role (49 heading lines missed, 54 running-head / page-number lines missed of
6,992), footnotes on 7 of 251 pages, lists on 9, verse on 5, abstracts on 10; 627 of Argon's 12,819 fixes (4.9%)
and 19 of 2,916 note calls lost; reading order identical on every one. To be safe it would also need: (a) a fallback
to Gemini whenever Indra and Azure disagree on more than ~8% of the page's words or Indra's confidence is low;
(b) Argon's text fixes done another way on skipped pages (a text-only call, or accept Azure's ~0.25 point more wrong
words there); (c) page-break joins and running-head removal by code; (d) a Desk sample of skipped pages each run.
The broad rule (47% of pages, ~$63k saved) is not safe: it loses half of Argon's fixes and a third of note calls.
**The licence may decide it anyway**: if Mandumah (or an entity it is affiliated with) has had more than $20M revenue in a year or more
than $20M of funding, it may not use the weights commercially at all without Datalab's paid licence; and the
share-alike clause puts Indra's **output** under the same licence — so roles and order taken from Indra into our
masters would carry Datalab's use restrictions and attribution into a commercial product. A paid licence would have to
cost well under the ~$10–20k a million documents it saves. Cheaper levers that need no new licence are untested here:
Flash instead of Argon on such pages, or a text-only call without the page image (the image is ~38% of input tokens).

*Where Indra could still help*, with its speed as the point and its output never the text of record: (1) a **reader of
born-digital PDF text layers** that keeps Arabic words whole and refuses broken layers (the `legacy/` PDFs need no
OCR: 116 of 137 first pages read from the layer; useful for the ~2% of `legacy/` without a Word file); (2) a **free
triage / routing signal** (two columns, tables, sideways pages, language, blank pages) before paying for a read;
(3) a **free second opinion for the Desk** where it is precise: an Indra footnote or running head that Gemini called
body text (98% precision) is a cheap detector task. Settle the licence first.

## Method

* **Setup** (`progress.md`). `github.com/datalab-to/indra` cloned at HEAD `e203553` (package 1.1.2; tags v1.1.0
  `3d4eb01`, v1.1.2 `0e96b93`), installed in its own venv `out/venv` (Python 3.12.3, onnxruntime 1.31.1,
  opencv-python-headless 5.0, pypdfium2 5.14 — inside the venv only, the repo's pypdfium2 pin is untouched); models
  from `huggingface.co/datalab-to/indra-ocr` (revision `bd02167f`, 98 MB with the optional math models) into
  `out/models`. CPU only. Memory guard `guard.sh` (kills this experiment's processes if less than 8 GB is available;
  never triggered). Every run `nice -n 19`, at most 8 single-thread workers.
* **Its options, tried** (`run58.py`): image input at 300 dpi; PDF rendered at 200 (its default), 300, 400 dpi;
  `mode=ocr` and `auto` (the S3 PDFs carry an invisible OCR layer; Indra rightly refuses it and OCRs, so auto = ocr);
  images scaled ×0.67 / ×1.33 / ×1.5; Otsu binarisation, CLAHE, unsharp mask; and its recogniser alone on Azure's line
  boxes (`crops58.py`, detector and layout taken out). Furniture kept in the output. Math mode left off (no math in the
  truth). Its docs give no language hint: a line classifier sends each line to the right-to-left recogniser.
* **Text** (`score58_text.py`): experiment 41's 34 truth pages (20 owner gold pages, 14 born-digital pages whose truth
  is the publisher's text layer) and exp 41's own measure, imported read-only (`score41.words/bag`: 1 − F1 of the word
  multisets, vowel marks count); also after `inkscript.gold.text.folded`, a reading-order character error, letter
  classes and letter substitutions. Azure's figures reproduce exp 41 exactly (1.80 / 1.36 / 2.36%).
* **Layout** (`score58_layout.py`, `hybrid58.py`, `bylang58.py`): all 3,404 pages of experiment 43's run
  `v33_300b_fix3` (300 unseen articles, the proof pack's run; Gemini 4 Argon answers after the code rules = what the
  masters are built from). Each Azure line gets Indra's label from the block it overlaps most and its rank from the
  Indra line it overlaps most; compared with Gemini's block type and order. Classes Indra has no word for are counted as
  agreeing when Indra's label is a fair stand-in (byline → body or heading, reference → list or body, verse and
  equations → body).
* **Cost** (`cost58.py`): Gemini's tokens per page fitted on the 498 chunks of the same run.
* **Pictures** (`side58.py`, looked at in Chromium).

## Results

### Text, 34 truth pages (words wrong; exp 41's measure)

| reader | all 34 | gold 20 | born-digital 14 | folded, all | order-sensitive CER, folded |
|---|---|---|---|---|---|
| Azure (our text) | **1.80%** | 1.36% | **2.36%** | 1.19% | 1.51% |
| Azure + Argon fixes (exp 41) | **1.55%** | 1.04% | 2.19% | | |
| Indra, 300 dpi image (default settings) | 10.37% | 15.57% | 3.78% | 8.26% | 5.09% |
| Indra, PDF at 400 dpi (best) | 10.08% | 15.28% | 3.48% | 7.95% | 5.10% |
| Indra, PDF at 200 dpi (its default) | 10.54% | 15.95% | 3.69% | 8.48% | 5.19% |
| Indra, ×1.5 + sharpen | 10.06% | 14.91% | 3.92% | 7.84% | 5.01% |
| Indra, Otsu / CLAHE | 10.95% / 10.78% | | | | |
| Indra recogniser on Azure's line boxes | 15.27% | 23.93% | 4.39% | | |

Where Indra wins: the reading-order character error on born-digital pages (2.28% vs Azure 3.21%: Azure's own line order
is worse there), and 4 of the 14 born-digital pages (e.g. `7956…_p001` 2.8% vs 6.3%, `0920…_p002` 1.5% vs 1.8%,
`2502…_p021` 1.9% vs 2.9%). Its errors are mostly wrong letters in a word (dots: ي/ب, ت/ن, ف/ق, خ/ح), then
added or missing words and merged words. Letter classes on the 34 pages: Persian ی 16 and ک 7 written where the truth
has none (Azure 6 and 3); vowel marks 112 read of 150 printed; hamza forms 1,680 of 1,753 (أ → ا 62 times).

By script and decade (3,404 pages, no truth: Indra's words against Azure's, folded): Latin 1.8%, Arabic 10.9%;
pre-1960 19.4%, 1960s 17.0%, 1970s 11.0%, 1980s 8.9%, 1990s 9.0%, 2000s 4.0%, 2010s 4.4%, 2020s 3.0%.

### Layout, 3,404 pages against Gemini's line roles (146,663 lines)

| Gemini's role (lines) | Indra says the same | Indra says instead |
|---|---|---|
| paragraph (81,745) | 96% | list 2% |
| table cells (20,071) | 98% | |
| footnote (6,205) | **41%** | list 25%, text 28% |
| list item (6,102) | 60% | text 35% |
| reference (4,507) | (list 78%) | text 18% |
| heading (4,002) | **51%** | text 35%, list 6%, table 8% |
| running head (3,679) / footer + page no. (3,413) | 71% / 84% | heading 11% / text 8% |
| verse (3,961) | (text 91%) | Indra has no verse |
| title (551) | (heading 75%) | text 21% |
| caption (903) | **21%** | text 45%, heading 18% |
| figure text (4,054) | — | none 54%, table 22% |
| other article on the page (1,517) | — | text 87% (Indra cannot tell) |

Precision where Indra speaks: footnote 98.1%, running head / footer 97.8%, caption 89%, table 85%, body 85%, heading
62%, list 32%. Overall 85.2% of lines agree. Code rules I added to raise footnote recall (smaller
line height in the lower half, lines under an Indra footnote) took recall 41% → 57% but precision 98% → 50%:
dropped.

Reading order (Kendall concordance of the lines): 97.8% of pairs; whole page identical 67.6% (74.5% without running
heads); two-column pages (685): 97.0% of pairs, 41.9% identical; pages below 0.9: 3.8% (two-column 13.9%). Same block
for neighbouring lines: 90.9%. Rotated pages: 5 of 3,404, read upright (Indra's text of a sideways table was better than
Azure's), but their boxes come back in the turned frame (not matched here).

Tables: 433 Gemini tables; Indra marks 400 of them as a table; of 387 compared, TEDS structure 0.61 (median 0.67; 56
at 0.9 or more, 115 under 0.5), with text 0.45; the same rows × columns on 77, the same row count on 107. Inside
tables its Arabic digits are unreliable, so it cannot fill the cells Azure missed (the proof pack's two serious pages).

### Speed and memory (this machine, shared with the live service)

| run | pages | wall | pages/s | CPU s / page | memory |
|---|---|---|---|---|---|
| 300 dpi page images, 8 workers, nice 19 | 3,404 | 508 s | 6.7 | 1.17 (per-step means: detect 0.19, orientation 0.18, recognise 0.68, order 0.02) | 0.82 GB max per worker |
| 34 truth pages, 8 workers | 34 | 9 s | 3.8 | | 0.53 GB |

Datalab's figure (44 pages/s on 32 cores = 0.73 CPU-s a page) is consistent: our pages are larger and denser.

### Can Indra take work off Gemini?

Gemini's work per page today (v3.3, the 300 articles; `cost58.py`): input 3,363 tokens (prompt 801, page image 1,295,
Azure's numbered lines 1,268), output 892 tokens; at Batch prices input is 43% of the bill, output 57%. Of the answer:
plain blocks (line ids by role) 39%, Argon's fixes 19%, tables 13%, footnotes 10%, references 9%, metadata 3%.

Pages skipped by rules on free signals only (`plain58.py`; the 3,404 pages; "lost" = what Gemini's answer has on those
pages that the skip would not):

| rule (each adds to the one above unless noted) | pages | roles differ (lines) | pages identical | Gemini found on those pages | Argon fixes lost (of 12,819) | note calls lost (of 2,916) | Gemini $ saved | saved per 1M docs (now / after 1 Dec) |
|---|---|---|---|---|---|---|---|---|
| R1 Indra-plain (text, heading, running head only), not page 1 | 46.9% | 10.2% | 40% | footnotes 201 pages, verse 161, lists 142, bylines 85, figures 70, captions 59; 649 heading and 653 running-head lines missed; order identical 83% | 6,923 (54%) | 989 (34%) | 42% | $63k / $126k |
| R2b + one column, no side-by-side lines, no note marker low on the page, no note-call pattern | 7.4% | 3.6% | 63% | footnotes 7, lists 9, abstracts 10, verse 5, bylines 6; 49 heading and 54 running-head lines missed; order identical 100% | 627 (4.9%) | 19 (0.7%) | 6.6% | $9.9k / $19.8k |
| R2c = R2b with note-call patterns allowed | 10.3% | 3.5% | 62% | footnotes 13, verse 12, lists 14 | 1,045 (8.2%) | 145 (5.0%) | 9.3% | $13.9k / $27.7k |
| R2 = R2b + no smaller-set lines low on the page | 1.7% | 3.8% | 69% | lists 2, abstracts 3 | 193 (1.5%) | 7 | 1.6% | $2.3k / $4.7k |
| R3 = R2 + not the last page, Indra ≈ Azure (< 8% words apart), no heading | 0.3% | 0.6% | 80% | abstract 1 | 41 | 7 | 0.3% | $0.4k / $0.8k |

Other designs:

| design | Gemini saved | per 1M documents | note |
|---|---|---|---|
| today | — | ~$149k now, ~$299k after 1 Dec | proof pack: 0 words wrong of 1,532, 43/60 pages fully right |
| skip every page Indra calls plain, page 1 included | ~48% | ~$78k left | as R1, plus titles on 214 and bylines on 184 first pages |
| Gemini sees all, answers only where Indra's draft is wrong | ≤17% | ≥$124k left | untested; anchoring risk on Indra's errors |
| Indra as a router (plain pages → Flash, or a call without the image) | not measured | | idea only |

Indra's own cost in every design is negligible (~$100–250 of CPU per million documents). Estimates: 15.9 pages a
document (exp 40); Argon's price doubles from 1 Dec 2026, which doubles the savings in dollars but not the risk.
Datalab's hosted API would be $0.50 / 1,000 pages ("Convert — lite", their pricing page 2026-10-30), ~$8k per million
documents — not used, not to be used: it sends the scans to a third party.

### Surya 2.5 and Chandra 2

**Surya 2.5** (Datalab's 689M-parameter page VLM; `github.com/datalab-to/surya` at `9d5aadf`, package surya-ocr
0.23.0, its GGUF from Hugging Face served by llama.cpp `b12017` CPU build on 127.0.0.1, 8 threads; `out/run_surya.sh`,
`surya58.py`) ran on 6 of the truth pages: **38.9 minutes, 6.5 minutes a page** (prompt 4,100 image tokens at ~35/s,
then ~1,600–2,300 tokens out at 8/s), llama-server 2.4 GB, client 1.8 GB. Words wrong on those 6 pages:

| page | Azure | Indra | Surya |
|---|---|---|---|
| 0197 p3 (gold, 1960s) | 2.8% | 12.0% | 3.0% |
| 0422 p2 (gold, 2000s) | 0.0% | 0.7% | 1.8% |
| 0656 p3 (gold, 1960s) | 6.2% | 38.9% | 16.9% |
| 0920 p2 (born-digital) | 1.8% | 1.5% | 1.3% |
| 1148 p4 (born-digital, tables + formulas) | 1.5% | 3.8% | 21.8% (its formulas come out as LaTeX: a scoring artefact, as in exp 41) |
| 7956 p1 (born-digital) | 6.3% | 2.8% | 7.6% |
| **all 6** | **3.4%** | **11.2%** | **8.7%** |

Surya reads old Arabic print far better than Indra and gives richer structure (equations, tables with row and column
spans, section headers), but on this CPU it is ~2,500 times slower than Indra (a million documents would take about
1.7 million hours of an 8-core machine): it is a GPU model, and its weights are free only under $5M revenue and funding (Datalab's
pricing page). **Chandra 2** (`datalab-to/chandra-ocr-2`, 5.3B parameters; source cloned at `b20d54d`, not run) is
built for vLLM on a GPU; on this shared CPU machine it would need 11–21 GB of memory and many minutes a page, so it was
skipped. Its weights are free only under $2M. Both are the Gemini-class tools in Datalab's line, not Indra's.

### legacy/ PDFs

The 137 local `legacy/` PDFs (exp 53: made from the publishers' Word files by LibreOffice) in Indra's auto mode, first
page (`legacy58.py`): 116 read from the text layer, 14 text layer + OCR of text in pictures, 7 OCR because the font map
is broken; 9.8 pages/s. Its words differ from PyMuPDF's extraction of the same layer by 13% — mostly PyMuPDF cutting
Arabic words apart, which Indra keeps whole; both keep the layer's own stray characters (a «3» inside words such as
«إدم3ان»). So `legacy/` does not need OCR at all: the text is in the Word file (exp 53) or the PDF's layer.

## What it is good at, what it is not

Good: speed on a plain CPU (the claim holds); clean modern print and Latin-script pages (close to Azure); running heads,
page numbers and footnotes when it names them (98% precise); finding tables; turning sideways pages; reading order on
one-column pages; it reads the PDF text layer of born-digital files and refuses an untrustworthy one.

Not: old Arabic print (15–19% of words wrong), dotted letters, hamza and vowel marks, Arabic-Indic digits in tables,
Persian look-alike letters; Arabic footnotes (41% found), headings, captions, verse, references, bylines, titles,
another article on the page; two-column Arabic reading order; table cell structure; anything that needs understanding
(metadata, reference fields, note calls, fixes and misprints).

## Files

`run58.py` (Indra on a page list, one JSON per page, resumable), `units58.py` (page lists), `score58_text.py`,
`crops58.py`, `dump_azure58.py`, `score58_layout.py` (`--rules`, `--tag`), `hybrid58.py`, `bylang58.py`, `cost58.py`,
`side58.py`, `plain58.py`, `surya58.py`, `legacy58.py`, `guard.sh`, `progress.md`. Outputs (gitignored) in `out/`: `indra/<variant>/` (every page's lines,
blocks, markdown, timings), `text_scores.json`, `layout_scores.json`, `layout_lines.jsonl`, `hybrid_scores.json`,
`bylang.json`, `plain_scores.json`, `surya_scores.json`, `legacy_scores.json`, `side/`, `time_*.txt`; the Indra source and venv (`indra_src/`, `venv/`, `models/`), Surya's
(`surya_src/`, `venv_surya/`, `llamacpp/`, `hf_cache/`), Chandra's source (`chandra_src/`, not run).

## Honest limits

34 truth pages, 20 of them corrected from Azure's draft (Azure flattered there); no English truth page (the Latin
figure is agreement with Azure). The layout reference is Gemini, not a person — but the proof pack judged its pages
right on 43 of 60, and on the pages where the orders differ most we looked and Gemini was right. Lines are matched by
box overlap, so a few disagreements are matching noise. Savings are estimates from token shares, not runs.

## What it changed

Nothing in the pipeline. Indra stays out of the text and structure of record. If the owner wants it, the cheap next
step is a licence reading; then Indra as a routing signal or Desk detector could be tried on gate 2's pages at no cost.

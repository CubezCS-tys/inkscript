# Public Arabic test sets: how we run them

Checked 2026-10-11. Every dataset id, size and field name below was read
from the Hugging Face API (`/api/datasets/<id>`, `datasets-server/info`, one
sample row), and every metric from the authors' own code or paper.
Nothing was downloaded except two samples for a test.

**Rule: these are test sets. We never train, fine-tune, tune prompts or pick
thresholds on them.** We only run a reader on them and report the score.
If we ever need to tune something, we use our own pages, not these.

The runner is [`bench.py`](bench.py) (standard library only):

```
python bench.py list                                  # the subsets it knows
python bench.py fetch misraj-dococr --out DIR --limit 20
python bench.py run misraj-dococr --gold DIR --pred PRED --reader "myreader {image} {out}"
inkscript score --gold DIR --pred PRED
```

---

## 1. KITAB-Bench (MBZUAI, ACL Findings 2025)

- Paper: https://arxiv.org/abs/2502.14949
- Code: https://github.com/mbzuai-oryx/KITAB-Bench (MIT licence, "Copyright (c) 2025 Ahmed Heakl")
- Data: one Hugging Face dataset per subset, all under the user
  `ahmedheakl`, named `ahmedheakl/arocrbench_<name>`. Each has one config
  `default` and one split `train` (it is still the test set; "train" is only
  the default name). Not gated.

### The subsets

| Our name | HF id | Rows | Gold field | What it is | For us? |
|---|---|---:|---|---|---|
| kitab-hindawi | `ahmedheakl/arocrbench_hindawi` | 200 | `text` (lines split by tabs) | printed e-book pages, 612×792 px | **yes** — closest to our pages |
| kitab-historicalbooks | `…_historicalbooks` | 10 | `answer` (lines split by `\n`) | old book pages | yes (tiny) |
| kitab-patsocr | `…_patsocr` | 500 | `answer` | printed lines, several fonts (PATS-A01) | yes |
| kitab-synthesizear | `…_synthesizear` | 500 | `text` | synthetic printed lines, often fully vowelled | yes |
| kitab-historyar | `…_historyar` | 200 | `text` | lines from old printed books | yes |
| kitab-isippt | `…_isippt` | 500 | `text` | lines from slides | yes |
| kitab-arabicocr | `…_arabicocr` | 50 | `text` | short printed snippets | yes |
| kitab-adab | `…_adab` | 200 | `text` | single printed words | yes (weak signal) |
| kitab-lines | `…_ourslines` | 378 | `data` (JSON list: `line_index`, `bbox{x1,y1,x2,y2}`, `text`, `class`) | full pages with line boxes | **yes** — line finding + reading |
| kitab-tables | `…_tables` | 456 | `code` (an HTML page; we keep its `<table>`) + `metadata`, `data` (JSON), `category` | synthetic rendered tables | **yes** — tables |
| kitab-evarest | `…_evarest` | 800 | `text` | scene-text word crops | no |
| kitab-khatt, kitab-khattparagraph, kitab-onlinekhatt, kitab-muharaf | `…_khatt` (200), `…_khattparagraph` (200, field `answer`), `…_onlinekhatt` (200), `…_muharaf` (200) | | | handwriting | no (out of scope) |

The 13 OCR subsets together have 3,760 rows. Other KITAB parts we do not
use: layout (`…_bcelayout` 1,701, `…_doclaynet` 400), charts (`…_charts`
576), VQA (`…_chartsvqa`, `…_diagramsvqa`, `…_mtvqa`, `…_patdvqa`).

**PDF-to-Markdown is not on Hugging Face from KITAB.** Their script reads
local folders `pdfs/*.pdf` and `labels/*.md` that are not in the repo. Use
the corrected copy from Misraj instead (section 2, `kitab-pdf2md-reviewed`).

Tables: KITAB's table script scores TEDS only on rows whose `metadata`
`_pipeline` contains "HTML"; the other rows are scored as CSV with a
Jaccard index. `bench.py` keeps only the HTML rows.

### Licence

- Code: MIT.
- Data: **no licence is declared** on 21 of the 22 datasets (only
  `arocrbench_khatt` is tagged MIT, which is doubtful, because the original
  KHATT is a research-only registration download). Each subset is copied
  from an older corpus (PATS, KHATT, EvArEST, Hindawi, Muharaf, ISI-PPT…)
  that keeps its own terms.
- What this means for us: running a reader and **publishing the score is
  normal** (the authors and many model papers do it). **Do not** copy the
  images or gold into the repo, do not redistribute them, and do not train
  on them. Keep downloads under the experiment's gitignored `out/`.

### Their metrics (from the code)

Text normalisation, `preprocess_arabic_text` in `ocr-eval/metrics.py`
(same in `lines-eval/metric.py` and `pdfs-eval/metrics.py`):
1. newlines and tabs → space;
2. **diacritics removed**: `[ً-ٰٟ]` (harakat, tanwin,
   shadda, sukun, and superscript alef);
3. alef forms `إ أ ٱ آ` → `ا`;
4. `ة` → `ه`; `ى` → `ي`;
5. tatweel `ـ` removed; whitespace collapsed.

They do **not** fold hamza on waw/ya (`ؤ ئ`), do not change digits, do not
remove punctuation, do not lowercase (except inside METEOR).

- **CER / WER**: `torchmetrics` `CharErrorRate` / `WordErrorRate`, i.e.
  total edits ÷ total reference characters (or words) over the whole
  subset — not a mean of per-sample rates. Can go above 1.
  The headline number is the **plain mean over the 13 subsets** (each
  subset counts the same, whatever its size).
- **chrF, BLEU**: `sacrebleu.corpus_chrf`, `corpus_bleu`; also METEOR and
  mean Levenshtein distance.
- **Lines** (`lines-eval/metric.py`): mAP@0.5 / 0.75 / 0.5:0.95 of line
  boxes (needs a confidence per box); then each gold line is matched to the
  predicted box with highest IoU and CER/WER are computed on those pairs.
- **TEDS** (tables): tree edit distance similarity. Before it they keep
  only `table/tr/th/td/tbody`, flatten `thead/tfoot` into `tbody`, collapse
  whitespace and change Arabic-Indic digits to ASCII.
- **MARS** (PDF→Markdown) = (chrF of the text outside tables + mean TEDS of
  tables) ÷ 2. For each gold table the best-matching predicted table is
  used.

### Entry points (their way)

```
cd ocr-eval;    python3 eval.py --model_name X;  python3 metrics.py --model_name X
cd lines-eval;  python3 eval.py --model_name X;  python3 metric.py  --model_name X
cd tables-eval; python3 eval.py --model_name X;  python3 metrics.py --model_name X
cd pdfs-eval;   python3 eval.py --model_name X;  python3 metrics.py --model_name X
```
`eval.py` writes `results/<model>_<subset>.json` = list of
`{"idx", "gt", "pred"}`; `metrics.py` reads it. OCR prompt:
"Extract the text in the image. Give me the final text, nothing else.",
`MAX_TOKENS = 500` (500 tokens can cut a long page short — keep in mind
when comparing).

---

## 2. Misraj-DocOCR (Baseer paper, arXiv 2509.18174)

- Paper: https://arxiv.org/abs/2509.18174 (Misraj, Sep 2025; paper text CC BY-NC-SA 4.0)
- Data: https://huggingface.co/datasets/Misraj/Misraj-DocOCR

| | Misraj-DocOCR | KITAB PDF→MD, reviewed |
|---|---|---|
| HF id | `Misraj/Misraj-DocOCR` | `Misraj/KITAB_pdf_to_markdown_reviewed` |
| Config / split | `default` / `train` | `default` / `train` |
| Rows | 400 pages (real + synthetic) | 62 pages |
| Fields | `uuid` (36 chars), `markdown`, `image` | `markdown`, `image` |
| Download size | ~209 MB parquet (2 files) | ~69 MB |
| Gold | page Markdown; tables as HTML `<table>` in 58 pages; LaTeX in ~7; harakat in 282 pages | HTML tables in 21 pages; harakat in 28 |
| Licence | **Apache-2.0** | **Apache-2.0** (ask to cite KITAB too) |
| Our name | `misraj-dococr` | `kitab-pdf2md-reviewed` |

Apache-2.0 allows use, publication of scores and commercial use, with
attribution. We still never train on it.

**Metrics** (paper §7): WER, CER, BLEU, chrF, TEDS, MARS (MARS =
(chrF + TEDS) / 2, which matches their numbers: Baseer (87.77 + 66)/2 =
76.885). Before scoring they standardise all outputs: remove HTML tags
outside tables, convert Markdown tables to HTML, unify horizontal rules,
headers and `<b>`/`<strong>`, and drop model-only tags (`<page_number>`,
`<watermark>`).

**Uncertain:** the paper does **not** say how Arabic text is normalised
(diacritics kept or not) or how CER is averaged, and no evaluation code is
published. Some numbers look odd (Baseer WER 0.25 but CER 0.53), so CER is
probably a mean of per-page rates, which long hallucinated pages blow up.
Their numbers are therefore **not directly comparable** with ours; we
re-score every reader ourselves, including Azure and Gemini as reference
points (paper: Azure CER 0.27, Gemini-2.5-Pro 0.31, dots.ocr 0.40).
The paper says the KITAB part has "30 samples"; the reviewed dataset has
62 rows — maybe pages vs documents. Not resolved.

---

## 3. Other sets (short)

| Set | Where | Arabic part | Licence / access | Verdict |
|---|---|---|---|---|
| MORE (Tencent, ICML 2026, arXiv 2607.02956) | HF `zimoqingfeng/MORE` (folders `paragraph`, `table`, `formula`, `code`, `catalog`); code https://github.com/zimoqingfeng/MORE | Arabic script = 11 languages, ~7% of 1,288 pages; at most 10 PDFs per language, so only ~10 Arabic-language pages | Apache-2.0 (data and code). Annotations model-assisted + human-refined. Metric: OmniDocBench v1.5 protocol (text = 1 − normalised edit distance) | Maybe later, as a small cross-check. Authors also make HunyuanOCR. |
| Inria "Reading or Guessing?" (arXiv 2605.27750) | Lines from OpenITI `arabic_print_data` (https://github.com/OpenITI/arabic_print_data): 3,197 line crops, 140 pages, 15 books | printed 19th–20th c. books | The OpenITI repo has **no licence**; Inria releases only ids, alignments and metrics, not images. Research use only | Good for line-level checks of Kraken-style readers; do not redistribute; ask before publishing. |
| KHATT | registration download from KFUPM | handwriting | research-only, registration | **Out of scope** (handwriting). |

---

## 4. How their scores map onto ours

Our scorer (`inkscript score`) has two text normalisations:

- **faithful**: NFC, tatweel removed, whitespace collapsed, vowels kept;
- **folded**: also vowels removed, alef/hamza forms folded, `ى→ي`,
  `ة→ه`, Arabic-Indic digits → ASCII, punctuation removed, Latin lowercased.

| Their number | Our closest number | Difference |
|---|---|---|
| KITAB CER/WER | our **folded** CER/WER | KITAB keeps punctuation and digit forms and does not fold `ؤ ئ`; we remove/fold them, so our folded CER is a little lower. KITAB pools per subset then averages 13 subsets; we report per subset and pooled. To reproduce KITAB exactly, also run their `metrics.py` on our predictions (step 5 below). |
| (none) | our **faithful** CER | nobody publishes a vowel-keeping score; this is the one that matters for Quran quotations and vowelled text (282 of 400 Misraj pages have harakat). |
| KITAB / Misraj TEDS | our TEDS | KITAB strips all tags except `table tr th td tbody`, flattens `thead`, and changes digits to ASCII before TEDS. We should do the same tag clean-up so numbers match. |
| MARS | (chrF + TEDS)/2 | easy to compute from our numbers if we add chrF; we report CER and TEDS separately instead. |
| Misraj CER/WER | our folded and faithful CER | their normalisation is unknown; treat their numbers as rough. |
| equations | our LaTeX token edit distance | neither set scores equations; Misraj gold has LaTeX in a few pages only (not extracted by `bench.py` yet). |

---

## 5. Steps to run one reader

1. `python bench.py list` — pick subsets. Start with `misraj-dococr`,
   `kitab-pdf2md-reviewed`, `kitab-hindawi`, `kitab-lines`, `kitab-tables`.
2. `python bench.py fetch misraj-dococr --out experiments/34_yardstick/out/bench/misraj-dococr`
   (add `--limit 20` for a first try). For each sample it writes the image
   and `<id>.gold.json` (lines, tables, full text). Downloads are untrusted
   data; nothing in them is executed.
3. Run the reader on each image. It writes `<id>.pred.json`
   (`{"lines":[{"text":..}], "tables":[{"html":..}], "equations":[{"latex":..}]}`)
   or `<id>.txt` into a prediction folder. `python bench.py run NAME --gold G
   --pred P --reader "cmd {image} {out}"` does this loop (no shell, resumes).
   Keep the reader's settings fixed; use the same prompt for every set.
4. `inkscript score --gold G --pred P` — faithful and folded CER/WER, TEDS.
5. (Optional, to match KITAB's own numbers) write `results/<model>_<subset>.json`
   as `[{"idx", "gt", "pred"}]` and run their `metrics.py`.
6. Record: reader version, prompt, image size, max tokens, date, and the
   per-subset numbers. Report what a reader *sees* (per-page examples of
   errors), not only the averages.

Memory: fetch is tiny (one row at a time). The reader is the heavy part —
measure it on one page first (`/usr/bin/time -v`).

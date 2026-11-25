# Experiment 100 — OCRia-1 (LlamaIndex's open-weights page reader) on the extraction exam

**Status:** done (2026-11-25, Riyadh). One RTX 5090 for 42 minutes: **$0.65** of the $15 GPU cap; host destroyed
(none of ours left). No paid API. Exam run once, at the setting chosen on dev.

## Question

OCRia-1 (`llamaindex/OCRia-1`, repo commit `dae83aa5`, 2026-11-24) is a 4B vision-language model fine-tuned from
Qwen3.5-4B. It reads one page image and writes the whole page as Markdown: HTML tables, LaTeX formulas, page furniture
in `<page_header>` / `<page_footer>` / `<page_number>`, multi-column text unrolled, **no boxes**. Its card tags only
English and says nothing about Arabic. Yesterday's experiment 99 tested the same company's small tools (LiteParse,
ocria-nano) on the same exam: best reading 8.9% letters wrong. What does the big model do on our Arabic journals?

Pre-registered questions (the brief, 2026-11-24); baselines from `experiments/97_extraction_evals/out/scores/scorecard.md`
and experiment 99:

- **Q1 Reading.** Each settled R1 truth line found in the page output by best fuzzy alignment; letters / words wrong,
  exact and folded (score97's folds), beside Azure raw (0.8%; 0.6% folded, punctuation ignored), t91 (1.3%; 0.7%),
  ocria-nano (8.9%). Lines not found reported apart. Arabic-specific: Arabic-Indic digits kept, tashkeel kept, hamza /
  alif / ya / alif maqsura as printed, word order in mixed Arabic/Latin lines.
- **Q2 Invented and dropped text.** Per page: share of printed text (Azure lines, settled reading where we have one)
  missing from the output; share of the output matching nothing on the page (runs of 20+ letters); pages cut short by
  the token limit; repeated loops. Counts and the worst 10 pages.
- **Q3 Tables** against `out/keys/TAB/final`: found, rows × columns, header rows, cells four ways (exact; folded;
  content wrong split into misplaced / different text; tables with no content-wrong cell). Baseline v1 found 100%,
  cells 98.5% folded; LiteParse best 28.7%.
- **Q4 Structure Markdown can express**, against `out/keys/PAGE/final`: headings (found, invented), paragraph grouping
  (P2 F1), reading order (P3, two columns apart), running heads and page numbers tagged as furniture, list items,
  footnotes and captions if it marks them, reference entries as separate items (P9 boundaries).
- **Q5 Cost and speed** on the rented GPU: output tokens per page (median, p90, max), pages per minute at the
  concurrency used, GPU memory, $ per 1,000 pages; estimates for 2.7–3.5 M pages (gate 3) and 30 M (the archive).

## Licence (read 2026-11-24, `card/LICENSE`, "OCRia-1 MODEL AND CODE LICENSE", modified OpenRAIL-M)

- §1(n): "“Research Purposes” means (i) non-commercial research, teaching and study, including at academic and
  non-profit institutions; (ii) evaluating or benchmarking the Model, by any person or organization, including
  publishing the results; …" — this experiment is (ii).
- Attachment A: no Use "(a) for any purpose if You … generated more than two million US Dollars ($2,000,000) in gross
  revenue in the prior year, except where Your Use is limited to personal use or Research Purposes; (b) … raised more
  than two million US dollars … in total equity or debt funding …; or (c) to provide, or as part of, a Competing
  Service, whatever Your revenue or funding, except for Research Purposes." A Competing Service (§1(o)) is any product
  offering "document parsing, optical character recognition, or extraction of text, tables, charts or fields".
- §8: "Output may not be used to create a Derivative of the Model (for example, by distillation) other than for
  Research Purposes"; §1(e) counts training another model on its outputs as a Derivative.
- So: **evaluation only**. The weights were downloaded only onto the rented host (sha256 checked against the card) and
  destroyed with it; never onto our server. The outputs stay in `out/model/` as evaluation records and must not be
  used to train or tune anything.

## Method

**Model and serving (host, `host100.sh`).** vLLM 0.34.0 (the card asks for 0.30+) in a fresh venv (`uv`), torch 2.14
(CUDA 13.0, so the host's driver must run CUDA 13: `gs100.py` filters `cuda_max_good >= 13.0`), nvcc 13.0 from the
`cuda-toolkit[nvcc]` wheel (the card: vLLM compiles kernels at start-up and needs nvcc). `vllm serve` bound to
127.0.0.1, `--max-model-len 40960` (card: 32768; raised so a full-size page of ~8,000 image tokens still leaves room for
24,576 output tokens; it changes nothing for shorter prompts), `--limit-mm-per-prompt '{"image": 1}'`. No telemetry
(`VLLM_NO_USAGE_STATS=1`, `DO_NOT_TRACK=1`, `HF_HUB_DISABLE_TELEMETRY=1`); the model runs offline once downloaded.

**What it took on the host (2026-11-25, instance 62412337, RTX 5090 32 GB, driver 580.178, CUDA 13.0, 4 CPUs,
$0.935/h).** Three fixes, none touching the model or its settings: (1) `VIRTUAL_ENV=… uv pip install -q` installed
nothing silently; replaced by `uv pip install --python /work/venv/bin/python` (vLLM 0.34.0, torch 2.14.0+cu130,
transformers 5.22.2, in 1 min); (2) flashinfer's JIT link wanted `-lcudart`, which the pip CUDA wheels do not ship as
`libcudart.so`: CUDA_HOME pointed at NVIDIA's apt packages for 13.0 (`cuda-nvcc-13-0`, `cuda-cudart-dev-13-0`);
(3) its sampling kernel then wanted `curand.h`: `VLLM_USE_FLASHINFER_SAMPLER=0` (greedy decoding needs no sampler)
plus `libcurand-dev-13-0`. Weights: 40 s download, sha256 as on the card. Server up 9 minutes after the first try
(21:42 UTC), 27.9 GB of GPU memory held (weights + cache at 0.90 utilisation).

**Requests (`infer100.py`), fixed from the card.** System message = the card's `prompt.txt` unchanged (md5
`089c42ca…`, checked against the host's copy); user message = one page image, no text; temperature 0;
`chat_template_kwargs={"enable_thinking": false}` (the template turns thinking on by default; the card: with it on the
format breaks); `max_tokens` 24,576; concurrency 16. One JSON per page with the raw answer, token counts, finish
reason, seconds; resumable, never overwrites.

**Inputs.** The 214 locked exam pages and 40 dev pages, 300-dpi JPEGs from `43_rehearsal/out/pages`
(~2466 × 3341 = 8.2 MP), symlinked under `out/up/` (162 MB). Dev = experiment 99's 5 dev articles outside the exam
(`DEV_STEMS.json`: 0013-028-004-001, 0097-040-002-003, 0246-016-001-006, 0840-000-015-002, 1001-012-002-003), 8
evenly spaced pages each, first to last (`DEV_PAGES.json`).

**The one setting decided on dev: image size** (written here before any output was seen). Card: render at 300 dpi
and downscale to an image budget of about 4.1 MP ("about 210 DPI for a letter page"); trained on ~1,024 px pages;
larger images work and cost more image tokens. Candidates, each run on all 40 dev pages:

| Tag | Image sent | Image tokens (32 × 32 px each) |
|---|---|---|
| `px41` | downscaled to ≤ 4.1 MP (Lanczos, the card's snippet), ~1,750 × 2,370 | ~4,000 |
| `full` | as scanned, 8.2 MP | ~8,000 |
| `px20` | downscaled to ≤ 2.0 MP, ~1,220 × 1,650 | ~1,950 |

Measure (`dev100.py`, against Azure's lines, as experiment 99 chose its options): letters wrong incl. lines not found
(folded, punctuation ignored). **Rule:** the lowest wins; when another candidate is within 0.3 points, the one with
fewer image tokens wins. Also recorded: missing, invented, cut short, loops, tokens, seconds. Everything else (prompt,
decoding, max_tokens, concurrency) is fixed by the card and not tuned.

**Dev result (2026-11-24 21:55 UTC, `out/dev/dev_summary.json`), written before the exam run:**

| Tag | letters wrong incl. missing | on found lines | Azure text missing | pages looping to the limit | prompt tokens | s / page (median) |
|---|---|---|---|---|---|---|
| `px41` (card) | 17.8% | 1.3% | 16.7% | 8 of 40 | 5,051 | 13.9 |
| `full` | 17.1% | 1.1% | 16.1% | 7 of 40 | 7,056 | 19.5 |
| `px20` | **6.8%** | 1.3% | 5.6% | 3 of 40 | 3,037 | 8.5 |

**Chosen by the rule: `px20`, images downscaled to ≤ 2.0 MP.** The differences come almost wholly from loops: at 4.1 MP
and full size, 7 of the 8 pages of article 0246-016-001-006 run its dotted running head («مجلة … . . . . .») into an
endless row of dots until the 24,576-token limit, and 0840-000-015-002 p3 ends in «-2-2-2-2…»; at 2.0 MP three pages
loop. On the lines it does write, reading is about the same at every size (1.1–1.3% letters wrong against Azure).

**From the answer to the key formats (`convert100.py`).** OCRia-1 gives no boxes, so Azure lines are found in its
text, not on the page. The answer (fence stripped with the card's regex) is cut into blocks by strict Markdown:
blank lines end a paragraph; `#` headings; `*` `-` `+` `\*` and `1.` `1)` list items; `>` quotes; `[^n]:` notes; HTML
tables (rowspan / colspan filled); ``` fences and `$$` maths; `![label: text]` images; the furniture tags. The block
texts (markup stripped) form one page text; each Azure line is located in it by fuzzy alignment on a matching-only
normalisation (diacritics and tatweel off, NFKC, digit sets alike, lower case): rapidfuzz `partial_ratio_alignment`,
then both ends moved to the lowest Levenshtein distance. Found = similarity ≥ 0.65 (4–11 characters: ≥ 0.75, whole
words only; ≤ 3: exact whole-word occurrence); numeric lines also match a 1–3 token window with the same digits and
signs wherever the signs stand; short or repeated lines are anchored on the line placed just before them. A found line
belongs to the block holding most of its span; pieces = blocks in the answer's order. Role mapping: heading →
heading, paragraph → paragraph, list → list-item, quote → quote, table → table, image / mermaid → figure, `$$` →
equation, page_header / page_footer → running-head, page_number → page-number, watermark / code → other,
`[^n]:` → footnote. Tables: the column direction is read from Azure's boxes (each cell matched to its Azure line, x
along the row; where a whole printed row is one Azure line, the order of the cells inside that line's text); a caption
is the paragraph just before or after a table that starts «جدول» / "Table".

**Scoring (`score100.py`).** Experiment 97's own `score97.run_part` → `compare_page` / `compare_tab` / `compare_refs`
(imported, not copied), exactly as key A is scored against key B. R1 truth: experiment 99's `score99.r1_truth`
(imported): 599 three-witness lines of `out/reading/lines.jsonl`, of which **584** have a truth (A = B 180, third
reader 39, all three witnesses agree 365). The difference from the 598 / 599 lines: 7 lines the third reader called
"order only" (stored order of mixed-direction text) and 8 it marked unreadable or unsure have no truth; one sampled line
of the 600 had no witness agreement field (dropped in experiment 97: line spread over two targets). R1 line text = the
truth line's best alignment in the page output, widened to whole words inside one block; a line not found counts as
empty (all its letters wrong) and is listed as omitted. P9 boundaries: list items + paragraphs on the reference pages
(the Markdown has no reference role; list items only reported beside). Q2 as defined above (the share of the output
that matches nothing is a run of ≥ 20 uncovered letters with partial similarity < 80 to the page's Azure text; runs
that do match the page are counted apart as "unmatched but on the page": repeats, alignment misses). Loops: a 50-letter
window repeated ≥ 4 times and ≥ 3 times more often than on the printed page.

## Self-test of the scoring, without the model (2026-11-25)

`selftest100.py` writes fake answers for all 214 exam pages from the final keys (pieces in key order, settled reading
where R1 has one, else Azure's text; key headings as `##`, titles `#`, list items `*`, quotes `>`, furniture tags; the
first table of each TAB-key page as an HTML table from the key's own cells) and scores them with `score100.py`
(`EXP100_MODEL`, `EXP100_SCORES` pointed at `out/selftest/<variant>/`).

| Measure | clean | damaged | mirror (tables written left to right) |
|---|---|---|---|
| R1 letters / words wrong, exact | 0.1% / 0.4% | 2.5% / 3.8% | 0.1% / 0.4% |
| R1 folded, no punctuation, found lines only | 0.0% / 0.0% | 0.2% / 1.3% | 0.0% / 0.0% |
| R1 lines omitted | 1 of 584 | 12 of 584 | 1 |
| Q2 printed text missing | 0.1% | 3.0% | 0.1% |
| Q2 output matching nothing on the page | 0.0% | 2.0% | 0.0% |
| Q2 pages cut short / with loops | 0 / 0 | 5 / 5 | 0 / 0 |
| P1 per line, roles Markdown can name | 97.0% | 94.0% | 96.8% |
| Key text lines in no block | 0.2% | 2.1% | 0.3% |
| P2 grouping F1 | 99.1% | 98.3% | 98.9% |
| P3 order one / two columns | 99.2% / 100% | 99.1% / 95.9% | 99.2% / 100% |
| Headings found / invented | 100% / 0.4% | 88.8% / 0.4% | 100% / 0.4% |
| Running heads / page numbers as furniture | 100% / 100% | 100% / 99.5% | 100% / 100% |
| P7 tables found | 100% | 100% | 100% |
| P7 cells exact / folded | 100% / 100% | 68.8% / 68.8% | 100% / 100% |
| P7 cells misplaced / different text | 0% / 0% | 30.6% / 0.6% | 0% / 0% |
| P9 boundaries (list items + paragraphs) | 96.9% | 96.9% | 96.9% |

Damage and where it showed (`out/selftest/damaged/damage.json`): 40 pages picked to lose their longest paragraph (23
had one): all 23 flagged, 191 of 195 dropped lines counted missing (at a found threshold of 0.5, first tried, only
92%: raised to 0.65 before any model output); invented paragraph on 30 pages: 30 of 30 flagged, 83 letters each; loop
+ token limit on 5 pages: 5 and 5; columns 0 and 1 swapped in every key table: 30.6% of cells misplaced, 0 tables
clean; one digit changed in each table and in 60 R1 lines: different text, R1 found-line letters 0.0 → 0.2%; first
two body pieces swapped on two-column pages: two-column order 100 → 95.9%; headings written as paragraphs on 20
pages: headings found 100 → 88.8%.

What the clean run does not reach 100% on, and why (artefacts of the fake, not of the scorer): P7 shape and header
rows 81.4%, because the key has cells only for each page's first table and the fake writes the other 8 tables as one
cell per line; P9 96.9%, because the fake is built from the PAGE key, whose reference grouping differs from the REFS
key on one page (0345-045-004-023 p11, off by one line throughout) and three lines elsewhere; P1 restricted 97%,
because figure text is written as paragraphs; P1 over all roles 67.6%, because Markdown has no name for 33% of the key's
lines (see below). The scorer itself (alignment) is checked by `dev100.py` on Azure-as-answer: 0.0% letters wrong.

## Roles the output cannot express

title, translated title, byline, affiliation, abstract, keywords, front matter, verse, endnote, reference, caption
(these are written as headings or paragraphs); the prompt gives no footnote syntax (a `[^n]:` note is counted if it
appears); no boxes (layout grounding is a separate package, out of scope); no table numbers, continuation of a table
from the previous page, note calls or reference fields.

## Cost estimate (before renting)

RTX 5090 32 GB, cheapest offer passing the rules on 2026-11-24: $0.94 / h (Alberta, CUDA 13.0). Weights 10.35 GB +
KV cache (only 8 of 32 layers keep one: 32 KB per token) fit with room for 16–32 pages at once.

- Exam pages carry a median 1,830 printed characters (p90 2,900, max 5,400): ~600–1,000 output tokens per text page,
  2,000–4,000 for HTML tables; assume 1,100 per page, and 5% of pages looping to the 24,576 limit.
- Requests: 3 dev candidates × 40 + 214 exam = 334, ~0.37 M tokens + ~17 looping pages × 24,576 = ~0.8 M tokens. At an
  assumed ~1,000 tokens/s aggregate with 16 in flight (single stream ~120–170 tokens/s: the card measures 320–330 on a
  B200 with stock vLLM) and a ~4-minute tail per set for looping pages: ~30 minutes of inference.
- Overhead: boot and link test 10 min, vLLM install 8 min, weights 5 min + checksum, server start-up and kernel
  compilation 10 min, upload 2 min, slack 15 min: ~50 minutes.
- **~1.4 h ≈ $1.4; worst case (half the throughput, a failed start-up) 3 h ≈ $3.** Cap $15; `gs100.py` destroys the
  host at the cap or after 20 idle minutes.

## Files

- `gs100.py` — GPU session (gs96 pattern: experiment 75's `gpu_session.py` with this folder's session, spend log,
  keeper; $15 total cap, 60 GB disk, CUDA 13 driver, idle 20 min).
- `host100.sh` — on the host: `all` (info, vLLM venv, model download + sha256, server on loopback), `dev`, `exam`.
- `infer100.py` — on the host: one request per page, JSON per page, resumable.
- `pictures100.py` — `data` (repo venv) then `draw` (Desk venv): `out/pictures/`.
- `prep100.py` — dev pages (`DEV_PAGES.json`) and `out/up/{dev,exam}` symlinks.
- `convert100.py` — answer → blocks → key formats (Azure line numbers). `score100.py` — Q1–Q5 → `out/scores/`.
  `dev100.py` — dev candidates → `out/dev/dev_summary.json`. `selftest100.py` — fake answers → `out/selftest/`.
- `card/` — the model card files read on 2026-11-24 (README, prompt.txt, LICENSE, configs; no weights).
- `out/` (gitignored): `up/`, `gpu/`, `model/` (raw answers: evaluation records only), `scores/`, `dev/`, `selftest/`,
  `pictures/`.

## Result (exam run once, 2026-11-24 21:58–22:02 UTC; scored with experiment 97's own functions)

| Measure | OCRia-1 | Azure + Gemini baseline v1 | our reader t91 / LiteParse best | Pass mark |
|---|---|---|---|---|
| R1 letters / words wrong, exact (584 lines) | 3.7% / 10.6% | Azure 0.8% / 4.3% | t91 1.3% / 5.5% | ≤ 0.5% / ≤ 2% |
| R1 folded, punctuation ignored | **2.5% / 6.2%** | Azure 0.6% / 2.3% | t91 0.7% / 2.6%; ocria-nano 8.9% / 26.5% | ≤ 0.5% / ≤ 2% |
| R1 same, on the 570 lines it wrote | 1.7% / 5.3% | – | – | – |
| R1 lines not found in the answer | 14 (2.4%) | – | – | – |
| Printed text missing (Q2) | 1.3% (1.0% without the looping page; 0.7% also without 0529's blank page images) | lost 0% | – | ≤ 0.5% |
| Answer text matching nothing on the page | 6.7% (one looping page); 0.5% on the other 213 | none possible | – | – |
| Pages looping / cut by the token limit | 1 / 1 of 214 | – | – | – |
| P1 label per line, all roles | 61.8% | 95.7% | LiteParse ≤ 54.5% | ≥ 97% |
| P1 on roles Markdown can name (7,047 lines) | 88.4% | – | LiteParse ≤ 81.0% | – |
| Key text lines in no block | 2.9% | 0.1% | LiteParse ≥ 5.3% | ≤ 0.5% |
| P2 grouping F1 | 92.0% | 99.6% | LiteParse ≤ 76.4% | ≥ 95% |
| P3 order one column / two columns | 99.0% / 98.3% | 99.1% / 100% | LiteParse 99.8% / 93.4% | ≥ 98% / ≥ 95% |
| Headings found / invented | 92.5% / 28.4% | (P5 not keyed) | LiteParse found 26–44% | ≥ 97% / ≤ 3% |
| Running heads / page numbers tagged as furniture | 82.8% / 79.2% | page numbers merged into the head | – | – |
| P7 tables found (43) | 100% (+2 extra) | 100% | LiteParse ≤ 95.3% | ≥ 98% |
| P7 shape / header rows (of found) | 90.7% / 100% | 100% / 93.0% | LiteParse ≤ 48.7% shape | ≥ 95% |
| P7 cells exact / folded (1,644) | 67.0% / **74.8%** (about 89% without one garbled table) | 90.1% / 98.5% | LiteParse 26.7% / 28.7% | ≥ 99.5% |
| P7 cells wrong: misplaced / different text; tables with no wrong cell | 6.6% / 18.6%; 37.1% of 35 | – | – | – |
| P9 reference boundaries (paragraphs + list items) | 87.4% | 99.2% | LiteParse ≤ 24.2% | ≥ 98% |
| Cost on an RTX 5090 at $0.935/h | $0.31 per 1,000 pages | – | – | – |

Full scorecard: `out/scores/scorecard100.md` / `.json`; every miss `out/scores/misses_<PART>.jsonl`; line readings
`out/scores/r1_lines.jsonl`; per page `out/scores/q2_pages.jsonl`.

**Q1 Reading.** 2.5% letters / 6.2% words wrong (folded, punctuation ignored): four times Azure's error, about 3.5
times our reader's, 3.6 times better than ocria-nano. Even on the lines it wrote, 1.7% / 5.3%. Worst on references
(4.3% letters) and notes (3.2%); best on table cells (1.2%) and front pages (1.3%). 14 truth lines were not found (6 on
reference pages, 3 of them on the looping page). Count difference: the brief's 598 lines are the three-witness lines;
584 have a settled truth (7 lines the third reader called "order only", 8 unreadable or unsure; exp 99 scored the
same 584). Arabic-specific behaviour, over the truth lines it wrote:
- **Digits:** of 221 Arabic-Indic digits printed, 118 came back as printed; 20 of 59 lines switched wholly to
  Western digits (the reference page in the pictures: «(٢٠١٩)» → «(2019)», «ص ٢٦٤-٢٢٣» → «ص 223-264», the range also
  re-ordered). The other way round never happened (0 of 67 lines). Exact 3.7% vs folded 2.9% is mostly this.
- **Tashkeel:** 108 marks printed, 101 written; 43 of the 54 lines with tashkeel kept some; on 12 lines without any it
  added some.
- **Hamza / ya / alif maqsura:** 55 substitutions in about 5,500 such letters; the main one «ى» printed → «ي» written
  (26), then أ ↔ ا (11).
- **Mixed Arabic / Latin lines:** 7 of 18 exactly right; 8 had the right words, 1 of them in the wrong order.

**Q2 Invented and dropped text.** Missing printed text 1.3%; without the one looping page 1.0%, and two of the worst
pages are 0529-004-007-007's page images, which have no body letters (known from exp 97: the picture was made with a
failed font), so the model could not see what Azure read from the PDF. Of the rest, what it drops: second half-lines
of verse (0738-002-003-016 p1: it wrote only the first hemistich of every bayt, 28% missing), small numeric table
cells, figure tick labels. One exam page looped (0246-015-004-008 p40: the dotted running head «مجلة اتحاد الجامعات
العربية … . . . .» repeated to the 24,576-token limit; the whole page is lost); on dev, 3 of 40 at this image size and
7–8 of 40 at 4.1 MP and full size, all on that journal's dotted head or a «-2-2-2…» list. Text matching nothing on
the page, 0.5% of the answer on the other 213 pages, and it is real invention: English descriptions of pictures the
page says nothing about ("YouTube video player interface with educational text overlay", "A concentric circle
diagram illustrating …", against the prompt's own rule), chart titles that are not printed, and a journal's
calligraphic logo "read" as another journal («الجلالة الأردنية للتراث», "Al-Jama'ah al-'Arabiyyah lil-Tarbiyah" for
«المجلة العربية للتربية»). Worst 10 pages: `scorecard100.md`.

**Q3 Tables.** Every keyed table found (plus 2 extra), shape right on 39 of 43, header rows on all; cells 74.8% folded,
67.0% exact. One table (0048-011-042-001 p22, 33 × 8, a two-level header) accounts for 260 of the 414 wrong cells:
the header is written in one column order and the body in another, every row shifted; without it about 89% of cells
are right. Elsewhere: decimal marks added («١٠٥» → «١٠.٥»), multi-line header cells cut, «(IFI) …» order in mixed
cells. 13 of 35 tables have no wrong cell. Captions matched 42% folded (they are written as headings or paragraphs).

**Q4 Structure.** Reading order is good: 99.0% one column, 98.3% two columns (right column first, as printed; the
two-column page in the pictures reads right column, then left). Grouping F1 92.0%: references are paragraphs (1,174
lines) or list items (379), abstracts paragraphs (554), list items mostly paragraphs (list-item right 34%), endnotes
and footnotes paragraphs. Headings: 92.5% of key headings written as `#` headings, but 28.4% of its headings are not
headings (31 captions such as «جدول رقم ٨», 16 bylines, 16 running heads, 14 invented chart titles). Running heads
tagged as furniture 82.8%, page numbers 79.2% (`<page_number>` 74.9%). Reference boundaries 87.4% when each paragraph
or list item counts as one reference.

**What the output cannot express:** title vs heading, translated title, byline, affiliation, abstract, keywords,
front matter, verse, footnote vs endnote (no footnote syntax was used: P6 notes 0%, calls 0%), reference, caption,
table number, continuation of a table, note calls, reference fields, and no boxes at all. 33% of the key's lines carry
such a role.

**Q5 Cost and speed.** Image 2.0 MP = 3,037 prompt tokens. Output tokens per page: median 730, 90th percentile 1,197,
max 24,576 (the looping page). 214 pages in 252 s at 16 at a time = 51 pages per minute, including the looping page's
4-minute tail; GPU memory 30.3 GB held (vLLM reserves 90% of the 32 GB; weights 10.35 GB). At $0.935/h: **$0.31 per
1,000 pages**. Estimate (same setting, same tail, stock vLLM, BF16): 2.7–3.5 M pages (gate 3) ≈ 880–1,140 GPU-hours ≈
$825–1,070; 30 M pages ≈ 9,800 GPU-hours ≈ $9,200. Whole experiment: $0.65 (42 minutes, three set-up fixes included).

**Changes after the exam was seen (scorer only, model output untouched; both disclosed):** (1) the card's
fence-stripping regex stops at the first inner fence, so the three answers holding a ```mermaid block lost everything
after it; replaced by a strip of the outer fence only. Before: R1 2.9% / 6.6% folded, missing 2.1%; after: 2.5% /
6.2%, 1.3%. (2) Uncovered runs for "matching nothing" no longer span two blocks (a found caption next to an invented
footer counted as one invented run). Self-test and dev re-run after both: unchanged, decision unchanged.

**Could not verify:** Azure's lines are the unit, so "missing" also counts lines Azure itself misread (small digit
cells), and a number range the model reversed («223-264») counts as a line not found; image descriptions are not
separated from text; speed with more requests in flight or the optimised stack was not tried.

## The lead's prediction (PREDICTION.md, written before any output) beside the result

| Measure | Predicted | Result |
|---|---|---|
| Letters wrong (folded, no punct.) | 2–4% (60%: 1.5–5%) | 2.5% — inside |
| Words wrong | 6–12% | 6.2% — inside, at the low end |
| Printed lines dropped | 1–3% | 1.3% of printed text (2.4% of truth lines) — inside |
| Invented text / looping pages | < 1% of output; 1–3 of 214 looping | 0.5% without the loop; 1 page — inside |
| Tables found | 90–95% | 100% — better |
| Table shape | 70–80% | 90.7% — better |
| Table cells (folded) | 80–90% | 74.8% (about 89% without one table) — worse overall |
| Order one / two columns | 98%+ / 85–92% | 99.0% / 98.3% — two columns much better |
| Headings found | 85–90%, some invented | 92.5% found, 28.4% invented — found better, invented worse |
| Cost on an RTX 5090 | $0.15–0.40 per 1,000 pages | $0.31 — inside |
| Arabic faults expected | digits to Western, hamzas corrected, table columns mirrored, right column not first | digits: yes (20 of 59 lines); hamza: few (55 in 5,500), «ى» → «ي» the main one; columns: one table garbled, others right; right column first: yes |

By the prediction's own reading ("2–5%: plausible but it needs real Arabic training data and our exam as the
reward"), the result falls in that band.

## Pictures (out/pictures/, looked at)

- `pages_<stem>_pNNN.png`, 6 exam pages (seed 100: 2 body, 1 two-column, 2 table, 1 references): page with lines
  missing from the answer in red; the answer as it reads, block by block, invented words on orange. Seen: body page
  0097-034-000-006 p4 complete and clean; table page 0097-043-002-006 p25: the chart turned into an invented table
  with an invented title, the chart's tick labels missing, the logo footer read as «الجلالة الأردنية للتراث»; the
  two-column page 0840-000-014-006 p12 read right column first, references as a numbered list, «خاتمة» heading read
  «ثلاثة»; the reference page 0246-021-003-004 p32: every Arabic-Indic digit written Western, each reference its
  own paragraph; scanned table page 0368-000-013-009 p17: table right, small decimal cells missing.
- `table_<stem>_pNNN.png`, 4 tables: printed crop, key, Azure + Gemini, OCRia-1, wrong cells coloured.
- `lines_strip_1.png`, `lines_strip_2.png`: 12 lines, truth / Azure / t91 / ocria-nano / OCRia-1.

## What it changed

Nothing in the pipeline. OCRia-1 is the best outside reader we have run on these pages (2.5% letters wrong against
ocria-nano's 8.9%, and the only one that keeps reading order and table structure), but it is four times worse than
Azure on reading, cannot name a third of our roles, loops on one journal's dotted running head, and invents picture
descriptions and logo text. Its licence allows evaluation only, so it cannot be used in production in any case. The
finding that carries over: an open 4B Qwen3.5 model fine-tuned on mostly Latin pages already reads our Arabic at
2.5%, the band in which fine-tuning the Apache-2.0 base (Qwen3.5-4B) on our own pages is plausible (never on these
outputs: the licence forbids training on them).

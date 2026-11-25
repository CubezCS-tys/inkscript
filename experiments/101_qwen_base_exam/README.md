# Experiment 101 — plain Qwen3.5-4B (and -9B) on the extraction exam: what did OCRia-1's fine-tune buy?

**Status:** done (2026-11-25, Riyadh). One RTX 5090 (Alberta, $1.001/h) for 46 minutes: **$0.78** of the $5 cap;
host destroyed (none of ours left). No paid API. Both arms run: the 4B (4 dev runs, exam once) and the 9B (one dev
sanity run, exam once at the 4B's setting).

## Question

Experiment 100 ran OCRia-1 (LlamaIndex's fine-tune of Qwen3.5-4B on about 101,000 mostly non-Arabic pages) on our
exam: 2.5% letters / 6.2% words wrong (folded, punctuation ignored), tables found 100%, cells 74.8% folded, two-column
order 98.3%, one looping page. How much of that is Qwen itself and how much the fine-tune? The same exam, the same
scorer, the plain instruct model `Qwen/Qwen3.5-4B` with our own prompt asking for OCRia-1's output format. Second arm,
if money and time allow: `Qwen/Qwen3.5-9B` ("does the next size up read Arabic better?").

The point of the experiment is one derived table: for each measure, base Qwen → OCRia-1 = what the fine-tune bought.

## Licence (read 2026-11-24 from the HuggingFace listings, `card/`)

- `Qwen/Qwen3.5-4B`, commit `851bf6e8…`: card front matter `license: apache-2.0`,
  `license_link: https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/LICENSE`; `LICENSE` = "Apache License Version 2.0,
  January 2004 … Copyright 2026 Alibaba Cloud" (202 lines, sha256 `bbedc3fd…`). Not gated.
- `Qwen/Qwen3.5-9B`, commit `c2022362…`: the same front matter and a byte-identical `LICENSE`. Not gated.
- Neither card has a use restriction or acceptable-use policy (searched for "restrict", "prohibit", "commercial",
  "acceptable use": none). So no stop was needed.
- Weights are downloaded only on the rented host (each shard's sha256 checked against the listing, `host101.sh`) and
  destroyed with it. Apache-2.0 outputs carry no training restriction, but the exam outputs stay evaluation records
  only (`out/model/`): **the exam must never become training data.**

## What is the same as experiment 100 (copied, not edited there)

Host set-up exactly as experiment 100 ended up with it, its three fixes included: vLLM 0.34.0 installed by
`uv pip install --python /work/venv/bin/python`; CUDA_HOME from NVIDIA's apt packages for 13.0 (`cuda-nvcc-13-0`,
`cuda-cudart-dev-13-0`, `libcurand-dev-13-0`); `VLLM_USE_FLASHINFER_SAMPLER=0`. RTX 5090 32 GB class host with a CUDA
13 driver (`gs101.py` filter), loopback-only server, `--max-model-len 40960`, `--limit-mm-per-prompt '{"image": 1}'`,
0.90 GPU memory, 32 sequences; no telemetry. Temperature 0, `enable_thinking=False` (the chat template, byte-identical
to OCRia-1's, thinks by default), `max_tokens` 24,576, concurrency 16. The same 214 locked exam pages and 40 dev pages
(`DEV_PAGES.json`, copied; `out/up/` symlinks to the same 300-dpi JPEGs, 156 MB). The same converter and scorer
(experiment 97's `score97` functions, experiment 99's R1 truth: 584 lines with a truth).

## What is different

1. **Our prompt, not OCRia-1's** (its `prompt.txt` belongs to its licensed package, and the plain model was never
   trained on it). Two candidates, the system message; the user message is the page image followed by one fixed line,
   `Transcribe this page.` (accepted by the lead 2026-11-25). **OCRia-1 in experiment 100 got the image alone**; a
   plain chat model is not trained to act on a bare image. No
   presence or repetition penalty (the card suggests `presence_penalty` 1.5 for chat; not used: greedy, as in
   experiment 100).

   **P1** (`prompts/P1.txt`, 7 lines, md5 `18938ecf…`):

   ```
   You transcribe one scanned page into Markdown. Answer with the whole page inside one ```markdown fence and nothing else.
   Follow the page's reading order; on an Arabic page with two columns, read the right column first, then the left one.
   Copy the text exactly as printed: do not correct spelling, keep numbers in the digits printed (Arabic-Indic or Western), and write tashkeel only where it is printed.
   Write headings as # lines, lists as Markdown list items, and leave a blank line between paragraphs.
   Write tables as HTML <table>, with colspan and rowspan for merged cells.
   Put the running head in <page_header></page_header>, the running footer in <page_footer></page_footer> and the printed page number in <page_number></page_number>.
   Write only text printed on the page: never describe pictures, charts or logos, and add nothing that is not printed.
   ```

   **P2** (`prompts/P2.txt`, md5 `5cc52ecd…`) = P1 plus one invented example (its sentences are made up for the
   prompt, from none of our documents):

   ````
   Example of the format, for an invented page (not the page you are given):
   ```markdown
   <page_header>مجلة الأمثلة، العدد ٣</page_header>

   # مقدمة

   يتناول هذا المثال طريقة الكتابة كما طُبعت في سنة ١٩٩٠،
   ويبين أن الأرقام تبقى كما هي.

   <page_number>١٢</page_number>
   ```
   ````

2. **Settings decided on the 40 dev pages only.** Four 4B dev runs, prompt × image size:

   | Tag | Prompt | Image sent |
   |---|---|---|
   | `p1_px20` | P1 | ≤ 2.0 MP (Lanczos), ~1,215 × 1,646 |
   | `p1_px41` | P1 | ≤ 4.1 MP, ~1,740 × 2,357 |
   | `p2_px20` | P2 | ≤ 2.0 MP |
   | `p2_px41` | P2 | ≤ 4.1 MP |

   **Rule (pre-registered here, 2026-11-25, before any model output; `dev101.py`):** a candidate with more than 10% of
   the dev pages (more than 4 of 40) cut by the token limit is out. Of the rest, the lowest letters wrong against
   Azure's lines (folded, punctuation ignored, a line not found counts all its letters). Every candidate within 0.3
   points of the lowest is tied; among the tied, the smaller image wins, then the shorter prompt (P1). The chosen
   setting is written into this README before the exam run.

   **The 9B** (if run) takes the 4B's chosen setting with no dev search of its own, plus one 40-page dev run at that
   setting as a sanity check (it is not used to choose anything).

3. **The exam once per model.** Nothing is tuned on it. Scorer changes after seeing exam output only for parsing faults
   (said exactly, self-test re-run), never for settings.

4. **One added measure** (`score101.py`): number pairs as printed (ranges «a-b», «a–b», «a/b» in the truth lines: kept,
   reversed, or other; digits of both sets alike). It is computed for the base models, for OCRia-1 by rescoring
   experiment 100's own outputs (read only), and for Azure and t91 on the same lines.

## Self-test (2026-11-25, without the model; `selftest101.py`, `score101.py`)

Experiment 100's self-test re-run on the copies: fake answers for all 214 exam pages from the final keys (`clean`,
`damaged` with known damage, `mirror` with tables written left to right). **Every one of experiment 100's measures
came out identical** to `100_ocria1_exam/out/selftest/*/scores/scorecard100.json` (0 differences in the 597–679 numbers per
variant, apart from the added measures and a GPU-memory figure the self-test had picked up from experiment 100's real
run):

| Measure | clean | damaged | mirror |
|---|---|---|---|
| R1 letters wrong, exact / folded | 0.15% / 0.09% | 2.46% / 2.44% | 0.14% / 0.08% |
| R1 lines omitted | 1 of 584 | 12 of 584 | 1 |
| Number pairs (new): in truth / kept / reversed | 32 / 32 / 0 | 32 / 29 / 0 | 32 / 32 / 0 |

(The rest of experiment 100's self-test table holds unchanged: see its README.) Two new checks:

- **OCRia-1 rescored with `score101.py`** (experiment 100's `out/model/exam`, read only; `out/scores/ocria1_rescored/`):
  every number identical to experiment 100's `scorecard100.json`; number pairs 30 on found lines, 26 kept, **2
  reversed** (experiment 100 saw «ص ٢٦٤-٢٢٣» → «ص 223-264»). Azure: 32 / 32 / 0; t91: 32 / 30 / 0.
- **Dev rule on fakes** (`selftest101.py devfake`, `out/selftest/devfake/`): Azure's own lines as the answer for the
  40 dev pages: `p1_px20` and `p2_px20` 0.0% letters wrong, `p1_px41` 0.0% but 5 pages finish "length" → out,
  `p2_px41` with a third of each page dropped 31.1% → chosen `p1_px20` (tie broken to the smaller image, then P1), as
  the rule says.
- `infer101.py` against a loopback stub (a blank synthetic image, no scan): request = model `qwen`, temperature 0,
  max_tokens 24,576, `enable_thinking: false`, system message byte-identical to the prompt file, user = image + text;
  a 2466 × 3341 page sent at 1,215 × 1,646 (2.0 MP).

## Cost estimate (before renting)

RTX 5090 32 GB, $0.935/h in experiment 100 (the cheapest offer passing the rules). Fits: 4B weights 9.3 GB (two
shards); 9B 19.3 GB (four shards), leaving ~6–8 GB of the 28.8 GB vLLM takes for cache (8 of 32 layers keep one,
32 KB per token, the same as the 4B: ~190,000 tokens, enough for 16 pages at once; `MAXSEQS=16` is the fallback if the
server will not start). Disk 80 GB.

Experiment 100's measured speeds at 2.0 MP: exam 214 pages in 252 s at 16 in flight, including one looping page's
~4-minute tail; dev sets of 40 pages 2–5 minutes, mostly the tails of looping pages. The plain model may loop more and
write longer, so assume 1.5 × that for the 4B, and 2 × the 4B's time for the 9B (twice the weights to read per token).

| Step | Minutes |
|---|---|
| Boot, link test, upload code + 254 pages (156 MB) | 12 |
| vLLM install (1 min in exp 100), apt CUDA packages, 4B weights 9.3 GB + sha256, server start + kernel compile | 15 |
| 4B: 4 dev runs × 40 pages, ~4–6 min each | 20 |
| scoring the dev runs here while the host waits on nothing else (the 9B weights download meanwhile) | 5 |
| 4B exam, 214 pages | 7 |
| fetch + verify on our server | 3 |
| **4B arm subtotal** | **~62 min ≈ $0.97** |
| swap: stop the 4B server, 9B weights 19.3 GB + sha256 (already fetched during the 4B runs if possible), start + compile | 8 |
| 9B: 1 dev run (sanity) + exam | 8 + 14 = 22 |
| fetch + verify, stop | 4 |
| **with the 9B arm** | **~96 min ≈ $1.50** |
| worst case (half the throughput, one failed start-up, both arms) | ~150 min ≈ $2.35 |

**Gate for the 9B:** after the 4B exam is fetched and verified, run the 9B only if `gs101.py spent` ≤ $1.40 and
`gs101.py budget 60` says 60 more minutes stays under $2.50; otherwise stop the host and say so. `gs101.py` destroys
the host at the $5 cap or after 20 idle minutes.

## PHASE B commands (in order)

```
cd /home/appuser/inkscript/experiments/101_qwen_base_exam
python3 gs101.py offers                           # lead: check the price
python3 gs101.py start RTX_5090                   # lead rents (the cheapest passing offer); writes out/gpu/gpu_session.json
python3 gs101.py upload out/up/dev /work/in/dev
python3 gs101.py upload out/up/exam /work/in/exam
python3 gs101.py run 'ARM=4B bash host101.sh all' && python3 gs101.py follow '[h]ost101.sh'
python3 gs101.py run '(ARM=9B bash host101.sh model > out/model9b.log 2>&1 &); ARM=4B bash host101.sh devall' && python3 gs101.py follow '[h]ost101.sh'
# fetch out/4B/dev_* -> out/model/4B/, dev101.py, write the choice HERE, then:
python3 gs101.py run 'ARM=4B PROMPT=<P> PIXELS=<N> bash host101.sh exam' && python3 gs101.py follow '[h]ost101.sh'
# fetch out/4B/exam; 9B gate; then:
python3 gs101.py run 'ARM=9B bash host101.sh swap && ARM=9B PROMPT=<P> PIXELS=<N> TAG=<tag> bash host101.sh dev && ARM=9B PROMPT=<P> PIXELS=<N> bash host101.sh exam'
python3 gs101.py follow '[h]ost101.sh'
# fetch out/9B; verify 214 + 40 on our server; python3 gs101.py stop 'exp 101: outputs verified'
```

## Dev result and the chosen setting

Four 4B dev runs, 2026-11-24 22:49–22:56 UTC (`out/dev/4B/dev_summary.json`), written here before the exam run:

| Tag | letters wrong incl. missing | on found lines | Azure text missing | answer matching nothing | pages cut by the limit | prompt tokens | s / page (median) |
|---|---|---|---|---|---|---|---|
| `p1_px20` | 7.4% | 3.8% | 3.7% | 2.0% | 0 of 40 | 2,174 | 7.5 |
| `p1_px41` | 4.0% | 2.1% | 1.9% | 26.9% | 1 of 40 | 4,188 | 11.2 |
| `p2_px20` | 6.1% | 3.5% | 2.7% | 24.0% | 1 of 40 | 2,264 | 7.7 |
| `p2_px41` | **3.9%** | 2.2% | 1.7% | 0.8% | 0 of 40 | 4,278 | 10.9 |

None is out for loops (the limit is more than 4 of 40). The lowest is `p2_px41` at 3.87%; `p1_px41` at 3.96% is within
0.3 points, so the two are tied, and among the tied the rule takes the shorter prompt at the same image size.
**Chosen by the rule: `p1_px41` — prompt P1, images downscaled to ≤ 4.1 MP.** (The large "matching nothing" shares of
`p1_px41` and `p2_px20` are each one looping page; the rule counts only pages cut by the limit, and one page is under
the 10% bar.) Unlike OCRia-1, which needed the smaller image to avoid loops, the plain model reads clearly better
with the larger image (4.0% against 7.4% for P1). The 9B uses `p1_px41` too, without a dev search of its own.

**9B dev sanity run** (`p1_px41`, `out/dev/9B/dev_summary.json`; not used to choose anything): letters wrong incl.
missing 19.1%, on found lines 2.0%, Azure text missing 17.5%, **6 of 40 pages looping to the token limit** (the 4B
rule would have put this setting out for the 9B). Run as pre-registered all the same.

## What happened on the host (2026-11-24 22:40–23:27 UTC, instance 62422017)

Experiment 100's set-up worked first time: venv + CUDA apt packages 2 minutes, 4B weights 40 s (both shard sha256 OK),
server up at 22:48 (27.9 GB held). The 9B weights were fetched during the 4B dev runs (4 shards, sha256 OK); the swap
(stop the 4B server, start the 9B) took 2.3 minutes and the 9B fitted at 0.90 memory with 32 sequences (27.7 GB). Upload
of the 254 pages: 60 s. Exam: 4B 214 pages in 457 s, 9B in 736 s, 0 errors each; all outputs (4 × 40 + 214 for the
4B, 40 + 214 for the 9B) counted on this server before the host was destroyed.

## Result (exam run once per model; scored with experiment 97's own functions)

`out/scores/compare101.md` (from `compare101.py`). Azure and t91 are counted through the same scorer on the same 584
truth lines (so they differ slightly from experiment 97's quoted 0.8% / 0.6%); Azure + Gemini v1 = experiment 97's
baseline. OCRia-1 = experiment 100's outputs rescored by `score101.py` (identical to its scorecard).

| Measure | Qwen3.5-4B plain | Qwen3.5-9B plain | OCRia-1 | Azure / t91 (same lines) | Azure + Gemini v1 |
|---|---|---|---|---|---|
| R1 letters / words wrong, exact | 8.6% / 17.8% | 8.5% / 16.1% | 3.7% / 10.6% | 0.8% / 3.8%; 1.2% / 5.0% | – |
| R1 letters / words wrong, folded, punct. ignored | **7.2% / 13.0%** | **7.5% / 11.6%** | 2.5% / 6.2% | 0.5% / 2.0%; 0.7% / 2.3% | – |
| R1 same, found lines only | 3.0% / 8.6% | 2.5% / 6.3% | 1.7% / 5.3% | – | – |
| R1 lines not found (of 584) | 32 | 49 | 14 | – | – |
| Arabic-Indic digits kept as printed | 31.9% (37 lines all Western) | 78.1% (12) | 53.4% (20) | 99.2%; 99.2% | – |
| «ى» printed → «ي»; all hamza/alif/ya swaps | 34; 81 | 22; 54 | 26; 56 | 0; 21 / 2; 13 | – |
| tashkeel marks written (108 printed) | 62 | 51 | 101 | 103; 99 | – |
| number pairs reversed / kept | 2 / 25 of 31 | 2 / 28 of 31 | 2 / 26 of 30 | 0 / 32; 0 / 30 | – |
| printed text missing | 5.0% | 6.0% | 1.3% | – | 0% |
| output matching nothing (all; pages without loops) | 41.0%; 1.6% | 44.1%; 2.0% | 6.7%; 0.5% | – | – |
| pages looping to the limit | **11 of 214** | **12 of 214** | 1 | – | – |
| P7 tables found | 0% (88.4% read leniently) | 20.9% (88.4%) | 100% | – | 100% |
| P7 shape / header rows (of found) | – (57.9% / 71.0%) | 100% / 100% (63.2% / 65.8%) | 90.7% / 100% | – | 100% / 93.0% |
| P7 cells exact / folded | – (43.8% / 46.2%) | 95.7% / 96.2% on 9 tables (53.5% / 70.9%) | 67.0% / 74.8% | – | 90.1% / 98.5% |
| P7 cells misplaced / different text | – (35.7% / 18.1%) | 2.2% / 1.6% (20.2% / 8.9%) | 6.6% / 18.6% | – | – |
| P1 label per line (all; roles Markdown can name) | 32.0%; 45.8% (52.1%; 74.5%) | 24.1%; 34.4% (49.6%; 71.0%) | 61.8%; 88.4% | – | 95.7% |
| key text lines in no block | 6.9% | 9.3% | 2.9% | – | 0.1% |
| P2 grouping F1 | 83.7% | 67.2% (85.6%) | 92.0% | – | 99.6% |
| P3 order one / two columns | 99.7% / 94.4% | 99.9% / 98.7% (99.5% / 94.7%) | 99.0% / 98.3% | – | 99.1% / 100% |
| headings found / invented | 39.6% / 23.5% | 27.6% / 21.0% (59.0% / 18.6%) | 92.5% / 28.4% | – | – |
| running heads / page numbers tagged as furniture | 3.0% / 3.8% | 14.2% / 21.3% | 82.8% / 79.2% | – | – |
| P9 reference boundaries | 68.5% | 46.4% (82.6%) | 87.4% | – | 99.2% |
| output tokens per page, median / p90 | 689 / 1,160 | 744 / 1,501 | 730 / 1,197 | – | – |
| image sent; prompt tokens | 4.1 MP; 4,188 | 4.1 MP; 4,188 | 2.0 MP; 3,037 | – | – |
| pages per minute (16 in flight, loop tails included) | 28.1 | 17.4 | 51.0 | – | – |
| $ per 1,000 pages (RTX 5090) | $0.59 | $0.96 | $0.31 | – | – |

In brackets: **read leniently** (`EXP101_LENIENT=1`, `out/scores/<arm>_lenient/`), a diagnostic added after the exam
output was seen (see "Changes after the exam was seen"): the plain models break the output contract, and this reading
separates what they read from whether they kept the format. Reading measures (R1) do not change.

### What the fine-tune bought: plain Qwen3.5-4B → OCRia-1 (the point of the experiment)

Same base weights; OCRia-1 used its own trained prompt at 2.0 MP, the plain model our P1 at 4.1 MP (each its best
setting on dev: at 2.0 MP the plain 4B read 7.4% wrong on dev against 4.0% at 4.1 MP). Values after a slash: read
leniently.

| Measure | plain 4B | OCRia-1 | change | fine-tune better? |
|---|---|---|---|---|
| R1 letters wrong, folded, punct. ignored | 7.2% | 2.5% | −4.8 points | yes (÷ 2.9) |
| R1 words wrong, folded, punct. ignored | 13.0% | 6.2% | −6.7 points | yes |
| R1 letters wrong, found lines only | 3.0% | 1.7% | −1.4 points | yes |
| R1 lines not found | 32 | 14 | −18 | yes |
| Arabic-Indic digits kept | 31.9% | 53.4% | +21.5 points | yes |
| lines switched wholly to Western digits | 37 | 20 | −17 | yes |
| hamza / alif / ya swaps (of ~5,400 letters) | 81 | 56 | −25 | yes |
| «ى» → «ي» | 34 | 26 | −8 | yes |
| tashkeel marks written (108 printed) | 62 | 101 | +39 | yes |
| number pairs reversed | 2 | 2 | 0 | no change |
| printed text missing | 5.0% | 1.3% | −3.7 points | yes |
| pages looping to the token limit | 11 | 1 | −10 | yes |
| output matching nothing, pages without loops | 1.6% | 0.5% | −1.1 points | yes |
| tables found (contract) | 0% / 88.4% | 100% | +100 / +11.6 points | yes |
| table shape | – / 57.9% | 90.7% | +32.8 points | yes |
| table cells folded | – / 46.2% | 74.8% | +28.6 points | yes |
| table cells misplaced | – / 35.7% | 6.6% | −29.1 points | yes |
| P1, roles Markdown can name | 45.8% / 74.5% | 88.4% | +42.6 / +13.9 points | yes |
| P2 grouping F1 | 83.7% | 92.0% | +8.3 points | yes |
| order, one / two columns | 99.7% / 94.4% | 99.0% / 98.3% | −0.7 / +3.9 points | two columns: yes |
| headings found / invented | 39.6% / 23.5% | 92.5% / 28.4% | +53.0 / +4.8 points | found: yes; invented: no |
| running heads / page numbers tagged | 3.0% / 3.8% | 82.8% / 79.2% | +80 / +75 points | yes |
| P9 reference boundaries | 68.5% | 87.4% | +19.0 points | yes |
| $ per 1,000 pages | $0.59 | $0.31 | −$0.29 | yes (mostly the smaller image and fewer loops) |

**Tables.** The plain 4B writes Markdown pipe tables, which cannot merge cells: on tables with two-level headers or
merged row labels every cell below slides a row (35.7% of cells misplaced, read leniently). Much of the fine-tune's
table gain is the HTML format itself.

**Reading.** On the lines the plain model writes, it reads 3.0% letters wrong against the fine-tune's 1.7%: the fine-
tune cut in-line errors by about 40%. Over all lines (7.2% → 2.5%) most of the gain comes from loops and dropped
text: the plain 4B loops on 11 pages (rows of empty table cells «| | |», «١، ١، ١،», «٠٠٠٠», a phrase repeated) and drops
32 truth lines. The fine-tune also bought the format (HTML tables, furniture tags, `#` headings, one block per
reference), which the plain model does not follow from a prompt alone. Reading order is about the same; the plain 4B
is weaker on two-column pages (94.4%), dropping whole runs of a column (the picture of 0840-000-014-006 p12: half the
page missing, no loop).

**The 9B.** Not better at reading: 7.5% letters wrong over all lines (2.5% on found lines against the 4B's 3.0%),
more lines dropped (49), 12 looping pages, and it broke the format more: 79 of 214 pages came back as a whole HTML
page in a ```html fence, which the contract reading takes as one code block (grouping 67%, headings 28%). Where it did
write HTML tables (9 of 43) they were nearly perfect (96% of cells); read leniently, 70.9% of cells. It keeps
Arabic-Indic digits far better (78% against 32%) and swaps «ى»/«ي» less. It costs 1.6 times the 4B per page.

**Arabic faults of the plain model** (4B, found lines): words replaced by likely words (the language model guessing:
«وحدات» → «محتوى», «انماء» → «اقامة», «المناخية» → «المناعية»); spelling corrected to the standard form («البينات» →
«البيانات», «فى» → «في», «المنحى» → «المنحي»); look-alike letters («ضمانات» → «ضهانات»); Arabic-Indic digits turned
Western (37 of 56 lines wholly) and digits scrambled in running heads («(٣٤،ع٤ … ٥٧٣-٦٥٠)» → «(٤٣٤٤ ع، … ٢٥٠-٥٧٣)»);
«ى» written «ي» (34); tashkeel dropped (62 of 108 marks written); page ranges reversed («ص ٢٦٤-٢٢٣» → «٢٢٣-٢٦٤», as
OCRia-1). By page kind: tables 9.8% and references 9.0% worst; notes 4.3% best.

**Q5 cost and speed.** 4B at 4.1 MP: 28 pages per minute at 16 in flight (11 loop tails included), $0.59 per 1,000
pages; 9B 17 pages per minute, $0.96. GPU memory held 28.4–29.1 GB (vLLM reserves 90%). Whole experiment $0.78.

**Changes after the exam was seen (scorer only, model output untouched; disclosed):** the main scorecard is unchanged
and keeps the output contract. One diagnostic reading was added, off by default (`convert101.py`, `EXP101_LENIENT=1`):
(a) Markdown pipe tables (`| a | b |` over `|---|`) are read as tables — the 4B wrote tables so on 53 pages and never
HTML; (b) a whole-page HTML answer (```html fence or `<html>`, the 9B on 79 pages) is turned into Markdown blocks
(`<h1>`–`<h6>`, `<p>`, `<li>`, `<table>` kept). The clean self-test gives identical numbers with it off and on. Not a
parsing fault in the sense of experiment 100's fence fix (the answers break the contract), so it is reported only in
brackets and never replaces a contract number. No setting was changed.

**Could not verify:** the derived table mixes two changes, the fine-tune and the prompt (theirs, trained on, vs ours;
image only vs image + one line), and the image size (each arm at its own dev-best); a plain-model run with OCRia-1's
prompt was not made (that prompt belongs to their licensed package). Azure's lines are the unit, so "missing" also
counts lines Azure misread. Presence / repetition penalty (the card's suggestion for chat) was not tried: it might
cut the plain model's loops, but it is a setting that would have to be chosen on dev, not on the exam.

## What it changed

Nothing in the pipeline. The fine-tune is worth a lot: from 7.2% to 2.5% letters wrong on our Arabic, from no usable
tables or page furniture to good ones, ten fewer looping pages, all from about 101,000 mostly non-Arabic pages. The
plain model's in-line reading (3.0% on the lines it writes) is the floor such a fine-tune starts from, and the next
size up (9B) does not read Arabic better and follows the format worse. Fine-tuning the Apache-2.0 base (4B) on our own
pages, with our output format and Arabic rules (digits as printed, no spelling correction, «ى» kept), is the plausible
path; the exam must stay out of that training data.

## Pictures (out/pictures/, looked at)

Same seeded picks as experiment 100 (seed 100). The plain models' tables are drawn as read leniently, labelled.

- `lines_strip_1.png`, `lines_strip_2.png`: 12 lines, truth / Azure / t91 / ocria-nano / OCRia-1 / plain 4B / plain 9B.
  Seen: «البينات» corrected to «البيانات» by OCRia-1 and both plain models; «4/254» and «68/1» reversed by OCRia-1 and
  the 4B; the 9B dropping the first word of a line («التجانس» → «المرونة»).
- `table_<stem>_pNNN.png`, 4 tables, with a grid for each plain model. Seen: 1001-018-001-004 p9 all 30 cells right
  for both plain models (the 9B's answer is an HTML page: in the contract reading its table is inside one code block
  and not found); 0345-045-004-023 p2: 4B 34 of 36 (the merged «Travel Bans» cell one row low: a pipe table cannot
  merge cells), 9B 36 of 36; 0097-034-000-003 p40, a two-level header: the 4B drops the top header row «الشعور
  بالسعادة» (no colspan in a pipe table), so every cell sits one row off (2 of 28 right), and the 9B writes only that
  header row (3 of 28); OCRia-1 28 of 28.
- `pages_<stem>_pNNN.png`, 3 pages with the plain 4B's answer: 0097-034-000-006 p4 (body), 0840-000-014-006 p12 (two
  columns: 31 lines, half the page, missing without any loop), 0246-021-003-004 p32 (references: Arabic-Indic digits
  kept, each reference one paragraph, one page range reversed and missed).

## Files

- `gs101.py` — GPU session (experiment 100's gs100.py: $5 cap, 80 GB disk, CUDA 13 driver, idle 20 min).
- `host101.sh` — on the host: `all`, `devall`, `dev`, `exam`, `swap`, `stopserve`, `model`; `ARM` = 4B | 9B.
- `infer101.py` — on the host: one request per page, JSON per page, resumable (our prompt + `Transcribe this page.`).
- `prompts/P1.txt`, `prompts/P2.txt` — the two candidate prompts.
- `convert101.py`, `score101.py`, `dev101.py`, `selftest101.py`, `pictures101.py` — experiment 100's, copied; changes
  named in each docstring (`convert101.py` also holds the lenient diagnostic, `EXP101_LENIENT=1`).
- `compare101.py` — the comparison and the "what the fine-tune bought" table → `out/scores/compare101.md` / `.json`.
- `card/` — the two HuggingFace listings, model cards, LICENSE, chat templates and configs read on 2026-11-24 (no
  weights).
- `out/` (gitignored): `up/` (symlinks), `gpu/`, `model/4B`, `model/9B` (raw answers: evaluation records only),
  `model/hostlogs/` (host, vLLM, install logs), `dev/` (`4B`, `9B`), `scores/` (`4B`, `9B`, `4B_lenient`, `9B_lenient`,
  `ocria1_rescored`, `compare101.*`), `selftest/`, `pictures/`.

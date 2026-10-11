# 01 — Open document OCR / parsing models, and which suit Arabic journals

Research date: **2026-10-11**. Web research only: no weights downloaded, nothing installed, nothing paid.
Every number below is quoted from the source linked next to it. Most are **reported by the people who built the model**, and I say so where it matters.

## Summary in plain words (10 lines)

1. General document benchmarks such as OmniDocBench and olmOCR-Bench are almost all English and Chinese pages. Their leaders (TeleOCR, OvisOCR2, PaddleOCR-VL-1.6, GLM-OCR, Chandra 2) are **not** proven on Arabic, and some say outright that they do not cover it (GLM-OCR: 8 languages; PP-OCRv6: no Arabic).
2. The independent Arabic evidence is thin: KITAB-Bench (2025), Baseer's Misraj-DocOCR (2025), the multilingual MORE benchmark (Jul 2026, from Tencent), and two 2026 academic studies (Inria, and the manuscripts study).
3. Across those, **dots.ocr (MIT, 3B)** is the most consistently strong open whole-page parser on Arabic. HunyuanOCR scores higher on MORE, but MORE was made by Tencent, which also makes HunyuanOCR, and HunyuanOCR's licence excludes the EU, UK and South Korea.
4. **No open model yet matches Azure or Gemini on Arabic characters.** On Misraj-DocOCR the CER was 0.27 for Azure, 0.31 for Gemini 2.5 Pro and 0.40 for dots.ocr. Chandra 2 reports Arabic at 68% against 84% for Gemini Flash.
5. On line images of real printed Arabic books, an old-style **Kraken** recogniser trained on Arabic print (OpenITI) beat every VLM tested by a wide margin: CER 3.1% against 10–21% for olmOCR-2, Qwen3-VL, DeepSeek-OCR and LightOnOCR.
6. VLMs fail in a dangerous way. They "repair" text from their language prior (a plausible word replaces the printed one), loop and repeat themselves, emit markup, and drift into Latin script. Classic recognisers make visible, local errors instead.
7. For tables and formulas, VLMs are far ahead of classic tools. Classic tools still win on exact character fidelity and on **line and word coordinates**, which inkscript needs to tie text to ink.
8. This points to a **hybrid**. A classic recogniser (Kraken or PP-OCR) gives the lines, boxes and faithful characters. A VLM (dots.ocr, PaddleOCR-VL or Qwen3-VL) gives tables, formulas, reading order and a second reading. Where the two disagree, the page is flagged rather than guessed.
9. On this machine (16 cores, 15 GB, no GPU), Kraken, Tesseract and PP-OCR run comfortably. A 1B VLM runs at roughly minutes per page (my estimate, not measured). Doing the whole archive with a VLM needs a rented GPU: published speeds are about 1–2 pages per second per GPU.
10. Nothing here should be trusted on Mandumah pages until it is measured on them. The next step is a small hand-checked Arabic test set of ~50–100 pages (footnotes, Quran, vowelled text, tables), scored with CER and a count of hallucinated words.

## Ranked shortlist for Mandumah's Arabic journals

| # | Candidate | Role | Why |
|---|---|---|---|
| 1 | **dots.ocr / dots.mocr** (rednote-hilab, MIT, 3B) | whole-page parser: blocks with boxes and categories, text, HTML tables, LaTeX | Best open model on Arabic in the two independent page-level tests: MORE (Arabic overall 81.3 script-level and 90.0 per-language, behind HunyuanOCR only) and KITAB PDF→MD (CER 0.28, the best open model in Baseer's paper). Its licence allows commercial use. Its known failure is endless loops on repeated "...", "____" and similar runs. dots.mocr (Mar 2026) is the newer version but does not report Arabic. |
| 2 | **Kraken 7.x + an Arabic-print model** (Apache-2.0, CPU) | line segmentation with baselines and polygons, plus faithful line text | Lowest Arabic CER in the only head-to-head test on real printed books (3.1%, Inria 2026). Runs on CPU. Can be fine-tuned per typeface with ~1,000 lines. It gives line coordinates, which VLMs do not. Caveats: the test used gold line crops, so segmentation errors were not counted, and the books were close to the model's own training domain. It does no tables or math. |
| 3 | **PaddleOCR-VL (1.5/1.6, Apache-2.0, 0.9B)** + PP-StructureV3 parts | small fast parser, tables, formulas | Best Arabic *text* score on MORE (80.45) and best Arabic formula score (97.4). Weaker Arabic reading order (76.8). Small enough to try on CPU. The 1.6 card no longer mentions Arabic, so the earlier version may be the safer one for Arabic (needs checking). |
| 4 | **Qwen3-VL-8B / Qwen3.5-9B** (Apache-2.0) | general reader, judge and second opinion | Not the best at OCR (10–11% CER on Arabic book lines), but a good base for an **Arabic fine-tune**, as Qari 0.4 (Qwen3-VL-4B) and Baseer (Qwen2.5-VL-3B) show. Runs in llama.cpp, on CPU at Q4 (slow). |
| 5 | **Baseer** (Misraj) / **Qari-OCR 0.4** (Apache-2.0) | Arabic-specialised readers | Baseer has the best Arabic WER in its own paper (0.25), but its CER (0.53) is worse than Azure's, and whether the weights are released is unclear (a 4B `Misraj/Baseer__Nakba` repo exists). Qari 0.4 is good on printed Islamic books (CER 0.12 on its own test), but an independent study saw it **hallucinate badly** on manuscripts. Both are worth a trial; neither has been proven elsewhere. |
| — | Watch: HunyuanOCR-1.5 (Jul 2026) | — | Highest Arabic scores on MORE, which Tencent authored about its own model. The licence excludes the EU, UK and South Korea, and that needs checking before any use. |
| — | Not for Arabic: GLM-OCR, olmOCR-2, Chandra 2 (non-commercial-ish licence), LightOnOCR-2, MinerU2.5 (Arabic text 9.4 on MORE), Nougat, GOT-OCR2, Florence-2, Granite-Docling (Arabic "experimental") | — | Each is English/Chinese/Latin-centred, scores poorly on Arabic where measured, or both. |

**Why this order.** The owner now wants accurate text, equations and tables. For Arabic text, the best independently measured systems are an in-domain classic recogniser (Kraken) and dots.ocr. For tables and formulas, VLMs (dots.ocr, PaddleOCR-VL) are the only open option that works. No single open model is safe on its own: every VLM tested on Arabic shows prior-driven substitutions and loops. The plan with the best evidence is therefore two readers with different failure modes, plus checking where they disagree.

## Comparison table

Licence key: **OK** means commercial use is allowed. Sizes are total parameters. "Boxes" says which coordinates the model returns.

| Model (release) | Licence (weights) | Size | Outputs | Boxes | Arabic evidence | CPU on owner's PC? | GPU speed (reported) |
|---|---|---|---|---|---|---|---|
| dots.ocr (Jul 2025) | MIT – OK | 3B (1.7B LLM) | JSON layout + MD text, HTML tables, LaTeX | block boxes + category | MORE Arabic: text 76.2, reading order 94.6, overall 81.3/90.0. Misraj-DocOCR CER 0.40 / WER 0.50. KITAB PDF→MD CER 0.28 (30 pages) | possible, slow (HF transformers; a CPU discussion is linked) | not optimised for bulk (card) |
| dots.mocr (Mar 2026) | MIT – OK | 3B | as above + SVG for graphics | block boxes | none (en/zh tags) | as above | — |
| PaddleOCR-VL (Oct 2025) / 1.5 / 1.6 (May 2026) | Apache-2.0 – OK | 0.9B (ERNIE-4.5-0.3B + NaViT) | JSON + MD; text, tables, formulas, charts | block boxes (PP-DocLayout); 1.6 "text spotting" | v1 card: 109 languages incl. Arabic. MORE Arabic: text 80.45 (best), formula 97.4, reading order 76.8 | yes, CPU build of Paddle; speed unknown | OmniDocBench v1.6 96.33 (1.6, self-reported) |
| HunyuanOCR 1.0 (Nov 2025) / 1.5 (Jul 2026) | Tencent Hunyuan Community – **no rights in EU/UK/KR** | ~1B | doc_parse, spotting, extraction | spotting boxes | MORE Arabic overall 84.7/94.6 (best, Tencent's own benchmark) | llama.cpp GGUF supported (repo) | vLLM |
| Qwen3-VL (Sep–Oct 2025) | Apache-2.0 – OK | 2B, 4B, 8B, 32B, 30B-A3B, 235B-A22B | free text/MD/HTML; grounding | can emit boxes on request (not reliable for OCR lines) | Arabic book lines: 8B CER 11.3%, 2B 17.6% (Inria). MORE Arabic: 2B text 78.9, but formulas 40.7 | 2B/4B/8B in llama.cpp, Q4 | — |
| Qwen3.5 (2026) | open weights (check per size) | 0.8B…397B-A17B, all multimodal | free text | — | none found. A practitioner names 9B as the OCR sweet spot; 0.8B drifts into summarising | llama.cpp | — |
| olmOCR-2-7B (Oct 2025) | Apache-2.0 – OK | 8B (Qwen2.5-VL-7B) | plain text/MD with YAML front matter | none | tagged English. Arabic lines CER 10.5% (Inria) | no (too slow) | <$200 per million pages claimed |
| Chandra OCR 2 (Mar 2026) | modified OpenRAIL-M: free under $2M revenue, **no competing with Datalab** | 5B (Qwen3.5 base) | MD, HTML, JSON layout | layout blocks | Datalab's own benchmark: Arabic 68.4% (Gemini 2.5 Flash 84.4%) | no | H100: 1.44 pages/s |
| DeepSeek-OCR (Oct 2025) / OCR 2 (Jan 2026) | Apache-2.0 on OCR-2 card (sources disagree) | 3B | MD or "Free OCR" text; grounding prompt | grounding boxes | Arabic lines CER 20.8% (Inria). MORE Arabic text 59.1 | no | — |
| GLM-OCR (Feb 2026) | MIT – OK | 0.9B + PP-DocLayoutV3 | MD, tables, formulas, JSON extraction | layout | 8 languages, **no Arabic** | Ollama (CPU possible) | 1.86 PDF pages/s |
| OvisOCR2 (Jul 2026) | Apache-2.0 (per mirrors) | 0.8B | MD/tables/formulas | — | none | — | OmniDocBench v1.6 96.58 (paper) |
| TeleOCR / NaviDC-OCR (Aug 2026) | Apache-2.0 (per Docsumo) | 1.2B | text, OTSL tables→HTML, LaTeX, layout boxes | layout | none | community GGUF | OmniDocBench v1.6 96.91 (reported) |
| MinerU2.5-Pro-2605 (May 2026) | VLM weights Apache (MinerU toolkit AGPL-3.0) | 1.2B | MD/JSON | blocks | MORE Arabic text **9.4** (MinerU2.5). Its pipeline mode uses PP-OCRv5 Arabic | pipeline mode yes | — |
| LightOnOCR-2-1B (Jan 2026) | Apache-2.0 – OK | 1B | MD; image boxes | image boxes only | Latin-centred. LightOnOCR-1B Arabic lines 15.4% CER | maybe | fast |
| Qianfan-OCR (Mar 2026) | Apache-2.0 (reported) | 4B | parse + layout + KIE | layout | CC-OCR multilingual 76.7 (self) | no | — |
| Nanonets-OCR2-3B (Oct 2025) | check card (one catalogue says "commercial") | 3B | MD, HTML tables, LaTeX | none | Arabic in training list. Misraj-DocOCR CER 0.55 (OCR-s v1) | no | — |
| Granite-Docling-258M (Sep 2025) | Apache-2.0 – OK | 258M | DocTags → MD/HTML | element boxes | Arabic "experimental" | yes | — |
| Arabic-Nougat (Nov 2024) | open (check) | 0.2–0.4B | MD | none | KITAB CER 4.37 (very poor) | yes | — |
| **Qari-OCR 0.4** (2025) | Apache-2.0 – OK | 4B (Qwen3-VL-4B) | plain text | none | own test (Islamic books): CER 0.122 / WER 0.256. Manuscripts: CER 167% from hallucination (independent) | slow | — |
| **Baseer** (Sep 2025) | weights unclear | 3B (Qwen2.5-VL-3B); 4B variant on HF | MD | none | Misraj-DocOCR WER 0.25, CER 0.53, TEDS 66 (own) | slow | — |
| AIN-7B (MBZUAI, 2025) | open (check) | 7B | text | none | KITAB OCR CER 0.20 (best open there). Misraj-DocOCR CER 1.11 (Baseer's eval) — the results contradict each other | no | — |
| **Kraken 7.1** + PP-OCRv6-based base models (Aug 2026) | Apache-2.0 – OK | 3M (small) | lines: text + baseline + polygon; ALTO/PAGE XML/hOCR | **line polygons, baselines** (character positions available) | base model Arabic CER: tiny 20.1, small 13.6, medium 9.4%. OpenITI print model: 3.1% on printed books (Inria) | **yes, comfortably** | n/a |
| Tesseract 5.5 (`ara`) | Apache-2.0 | small | hOCR/ALTO/TSV | **word boxes** | Arabic book lines 24.6% CER (Inria). KITAB CER 0.54 | yes | n/a |
| PP-OCRv5 `arabic_PP-OCRv5_mobile_rec` | Apache-2.0 | small | lines + boxes | line boxes | 81.27% average accuracy (Paddle's own set). PP-OCRv6 has **no Arabic** | yes | n/a |
| Surya / Marker (Datalab) | code GPL/Apache. Weights cc-by-nc-sa with a <$5M waiver | — | lines, layout, MD | line boxes | KITAB CER 4.95 (poor). Line detection mAP50 79.7 (best of three) | yes, slow | — |
| Mistral OCR 4 / 4.1 (Jun–Jul 2026) | **closed** (API + paid self-host container) | — | MD | — | — | — | $4 per 1k pages |

## Benchmarks: who leads, and what each says about Arabic

**OmniDocBench** (opendatalab; EN/ZH pages; v1.6 is the current scale and not comparable with v1.5). Reported leaders as of late Sep 2026: TeleOCR 96.91, OvisOCR2 96.47–96.58, PaddleOCR-VL-1.6 96.33, MinerU2.5-Pro 95.75, GLM-OCR 95.22, DeepSeek-OCR-2 90.25. Among general models, Gemini 3 Pro scores 92.91 and Qwen3-VL-235B 89.78. All of these are small, specialised ~1B models. **It has no Arabic pages and says nothing about Arabic.** Sources: [Docsumo roundup, checked 2026-09-29](https://www.docsumo.com/blog/best-ocr-models) (vendor blog that marks self-reported scores); [OvisOCR2 paper](https://arxiv.org/abs/2607.13639); [PaddleOCR-VL-1.6 card](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6/blob/main/README.md); [GLM-OCR card](https://huggingface.co/zai-org/GLM-OCR).

**olmOCR-Bench** (AI2; English PDFs; pass/fail unit tests). Chandra 2 scores 85.8–85.9, dots.mocr 83.9, Chandra 1 83.1, olmOCR-2 82.4, PaddleOCR-VL 80.0, dots.ocr 79.1, DeepSeek-OCR 75.4. Mistral OCR 4 claimed state of the art, but ranked #3 on the public board ([mind-verse](https://mind-verse.de/news/debatte-leistung-mistral-ocr-4-olmocrbench)). **No Arabic.** Sources: [Chandra repo](https://github.com/datalab-to/chandra), [dots.mocr card](https://huggingface.co/rednote-hilab/dots.mocr), [olmOCR-2 card](https://huggingface.co/allenai/olmOCR-2-7B-1025).

**OCRBench v2 / CC-OCR**: general VLM tests. Qwen3-VL-32B/235B lead the open models on OCRBench v2 EN (~67–68, aggregator snapshot Sep 2026, [anotherwrapper](https://anotherwrapper.com/tools/llm-pricing/evals/ocrbench-v2)). On CC-OCR multilingual, Qianfan-OCR reports 76.7 against 74.2 for Qwen3-VL-4B ([Qianfan-OCR paper, self-reported](https://arxiv.org/pdf/2603.13398)). No Arabic-specific breakdown was found.

**KITAB-Bench** (MBZUAI, ACL Findings 2025; 8,809 Arabic samples). [paper](https://arxiv.org/html/2502.14949v2), [repo](https://github.com/mbzuai-oryx/KITAB-Bench).
- Image→text CER: Gemini-2.0-Flash 0.13, AIN-7B 0.20, GPT-4o 0.31, Azure 0.52, Tesseract 0.54, EasyOCR 0.58, PaddleOCR 0.79, Gemma3 1.05, Qwen2.5-VL-7B 1.20, Qari (v0.1/0.2) 1.80, Arabic-Nougat 4.37, Surya 4.95. A CER above 1 means the output has more errors than the reference has characters, which usually means hallucinated or looping output.
- PDF→Markdown MARS: Gemini-2.0-Flash 65.7 (the best), GPT-4o 65.1, Docling+EasyOCR 54.3, AIN 52.9, Marker/Surya 51.3, Qwen2.5-VL-7B 40.4.
- Tables TEDS (HTML): GPT-4o 85.8, Gemini 83.1, AIN 75.9, Qwen2.5-VL 59.3, Docling+EasyOCR 49.1, Marker 50.2.
- **Caveats.** It predates every 2025-H2/2026 model. The Baseer authors found errors in its ground truth, including hallucinated text and missing small-font text and page numbers, and published a corrected PDF→MD subset. The repo now lists evaluation scripts for AtlasOCR, dots.ocr and PaddleOCR, but publishes no scores for them.

**Misraj-DocOCR** (400 expert-checked Arabic pages, from [Baseer paper, Sep 2025](https://arxiv.org/abs/2509.18174)). WER / CER / TEDS: Baseer 0.25 / 0.53 / 66; Gemini-2.5-Pro 0.37 / 0.31 / 52; **Azure DI 0.44 / 0.27 / 42**; dots.ocr 0.50 / 0.40 / 40; Nanonets 0.71 / 0.55 / 37; Qwen2.5-VL-32B 0.76 / 0.59 / 41; Qari 0.76 / 0.64 / 21; GPT-5 0.86 / 0.62 / 48; AIN 1.23 / 1.11 / 21. Note that **Azure has the lowest CER**. This matters for the owner's change of direction, because no open model in the table matched Azure on characters. The authors also note that base Qwen sometimes reverted to left-to-right output and handled vowelled (diacritised) text poorly.

**MORE** (multilingual document parsing, 149 languages, [arXiv 2607.02956, 2026-07-03](https://arxiv.org/html/2607.02956); **all authors are from Tencent, as is HunyuanOCR**). Arabic scores:

| Model | Text | Formula | Reading order | Overall (script) | Overall (per language) |
|---|---|---|---|---|---|
| HunyuanOCR | 80.17 | 94.50 | 89.44 | 84.72 | 94.56 |
| dots.ocr | 76.23 | 93.99 | 94.63 | 81.25 | 90.01 |
| PaddleOCR-VL | **80.45** | **97.44** | 76.81 | 77.26 | 79.82 |
| Qwen3-VL-2B | 78.94 | 40.66 | 88.49 | 79.98 | 73.65 |
| DeepSeek-OCR | 59.05 | 81.80 | 99.63 | 75.65 | 81.33 |
| Qwen2.5-VL-3B | 75.92 | 95.60 | 80.65 | 74.67 | 87.80 |
| MinerU2.5 | 9.44 | 70.54 | 39.12 | 24.94 | 36.01 |

There is no Arabic table score: Arabic is not in its top-15 for tables. Gemini 3 has no Arabic breakdown.

**"Reading or Guessing?"** ([Inria, arXiv 2605.27750 v2, 2026-09-07](https://arxiv.org/html/2605.27750)). This is the most useful independent test for printed Arabic books. It used 3,197 gold **line crops** from 15 held-out 19th–20th-century books from OpenITI. Median CER / WER (%): Kraken-OpenITI 3.1 / 18.2; olmOCR-2-7B 10.5 / 43.8; Qwen3-VL-8B 11.3 / 44.4; LightOnOCR-1B 15.4 / 57.1; Qwen3-VL-2B 17.6 / 60.0; DeepSeek-OCR 20.8 / 66.7; Tesseract-ara 24.6 / 77.8. Findings:
- Only the VLMs showed repetition collapse (0.1–1.5% of lines), markup emission and Latin letters inside Arabic lines.
- When the text was deliberately perturbed, VLM error rose by 10.6–26.2 points against 2.5–5.7 for the classic systems. In other words, VLMs "repair" text towards what they expect.
- Text-only post-correction made 6 of 7 Arabic systems worse.
- Caveats: the test used line crops, so there was no layout or segmentation step. The Kraken model ([Kiessling 2022, zenodo 7050296](https://doi.org/10.5281/zenodo.7050296)) is in-domain. The VLMs ran with greedy decoding and a ~1 MP image budget.

**"When do VLMs help Arabic manuscript OCR?"** ([arXiv 2608.22366, 2026-08-23](https://arxiv.org/html/2608.22366v1)). Printed Arabic CER: SARD (clean synthetic print) Tesseract 4.7%, Qwen2.5-VL-7B 3.8%, Tesseract→Qwen correction 2.6%. KITAB 40.2 / 38.7 / 32.7. QNL aged books 33.1 / 20.1 / 15.5 (via Fanar-2). Findings:
- A VLM that is given the classic OCR output *plus* the image helps when the OCR output is roughly right, and hurts when it is badly wrong.
- Qari-OCR 0.4 hallucinated on manuscripts (CER 167%).
- Practical traps: max-token truncation (at 512 tokens, Qwen looked 10× worse), loops under greedy decoding, and sensitivity to diacritics.
- Recommendation: route pages adaptively and probe each collection first.

## Classic pipeline versus one end-to-end VLM

**Accuracy on English/Chinese structure.** End-to-end VLMs have caught up with or passed pipelines on OmniDocBench. OvisOCR2 says it is the first end-to-end model to top a board "previously dominated by pipeline methods". The leading systems are still often *hybrids*: PaddleOCR-VL, GLM-OCR and MinerU all run a layout detector first, then a small VLM on each region. ABot-OCR's report says pipeline baselines "remain strong" ([alphaxiv](https://www.alphaxiv.org/abs/2605.27978)).

**Accuracy on Arabic text.**
- On clean, in-domain print, a trained classic line recogniser is clearly better (Kraken 3.1% against ≥10% for VLMs).
- On aged or unusual print without an in-domain model, VLMs beat Tesseract (QNL 20% against 33%).
- On whole pages, the best open VLMs are still behind Azure and Gemini on CER.

**Not hallucinating.** The evidence favours classic recognisers. Their errors are local and visible. VLM errors are fluent substitutions, loops, skipped regions and wrong-script output that a reader does not notice ([Inria](https://arxiv.org/html/2605.27750); [FireRed-OCR on "structural hallucination"](https://arxiv.org/pdf/2603.01840)). dots.ocr's own card warns of endless output on repeated characters. Production vendors such as Reducto combine VLMs with classic OCR and route regions between them ([ZenML case study](https://www.zenml.io/llmops-database/production-scale-document-parsing-with-vision-language-models-and-specialized-ocr)).

**Tables and formulas.** Only VLMs, or dedicated table and formula models, produce usable HTML and LaTeX. On KITAB tables, Docling and Marker scored 28–50 TEDS, against 76–86 for the large VLMs. Classic choices if a pipeline is wanted:
- Tables: PP-StructureV3 (SLANeXt), Docling TableFormer.
- Formulas: PP-FormulaNet, UniMERNet.
- Layout: PP-DocLayoutV2/V3, DocLayout-YOLO.

**Coordinates.**
- Only the classic engines return **line or word geometry**: Kraken (baselines and polygons, ALTO/PAGE), Tesseract (word boxes), PP-OCR (line boxes), Surya (lines).
- VLM parsers return block boxes at best: dots.ocr, PaddleOCR-VL pipeline, MinerU, TeleOCR.
- Qwen-style "grounding" boxes are not reliable enough to place text exactly.

For inkscript, where text must sit on its own ink, this alone argues for a classic line layer under any VLM.

**Conclusion.** For Arabic journals, use classic segmentation and recognition for the faithful text and the geometry, a VLM for tables, formulas and reading order, and checking where the two disagree. A single end-to-end VLM should not be trusted alone.

## Hardware: what runs where

The owner's machine has 16 cores, 15 GB RAM and no CUDA GPU (WSL2).
- **Runs well on CPU.** Kraken (training on CPU is slow but possible for small fine-tunes), Tesseract, PP-OCRv5 mobile models, and PP-DocLayout. The Paddle CPU build also covers PP-StructureV3's small table and formula models.
- **Runs on CPU, slowly** (estimate: on the order of minutes per page; not measured):
  - ~1B VLMs: PaddleOCR-VL through transformers or Paddle CPU, HunyuanOCR through llama.cpp GGUF, GLM-OCR through Ollama, Granite-Docling.
  - 2–8B models quantised to Q4 in llama.cpp: Qwen3-VL-2B/4B/8B, Qwen3.5.
  - The only published CPU data point is a Qwen3-VL-2B fine-tune at ~23 tokens/s CPU against ~127 tokens/s on an RTX 4060 ([model card](https://huggingface.co/keyvan-ai/german-ocr-2b-gguf)). An Arabic journal page is likely 1,500–3,000 output tokens, so that is roughly 1–2 minutes per page for a 2B model and several times longer for 8B.
  - Memory: 3B models in BF16 need ~7–8 GB, which fits in 15 GB but is tight alongside anything else.
- **Needs a rented GPU for the archive.**
  - dots.ocr, olmOCR-2, Chandra and Qwen3-VL-8B+ at any useful speed.
  - Published speeds: Chandra 2 does 1.44 pages/s on one H100 (vLLM, 96 parallel). GLM-OCR does 1.86 pages/s (GPU not stated). olmOCR claims under $200 per million pages.
  - At ~1 page/s, a million pages is ~280 GPU-hours. A 24 GB card (L4/4090/A10) is enough for every ≤8B model here.

## Where the evidence is thin

- **No independent Arabic test exists for any 2026 model** (PaddleOCR-VL-1.5/1.6, dots.mocr, OvisOCR2, TeleOCR, GLM-OCR, HunyuanOCR-1.5, Chandra 2, DeepSeek-OCR-2, Qwen3.5). The Arabic numbers above are for their 2025 predecessors.
- Arabic scores for Chandra, Qari, Baseer, HunyuanOCR (via MORE) and PaddleOCR (PP-OCRv5 accuracy) are **all self-reported**, each on its own data.
- The results contradict each other: AIN-7B is best open on KITAB (CER 0.20) and near-worst on Misraj (CER 1.11). Qwen3-VL-8B gets 11% CER on Inria's lines and 69% on Qari's test set. Prompts, image size, token limits and diacritic handling swing the numbers enormously.
- Nothing measures **vowelled Quran quotations, footnotes, mixed Arabic/French/English lines, or Arabic equations** specifically. Those are exactly Mandumah's hard cases.
- Several licence and size facts come from aggregators: OvisOCR2, TeleOCR, Qianfan-OCR, Nanonets-OCR2, DeepSeek-OCR-2 (conflicting reports), Baseer (weights availability), and HunyuanOCR (territory exclusion stated by Docsumo; LICENSE file not read). Read each LICENSE before adopting it.
- Several items are from aggregator snapshots: the olmOCR-Bench ordering, OCRBench v2, and the KITAB "Codesota" board.

## Other sources

- [dots.ocr card](https://huggingface.co/rednote-hilab/dots.ocr)
- [PaddleOCR-VL card](https://huggingface.co/PaddlePaddle/PaddleOCR-VL)
- [PaddleOCR-VL paper](https://arxiv.org/pdf/2510.14528)
- [PP-OCRv5 multilingual](https://www.paddleocr.ai/v3.3.2/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html)
- [PP-OCRv6 no-Arabic thread](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec/discussions/2)
- [Kraken 7.1 release](https://newreleases.io/project/github/mittagessen/kraken/release/7.1)
- [Kraken PP-OCRv6 base model, zenodo 21788405 (2026-08-04)](https://zenodo.org/records/21788405)
- [HunyuanOCR repo](https://github.com/Tencent-Hunyuan/HunyuanOCR)
- [Qari-OCR 0.4 card](https://huggingface.co/NAMAA-Space/Qari-OCR-0.4.0-VL-4B-Instruct)
- [Qari paper](https://arxiv.org/abs/2506.02295)
- [Arabic-Nougat](https://arxiv.org/html/2411.17835v1)
- [AtlasOCR (gated)](https://huggingface.co/atlasia/AtlasOCR)
- [Chandra OCR 2 card](https://huggingface.co/datalab-to/chandra-ocr-2)
- [DeepSeek-OCR-2 card](https://huggingface.co/deepseek-ai/DeepSeek-OCR-2)
- [DeepSeek-OCR-2 paper](https://arxiv.org/pdf/2601.20552)
- [LightOnOCR-2 paper](https://arxiv.org/pdf/2601.14251.pdf)
- [MinerU 2.5 paper](https://arxiv.org/pdf/2509.22186)
- [MinerU2.5-Pro card](https://huggingface.co/opendatalab/MinerU2.5-Pro-2605-1.2B)
- [Mistral OCR 4 launch (closed)](https://www.hpcwire.com/aiwire/2026/06/25/mistral-unveils-ocr-4-for-enterprise-search-rag-and-document-processing/)
- [Qwen3.5 OCR practitioner notes](https://martinalderson.com/posts/how-to-use-qwen-3-5-to-ocr-documents/)
- [Qwen3-VL tech report](https://arxiv.org/pdf/2511.21631)
- [Fanar 2.0](https://arxiv.org/pdf/2603.16397)
- [Surya licence (README mirror)](https://huggingface.co/pitapo/surya/blob/main/README.md)
- [OpenITI Arabic OCR case study](https://arxiv.org/pdf/2402.10943)

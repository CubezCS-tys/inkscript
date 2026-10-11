# 03 · Building our own Arabic document reader: what it takes, and how we prove it is the most accurate

*Research note, 2026-10-11. Web research plus what this repo already measured. Nothing was downloaded,
trained or paid for. Numbers from papers are the papers' own; where a figure comes from a blog or vendor
page it says so. Prices move weekly. Treat them as of September–October 2026.*

## In ten lines

1. A document VLM is three parts: an **eye** (a vision encoder cutting the page into small tiles), a
   **translator** (a small projector), and a **writer** (a language model that writes the text token by token).
2. Nobody trains one from scratch for a project like ours. Every Arabic OCR model of 2025–26 (Qari, Baseer,
   AtlasOCR) is an open model (Qwen2/2.5/3-VL) **fine-tuned** on 5k–500k image/text pairs, for tens of dollars to
   a few thousand.
3. The bar is high: on our archive **Azure misreads 0.61% of printed Arabic words** (1.55% of all words on scans,
   most of the rest specks, ornaments and handwriting; experiment 19). Published Arabic models report 6–50% CER on
   their own benchmarks. None has been measured on pages like ours.
4. A VLM's characteristic failure is *fluent* error: invented text, rewritten words, skipped or looping lines.
   It is measurable, and partly preventable (line-level reading, repetition guards, agreement with a second reader,
   a check against the ink).
5. We hold two unusual assets: **42% of the archive is born-digital** (exact text for free, in the archive's own
   fonts and layouts), and **ink-level checks no one else has** (Quran verses, the pen path's piece count, the judge).
6. "Most accurate" can only be shown on **our own gold pages**: about 200 hand-checked pages from 120+ documents,
   stratified by decade and kind of text, scored with two Arabic normalisations and confidence intervals.
7. Step one is free: build the gold set and score Azure on it. Then a one-week bake-off of 5–7 open models on
   rented GPUs (about $20–50).
8. Fine-tuning a 2–4B model with LoRA on ~50k line or page pairs costs about **$30–300** a run on a rented
   24–48 GB GPU. A full 7B fine-tune is about $300–400 a run on 8×H100.
9. Reading the ~11.6M scanned pages once costs roughly **$2k–6k** on rented GPUs, against roughly $8k for Azure Read.
   Cost is not the reason to do this; accuracy and control are.
10. The owner's machine (no NVIDIA GPU, 15 GB RAM) can prepare data and score results, but cannot train. Rent first.
    Buy a 32 GB card (~$4k) only once the recipe is proven and iterations become frequent.

## How a VLM reads a page: a picture to hold

Think of **a mosaic, a translator and a storyteller**.

- **The mosaic (vision encoder).** The page image is cut into a grid of small square tiles, each 14 or 16 pixels
  wide (a "patch"). Each tile is turned into a list of numbers that describes what is in it: a stroke edge, a dot,
  a bit of white. Then every tile looks at every other tile (that is what a transformer does) and refines its
  description with the context: "I am the dot *under* a stroke, two tiles left of a tooth." Neighbouring tiles are
  then merged 2×2. So **one "word" of the model's vision is a 28×28 or 32×32 pixel square of the page.**
- **The translator (projector).** A small two-layer network rewrites each tile's description into the vocabulary
  the storyteller understands. It is the only part that has to be newly trained when an eye and a writer are joined.
- **The storyteller (language model decoder).** A text model (0.3B to 7B parameters) writes the transcription one
  token at a time. Before each token it glances back over *all* the tile notes and everything it has written so far.
  It has read billions of sentences, so it knows what Arabic usually says next.

**Why small text needs high resolution.** At 300 dpi a body line is about 40 px tall, and a dot about 4–6 px. If
the page is shrunk before it is cut into tiles, two dots and one dot land in the same blurred tile, and ت and ث
become a guess. olmOCR shrinks pages to **1,024 px on the long side** (about 90 dpi for A4). PaddleOCR-VL allows
up to 2048 tiles of 28×28 (about 1.6 megapixels). dots.ocr allows 11 megapixels. A full A4 page at 300 dpi is 8.7
megapixels, about 11,000 merged tiles. That is more than most models accept in one look. Models therefore either
shrink the page, cut it into overlapping tiles plus one shrunken overview (DeepSeek-OCR's "Gundam" mode, Qwen's
dynamic resolution), or read it **block by block or line by line** after a layout model has found the regions
(PaddleOCR-VL's pipeline).

**Why it hallucinates.** The storyteller is fluent. Where the tiles are smudged it does not stop. It writes what
usually comes next: a common word in place of a rare one, a plausible spelling ("normalising"), a line read twice,
or a sentence finished that the page never finished. In the owner's picture of writing on someone's back: a
reader who knows the language well "feels" a familiar word even when the finger traced something else.
Traditional OCR, when it is unsure, outputs *noise*. A VLM outputs *plausible text*, which is worse because it
looks right.

## The staged plan

| Stage | What it proves | Cost (cash) | Time |
|---|---|---|---|
| **0 · Gold set and scorer** | We can measure. Azure's own score on our pages becomes the bar, per stratum. | $0 (owner's correcting time, ~30–40 h for 200 pages pre-filled with Azure's reading) | 2–3 weeks part-time |
| **1 · Bake-off, no training** | How far off-the-shelf open models are from Azure on our pages, at page and at line level, and how often each one invents, skips or loops. | ~$20–50 rented GPU | 1 week |
| **2 · Training data** | We have ≥50k clean pairs in the archive's own faces: born-digital pages rendered and degraded, synthetic renders (vowels, Quran, tables), and *filtered* Azure lines. | $0–20 (CPU work; optional Gemini check under the $20 cap) | 2–3 weeks |
| **3 · LoRA fine-tune of a 2–4B model** | Whether a model we own beats Azure on the gold set, overall and on the weak strata (pre-2000 prints, added hamza, vowelled text, ﷺ, note numbers). | ~$50–300 (several runs at $10–60) | 1–2 weeks |
| **4 · Guards** | Agreement with Azure, the pen-path piece count, the Quran check and token confidence, combined into trust marks. Measured as experiment 22 measured them: share flagged, errors left in unflagged words (today 0.42%). | ~$0–50 | 1–2 weeks |
| **5 · Scale pilot** | Pages per GPU-hour and cost per 1,000 of *our* pages (Arabic pages are denser than benchmark pages). No regression on 10k pages. | ~$50–200 | 1 week |
| **6 · Optional, later** | Tables (TEDS), formulas (CDM), a full fine-tune or RL with page "unit tests" (olmOCR 2's method), and the full archive. | $1k–10k | months |

Stop and decide after stages 0, 1 and 3. If stage 1 shows nothing open comes within 2× of Azure's 0.6% on body
text, stage 3 is the real test. If stage 3 cannot beat Azure on modern body text, the realistic product is
**Azure plus our reader as a second opinion on the strata where Azure is weak**, not a replacement.

---

## 1. How document VLMs are built and trained

### 1.1 The parts, with real sizes

| model (date) | eye (vision encoder) | translator | writer (decoder) | resolution handling |
|---|---|---|---|---|
| **olmOCR 2** (Oct 2025) | Qwen2.5-VL's ViT | MLP | Qwen2.5-VL-7B | page shrunk to 1,024 px long side |
| **PaddleOCR-VL** 0.9B (Oct 2025; 1.5 Jan 2026) | NaViT-style, from Keye-VL | 2-layer MLP, 2×2 merge | ERNIE-4.5-0.3B | native resolution, no tiling, up to 2048×28×28 px; a separate layout model (PP-DocLayoutV2) finds regions and reading order first |
| **dots.ocr** (Jul 2025; dots.mocr Mar 2026) | 1.2B, trained from scratch | — | 1.7B (from Qwen2.5-1.5B) | native, up to 11 Mpx |
| **DeepSeek-OCR** (Oct 2025) | "DeepEncoder" 380M = SAM-base 80M → 16× compressor → CLIP-large 300M | — | DeepSeek-3B-MoE (570M active) | modes from 64 to 400 tokens a page; "Gundam" = 640 px tiles + 1,024 px overview |
| **Granite-Docling** 258M (Sep 2025) | SigLIP2 | — | Granite-3-based ~165M | outputs DocTags (structure + text) |
| **Qwen3-VL** (base of most 2026 fine-tunes) | SigLIP2 (400M; 300M for 2B/4B) | MLP, 2×2 merge; DeepStack feeds several encoder layers into the LM | 2B–235B | dynamic resolution |
| **Qari-OCR** (Jun 2025) | Qwen2-VL-2B, unchanged design | | | |
| **Baseer** (Sep 2025) | Qwen2.5-VL-3B, **encoder frozen** | | decoder fine-tuned | |

Sources: [olmOCR 2](https://arxiv.org/abs/2510.19817), [PaddleOCR-VL](https://arxiv.org/html/2510.14528v3),
[PaddleOCR-VL-1.5](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5),
[dots.ocr paper](https://arxiv.org/abs/2512.02498), [dots.ocr repo](https://github.com/rednote-hilab/dots.ocr),
[DeepSeek-OCR](https://arxiv.org/abs/2510.18234),
[Granite-Docling](https://ibm.com/new/announcements/granite-docling-end-to-end-document-conversion),
[Qwen3-VL report](https://arxiv.org/abs/2511.21631), [Qari-OCR](https://arxiv.org/abs/2506.02295),
[Baseer](https://arxiv.org/abs/2509.18174).

### 1.2 How they were trained (data, compute)

The typical recipe has three steps. (1) *Alignment*: teach the translator on many image–text pairs. (2)
*Instruction tuning* on curated OCR, table and formula data. (3) Sometimes *RL* with checkable rewards. Labels are
almost never written by hand. They come from **a bigger model (the "teacher") or from rendering**, with humans
checking a small slice.

- **olmOCR (Feb 2025).** 258,641 pages from 102,825 PDFs, transcribed by **GPT-4o** with "document anchoring" (the
  PDF's own text and coordinates put in the prompt). Full fine-tune of Qwen2-VL-7B. One run took **16 node-hours on
  8×H100**; all experiments together took 365 node-hours. Inference: **$176 per million pages** on an L40S at
  $0.79/h (about 1.25 pages/s), $178 on an H100 at $2.69/h (about 4.2 pages/s).
  [paper](https://arxiv.org/html/2502.18443v3)
- **olmOCR 2 (Oct 2025).** SFT of Qwen2.5-VL-7B on olmOCR-mix-1025 (267,962 pages). Then **GRPO** (RL) on 2,186
  synthetic pages carrying **30,381 unit tests**: text present, text absent (headers and footers), reading order,
  table cell, formula, and baseline sanity (no long repeated n-gram, no stray script). Synthetic pages were made by
  having Claude Sonnet 4 re-create real pages as HTML, so the truth is exact. 28 samples per page, reward = share
  of tests passed. Six seeds averaged ("souped"). Ran on 8×H100. olmOCR-Bench 82.4 (first olmOCR: 68.2).
  [paper](https://arxiv.org/html/2510.19817), [blog](https://allenai.org/blog/olmocr-2)
- **PaddleOCR-VL (Oct 2025).** Stage 1: **29M** image–text pairs. Stage 2: **2.7M** curated instructions. Text
  labels came from their older pipeline (PP-StructureV3), refined by ERNIE-4.5-VL and Qwen2.5-VL, plus renders in
  200+ fonts. Tables: 5.5M+ synthetic. Formulas: rendered from arXiv LaTeX. Its in-house **Arabic** edit distance
  is 0.122 (Qwen2.5-VL-72B: 0.405). Speed: 1.62 pages/s on one A100 (FastDeploy), 1.35 with vLLM, on
  OmniDocBench pages. Compute not reported. [paper](https://arxiv.org/html/2510.14528v3)
- **dots.ocr (Jul/Dec 2025).** A 72B teacher (Qwen2.5-VL-72B) translates labelled English documents into 100+
  languages and re-renders them. A 7B student then auto-labels "millions" of real PDFs. Model errors are audited,
  and humans correct over 15,000 hard cases. About 300k SFT samples. Compute not reported.
  [paper](https://arxiv.org/html/2512.02498)
- **DeepSeek-OCR (Oct 2025).** **30M PDF pages** in about 100 languages (5M non-Chinese/English). Coarse labels from
  the PDF text layer (fitz); fine labels for 4M pages from layout and OCR models; about 600k minority-language pages
  through a "model flywheel". Plus 10M synthetic charts, 5M chemical formulas, 1M geometry figures. Trained on
  **160 A100-40G**. Claimed throughput: 200k pages/day on one A100. Reads at 97% precision when the page is
  compressed under 10× (text tokens ÷ vision tokens), and 60% at 20×. [paper](https://arxiv.org/html/2510.18234)
- **Granite-Docling (Sep 2025).** Successor to SmolDocling. Public datasets plus synthetic code, formula and chart
  sets and a curated real-page set (DoclingMatix). Trained with nanoVLM on IBM's H100 cluster. Stability came from
  "extensive dataset filtering and cleaning", not more data.
  [IBM](https://ibm.com/new/announcements/granite-docling-end-to-end-document-conversion)
- **Qari-OCR (Jun 2025, Arabic).** Qwen2-VL-2B. **LoRA rank 16 on both vision and language**, Unsloth + TRL
  SFTTrainer, 1 epoch, lr 2e-4, effective batch 8, on **one A6000 (48 GB)**. v0.1: 5k samples. v0.2: **50k samples,
  about 55 h**. Data: news text and a heavily vowelled classical corpus, rendered via HTML → WeasyPrint →
  images, 10–12 fonts, 14–100 px, three degradation levels. v0.2: CER 0.061 / WER 0.160 on their 200 pages. 4-bit
  quantisation destroyed it (CER 3.45); 8-bit cost 50% more errors. [paper](https://arxiv.org/html/2506.02295)
- **Baseer (Sep 2025, Arabic).** Qwen2.5-VL-3B. **500k pairs**: 300k synthetic (Common Crawl Markdown → HTML →
  Word → PDF → image, **39 Arabic fonts**, 29 degradation transforms on half), and 200k real pages (books, magazines,
  papers) labelled by a VLM and spot-checked by experts. On a 50k subset, **decoder-only fine-tuning beat LoRA and
  full fine-tuning** (ChrF 89.8 vs 85.5 vs 84.8). 3 epochs, 8×H100. They released **Misraj-DocOCR** (400 expert-checked
  pages). [paper](https://arxiv.org/html/2509.18174)
- **AtlasOCR (Apr 2026, Darija).** Qwen2.5-VL-3B, **QLoRA with Unsloth**, synthetic (their OCRSmith library) plus
  real data. [abstract](https://arxiv.org/abs/2604.08070)
- **HunyuanOCR (Nov 2025).** 1B end-to-end. 200M+ image–text pairs over 130+ languages, with synthetic
  right-to-left paragraph rendering. [report](https://arxiv.org/abs/2511.19575)

**What carries over to us.** Large labs spend millions of pages because they cover 100 languages and every kind of
document. We cover one script, a few dozen typefaces and journal layouts. The Arabic projects show that **5k–500k
pairs on a 2–4B base** is the working range. The OpenITI team found **800–1,000 hand-corrected lines enough for a
line-level Kraken model to reach the high 90s on one typeface**
([Romanov et al. 2017](https://arxiv.org/pdf/1703.09550)). Per-typeface adaptation is old, cheap knowledge, and it
matches this repo's finding that each document is its own alphabet (experiments 02–03).

### 1.3 Who leads, and on what

- General benchmarks (OmniDocBench, olmOCR-Bench) are English and Chinese. A September 2026 roundup puts small
  models on top of OmniDocBench v1.6 (TeleOCR 96.9, PaddleOCR-VL-1.6 96.3)
  ([docsumo](https://www.docsumo.com/blog/best-ocr-models), secondary). olmOCR-Bench: Chandra 83.1, dots.mocr 83.9,
  olmOCR 2 82.4, PaddleOCR-VL 80.0, DeepSeek-OCR 75.7, Mistral OCR 72.0.
- **Arabic.** KITAB-Bench (Feb 2025; 8,809 samples, much of it handwriting and scene text): Gemini-2.0-Flash CER
  0.13, AIN-7B 0.20, GPT-4o 0.31, **Azure 0.52**, Tesseract 0.54, Qari 1.80
  ([paper](https://arxiv.org/html/2502.14949)). On Misraj-DocOCR: Baseer WER 0.25; Gemini-2.5-Pro 0.37; **Azure 0.44
  (but best CER, 0.27)**; dots.ocr 0.50; Qari 0.76. (Baseer's table gives its own CER as 0.53, *higher* than its
  WER, which is odd; check before quoting.)
- A September 2026 community benchmark on 462 pages (Misraj + KITAB): best normalised CER **0.41** (amad-vlm6),
  HunyuanOCR 0.43. **Qari-OCR 0.4 and AIN scored above 2.0 because of repetition loops**, and several Arabic
  fine-tunes failed to load or finish ([Clouda](https://github.com/sahrasayed3-crypto/clouda-ocr-model-selection-benchmark)).

**Read these numbers with care.** Azure is "0.52 CER" on KITAB-Bench but misreads 0.61% of printed Arabic words
on *our* archive. The benchmarks mix handwriting, scene text, Markdown formatting and their own conventions. The
Baseer authors found English annotation-tool text inside KITAB-Bench's "ground truth". **None of these tables
predicts accuracy on Mandumah pages.** Only our own gold set can.

## 2. Fine-tuning recipes for Arabic OCR

### 2.1 Which kind of fine-tuning

| method | what changes | memory for a 4B model (rough) | evidence |
|---|---|---|---|
| **QLoRA** | small adapters; base frozen in 4-bit | ~10–16 GB | cheapest. But Qari's *inference* collapsed at 4-bit, so train in 4-bit only if you serve in 16-bit. |
| **LoRA** | small adapters; base frozen in 16-bit | ~16–24 GB | Qari (rank 16, vision + language), Unsloth's default |
| **Decoder-only** | all LM weights; encoder frozen | ~40–80 GB | Baseer: best of the three on 50k samples |
| **Full** | everything | 8×H100 for 7B | olmOCR |
| **RL with checkable rewards** | after SFT | 8×H100 | olmOCR 2: +14 points on its benchmark, mainly tables, formulas and multi-column |

**Recommendation.** Start with **LoRA on a 2–4B model** (Qwen3-VL-4B or 2B; PaddleOCR-VL-0.9B is a second
candidate because it is small and fast). Freeze the encoder at first. Baseer's result suggests the eye already
sees Arabic and the gap is in the writer. If the gold set shows errors on dots and small marks, unfreeze the
encoder or raise the resolution.

**Tools.** [Unsloth](https://docs.unsloth.ai/models/qwen3-vl-run-and-fine-tune) (Qwen3-VL 2B–32B; claims 1.7× faster,
60% less VRAM; Colab notebooks for 8B; used by Qari and AtlasOCR); Hugging Face **TRL** (SFTTrainer; GRPOTrainer is
what olmOCR 2 used); **ms-swift** and **LLaMA-Factory** (config-file training for Qwen-VL families); PaddleOCR-VL
has its own ERNIEKit route. All are free. The choice matters less than the data.

### 2.2 How much data, how many GPU hours, what it costs

- **Data.** 20k–50k pairs is a reasonable first target, in our faces (Qari reached CER 0.06 at 50k). Line pairs
  are cheaper per sample than pages. A page holds 20–40 lines, so 50k lines is only about 2k pages.
- **Time.** Qari: 50k samples, about 55 h on an A6000 (batch 8, 2B, 1 epoch). On an L40S or A100 expect roughly
  20–40 h for a 2–4B LoRA run of that size; less for line crops (fewer image tokens each).
- **Rented GPU prices** (on-demand, Sep–Oct 2026, [Hostinger table](https://www.hostinger.com/tutorials/?p=158956),
  secondary). **RunPod Secure:** 4090 $0.74/h, L40S $0.99, A100 80 GB $1.39, H100 $2.89. **Vast.ai marketplace:**
  from 4090 $0.14, L40S $0.47, A100 $0.44, H100 $1.33. **Lambda:** H100 $3.29. Community tiers are cheaper and less
  reliable. Modal bills per second and suits short bake-offs.
- **So:** a 2–4B LoRA run costs **$10–60**. A stage-3 campaign of 5–8 runs costs **$50–300**. A full 7B fine-tune
  like olmOCR's (16 node-hours × 8 H100) costs **~$300–400 per run**. An olmOCR-scale project (365 node-hours)
  costs **~$6–9k**.

## 3. Training data

### 3.1 What we can make or take

| source | truth quality | what it teaches | licence / risk |
|---|---|---|---|
| **Born-digital Mandumah documents (42% of the archive, experiment 19)**, rendered to images and degraded to look scanned | exact where the font's text layer is clean (the pipeline already detects junk-encoded fonts and can skip them) | the archive's own journals' layouts, fonts, footnotes and tables, mostly 2010+ | Mandumah's content. Fine for an internal model; publishing weights trained on it is a rights question for the owner. |
| **Synthetic renders**: Arabic Wikipedia, OpenITI, Tanzil Quran (vowelled), our own JATS text, rendered with harfbuzz/raqm or Chromium | exact | vowels, rare words, Quran, numbers, ﷺ, tables (render HTML tables), mixed Latin | Wikipedia CC BY-SA; OpenITI **CC BY-NC-SA 4.0** ([Zenodo](https://zenodo.org/records/4075046)); Tanzil: credit, verbatim text |
| **Fonts**: Amiri, Scheherazade New, Noto Naskh/Kufi, Lateef and others (SIL OFL), **plus our own restored typefaces of archive books** (experiment 11; two installed already) | — | old Naskh faces of the archive. **Unique to us.** | OFL is free; ours are ours |
| **Azure's reading of the scans ("silver")** | 0.61% of printed Arabic words wrong; the added hamza in old prints sits at confidence 0.99 | everything real: scan noise, old prints, layout | the model learns Azure's habits, including its errors. See 3.2. |
| **Gemini or another teacher re-reading hard crops** | judge-level (calibrated in experiments 17/19: 2% misses on archive prints) | pre-2000 prints, decorative type | Gemini spend cap (~$20 an experiment) |
| **Public sets**: PATS-A01 (2,766 printed lines, 8 fonts, KFUPM), KHATT (handwriting, KFUPM), Muharaf, SARD, Qari's and Baseer's released data, Misraj-DocOCR | gold or synthetic | breadth | **keep KITAB-Bench and Misraj-DocOCR for testing only**. Check each licence on its host page (KHATT and PATS: KFUPM research terms; Hugging Face mirrors are not authoritative). |
| **Hand-corrected gold** (stage 0) | gold | **only for testing, never for training** | — |

**Degradations**, from Qari and Baseer: blur, noise, JPEG artefacts, low contrast, textured paper, show-through,
skew, warping, bleed, and binarisation-like thinning. Better than inventing these: **measure** the archive's real
degradations (dpi, contrast, stroke-width spread per decade) and match them.

### 3.2 Silver labels: the risk and how to fence it

Training on Azure's output teaches the model to be Azure, errors included. Experiments 19 and 22 tell us exactly
which errors those are: added hamza in old prints, ى/ي, specks read as words, ornaments, ﷺ and note numbers. Fences:

1. Keep only lines where **every word is above confidence 0.9** and nothing raised a trust flag (experiment 22's
   free signals). On post-2000 scans this leaves an estimated ~0.0–0.2% error.
2. **Exclude old prints' hamza-bearing words** from silver training, or train on them only where the Quran check
   or a born-digital reprint confirms the spelling.
3. Prefer lines where **two readers agree** (Azure plus an open model). Experiment 17 found 0 of 190 agreed pieces
   both wrong.
4. Use the **Quran-verified spans** (experiments 20/27: 290 of 387 quotations equal to the verse after fixes) as
   gold-quality vowelled lines.
5. Never take silver from the gold set's documents.

## 4. Avoiding hallucination

**The evidence.**

- *Fluent rewriting is real and measurable.* FaithC4 (2026): general VLMs lose up to 6.9 WER points when the page
  carries deliberately misspelt words (they "correct" them), OCR-specialised VLMs 0.1–3.4, traditional OCR under
  0.8. Short words (4–6 characters) are rewritten up to 10% of the time. [arXiv 2607.21617](https://arxiv.org/abs/2607.21617).
  This matters for us: old prints' bare-alef spellings are exactly a "plausible correction" target.
- *VLM errors stay fluent when wrong; traditional OCR makes local noise.* Decode-time tricks did not reliably
  restore grounding. [Ancient Greek study, 2605.27750](https://arxiv.org/abs/2605.27750). Low CER hid named-entity
  substitutions on degraded scans. [Uruguay, ICDAR-WS 2026](https://arxiv.org/abs/2607.24077).
- *Arabic specifically* ([2608.22366](https://arxiv.org/html/2608.22366v1)): Qari-OCR's errors on manuscript lines
  were **62% hallucination**. Greedy decoding gave **repetition loops in 28%** of one set's outputs; a no-repeat
  constraint took corpus CER from 199% to 67%. Truncating the vision budget (512 tokens) made Qwen fail badly.
  Feeding the VLM Tesseract's text *and* the image helped on aged print (QNL books: 33.1% → 15.5% CER) but hurt
  where the prior was misleading. Sharpening helped; binarisation and denoising hurt.
- *olmOCR*: putting the PDF's own text in the prompt ("anchoring") reduced invented text. A data-loader bug that
  dropped blank pages caused hallucination on blank pages. Repetition loops are caught by a missing end-of-text token
  and retried at a higher temperature (0.1 → 0.8).
- *Confidence*: a model's **token probabilities** separate right from wrong reasonably well. Its *stated*
  confidence ("I am 90% sure") is near chance for small models
  ([2607.22034](https://arxiv.org/pdf/2607.22034), [2511.19806](https://arxiv.org/pdf/2511.19806)). Both fail on very
  bad images.

**What to build (ordered by expected value for us).**

1. **Read line by line, not page by page.** We already have every line's box (Azure's lines, and our own lines in
   `shapes.json`). A line crop can be fed at full 300 dpi. "Skipping a line" becomes impossible by construction, and
   every output is tied to its box (grounding for free). Page-level reading stays useful for structure, and the
   line text can be stitched in afterwards.
2. **Repetition and length guards.** No-repeat n-grams; reject output whose length is out of proportion to the
   line's ink width; retry on a missing end token.
3. **Allowed characters.** Mask the decoder to Arabic script, digits, punctuation and Latin. This stops off-script
   output (Chinese and emoji are olmOCR-Bench's own "baseline" failures).
4. **The ink check only we can run: piece count.** Arabic words break into connected pieces at the six
   non-joining letters. The pen path already knows how many pieces of ink each word and line has. A reading whose
   implied piece count (and dot count, roadmap item 1) does not match the ink is suspect. This is deterministic,
   free, and blind to fluency.
5. **Agreement with Azure.** Where both readings agree, trust is high (experiment 17). Where they disagree, send the
   crop to the calibrated judge, or flag it. Experiment 17's lesson applies: disagreement is only a useful flag when
   the second reader is strong. The feeler at 82.6% was not.
6. **Token confidence** as one more trust signal, calibrated on the gold set the way experiment 19 calibrated
   Azure's (AUC, share flagged, errors caught).
7. **Faithfulness test in the bake-off.** Plant controlled misspellings (bare alef, ة→ه, dropped dot) into rendered
   lines and measure how often each model "corrects" them, in FaithC4's style.

## 5. Measurement

### 5.1 Text

- **CER** = (substitutions + deletions + insertions) ÷ reference characters. **WER** the same over words. Do not
  cap at 1. Loops *should* blow it up (Clouda's benchmark shows why). Report **insertions separately**: they are
  the hallucination signal.
- **Two normalisations, always both:**
  - **Faithful** (what the print says): NFC; Persian look-alikes counted as errors; hamza forms, ى/ي, ة/ه and digits
    kept distinct; tatweel removed; vowels scored separately, as their own metric on vowelled spans.
  - **Search** (what a reader typing a query experiences): additionally remove vowels, fold أ إ آ ٱ → ا, ى → ي,
    ة → ه, Arabic-Indic digits → one form.
  Experiment 19's judge ignored short vowels and kashida but counted hamza and ى/ي. Keep that as the headline
  definition, so the gold-set number is comparable with the 0.61% bar.
- **Word-level with confidence intervals**, stratified as experiment 19 did (body, footnotes, titles, running heads,
  vowelled, numbers, Latin, ornaments), and **bootstrapped over documents**, not words.
- **Line accounting**: lines skipped, lines duplicated, and lines invented (output with no ink box). These are
  counted directly with line-level alignment.

### 5.2 Tables, formulas, order

- **Tables: TEDS** (tree-edit-distance similarity between HTML trees; PubTabNet, 2020) and **TEDS-S** (structure
  only). KITAB-Bench and OmniDocBench both use it. olmOCR's cell "unit tests" (cell X is right of Y, below Z) are
  easier to hand-write for our own pages.
- **Formulas: CDM** ([CVPR 2025](https://arxiv.org/html/2409.03643v2)) renders predicted and true LaTeX and matches
  characters as images, so equal-looking formulas written differently are not penalised. BLEU and edit distance on
  normalised LaTeX are reported alongside. The archive is mostly humanities, and D17 keeps tables and equations off
  the live list. Count how many pages have them before building anything.
- **Reading order**: edit distance over the block sequence (OmniDocBench), or order "unit tests" (A before B).
  This repo already measures lines in order (99.94%).

### 5.3 The gold set: how big for trustworthy numbers

- What we know: in experiment 19, 2,971 judged words from 139 documents gave 1.55% with a 95% interval of
  0.62–2.79%. That is wide because errors cluster in a few documents.
- **Target: ~200 pages from ≥120 documents (~50,000 words)**, stratified by decade (pre-1980, 1980–99, 2000+) and
  drawn at random within strata, plus ~50 table regions. At 0.6% that is ~300 errors. With clustering (design
  effect ~4) the 95% interval is about ±0.15 points: enough to tell 0.6% from 0.3%. Comparisons between two systems
  on the *same* pages (paired, bootstrap over documents) are much tighter than that.
- **Per stratum** you need about 30–50 errors to say anything. Rare strata (ﷺ, note numbers, sideways pages) get
  targeted pages on top.
- **How to make it fast**: pre-fill each page with Azure's reading. The owner corrects it in `inkscript check
  --html` (it already exists, experiment 12). Two people (or the owner twice, a week apart) on 10% of pages measure
  the gold's own error. Experiment 12 found 5 of 577 words doubtful even to the owner; the gold set needs an
  "unreadable" mark.
- **Keep it hidden**: never train or tune prompts on the gold pages. Keep a second, untouched slice for the final claim.

## 6. Hardware and cost

**The owner's machine** (16 cores, 15 GB RAM, WSL2, no NVIDIA GPU) can render synthetic data, run the
scorer, run the existing pipeline and run Azure comparisons. It can run a 0.9–2B model on CPU for a few test pages
(expect tens of seconds to minutes a page; measure). It cannot train. 15 GB of system RAM is also too little to
host a training run even with a GPU added. Plan 32–64 GB if a GPU is bought.

**Rent** (section 2.2 prices). For bake-offs and LoRA runs, rent a 24–48 GB card (4090, L40S, A6000) or an A100.
Use Vast.ai or RunPod Community for cheap batch inference, Secure tiers for training runs.

**Buy** (October 2026 prices are inflated by memory shortages; [videocardprices](https://videocardprices.com/compare/nvidia-rtx-5090-vs-nvidia-rtx-pro-6000-blackwell/),
[digitalcitizen](https://www.digitalcitizen.life/nvidia-rtx-pro-6000-blackwell-price-jumps-to-13250-as-memory-shortage-hits-high-end-gpus/)).
**RTX 5090 32 GB: ~$3.7–4.3k**, enough for LoRA on 2–8B. **RTX PRO 6000 96 GB: ~$9.5–16k.** A used 24 GB 3090 or
4090 is the budget option (prices unverified; check sold listings). Break-even against renting a ~$0.5/h card is
~8,000 GPU-hours, roughly a year of continuous use. **Buy only after stage 3 proves the recipe.**

**Throughput and cost for the archive.** Rough sizes: 1,013,912 documents × ~20 pages (experiment 19: 4,737 pages
in 240 documents) ≈ 20M pages; 58% scans ≈ **11.6M pages to read**.

| | pages/hour | $ per 1,000 pages | 11.6M pages |
|---|---|---|---|
| olmOCR 7B, H100 (paper; English pages) | ~15,000 | 0.18 | ~$2.1k |
| PaddleOCR-VL 0.9B, A100 $1.39/h (paper speed on OmniDocBench) | ~5,800 | 0.24 | ~$2.8k |
| same, assuming Arabic pages are 2× slower (denser, more tokens) | ~2,900 | 0.48 | ~$5.6k |
| line-level reading at 300 dpi (more image tokens) | unmeasured; stage 5 measures it | likely 0.3–1.0 | ~$3.5–12k |
| **Azure Read** (third-party listings: $1.50/1k up to 1M, $0.60/1k above; Microsoft's page shows placeholders) | — | 0.6–1.5 | **~$8k** |

Sources: [olmOCR](https://arxiv.org/html/2502.18443v3), [PaddleOCR-VL](https://arxiv.org/html/2510.14528v3),
[Azure listing](https://aiproductivity.ai/pricing/azure-document-intelligence),
[Microsoft Q&A](https://learn.microsoft.com/en-us/answers/a/12439288). Azure has *already* read much of the archive,
so the real comparison is a second reading on top of Azure (paid once, ~$2–6k) against nothing.
**Accuracy, not price, is the case for our own stack.** Plus control: no API change, our own confidence, and
weights fitted to our typefaces.

## 7. What this repo already knows that carries over

| knowledge | where | how it is reused |
|---|---|---|
| **Azure's error rate on our archive**: 1.55% of words on scans [0.62–2.79], printed Arabic 0.61%, pre-2000 2.8% vs 0.65% after; errors by cause | `experiments/19_azure_map/README.md` | **the bar to beat**, per stratum; the strata definitions; the weighting and bootstrap code |
| **Where Azure is weak**: added hamza at 0.99 confidence, ى/ي, ﷺ, superscript note numbers, specks, ornaments, handwriting, Persian code points | 19, 22 | where our reader must win; the bake-off's targeted pages |
| **The calibrated judge** (Gemini Flash screen, Pro confirm; 2% misses on archive prints; $0.0026 a flagged word) | 17, 19, 27 | score models on pages before the gold set is finished; check disagreements; check silver labels. Under the ~$20 cap. |
| **Trust marks** (confidence < 0.8 plus free signals; 4.3–5.3% flagged; 0.42% of unflagged words wrong) and their metric | 22, 27, 30; `src/inkscript/enrich/` | the same metric judges our reader's confidence; the marks absorb our reader's agreement and confidence as new reasons |
| **The Quran check** (387 quotations; 147 corrections written for $0.80) | 20, 27 | exact gold for vowelled lines; an exact test of any reader; a source of silver labels that are actually gold |
| **The pen path and the feeler**: pieces, cuts, 82.6% piece reading | 09, 16 | the piece-count/dot-count consistency check (section 4, item 4); D19: the feeler's job is cuts, not reading. A VLM does not change that. |
| **Restored typefaces of archive books** | 11 | synthetic training data in the archive's own faces |
| **Line and word boxes for every page** (ALTO, `shapes.json`) | 24, 31 | line-level reading and grounding; showing a new reading in `inkscript view` beside Azure's |
| **The owner's hand-marked sheets and `check --html` editor** | 12 | the gold-set tool; the 99.1% "change nothing" baseline idea: any corrector must beat leaving the text alone |
| **Disagreement is not automatically a flag** | D19, 17 | a second reader only helps if it is strong; measure before wiring it in |
| **Born-digital detection** (42% of documents need no OCR) | 19; `born_digital()` | exact training pairs; reading budget only for the 58% |
| **Memory discipline** (watchdog, ≤3–4 workers) | CLAUDE.md | data generation on the owner's machine |

## 8. Open questions for the owner (turning points)

1. Is the goal to **replace** Azure, or to **beat it where it is weak** (old prints, decorative type) and keep it
   elsewhere? The plan works for both; stage 3 decides which is realistic.
2. May a model trained on Mandumah pages be **published** (open weights), or is it internal? This decides whether
   born-digital and silver data can be used.
3. Should **tables and equations** enter scope now (D17 says not yet)? First count how many pages have them.
4. How many hours can go into the gold set? 200 pages at ~10 minutes each, pre-filled, is about 35 hours.

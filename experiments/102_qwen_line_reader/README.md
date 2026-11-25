# Experiment 102 — fine-tune Qwen3.5-4B to read one printed Arabic line (stage 1)

**Status: done (2026-11-25).** M is trained, chosen on DEV, and read once on the exam lines and once on the locked test
(the owner's OK for the third read: "ok for the locked test"). **GPU: $6.36 of $60** in two rentals of one RTX 5090.
Both hosts are destroyed. L was not run: that is the owner's and the lead's decision.

## Verdict

| reader | exam lines (584): letters wrong, folded, no punct (exact) | locked test, strict, mastheads out (lines wrong) | locked, folded |
|---|---|---|---|
| Azure | 0.53% (0.79%) | 1.50% (22.4%) | 0.96% |
| our reader t91 / v7-28M | 0.71% (1.20%), t91; 235 of these lines were in its training | 1.34% (17.5%), v7-28M | 0.95% |
| Qwen3.5-4B untrained (this prompt, line crops) | 4.11% (6.95%) | not read | – |
| **Qwen3.5-4B + LoRA M (200k lines)** | **0.69% (1.01%)** | **2.07% (32.5%)** | **1.50%** |
| OCRia-1 (experiment 100) | 2.5%, read from whole pages, not the same task | – | – |

- **SUCCESS bar** (≤ 1.0% on the exam and ≤ 2.0% on the locked test): **not met, by 0.07 points on the locked test.**
  The exam half passes, and even the STRONG exam half passes (≤ 0.7%). The locked test is at 2.07%, against v7-28M's
  1.34% and Azure's 1.50%.
  - Paired with Azure on the locked lines: +0.58 points (95% CI +0.43 to +0.75).
  - By period, M is behind both in every one (pre-1950 2.84 / 1950–79 1.59 / 1980–99 1.76 / 2000+ 2.19, strict).
  - Titles: 12.6% strict, against v7-28M's 7.5%.
- **Kill rule:** not triggered (0.69% ≤ 1.5%). L is allowed by the rule, but it is held for the owner's decision.
- **The locked estimate is biased against M, by an unknown amount.** The judge never saw M's readings. On only 55% of
  judged lines (folded 65%) is M's reading the truth or a candidate the judge saw; v7 had 83% in experiment 90. A new
  judging round would settle it; there is no money for it in this experiment.
- **Mixed Arabic + Latin lines (a diagnostic found after scoring, not pre-registered).** On the exam's 18 lines with
  a Latin citation inside Arabic, M and Azure both make about 6.7% letters wrong; t91 makes 2.6%.
  - The cause: M learned Azure's way of ordering a Latin run inside an Arabic line, «(2005 ,Adin)» where the settled
    truth has «(Adin, 2005)». The two look the same on screen; they differ in logical order.
  - On the other 566 lines: **M 0.42%, t91 0.62%, Azure 0.25%**.
  - So most of M's exam error is a target convention it copied from Azure, not misreading.

## Question

The owner approved this on 2026-11-24 ("ok lets do that"). Can the open model Qwen3.5-4B (Alibaba, Apache-2.0) learn
to read our printed lines exactly as printed, from our own training lines? We measure it against Azure and against
our own reader t91.

This is stage 1. Stage 2 is a later experiment: the writer (experiments 87 and 95) becomes an automatic reward while
the model learns. Stage 1 therefore works on single lines, because a line is what the writer can judge.

## What training data exists on this server (checked 2026-11-25)

- **Experiment 83's 2.17 M new lines (7,763 documents) are not here.** Experiments 83, 89 and 91 each cut them on a
  rented host from S3 and never brought them back: no crops, and no per-line labels. Only the 444,265 held-aside
  disputes are here (`83_reader_scale/out/held/held_v3.jsonl.gz`), plus the document plan (`docs83.jsonl`,
  `plan83.jsonl`).
- **Experiment 77's lines are here.** That is 513,533 train + 8,198 dev lines from 2,169 documents, and experiment
  80's pull of 231,012 old-print lines from 572 documents.
  - Their manifests (Azure's clean label per line) are in `77_scratch_reader/out/shards/manifest-*.jsonl`.
  - Their 48-px crops are there too: 5.3 GB in 166 files.
  - **The source PDF and Azure JSON of all 2,741 documents are still on disk.** They are scattered across the
    `out/` folders of experiments 19, 28, 33, 34, 39, 43, 52, 70, 74 and 80, and `pages77.jsonl` / `pages80.jsonl`
    list them. Every file was checked for existence; none is missing.
- **The labels t91 trained on are here:**
  - v6r's verdicts on the held disputes: `85_disputes/out/labels/labels_v6r.jsonl`, 444,265 keys (8,012 judged,
    42,280 under rule85, the rest dropped);
  - experiment 91's title overrides: `91_titles/out/host/overrides91.jsonl`, 25,315.
- **The 48-px crops are too small for this model.** Qwen's vision patches are 16 px, and 2 × 2 patches make one
  token. So every crop is re-cut from the local PDFs (`cut102.py`) with experiment 77's geometry at 96 px.
  - Cutting M (200,000 lines, 16,765 pages, 2,416 documents) took **11.5 minutes** on 4 niced workers. Disk use
    stayed at 12–49%.
  - Cutting all of L_local would add about 25 minutes and 7 GB.

### The pool (`pool102.py` → `out/pool/pool102.jsonl.gz`)

752,743 manifest lines. After the rules below, **670,922 lines** are kept, from 2,471 documents and 546 journals:

| Left out | lines |
|---|---|
| exam articles (experiment 97, LOCKED_EVAL: every line of the 60 documents) | 18,879 |
| experiment 100/101 dev-page documents (our own extra caution) | 874 |
| held dispute with no settled label (v6r drop) | 45,964 |
| Azure label with (( or )) (experiment 84's rule: Azure writes (( )) for printed «») | 16,065 |
| title line where catalogue and readers disagree (experiment 91) | 39 |

Experiment 84's locked journals, experiment 88's locked documents and experiment 76's held-out journals were already
absent from these manifests. The guard still checks every key against them.

**Found on the way: t91 has seen part of the exam.** Experiment 77's training pages include 52 of the exam's 59
articles with R1 lines and 69 of its 183 pages. **235 of the 600 exam lines** (the same Azure line id) are in
experiment 77's training manifests, so v1, v3, v7-28M and t91 all trained on them, with Azure's labels.

t91 gains nothing visible from this. On the 228 "seen" lines with a truth it is *worse* (1.05% letters wrong,
folded, punctuation ignored) than on the 356 unseen lines (0.54%); Azure scores 0.45% and 0.57%. Still, the t91
exam baseline is not a clean held-out number. `score102.py` reports every reader on the seen and unseen lines apart.

### What the targets are (rule 3: as printed?)

The model will learn whatever the targets do. In M:

- **Most targets are Azure's line, unfiltered.**
  - 57% of M (`azure_r77`) are experiment 77's lines with Azure's text. No consensus filter was applied; v1, v3,
    v7 and t91 trained on them the same way.
  - 40% (`azure_consensus`) are experiment 80's old-print lines where v1 and Azure read identically.
  - 1.7% have v6r's settled label (judged, or rule85's bare alif). 0.6% are catalogue-matched titles.
  - **Azure's error is therefore in the targets.** On the exam lines Azure is 0.79% letters wrong exact and 0.53%
    folded without punctuation. 9% of the exam lines have at least one Azure error even after folding.
- **Hamza on alif is added where the print has a bare alif.** This is Azure's habit (experiment 85's rule85 audit).
  It is corrected only on the held disputes, not on consensus or r77 lines where Azure is the only witness.
  - On the exam, Azure's spelling-class substitutions are 17 alif-hamza and 3 ى/ي.
  - Expect the model to learn the same habit.
- **Printed vowel marks are often missing.**
  - Experiment 91's eye check: marks missing on 8 of 100 title crops.
  - 9.0% of M's targets carry any mark.
  - Experiment 97's settled exam lines show Azure dropping 9 printed marks and adding 4.
- **The rest:**
  - Tatweel (kashida) is removed by `clean_label`, as in every reader's labels. It is a stretch of the line, not a
    letter, but strictly it is not "as printed".
  - Presentation forms are decomposed, and whitespace is collapsed.
  - Printed «» lines are mostly absent: the lines where Azure wrote (( )) were dropped, so only 1.0% of M's targets
    have «».
  - The digit set is Azure's (Arabic-Indic in 12.5% of lines, Western in 11.5%). Azure keeps the printed set
    (experiment 101: 32/32 number pairs kept). No digit-set faults were seen on the exam.

The exam and the locked test do not inherit these habits: their truths were settled from the image (R1) or by the
judge (experiment 90).

## The sets (`build102.py`, seed 102, pre-registered rules in its docstring)

| set | lines | documents | journals | 2000+ / 1980–99 / 1950–79 / pre-1950 | titles (display) | largest journal share |
|---|---|---|---|---|---|---|
| **S** | 20,000 | 1,593 | 539 | 8,000 / 4,000 / 4,000 / 4,000 | 1,222 (821) | 1.05% |
| **M** | 200,000 | 2,416 | 539 | 80,000 / 40,000 / 40,000 / 40,000 | 1,222 (821) | 1.56% |
| **L_local** | 622,918 | 2,416 | 539 | 339,319 / 94,226 / 127,796 / 61,577 | 1,222 (821) | 5.9% |
| **DEV** | 2,000 | 55 | 35 | 500 each | 0 | 11% |

- **Nested.** S ⊂ M ⊂ L, as prefixes of one order. Within each period the lines are dealt journal by journal in turn,
  then document by document within a journal.
- **Period shares.** S and M are 40% modern and 20% each for the three older periods. The pool itself is 55% modern;
  old print is where readers differ most.
- **Titles.** All catalogue-matched title lines go into S first: 1,222 lines, 821 of them display size.
- **L is short of 1,000,000.** This server holds 622,918 eligible lines. The other **377,082** must come from
  experiment 83's new documents, cut on the host after a re-download from S3.
  - The rule for that is written in `out/sets/L_n83_rule.json`.
  - A line counts as consensus when its key is not in held_v3; v6r and the title overrides apply as for t91.
  - The re-download is S3 egress: about 27.5 GB if every one of the 7,763 documents is fetched, fewer if only the
    needed ones. That is AWS money, outside "no other money", and needs the lead's OK.
  - Without it, L is L_local (0.62 M lines).
- **DEV.**
  - It is made of whole documents that no training set touches:
    - all 40 of experiment 77's dev documents, which no reader has trained on;
    - plus random documents (seed 102) until each period has at least 600 lines and 8 documents.
  - 500 lines are drawn per period, with no title lines.
  - Some added old-print DEV documents were in t91's training (experiment 80's pull), so DEV is for choosing our
    settings, not for comparing with t91.
- **Manifests** (ids and labels, no images): `out/sets/{S,M,L_local,L_rest,dev,exam}.jsonl` and
  `sets102_summary.json`. `L_rest` is L_local − M, the lines still to cut and upload if L runs.

## The task

One line image in; the line's text out, and nothing else.

- **System prompt.** Ours, in plain English: `prompts/system102.txt`.

  ```
  You read one line of printed text cut from a scanned page. Write the text of that line exactly as printed, and nothing else.
  Copy every letter as printed: do not correct spelling, do not add or remove hamza, keep ى and ي, ة and ه as printed, and write vowel marks only where they are printed.
  Keep numbers in the digits printed (Arabic-Indic or Western), and keep punctuation and brackets as printed.
  If the line mixes Arabic and another script, write it in reading order.
  Do not translate, explain, complete or repeat anything: write only what is on the line.
  ```

- **User turn:** the image, then `Read this line.`
- **Thinking is off.** The chat template is called with `enable_thinking=False`, which ends the prompt with
  `<think>\n\n</think>\n\n`. This is the same as ms-swift's `--add_non_thinking_prefix` and the same prompt vLLM
  gets.
- **Answer:** the text, then `<|im_end|>`.
- **The image** (`cut102.model_image`):
  - experiment 77's crop geometry: Azure's polygon turned upright, padded 0.22 × the line height above and below and
    0.35 × at the ends, from a 250-dpi render;
  - stored at 96 px high and resized to H, where H is 96 or 64 (the zero-shot rule below picks it);
  - padded with white on the left to a width that is a multiple of 32 and at least 65,536 / H, so that both
    Transformers' and vLLM's `smart_resize` leave it untouched. 65,536 is the checkpoint's `min_pixels`, from
    `preprocessor_config.json` `shortest_edge`.
  - The body text is then about 67 px high at H = 96, or 44 px at H = 64: 4 or 3 patches.
  - The contact sheet `out/look/sample_crops.png` was looked at.
- **Tokens, measured with the real tokenizer** on 200 DEV lines at H = 96:

  | part | median | mean | max |
  |---|---|---|---|
  | image tokens | 102 | 104 | 282 |
  | at H = 64 | 64 | 67 | – |
  | prompt incl. image (system prompt 154 tokens with the template) | 255 | 257 | 435 |
  | answer | 17 | 17 | 42 |

  So an example is **about 272 tokens**. Arabic takes about 3 characters a token.

## The recipe

Sources, read 2026-11-24/25:

- the [Qwen3.5-4B model card](https://huggingface.co/Qwen/Qwen3.5-4B) (commit `851bf6e8…`, saved in experiment 101's
  `card/`);
- the [Qwen3.5 repository](https://github.com/QwenLM/Qwen3.5). Its fine-tuning section only points to Unsloth,
  ms-swift and LLaMA-Factory;
- [ms-swift's Qwen3.5 best practice](https://swift.readthedocs.io/en/v4.4/BestPractices/Qwen3_5-Best-Practice.html).
  Its dense example is Qwen3.5-4B LoRA: rank 8, alpha 32, all-linear, lr 1e-4, warm-up 5%, bf16, 1 epoch;
  `IMAGE_MAX_TOKEN_NUM=1024`, `--add_non_thinking_prefix true`; 4 × 20 GiB; `transformers>=5.9`,
  `flash-linear-attention>=0.4.2`, causal-conv1d; `freeze_vit` left at its default (true);
- [Transformers' Qwen3.5 page](https://huggingface.co/docs/transformers/main/en/model_doc/qwen3_5): the Gated DeltaNet
  layers need `fla` and `causal_conv1d`, otherwise "silently falls back to slower and more memory hungry PyTorch ops";
- [vLLM's supported-models table](https://docs.vllm.ai/en/latest/models/supported_models.html):
  `Qwen3_5ForConditionalGeneration` supports LoRA on the language backbone;
- [OCRia-1 (arXiv 2611.00092)](https://arxiv.org/html/2611.00092v2), for the recipe only:
  - full fine-tune of Qwen3.5-4B, AdamW peak 1e-5, cosine, 3% warm-up, global batch 64, 2 epochs, bf16;
  - pages at 1,024 px long side, 101k pages;
  - its note: "fine-tuning changed the vision side little";
  - looping was fixed only in its RL stage, with a repetition penalty.

**Ours, in five lines:**

1. **LoRA on the language model only.** It covers every Linear layer under `model.language_model`: the attention
   q/k/v/o, the Gated DeltaNet `in_proj_qkv/z/a/b` and `out_proj`, and the MLP. The settings are **rank 32, alpha
   64**, dropout 0.05: about 65 M trainable parameters, an adapter of about 0.26 GB. The vision tower and merger stay
   frozen. Why:
   - ms-swift's default, and OCRia-1 saw little change on the vision side;
   - vLLM serves this LoRA directly.

   Rank 32 rather than ms-swift's 8, because reading a new script exactly is a skill, not a style.
2. **bf16 base, fp32 adapter.** No QLoRA: the 4B fits in bf16 (9.3 GB). AdamW at **lr 1e-4**, cosine schedule, 3%
   warm-up, weight decay 0, gradient clip 1.0. Each step is 16 lines × 4 accumulations = **64 lines**. Gradient
   checkpointing is on. The loss is on the answer tokens only, and logits are computed only at those positions.
3. **Epochs:** S 1, M 1, L 1. Checkpoints every 50 steps for S (about 6) and every 500 for M (about 7).
   `run_*/last/` allows a resume at the same place in the same order.
4. **Pinned versions** (one venv on the host; every one at least 8 days old):
   - vllm 0.34.0, which brings torch 2.14.0 for CUDA 13.0 and caps transformers below 5.23;
   - transformers 5.22.2, peft 0.21.2, accelerate 1.15.0;
   - flash-linear-attention 0.6.0, causal-conv1d 1.7.0 (built with nvcc 13.0);
   - Python 3.12, `cuda-toolkit 13.0.3` plus NVIDIA's apt CUDA 13.0, as in experiment 101.

   The CPU dry run here used torch 2.14.0+cpu, transformers 5.22.2 and peft 0.21.2.
5. **Inference:** vLLM offline engine, greedy, max 256 new tokens, no repetition penalty, LoRA swapped per request.
   If vLLM refuses the Gated DeltaNet LoRA targets, the fallback is coded: each adapter is merged with PEFT and
   served as a plain model.

**What fits a 32 GB RTX 5090.**
- Weights: 9.3 GB.
- LoRA with Adam state: about 0.8 GB.
- Activations at 16 × 272 tokens with checkpointing: a few GB.
- The full-vocabulary logits, which would be about 4 GB in fp32, are avoided by computing them at the answer
  positions only.
- Expected peak: about 16–20 GB. ms-swift reports 20 GiB per GPU at batch 4 × max length 2048, without our logits
  trick.

## The estimate (before renting)

**Throughput is the unknown.** By arithmetic:
- forward, backward and the checkpoint recompute cost about 6 × 4.2 B parameters × 272 tokens ≈ 7 TFLOP per line;
- the 5090 sustains roughly 35–70 TFLOPS in bf16 at a realistic 30–35% utilisation;
- so **5–10 lines a second**, if the fla / causal-conv1d kernels are in. The plan uses **8 lines/s**.
- The real figure is printed in `train_log.jsonl` (`lines_per_s`) within the first minutes of S. M and L are
  re-estimated from it before they start.

Price: about $1 an hour. The 5090 has been $0.65–1.12 in experiments 83–101.

| step | hours at 8 lines/s | at 5 lines/s |
|---|---|---|
| boot, venv + causal-conv1d build, weights 9.3 GB, upload of S/M/DEV/exam (3.38 GB at 3–8 MB/s) | 0.75 | 0.75 |
| zero-shot: DEV at H = 96 and 64 (2 × 2,000 lines, two engine starts) | 0.25 | 0.25 |
| **S**: 20,000 lines × 1 epoch = 313 steps | 0.7 | 1.1 |
| S checkpoints on DEV (about 6 × 2,000 lines) | 0.15 | 0.15 |
| **M**: 200,000 × 1 epoch = 3,125 steps | 6.9 | 11.1 |
| M checkpoints on DEV (about 7 × 2,000) | 0.15 | 0.15 |
| finals: base + M on exam (600) and locked (about 29,000 lines), speed test (5,000) | 0.4 | 0.5 |
| fetch, verify, idle margins | 0.3 | 0.3 |
| **S + M** | **≈ 9.6 h ≈ $10** | **≈ 14.3 h ≈ $14** |
| **L** (1,000,000 × 1 epoch, 15,625 steps), if allowed | 35 h ≈ $35 | 56 h ≈ $56 |
| L as L_local only (622,918) | 22 h ≈ $22 | 35 h ≈ $35 |

**Money rule for L** (pre-registered): L runs only if M passes the kill rule below, and the spend so far plus L's cost
at the speed measured on M stays at or under $55. That leaves $5 for the finals.

At 5 lines/s the full L does not fit. L_local fits only if S + M cost under about $20.

## The exam and the bars (pre-registered 2026-11-25, before any model output)

**Measures.**

1. **The exam: experiment 97's R1 reading.** The model reads the 584 lines that have a truth.
   - Score: experiment 99's `r1_truth` / `r1_rates`, imported unchanged, through `score102.py exam`. The headline is
     **letters wrong, folded, punctuation ignored**; exact is also given.
   - The crops come from the exam's own page images and Azure's boxes (`cut102.py exam`, `out/crops_exam/`), with
     the training geometry.

   Baselines through the same count (`out/scores/exam_azure.json`, `exam_t91.json`). Letters wrong, folded and
   punctuation ignored:

   | reader | all lines (exact in brackets) | on the 356 lines t91 never saw | on the 228 lines it saw |
   |---|---|---|---|
   | Azure | **0.53%** (0.79%) | 0.57% | 0.45% |
   | t91 | **0.71%** (1.20%) | 0.54% | 1.05% |
   | OCRia-1 (experiment 100, page level) | 2.5% | – | – |

   - **How to quote t91 on this exam:** 0.71% on 584 lines, of which 235 were in its training (experiment 77's
     pages, Azure-labelled). It reads them no better (1.05% on those, 0.54% on the rest), but the figure is not a
     clean held-out number.
   - The brief's figures, 0.6% (0.8%) and 0.7% (1.3%), are score97's estimate; the direct count is used here.
   - Experiment 101 read whole pages; its result is not in yet. A page-level reading is not comparable to a
     line-level one anyway.
   - **The zero-shot arm.** The untrained Qwen3.5-4B reads the same line crops with the same prompt. That is this
     experiment's true starting point.
2. **The locked test of experiment 90.** It holds about 29,000 lines: the 20 locked journals and the 280 locked
   old-print documents.
   - It is scored exactly as experiment 90 scored v7-28M and Azure: `est90.run`, imported, with the new reading
     added as one more reader, through `score102.py locked`.
   - The headline is **strict letters wrong, mastheads out**. Folded, lines wrong, by era (pre-1950 / 1950–79 /
     1980–99 / 2000+), by set and titles are given too.
   - Baselines: v7-28M **1.34%**, Azure **1.50%**; lines wrong 17.5% and 22.4%.
   - Like experiment 90's v7, the model's readings were never shown to the judge. Where it reads something no
     candidate had, the line counts against it; coverage is reported.
   - **This needs the owner's OK for a third read of the locked set**: experiment 90 was the first read, experiment
     91's titles the second. `cut102.py locked` refuses to run without `LOCKED_OK102=1`.

**Order of runs.**

- **Zero-shot base on DEV at H = 96 and H = 64.** **Height rule:** H = 64 unless H = 96 is better by more than 0.3
  points of letters wrong (DEV, folded, punctuation ignored). Write the choice here, and into `/work/H`.
- **S.**
  - **Checkpoint rule:** the lowest DEV letters wrong. Any checkpoint within 0.05 points of it counts as tied, and
    the latest of the tied is taken.
  - **Smoke test:** S passes if its chosen checkpoint's DEV letters wrong is **≤ 0.7 × the zero-shot DEV figure**,
    with no more loop lines than zero-shot. Otherwise stop and report.
- **M**, trained from the base, not from S. The same checkpoint rule.
- **Finals, once for each model, at the end.** The zero-shot arm and the chosen M checkpoint are scored on the exam
  and the locked test. Nothing is tuned on either.
- **Kill rule:** if M is still **above 1.5%** on the exam lines, L is not run; report.
- **L** only if the kill rule and the money rule both allow it. Its finals are scored once, the same way.

**Bars for stage 1.**

- **SUCCESS:** the fine-tuned model is at **≤ 1.0%** letters wrong on the exam lines (folded, punctuation ignored)
  **and ≤ 2.0%** on the locked test (strict, mastheads out).
- **STRONG:** it matches our reader: **≤ 0.7%** on the exam lines **and ≤ 1.34%** on the locked test. (On the exam
  t91's own figure is 0.71% through this count, partly on lines it trained on.)
- **Also reported, for stage 2 and for trust** (`score102.py`; every definition is in its docstring, fixed before any
  output):
  - invented text: words per 100, and lines with 2+ invented words in a row or 30%+ too long;
  - dropped words: per 100, and lines with 2+ in a row;
  - repeated loops: hit the token limit, or a 1–4-word n-gram repeated 3+ times that is not in the truth;
  - digits changed to another digit set;
  - "spelling" substitutions inside hamza-alif, hamza seats, ى/ي and ة/ه (both directions);
  - vowel marks added or dropped;
  - speed in lines per second (eval102's summary) and **cost per million lines** = $/h ÷ (lines/s × 3,600) × 10⁶.
- **Baseline faults on the exam:**

  | reader | invented words per 100 (lines) | dropped words per 100 (lines) | loops | digit set | spelling lines (alif-hamza, ى/ي) | marks added / dropped |
  |---|---|---|---|---|---|---|
  | Azure | 0.70 (2) | 0.23 (1) | 0 | 0 | 19 (17, 3) | 4 / 9 |
  | t91 | 0.38 (2) | 0.65 (3) | 0 | 0 | 11 (9, 3) | 9 / 18 |

## Self-test (2026-11-25, no GPU)

- **The lock.** The test is `selftest102.py lock` → `out/selftest/lock.json`.
  - One line was planted at a time, each from a different forbidden source:
    - an exam article;
    - a locked journal (experiment 84);
    - a locked old-print document (experiment 88);
    - a held-out journal (experiment 76).
  - The builder refused every one of them, and so did the trainer's own check against `forbidden102.json`.
  - The builder also refused a label marked as OCRia-1 output.
  - A clean sample builds. The real S, M, L_local and DEV pass both checks (845,918 keys in all).
- **The scorer, on fake exam outputs** (`selftest102.py faults` → `out/selftest/faults.json`). Each fault was planted
  on its own tenth of the 584 lines.

  | variant | letters wrong (folded, no punct) | invented lines | dropped lines | loop lines | digit-set lines | spelling lines | marks added |
  |---|---|---|---|---|---|---|---|
  | perfect | 0.00% | 0 | 0 | 0 | 0 | 0 | 0 |
  | invent (+3 words) | 3.37% | **59** | 0 | 0 | 0 | 0 | 0 |
  | drop (2 words) | 1.84% | 0 | **40** | 0 | 0 | 0 | 0 |
  | loop (last word × 4; half stopped by the limit) | 5.63% | 0 | 0 | **59** | 0 | 0 | 0 |
  | digits (set swapped) | 0.00% | 0 | 0 | 0 | **28** | 0 | 0 |
  | spelling (أ→ا, ى→ي, ة→ه) | 0.18% | 0 | 0 | 0 | 0 | **28** | 0 |
  | marks (a fatha added) | 0.00% | 0 | 0 | 0 | 0 | 0 | **36** |
  | all at once | 11.0% | 59 | 40 | 59 | 28 | 28 | 36 |

  Every fault lands in its own measure. Folding hides the digit set and the marks, as it should; the fault columns
  show them. Only lines with at least 5 words had words dropped.
- **The locked scorer** (`selftest102.py locked`). With v7-28M's own readings given as the new reader, it reproduces
  experiment 90's `est90.json` exactly:
  - strict 1.340% against Azure 1.496%;
  - lines 17.54%;
  - folded 0.954%;
  - every era identical.
- **The trainer, dry run on the CPU** (own venv `out/venv`, 1.2 GB):
  - The run used the real tokenizer and processor of Qwen3.5-4B (8 small files, 22 MB, in `out/tok`; **no
    weights**), with a tiny random model built from the 4B's config: 4 text layers, 3 of them Gated DeltaNet and 1
    full attention, and a 2-layer vision tower. Data: 50 DEV lines, 2 steps of 8.
  - The guard checked 58 keys.
  - LoRA was attached to 31 language-model Linear layers. The names came out right (`linear_attn.in_proj_qkv/z/a/b`,
    `out_proj`, `self_attn.q/k/v/o_proj`, `mlp.*`) and nothing went to the vision tower.
  - The loss started at 12.40 (ln of the 248k vocabulary = 12.42). The fast answer-only loss equals the model's own
    loss to 4 decimals (12.4047 / 12.4334 both ways).
  - Checkpoints saved. A stop after step 1 resumed at step 2 with the same loss as the uninterrupted run.
  - Commands:

    ```
    out/venv/bin/python train102.py --dry_run 50 --tiny_config ../101_qwen_base_exam/card/config_4B.json --model out/tok \
      --set out/selftest/dry50.jsonl --crops out/crops_dev --dev out/sets/dev.jsonl --dev_crops out/crops_dev \
      --dev_loss_n 8 --out out/selftest/dry_run --save_every 1 --micro 4 --accum 2      [--slow_loss | --max_steps 1]
    ```

  - Not testable here: vLLM (`eval102.py`) needs the GPU. Its request is the trainer's prompt; the first zero-shot
    run on the host is its test.

## Open questions (need the GPU or the lead)

1. **Speed:** 5–10 lines/s is arithmetic, not a measurement. It decides whether L fits.
2. **Does the causal-conv1d build succeed** on the host? If it does not, Transformers uses the slow PyTorch path; the
   failure is logged and the run continues.
3. **Does vLLM 0.34 take LoRA on the Gated DeltaNet projections?** The merge fallback is coded.
4. **L's missing 377k lines need S3 egress** (lead). Otherwise L is L_local.
5. **The owner's OK for the third read of the locked set.**
6. **Exam crops vs training crops.** Exam crops are cut from the exam's page JPEGs with upright boxes; training crops
   come from PDF renders with Azure's tilted polygons. Both use the same padding and scale. Zero-shot DEV against
   zero-shot exam will show whether the difference matters.
7. **Unfiltered targets.** About 57% of M's targets are unfiltered Azure (r77). If M stalls near Azure's error, a
   consensus filter by t91 is cheap on the CPU (about 1 hour for M), but weak: t91 trained on those labels.
8. **Vision tower.** It stays frozen. A vision-LoRA arm only if S/M errors are about fine marks and dots, and money
   allows.
9. **experiments/README.md has no line for this experiment yet.** Left to the lead: experiment 101 may still be
   editing that index.

## PHASE B, part 1 (2026-11-24 23:46 – 2026-11-25 00:44 UTC): zero-shot and S

One RTX 5090 32 GB (Vast 62430083, datacentre, $1.001/h, 128 CPUs, 5.6 MB/s up). It ran for 58 minutes and cost
**$0.975**. It was destroyed after the adapters and logs were verified on this server; no instance is left.

**Set-up.** Everything installed as pinned. `causal-conv1d` 1.7.0 built in 8 min 19 s; `fla` and `causal_conv1d`
imported OK. The weights' sha256 matched. Fixes found:
- The weights download ran in parallel with the build, and zero-shot ran as soon as vLLM was in (it does not need
  causal-conv1d).
- S was trained from its own 0.34 GB of shards (`out/crops_S/`, `CROPS=crops/S`), so the 3.3 GB of M was never
  uploaded in this session.
- `host102.sh` now takes `CROPS`.
- `host102.sh` must not be overwritten while it runs: an scp rewrite of it during `all` was harmless here, but it is a
  risk.
- `gs102.py follow` exits between jobs, so restart it for each job, or the 20-minute idle keeper counts.

**Height rule (zero-shot DEV):** H = 96 gives 5.67% letters wrong (folded, punctuation ignored) and H = 64 gives
8.51%. 96 is better by 2.8 points, so **H = 96**.

**Zero-shot (untrained Qwen3.5-4B, our prompt, line crops, H = 96):**

| | letters wrong, folded, no punct | folded | exact | lines wrong |
|---|---|---|---|---|
| DEV (2,000, Azure-derived labels) | 5.67% | 6.48% | 7.32% | 1,215 |
| DEV by period: 2000+ / 1980–99 / 1950–79 / pre-1950 | 2.9 / 6.4 / 6.1 / 7.7% | | | |
| **exam lines (584; its one base reading)** | **4.11%** | 6.57% | 6.95% | 236 |
| exam, Azure (same count) | 0.53% | 0.71% | 0.79% | 53 |
| exam, t91 (same count) | 0.71% | 1.10% | 1.20% | 49 |

Faults of the zero-shot model on the exam:
- invented: 7.4 words per 100, 13 lines;
- dropped: 1.3 words per 100, 5 lines;
- 1 loop;
- digit set changed in 4 lines;
- spelling-class substitutions in 44 lines (ى/ي 34, alif-hamza 18, ة/ه 8);
- marks dropped 53, added 13.

**S** (20,000 lines, 1 epoch, 312 steps of 64; `out/host_S/train_log_S.jsonl`). The training loss fell from 0.42 to
about 0.22. The DEV loss (256 lines) by checkpoint:

| step | 50 | 100 | 150 | 200 | 250 | 312 |
|---|---|---|---|---|---|---|
| DEV loss | 0.115 | 0.097 | 0.093 | 0.087 | 0.084 | – |

**S's checkpoints on DEV** (vLLM, LoRA served directly, `out/scores/dev_S_*.json`):

| step | folded, no punct | exact | lines wrong | 2000+ | 1980–99 | 1950–79 | pre-1950 | loops | spelling lines |
|---|---|---|---|---|---|---|---|---|---|
| 0 (zero-shot) | 5.67% | 7.32% | 1,215 | 2.93 | 6.40 | 6.10 | 7.74 | 3 | – |
| 50 | 2.93% | 3.62% | 927 | 0.76 | 3.09 | 4.23 | 3.94 | 2 | 194 |
| 100 | 2.49% | 3.14% | 888 | 0.51 | 2.93 | 3.37 | 3.49 | 0 | 177 |
| 150 | 3.17% | 3.81% | 838 | 0.53 | 7.05 | 2.72 | 3.03 | 2 | 155 |
| 200 | 2.17% | 2.78% | 798 | 0.48 | 3.04 | 2.65 | 2.80 | 0 | 150 |
| 250 | 2.14% | 2.74% | 814 | 0.40 | 2.98 | 2.59 | 2.90 | 0 | 156 |
| 300 | 2.11% | 2.71% | 808 | 0.35 | 2.98 | 2.57 | 2.85 | 0 | 154 |
| **312** | **2.10%** | 2.70% | 802 | 0.35 | 2.96 | 2.56 | 2.83 | 0 | 156 |

- **Chosen by the rule: ckpt-312.** It is the lowest; 300 is within 0.05 points, and the rule takes the latest of
  the tied.
- **Smoke rule: PASS.** 2.10% is 0.37 × zero-shot (the bar is 0.7 ×), and it has 0 loop lines against 3.
- The 1980–99 jump at step 150 is one line with long invented or dropped text. It is gone from step 200 on.
- **DEV's truth is Azure's label, so DEV error includes Azure's own errors.** The spelling-class "errors" at step
  312 (118 alif-hamza, 37 ى/ي) are where the model and Azure's label disagree. This is not the exam's settled
  truth, so DEV is for choosing the checkpoint, not for a level.
- **The exam and the locked test were not read with S** (S is a smoke test).
- **Adapters brought home.** `out/weights/S/ckpt-300` and `ckpt-312` (248 MB each). Their sha256 matches the host
  (`6900e4e8…`, `5f223221…`). The logs, DEV and exam readings are in `out/host_S/` and `out/eval/`.

**Measured speed.**
- **Training:** 11.4–11.6 lines/s steady (10.7 lines/s over the whole run, including saves and DEV loss), about 2,950
  tokens/s.
- **Memory:** peak allocated 14.0 GB (16.3 GB on the card), GPU use 99%.
- **Serving** (vLLM offline, greedy, LoRA): 59–62 lines/s for the base and every adapter. That is about **$4.6 per
  million lines** at $1/h, before any serving tuning.
- **vLLM 0.34 serves the language-model LoRA, including the Gated DeltaNet projections, with no merge.**

**Corrected estimate** (10.7 lines/s, $1.00/h):

| run | training | whole session (set-up 0.2 h with M's upload overlapping, DEV checkpoints 0.1 h, finals incl. locked 0.25 h) | $ |
|---|---|---|---|
| M (200,000 × 1 epoch) | 5.2 h | **about 5.8 h** | about $6 |
| L_local (622,918 × 1 epoch, the lead's decision) | 16.2 h | about 17 h | about $17 |

- **M is right at the 6-hour guard** (`ops/vast_guard.sh`, MAX_MIN 360). Either lengthen the guard to 8 hours for that
  rental, or run M across two rentals. `train102.py` resumes from `run_M/last/`, which the monitor mirrors every 10
  minutes: upload it into `/work/run_M/last/` on the second host.
- L_local needs three rentals under the 6-hour guard, or a longer guard.
- Money is no problem: $0.98 spent, $60 cap.

**Owner's decisions (2026-11-24, relayed by the lead): "yes lengthen the guard and ok for the locked test".**
- The guard now allows 14 hours (MAX_MIN 840), so M runs in one session.
- The locked test is read once, at the end, for the final trained model only (`LOCKED_OK102=1`). It is never read for
  S or for choosing anything.

**PHASE B part 2 sequence (new host):**
1. Upload M's crops first (3.26 GB, about 10 min at 5.6 MB/s), in parallel with `host102.sh all`.
2. Upload sets, dev and exam.
3. Train M: `echo 96 > /work/H; bash host102.sh train M sets/M.jsonl 1 500` (CROPS defaults to crops/M).
4. `devckpts M`, then choose by the rule.
5. Here: `LOCKED_OK102=1 cut102.py locked out/crops_locked`; upload it with `sets/locked.jsonl`.
6. `final M <ckpt>` (exam + locked) and `speed`.
7. Fetch and verify, then stop.

The zero-shot arm's locked read is part of the same final read if the lead counts the base model as a final model.
Otherwise the base is scored on the exam only (done).

## PHASE B, part 2 (2026-11-25 00:46–06:12 UTC): M, the final readings

One RTX 5090 32 GB (Vast 62437133, $1.001/h, datacentre), $5.38. It was destroyed after every output was verified
here: adapter sha256 `c08181c9…` matches the host's, and the exam / locked reading files' md5 match.

**Set-up:** 10 min. M's 3.26 GB upload overlapped the causal-conv1d build, at 16 MB/s.

**One fix found:** `host102.sh` counted CPUs with `nproc` after exporting `OMP_NUM_THREADS=2`, and GNU nproc obeys
that variable, so the data loader got 2 workers on a 128-CPU host. Speed did not suffer (GPU at 99%). Fixed for next
time: `OMP_NUM_THREADS= nproc --all`.

**M** (200,000 lines, 1 epoch, 3,125 steps, from the base model).
- Training ran 4 h 47 min at **11.6 lines/s**; peak memory 14.0 GB.
- Training loss went from about 0.42 to 0.07–0.15.
- DEV loss: 0.067 (step 500), 0.061, 0.051, 0.047, 0.044 (step 2,500).

**M's checkpoints on DEV** (letters wrong, folded, punctuation ignored; `out/scores/dev_M_*.json`):

| step | 500 | 1,000 | 1,500 | 2,000 | 2,500 | 3,000 | **3,125** |
|---|---|---|---|---|---|---|---|
| all | 2.39% | 1.52% | 1.35% | 1.27% | 1.23% | 1.23% | **1.22%** |
| 2000+ | 0.29 | 0.21 | 0.21 | 0.17 | 0.16 | 0.13 | 0.13 |
| 1980–99 | 4.76 | 2.04 | 1.85 | 1.88 | 1.77 | 1.81 | 1.80 |
| 1950–79 | 2.36 | 2.08 | 1.83 | 1.72 | 1.66 | 1.74 | 1.72 |
| pre-1950 | 2.62 | 1.96 | 1.69 | 1.52 | 1.51 | 1.41 | 1.42 |
| lines wrong | 724 | 629 | 558 | 541 | 506 | 496 | 496 |

- **Chosen by the rule: ckpt-3125** (`out/M_choice.txt`, written before the final readings). Steps 2,500 and 3,000
  are within 0.05 points; the rule takes the latest.
- For comparison: S's best was 2.10% and the untrained model 5.67% (`out/pictures/dev_curve.png`).
- The curve still falls at the end: −0.05 points over the last 1,125 steps.

**Final readings, once each, with ckpt-3125.**
- The exam: 600 lines.
- The locked test: 29,388 lines, cut here with `LOCKED_OK102=1` (started 2026-11-25T00:50:49Z), read 05:53–06:05 UTC. Logged in
  `out/LOCKED_READ102.json`: experiment 90 was the first read, experiment 91's titles the second.
- The untrained model and S never read the locked lines.

**Faults on the exam lines** (`score102.py`, definitions fixed before any output):

| reader | invented words per 100 (lines) | dropped words per 100 (lines) | loop lines | digit set changed (lines) | spelling-class substitutions: lines (alif-hamza / ى-ي / ة-ه) | marks added / dropped |
|---|---|---|---|---|---|---|
| Azure | 0.70 (2) | 0.23 (1) | 0 | 0 | 19 (17 / 3 / 0) | 4 / 9 |
| t91 | 0.38 (2) | 0.65 (3) | 0 | 0 | 11 (9 / 3 / 0) | 9 / 18 |
| untrained Qwen | 7.43 (13) | 1.26 (5) | 1 | 4 | 44 (18 / 34 / 8) | 13 / 53 |
| **Qwen + M** | **0.47 (3)** | **0.27 (2)** | **0** | **0** | **17 (11 / 6 / 0)** | **6 / 18** |

Training removed the untrained model's faults: invention, loops, the digit set, and the ى→ي and ة→ه "corrections".
What is left looks like Azure's habits: alif-hamza, printed marks dropped, and the order of Latin runs. That is what
the targets carry (see "What the targets are").

One more fault, seen in the pictures: on a tightly set old page, M also read part of the line above
(0005-012-004-007 p2 l31), because the crop catches it. Azure and t91 did not.

**Speed and cost** (vLLM 0.34 offline, greedy, LoRA served directly, no tuning):
- 57–59 lines/s on the exam, the locked lines and 5,000 pool lines;
- **$4.9 per million lines** at $1.001/h;
- t91 reads on the CPU, so it is not compared here.

**Pictures** (looked at; `out/pictures/`):
- `dev_curve.png`: S and M on DEV, with Azure's and t91's exam levels drawn as reference lines, labelled as a
  different set.
- `exam_strip_right.png`: 8 lines M reads right and the untrained model wrong.
- `exam_strip_worst.png`: M's 8 worst lines.
  - Five of them look identical to the truth when drawn, because they differ only in the logical order of the Latin
    citation (see the Verdict).
  - The other three are real misses: a line above read too, a rotated table label read as another word, and a
    stretched display word «ضمانات» read «معلومات».

## What it changed

- **Qwen3.5-4B learns our lines quickly and cheaply.**
  - The exam goes from 4.1% (untrained) to 0.69% with 200,000 of our lines, for $5.4 of GPU.
  - Loops, invention and spelling "corrections" disappear.
  - It reads 58 lines a second on one rented card.
- **It is not yet better than our reader or Azure on the locked test** (2.07% against 1.34% / 1.50%), with the
  caveat of judge coverage.
- **Its exam error is mostly a habit learned from the targets** (the Latin-run order), not misreading. Before stage 2
  or L, the targets for mixed lines should be put into true logical order. t91's `to_visual` / `from_visual` already
  does this for its own reading.
- **Finding for every reader's exam figure:** t91 trained on 235 of the 600 exam lines (no gain on them). Quote t91's
  exam figure with that note.
- **L** (623k local lines, about 17 h, about $17): the DEV curve still falls slowly (−0.05 points over the last third
  of M), so L would gain little as it stands. Worth it only after the mixed-line targets are fixed, and only with
  the locked test re-judged or a fresh held-out set.

## PHASE B commands (in order)

```
cd /home/appuser/inkscript/experiments/102_qwen_line_reader
python3 gs102.py offers                                     # lead: check the price
python3 gs102.py start RTX_5090                             # lead rents; uploads the code (train/eval/host/data/cut/prompt/forbidden)
python3 gs102.py run 'bash host102.sh all' && python3 gs102.py follow '[h]ost102.sh'     # setup + weights (sha256)
python3 gs102.py upload out/up/sets /work/sets              # meanwhile (another terminal): 4 manifests
python3 gs102.py upload out/up/crops_dev /work/crops/dev
python3 gs102.py upload out/up/crops_exam /work/crops/exam
python3 gs102.py upload out/up/crops_M /work/crops/M        # 3.26 GB
python3 gs102.py run 'bash host102.sh zeroshot' && python3 gs102.py follow '[h]ost102.sh'
# fetch out/eval/dev_base_H*.jsonl; score102.py dev ... --adapter base for each; apply the height rule; write it HERE; then
python3 gs102.py run 'echo <H> > /work/H; bash host102.sh train S sets/S.jsonl 1 50' && python3 gs102.py follow '[h]ost102.sh'
#   (look at lines_per_s in out/train_S.log in the first 10 minutes; re-estimate M and L here)
python3 gs102.py run 'bash host102.sh devckpts S' && python3 gs102.py follow '[h]ost102.sh'
# score each S checkpoint on DEV (score102.py dev out/.../dev_S.jsonl --adapter <path>); smoke rule; then
python3 gs102.py run 'bash host102.sh train M sets/M.jsonl 1 500 && bash host102.sh devckpts M' && python3 gs102.py follow '[h]ost102.sh'
# choose M's checkpoint on DEV (rule above); then, with the owner's OK for the locked read (LOCKED_OK102=1 cut102.py locked
# out/crops_locked here, then upload out/sets/locked.jsonl and the crops to /work/sets, /work/crops/locked):
python3 gs102.py run 'bash host102.sh base_final && bash host102.sh final M /work/run_M/ckpt-<N> && bash host102.sh speed M /work/run_M/ckpt-<N>'
# fetch; score102.py exam / locked for base and M; kill rule; money rule; L or stop:
python3 gs102.py stop 'exp 102: M scored'
# the chosen adapter comes home in the monitor's copy of /work/out/weights/ -> out/weights/ (never uploaded anywhere)
```

## Files

- `guard102.py`: the data guard; `python3 guard102.py export` writes `forbidden102.json` for the host.
- `pool102.py`: the local pool with t91's labels.
- `build102.py`: S / M / L / DEV, with the refusal built in.
- `cut102.py`: crops (`sets`, `exam`, `locked`) and `model_image`.
- `data102.py`: the prompt, the tar reader and the manifests.
- `train102.py`: LoRA training (resumable; `--dry_run` on the CPU).
- `eval102.py`: vLLM reading (LoRA or merged).
- `score102.py`: `exam`, `dev`, `locked` and `baselines`, with the fault measures.
- `selftest102.py`: `lock`, `faults` and `locked`.
- `host102.sh`: the host side.
- `gs102.py`: the GPU session ($60 cap, 150 GB, at least 12 CPUs and 64 GB RAM, CUDA 13, idle limit 20 minutes).
- `prompts/system102.txt`: the system prompt.
- `pictures102.py`: the owner's pictures (`curve`, `strip`).
- `out/` (gitignored, private):
  - `pool/`, `sets/`;
  - `crops_M/` (42 tars, 3.26 GB), `crops_dev/` (33 MB), `crops_exam/` (11 MB);
  - `up/` (symlinks, **3.38 GB** to upload for S + M + DEV + exam);
  - `scores/`, `selftest/`, `look/`;
  - `venv/`, `tok/` (tokenizer files only);
  - later `gpu/`, `eval/`, `weights/`.

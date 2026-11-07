# Experiment 77: our own Arabic line reader, trained from scratch

**Question (owner, 2026-11-04).** Can a narrow line reader trained only on our own Mandumah pages, with every weight
ours (no pretrained model anywhere), get close to Azure? And can Gemini, instead of the owner, act as the judge of
the lines where our reader and Azure disagree, so that the second round learns from better labels? Caps: **$20 GPU
(Vast) and $20 Gemini**. A conditional $40 more for Gemini was approved later, for use only if v2 beat v1. It did not,
so none of it was spent.

**Status: done, stopped and reported (2026-11-04/05).** v1, v2, v2b (with experiment 80's old print) and a size
sweep (2M / 8M / 28M) were run; nothing was scaled up.

## Summary

1. **Our own reader gets close to Azure, but not past it.** It is an 8.3 M-parameter CRNN with every weight trained
   from zero on 514k of our lines (42 minutes on one RTX 5090).
   - **On the owner's 20 checked pages:** 0.75% of letters wrong and 1.92% of words, against Azure's 0.60% and
     1.42% (Argon 0.52% and 1.05%).
   - **On lab documents 1–2:** 0.20% of letters, Azure 0.23%. On document 1 alone it makes fewer letter errors than
     Azure (0.14% against 0.21%).
   - **Caveat:** the owner's truths were corrected from Azure's drafts, which flatters Azure.
2. **Gemini as the judge (5,226 disputed lines, $19.09).** Where v1 and Azure disagree, v1 was right 45% of the
   time, Azure 26%, both were wrong 26%, and 2% were unreadable. **About three in four of Azure's labels on a
   disputed line are wrong.** Most of what v1 wins on is marks and letter forms: missing shadda and fatha, Azure's
   Persian ی, and ة against ه.
3. **v2 (judged labels, unjudged disputes dropped) did not beat v1** on the held-out truths: 0.78% / 1.98% against
   0.75% / 1.92% on the yardstick, and 0.26% / 1.97% against 0.20% / 1.50% on lab docs 1–2. Per the owner's
   condition, **the extra $40 of judging was not spent.**
4. **v2b = v2 + experiment 80's old print** adds 178k lines (1924–1999) where v1 and Azure agree. It is **the best of
   ours**: 0.74% / 1.84% on the yardstick. It gains most where the extra lines are, on pre-1950 print (0.24% of
   letters against v1's 0.30%) and on 2000+ print (0.28% against 0.32%).
5. **Size sweep (same recipe, v2 labels, 16 epochs).** 2.1 M parameters: 0.88% / 2.47%. 8.3 M: 0.78% / 1.98%.
   28.2 M: 0.77% / 2.00%. **Bigger does not help at half a million lines; 2M is clearly worse.**
6. **Speed.** 8.3 M reads about 3,100 lines a second on an RTX 5090 (6,500 a second over the 514k training lines),
   and about 23 a second on 4 CPU threads. 2.1 M reads 67 and 28.2 M 10 a second on CPU.
7. **Spend:** GPU **$9.51** of $20 in 6 rentals; Gemini **$19.09** of $20.

## Method

**Data (step 1).** The source is experiment 76's inventory: 2,315 articles with Azure JSON and a scan PDF on disk.
- **Held out.** The 27 held-out journal codes of `76_finetune_pilot/out/split76.json` are excluded entirely. A check
  in code finds none of them in the training or dev manifests.
- **Training set.** Every pre-2000 page (old print is scarce), then modern pages at random (seed 77) up to about
  520k Azure lines, with no journal over 38k lines.
- **Dev set.** 40 more articles, from journals seen in training, are held back as a held-in dev set (156 pages,
  8,198 lines).
- **Cutting a line.** Each line is cut from a pypdfium2 5.12.1 render at 250 dpi using Azure's 4-point polygon.
  The polygon is turned upright and padded by 22% of the line height above and below (so dots and marks survive)
  and by 35% at the ends. The crop is scaled to **48 px high** and stored as grey JPEG q80 in tar shards (`build77.py`).
- **Lines left out of training** (1.2%): lines tilted more than 8° (6,349, mostly table and vertical text), tiny
  ones (129) and empty ones (3). Test lines are all cut.
- **Label.** Azure's text in the scorer's `faithful` form: NFC, presentation forms decomposed, tatweel removed.
- **What was used:** **513,533 lines, 10,567 pages, 1,916 articles, 379 journals.** Of these, **135,583 lines on
  3,276 pages are pre-2000**: 26% of lines, against 6% in what is on disk. That is 3.4 GB of shards.
- **Cost on this machine.** Peak memory was 178 MB per worker. The build ran with 2 workers at nice 19 / ionice idle
  (the lead's rule for the shared box, after a first 4-worker start pushed the load to 55; stopped by PID and
  restarted), under this folder's own memory watchdog `watch77.sh`. The rule is the one in
  `experiments/09_pen_path/watchdog.sh`, which only watches `inkscript native` runs.

**Right to left.** The crop is flipped left to right before it reaches the network, so the network reads from the
line's right end, which is Arabic logical order.
- **Runs printed left to right** (Latin words, numbers such as «2023/11/04» and «3.5%») would then appear reversed.
  The target reverses exactly those runs (`common77.to_visual`, a small approximation of the bidi algorithm), and
  decoding maps back.
- **Checked before training on real crops** (`out/look/rtl_check_flipped.png`): «(Quine, 2001)», «ص : ٣٦», «١٥١».
  The mapping round-trips on 99.3% of training labels.
- **The 0.7% that do not round-trip** are Latin citations that Azure writes in bidi order: «(2005 ,Keyes)» decodes
  as «(Keyes, 2005)». This is the same printed line, so the scorer puts every line in one bidi form first, and
  neither order is counted as an error.

**Model (`train77.py`).** A CRNN: a CNN followed by a 2-layer BiLSTM and a CTC head over Unicode code points.
- **CNN:** 48×W → 1×W/4, with channels 32, 64, 128 (+ a residual block), 256 (+ a residual block), and 384 out.
- **BiLSTM:** 384 units each way.
- **Size:** **8.3 M parameters**, all from random initialisation, with 261 output classes.
- **Why CTC + BiLSTM:** it is the plain, well-proven recipe for printed lines. W/4 frames gives about 3 frames a
  character at the median (5% of lines under 2.1). Lines with too few frames for their target are dropped (11).
- **Training:**
  - AdamW, lr 1e-3, one-cycle, 16 epochs, fp16 autocast;
  - batches of similar width (about 140 lines);
  - light augmentation: width ±15%, a vertical shift, contrast, blur and noise.
- **A transformer encoder was also measured:** 9.4 M parameters, 2,930 lines/s against the LSTM's 2,560 on a
  healthy 5090. The LSTM was kept.

**GPU (`gs77.py`).** This wraps experiment 75's `gpu_session.py`, imported unchanged, pointed at `out/gpu/`, with a
20-minute idle limit and the cap set to what was left of $20. It follows the rules:
- datacenter, verified, reliability ≥ 99.5%, ≥ 300 Mbps, a link test, and the keeper;
- `vastai destroy instance ID -y` and then a check, after every session.

**Judging (step 3, `gem77.py`).**
- **Picking disputes.** v1 read all 513,533 training lines. A dispute is a line where v1 and Azure differ in
  letters or words, with punctuation ignored.
- **Sample.** 10,011 lines on 2,296 whole pages (half of them pre-2000) were cut again at 96 px from 300-dpi renders.
- **Who judged.** gemini-3.8-flash, thinking low (experiment 71's production Flash).
- **What Gemini saw:** the line image and the two readings as A/B, in random order. It answered A, B, both,
  neither (with its own reading) or unreadable. The instructions were "as printed: no modernising, no correcting
  misprints, ignore spacing around punctuation".
- **Lines skipped before asking:** disputes that are only the bidi order of a Latin run (11%). They give the same
  training target, so they were not worth a paid question.
- **Cost.** It was costed on 50 lines first: **$0.0037 a line**, mostly thinking tokens. That meant ~5,000 lines
  fitted the cap, not 10,000. There is a running log (`out/judge/spend.jsonl`), and sending stops at $19.

**v2 labels (step 4, `labels77.py`).**
- Judged "Azure" or "both": Azure's label is kept.
- Judged "v1": v1's reading becomes the label.
- Judged "neither": Gemini's reading becomes the label when it is close to one of the two readings; otherwise the
  line is dropped.
- Judged "unreadable": dropped.
- **Every unjudged dispute is dropped.** On the judged ones Azure was right only 26% of the time.

**Test (step 5, `test77.py`, `eval77.py`).** Only held-out journals are used.
- **Segmentation.** Every reader uses Azure's line boxes, so **this tests reading, not layout.**
- **The owner's 20 checked yardstick pages** (experiment 34, 745 lines, 1937–2006).
- **Lab documents 1 and 2** against the lab's rev1. Document 2's page is also a yardstick page, with the October
  gold there.
- **Lab document 3**, which has no truth yet: disagreement with Argon only.
- **Readers compared on the same lines:**
  - Azure;
  - Argon (Azure + Argon's fixes; Azure's text where Argon has none);
  - our models;
  - Nuqta, from experiment 75's existing runs (lab docs only; not re-run).
- **Scorer.** The lab's (`labocr/evaluation.py`, imported). The line readers' text is put in the truth's order, so
  reading order is not measured.
  - **Headline:** letters = CER under `no_punct`; words = the order-free word error under `no_punct`.
  - **Shown apart:** the same with punctuation (`faithful`), and the count of printed spaces before punctuation.
    The owner has not yet chosen the spacing rule.

## Results

All rows read the same Azure line boxes. Letters = CER, words = order-free word error, both with punctuation
removed (%). Reading order is not measured. Files: `out/results77.json` and `out/confusions77.json`.

**The owner's 20 checked yardstick pages** (745 lines, 1937–2006):

| reader | letters | words | ≈ words wrong | letters with punctuation | lines exactly right (as printed / letters) |
|---|---|---|---|---|---|
| Argon (Azure + Gemini fixes) | 0.52 | 1.05 | 64 | 0.77 | 91.6 / 94.7 |
| Azure | 0.60 | 1.42 | 86 | 0.84 | 90.5 / 93.0 |
| **v2b** (8.3M, v2 labels + old print) | **0.74** | **1.84** | 111 | 1.15 | 81.0 / 90.2 |
| v1 (8.3M, Azure labels) | 0.75 | 1.92 | 116 | 1.17 | 80.2 / 89.3 |
| 28.2M (v2 labels) | 0.77 | 2.00 | 120 | 1.15 | 80.5 / 89.2 |
| v2 (8.3M, judged labels) | 0.78 | 1.98 | 119 | 1.20 | 80.2 / 89.2 |
| 2.1M (v2 labels) | 0.88 | 2.47 | 149 | 1.27 | 77.7 / 86.6 |

**By era** (letters / words): the yardstick pages plus lab doc 1. Pre-1950 is only 2 pages.

| reader | 2000+ (5 pages) | 1950–1999 (14) | pre-1950 (2) |
|---|---|---|---|
| Argon | 0.16 / 0.98 | 0.61 / 1.07 | 0.12 / 0.98 |
| Azure | 0.22 / 0.92 | 0.70 / 1.51 | 0.18 / 1.31 |
| v1 | 0.32 / 1.30 | 0.86 / 2.01 | 0.30 / 2.30 |
| v2 | 0.42 / 1.51 | 0.87 / 2.04 | 0.30 / 2.13 |
| v2b | 0.28 / 1.09 | 0.85 / 1.98 | 0.24 / 1.80 |
| 2.1M | 0.48 / 1.59 | 0.97 / 2.59 | 0.43 / 2.94 |
| 28.2M | 0.36 / 1.30 | 0.88 / 2.17 | 0.18 / 1.47 |

**Lab documents 1 + 2** (rev1). Nuqta was not re-run; its readings come from experiment 75. The truth started from
Nuqta's own text, which flatters it.

| reader | letters | words | doc 1 letters | doc 2 letters |
|---|---|---|---|---|
| Nuqta as written | 0.10 | 0.56 | 0.00 | 0.18 |
| Argon | 0.18 | 1.48 | — | 0.18 |
| v1 | 0.20 | 1.50 | 0.14 | 0.24 |
| v2b | 0.20 | 1.60 | 0.07 | 0.30 |
| 28.2M | 0.20 | 1.60 | 0.14 | 0.24 |
| Azure | 0.23 | 1.32 | 0.21 | 0.24 |
| v2 | 0.26 | 1.97 | 0.14 | 0.36 |
| 2.1M | 0.26 | 1.78 | 0.14 | 0.36 |

**Document 3** (no truth): disagreement with Argon, letters / words.
- Azure 0.07 / 0.36.
- v2 0.17 / 1.00, v2b 0.17 / 1.09, 28.2M 0.21 / 1.27, 2.1M 0.24 / 1.45, v1 0.31 / 1.73.
- Nuqta Markdown 2.03 / 10.12. Nuqta as written 20.9 / 12.3, because it drops a column.

**Punctuation and spacing, shown apart.** With punctuation counted, every one of our models is about 0.3 points
worse than Azure on the yardstick. Lab doc 2's rev1 has no printed spaces before «،» and «.»; every Azure-line
reader (ours and Azure) keeps 14–19 of them. The labels teach Azure's spacing, so this waits for the owner's rule.

**The most common letter confusions** (v1 → truth on the yardstick; examples with crops in `out/report77.html`):
1. أ→ا (hamza dropped) and ا→أ (hamza invented, e.g. «ان»→«أن» on old pages): the model's modern-spelling bias;
2. إ→ا;
3. ة→ه;
4. tanwin ً added or dropped;
5. a ل lost in «لل»;
6. Arabic-Indic digits dropped or added (table and footnote numbers);
7. ة read as «"» at the end of a line;
8. ت/ن and ج/ح (one dot);
9. whole rotated or vertical lines, which training skipped. One table label became digits.

Azure's own top confusions are the same hamza family (ا→أ 9, ا→إ 6), plus ه/ة.

**What Gemini's judging changed** (`out/judge/summary.json`).
- 5,226 lines were judged, half of them pre-2000.
- **Verdicts:** v1 45% (pre-2000 47%), Azure 26% (pre-2000 23%), neither 26%, unreadable 2%.
- **Kind of dispute:** 1,316 of v1's 2,353 wins are marks or letter forms only. On disputes in the letters
  themselves, v1, Azure and "neither" split about evenly (1,037 / 962 / 932).
- **v2's labels:** 3,620 labels replaced (v1's reading 2,341; Gemini's 1,279), 25,938 lines dropped (25,728
  unjudged disputes, 117 unreadable, 93 "neither" too far from both readings).
- **Effect:** none measurable on the truths. v2's yardstick numbers are within 3 words of v1's, and slightly worse
  on lab docs 1–2.
- **The likely reasons:**
  1. The truths were drafted from Azure, so a model that moves away from Azure on marks and hamza is not rewarded
     even where it is right.
  2. Dropping 5% of the hardest lines removes useful examples as well as bad labels.
  3. One training run each; the noise between runs is about the size of the differences.

**Training time** (16 epochs; v2 to 28.2M shared one GPU 2–3 at a time, so their minutes are not comparable):
v1 42 min alone, v2 70, v2b 127 (15 epochs), 2.1M 96, 28.2M 140.

**What went wrong.**
- **A power-capped 5090** ran at 24 TFLOPs instead of 230. It was found by a matmul test and destroyed ($0.51).
- **Two hosts were destroyed by the 20-minute idle keeper** when the follower process died mid-job. v2b and the
  sweep had to be re-run ($2.0 + $2.5).
- **Fixes:**
  - the follower now ignores ssh errors and fetches results as each run finishes;
  - the idle limit is 45 minutes;
  - `train77.py` now guards the scheduler's last step (v2b's last run crashed at step 66,689 of 66,688, after
    saving its best epoch).

## What it changed

- **We now know what a from-scratch reader on our own pages costs and reaches.** About $1 of GPU and 0.5M Azure-labelled
  lines give a reader within about 0.15 letter points of Azure on the owner's pages, and level with Azure on the
  clean modern lab page. It is not yet as good as Azure + Argon.
- **Gemini as a judge is cheap and sharp at finding bad Azure labels:** in about 3 of 4 disputes Azure's label was
  wrong. But fixing 0.7% of the labels did not move the test scores. The owner's truths cannot reward a reader for
  departing from Azure where Azure is wrong, and they are the only truths we have.
- **What would most improve it at full scale (proposal, not run):**
  1. **More and older lines.** v2b's old print helped most, and the 1.2M+ lines on disk plus experiment 80 are unused.
  2. **A truth not drafted from Azure** (or the lab's own corrections), so that label fixes can show.
  3. **Teach the line's context** (a language model or a wider receptive field), to cut the hamza-modernising
     errors that are the most common confusion.
  4. **Tilted and vertical lines in training.**
  5. **The owner's spacing rule** before training on punctuation.
- **Size is not the bottleneck:** 8M parameters is enough at this data size, and 28M adds nothing.

## Files

- `common77.py`: paths, line cutting, labels, the right-to-left mapping.
- `pages77.py`, `build77.py`: the training and dev shards.
- `pages80.py`: experiment 80's old print as split `old80`.
- `test77.py`: the test crops and `out/test/pages.json`.
- `train77.py`: the model, training and inference. It runs on the GPU host.
- `gs77.py`, `setup_gpu77.sh`: the GPU sessions.
- `gem77.py`, `gem80.py`: the Gemini judge. `gem80.py` is round 2 on old print: sample and crops prepared, **never
  run**, because its condition failed.
- `labels77.py`: the v2 / v2b labels.
- `eval77.py`: the scores. `report77.py`: a local HTML page with crops.
- `curve77.py`, `sheet77.py`, `shot77.py`: images for the owner.
- `watch77.sh`: the memory watchdog.
- `out/` (gitignored, private: scans, crops, labels, weights): `shards/`, `test/`, `pred/`, `weights/`, `judge/`,
  `judge80/`, `gpu/`, `look/`, `results77_*.json`, `confusions77_*.json`, `STATUS.txt`.

No weights or data left this machine except to the rented hosts, which were destroyed. Nothing was pushed anywhere.

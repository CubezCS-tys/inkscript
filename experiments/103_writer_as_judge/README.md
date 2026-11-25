# Experiment 103 — mixed-direction targets, and the writer as the judge of the reader

**Status: B1 and B2 scored after the blind key (2026-11-25).**
- **B1: FAIL. B2: no use at letter level.** So, by the rule, **B3 is not run and there is no second rental.**
- **Job A's repair: FAIL** by one bar. A blind check of that bar is staged.

## Result so far (after the blind key, 2026-11-25)

Strict = pre-registered: whole strings compared exactly after whitespace. The strict tables decide the bars.
Folded = **added after seeing the key, not pre-registered**: score97.r1_fold + no punctuation, the experiment's usual
space. Both come from `score103.py b1|b2` and `analyse103.py` (`out/scores/b1.json`, `b2.json`, `b_after_key.json`).
The writer's 4 fits on ink-free crops (infinite chamfer) are set to twice the largest finite value, so they stay
"most suspect". That is numerical handling, added when they appeared.

**B1, gross errors: FAIL in both versions.** Thresholds keep 99% of correct lines.

| | real gross errors / correct lines | writer AUC [95% CI] | writer catch | confidence (−lp_mean) AUC | confidence catch | writer − confidence |
|---|---|---|---|---|---|---|
| **strict (decides)** | 242 / 1,554 | **0.59** [0.51, 0.65] | **0.8%** | 0.91 | 41.7% | **−40.9 pts** [−54.8, −15.8] |
| folded (added after the key) | 163 / 1,633 | 0.62 | 1.2% | 0.93 | 55.8% | −54.6 pts |

- Bars: AUC ≥ 0.90 fails; catch ≥ 60% fails; ≥ +5 points over the confidence fails.
- Writer + confidence (cross-validated) has AUC 0.90 and catch 39%, no better than the confidence alone.

**What the 471 B1 candidates were:**

| outcome | lines |
|---|---|
| real gross error of the reader, strict | 241 (118 when folded); on 136 of them Azure is exactly right |
| reader exactly right, Azure wrong | 88 |
| reader near the truth, Azure far | 70 |
| no readable text on the crop | **61** |
| no settled truth | 11 |

- The writer could score 365 of the 471. The rest are on pages without 3 agreed style lines.

**The 61 unreadable crops** are mostly show-through from 0744-000-059-007.
- **The reader wrote text on every one of them, which is invented text.** Azure did too.
- The writer scored all 61 and flags **2**. The confidence flags **61 of 61**.

**B2, disagreements: "no use at letter level" in both versions.**

| rule | strict, 221 lines | folded, 175 lines (ties out) |
|---|---|---|
| always the reader | 23.1% | 20.0% |
| always Azure | 76.9% | 80.0% |
| higher likelihood (the reader's own) | 35.8% | 35.4% |
| confidence with a threshold (CV): **best free rule** | **77.4%** | **80.0%** |
| writer (experiment 95's rule) | 74.2% (−3.2 [−12.4, +5.8]) | 76.6% (−3.4) |
| writer + confidence (CV) | 76.5% (−0.9 [−3.8, +1.9]) | 80.0% (0.0) |

- **Strict leaves out 58 lines where the truth is neither reading or both, and 1 with no settled truth.** The blind
  readers kept spaces, marks and alif forms that neither machine keeps. 20 of the 300 J lines had no page style.
- Folded leaves out 104 ties.
- **The two versions tell the same story.**
  - In these disagreements Azure is right about 3 times in 4. Many are vowel marks the reader dropped or changed (see
    the picture).
  - The writer is a little below "always Azure", and adding it to the confidence adds nothing.

**Pictures** (`out/pictures/`, looked at):
- `b1_real.png`: 12 random real gross errors, each with the writer's and the confidence's verdict, and whether it is
  still gross when folded.
- `b2_pairs.png`: 12 disagreements, with the differing words marked and each rule's pick.
- `b1_separation.png`: the two score distributions with their thresholds.
- `b2_rules.png`: the rules' accuracy, strict and folded.

**What it means.**
- By the rule, B3 is not run, and the writer is not adopted as a judge at either level.
- The writer-as-reward page (B4) stands as a cost note only.
- **The free signals do the job the writer was meant for.** The reader's own confidence flags invented text on
  empty crops perfectly and catches 42–56% of gross errors. Where the reader and Azure disagree, Azure is the better
  bet.
- Seen in `b1_real.png`: the reader sometimes reverses a digit run («0102» for 2010, «٧٤٩١» for ١٩٤٧).

**The repair's failed bar.** One blind reader will check the 141 test-half control lines where M and R ckpt-150
differ: `out/blind_repair/` (candidates: M, R, Azure; origin in `out/b/private/repair_witnesses.jsonl`).

The owner approved the stage after experiment 102 on 2026-11-25 ("ok go with your recommendations"). GPU cap **$40**
(the lead's figure, inside the owner's approved range); no other money.

## Question

1. **Job A.** Experiment 102's reader M learned Azure's way of storing a Latin run inside an Arabic line: «(2005 ,Adin)»
   where the settled truth has «(Adin, 2005)». The two look the same on screen and differ only in the stored order.
   - Can the training targets be put into true logical order, mechanically and safely?
   - Can the reader be repaired cheaply on them?
2. **Job B.** Before the writer of experiments 87 and 95 is ever used as a training reward, does its judgement add
   anything to what we get for free?
   - The free baselines are: always trust the reader; trust Azure where the two disagree; the reader's own confidence.
   - The writer is tested part by part, on a ladder, with bars fixed now.

## Rules (from the brief, applied in code)

- **Locked data.** These are never trained on and never used to choose anything: experiment 97's 60 exam articles
  (every line), the 20 locked journals, the 280 locked old documents, and experiment 76's held-out split.
  - Experiment 102's `guard102.py` is imported unchanged by every set builder here (`pool103.py`, `diag103.py`,
    `cut103.py`).
- **The exam.** Its 584 lines are read ONCE per final system, at the end (B3 only). **The locked test is not read at
  all.** Nothing from OCRia-1.
- **No exam line was looked at in Phase A.** The convention below comes from experiment 97's written rulings and
  from experiment 102's README, not from the exam lines.
- **Images and weights.** Line images go only to the rented host, through `gs103.py`. Weights are downloaded only on
  the host. Our adapters come back to `out/weights/`.

## The ladder and the bars (fixed 2026-11-25, before any GPU output)

**Free baselines, on the same lines at every rung.**
- (i) always the reader;
- (ii) always Azure where the two disagree;
- (iii) the reader's confidence: token log-probabilities from vLLM (`eval103.py`).
  - In B1: the better of −lp_min and −lp_mean, chosen after the fact in the baseline's favour.
  - In B2: two rules. One picks the reading with the higher forced mean log-probability. The other keeps the reader
    unless its lp_min is below τ, with τ by 5-fold page-grouped cross-validation.

A rung that does not beat the best free baseline is a FAIL for that use, and is reported plainly.

| rung | test set | writer rule | bar | use |
|---|---|---|---|---|
| **A3 repair** | DEV-MIXED test half (601 fixed lines + 654 controls, documents never in R and never used to choose), DEV (2,000) | – | DEV-MIXED fixed: letters wrong ≤ 0.5 × M's; **order right ≥ 90%** (stored string = target, among lines whose display equals the target's); DEV ≤ M + 0.05 pts; controls ≤ M + 0.05 pts | the reader for job B is R if this passes, else M |
| **B0.5 the writer works on our crops** | the style lines of the held-out pages | 87's style fit | median style-line IoU ≥ 0.45 (87: 0.55–0.58 modern, 0.49 pre-1950) | if not met: B1/B2 are not run for the writer ("does not run on our crops"); no rebuild here |
| **B1 gross errors** | REAL: reader far from Azure on held-out lines, settled by blind readers; CORRECT: 1,500 lines where reader = Azure; PLANTED: 300 wrong plausible words + 300 missing words | experiment 87 round 2's frozen logistic checker (`checker87_r2.json`, unchanged) on the absolute fit | **AUC ≥ 0.90** on real gross errors vs correct lines **and**, at the threshold that keeps 99% of correct lines, **≥ 60% caught**, **and** catch ≥ confidence's catch **+ 5 points** | abstain / flag |
| **B2 disagreements** | J: 300 reader–Azure disagreements (not gross), settled by two blind readers and a third, as in experiment 97; + 60 agreed controls | experiment 95's frozen rule (`rule95.json`: chamfer on the gap, min over anchors, δ 0, a tie keeps the reader); and writer + confidence (logistic, 5-fold page-grouped CV) | each writer rule against the best free rule: **≥ +5 points → PASS**; within ±5 → **"no use at letter level"**; below −5 → **FAIL** | letter-level choice |
| **B3 end to end** (only if B1 or B2 passes) | DEV first, then the exam's 584 lines ONCE | the passing rule(s) on the repaired reader | fewer invented words per 100 than M (0.47) with letters wrong not above M's (0.69%, folded, no punct); the share of lines flagged or changed is reported | the system |
| **B4** | not run | – | one page below: how a writer reward would be done, with costs | owner decides |

**Definitions** (all in code, in `score103.py` and `pool103.py`):
- **"Far" / gross**, used both to find B1 candidates and to call a settled line a real gross error. It holds if any of:
  - folded word error ≥ 0.34 of the reference's words;
  - 2 or more words in a row wrong;
  - the reading is 30% or more longer or shorter in letters.
- **B lines** carry no Latin letter, at least 3 Arabic letters, and no token-limit stop. Why no Latin: the writer has
  no bidi step and AlQalam has no Latin (B0 below).
- **Page styles** come from the page's first 3 lines where the reader equals Azure and that are not test lines. Pages
  with fewer such lines are left out and counted.
- **Intervals** are 95%, by bootstrap over pages.
- **The repair's checkpoint** is chosen on the CHOOSE half of DEV-MIXED (documents split by hash). The bars are read
  on the TEST half. The rule: among checkpoints whose DEV letters wrong is ≤ M's + 0.05, take the lowest
  DEV-MIXED-choose letters wrong; within 0.05 points of it, take the latest.

## Phase B, part 1 (2026-11-25, 07:15–10:07 UTC): results

**The rental.**
- One RTX 5090 32 GB (Vast 62481418, datacentre, $0.868/h), **$2.51** of the $40.
- The host was destroyed after every output was checked: md5 of all reading and writer files and sha256 of all five
  R checkpoints match the host. No instance is left.
- Set-up took 15 min (causal-conv1d build, writer venv in parallel).
- One fix on the way: `stage103.sh` links `programs/` and `fonts/` as directories, and the code tgz did not follow
  them. They were uploaded separately.

### Job A: the repair — FAIL by one bar (pre-registered)

- **Training.** R, 2 epochs, 218 steps, from M's adapter. It took 26 min (~9 lines/s; slower than M's 11.6 at the
  start, while a writer smoke shared the GPU).
- **Checkpoint chosen by the rule: ckpt-150** (`out/scores/repair.json`; all five pass the DEV condition).

| measure (letters wrong, folded, no punct) | M | R ckpt-150 | bar | |
|---|---|---|---|---|
| DEV-MIXED test half, 601 fixed lines | **19.01%** | **0.87%** | ≤ 0.5 × M | pass |
| order right (stored = target, among lines displayed right) | 1 of 409 (0.2%) | **434 of 440 (98.6%)** | ≥ 90% | pass |
| DEV (2,000, dev103) | 1.40% | **1.20%** | ≤ M + 0.05 | pass |
| DEV-MIXED test half, 654 unchanged Arabic + Latin controls | 1.65% | **1.74%** | ≤ M + 0.05 | **FAIL (+0.09)** |

- **The controls' regression is real, not an artefact of order.** Only 2 of M's and none of R's control lines differ
  from the label in order only. R reads 397 controls exactly, M 409 (`out/scores/repair_controls_diag.json`).
- Where R differs, it is mostly on Latin-heavy lines whose Azure label is itself broken:
  - «0.79) Dependence).» is read «Dependence (0.79).»;
  - «02H» is now «H02»;
  - also «(Jordan et al, b2010)».
  - Some of these may be R right and the label wrong. The bar counts against the label, as fixed.
- **By the pre-registered rule, the reader for job B is therefore M.**
- The repaired reader's readings of the held-out pool were also taken (`out/eval/heldout_R150.jsonl`). The adapter is
  in `out/weights/R/ckpt-150`, with the other four checkpoints beside it.
- On the held-out pool against Azure's (unfixed) labels: R ckpt-150 0.0112 letter error against M's 0.0115; invented
  words per 100: 0.52 against 0.97.

### The held-out pool and the B sets (`out/b/b_summary.json`)

- **M read all 9,731 lines** with log-probabilities, at 45 lines/s. 2,644 lines are not eligible (a Latin letter,
  short, or the token limit).
- Of the 7,087 eligible lines:

| lines | count |
|---|---|
| M = Azure exactly | 5,324 |
| **B1 real candidates** (M far from Azure) | **471** |
| other disagreements | 1,292 |

- Drawn from these: J = 300, CORRECT = 1,500, planted = 572, controls = 60.
- 44 of 285 pages have fewer than 3 agreed lines, so they have no style and their lines were not written.
- The writer therefore judged:
  - 1,451 correct lines;
  - 365 B1 candidates (both readings);
  - 545 planted pairs;
  - 280 J lines (both readings and the contrast; 1 group fell back for lack of a scored anchor).

**Blind readers' files:** `out/blind/disputes.jsonl`, 831 rows (471 B1 + 300 B2 + 60 controls), crops in
`out/blind/crops/` (README beside them). The witnesses are only in `out/b/private/`.

### B0.5: the writer works on our crops — PASS

- The median style-line IoU is **0.501** over 723 lines on 241 pages; the bar is 0.45.
- Experiment 87 had 0.55–0.58 on its clean lines; experiment 95's ordinary lines 0.42–0.51.
- Winning libraries: Amiri Bold 37 pages, Amiri 26, Scheherazade Bold 23, Lateef 23.

### B1 on the PLANTED set (needs no key) — FAIL against B1's bars (`out/scores/b1_planted.json`)

| planted vs 1,451 correct lines | writer AUC | writer catch at 99% kept | catch at 90% kept (87's point) | confidence AUC / catch | writer prefers the true text on the same line |
|---|---|---|---|---|---|
| wrong plausible word (286) | 0.686 | 0.7% | 18.2% | 1.00 / 100% | 84.3% |
| missing word (259) | 0.866 | 1.2% | 46.3% | 1.00 / 100% | 94.6% |
| both (545) | 0.772 | 0.9% | – | 1.00 / 100% | 89.2% |

- Every bar fails: the AUC is under 0.90, the catch is far under 60%, and it does not beat the confidence.
- The writer repeats experiment 87: dropped words show (46% at 10% false flags; 87 had 50–69%), wrong words barely
  (18%; 87 had 10–13%).
- Its correct-line scores have a long tail: 99th percentile 7.2 against a median 1.1. So at 99% kept almost nothing
  is caught.
- **The reader's confidence separates planted readings perfectly. That is a property of planting, not of the
  confidence.** A planted text is one the reader would not write, so its forced likelihood is far below that of any
  greedy reading.
  - So the planted set cannot rank the confidence against the writer fairly; the REAL set (blind key) can.
  - Paired on the same line, the confidence prefers the true text 100% of the time, the writer 89%.

### Measured writer speed and cost on the RTX 5090 ($0.868/h)

| step | measured | cost |
|---|---|---|
| page style: screen | 3,374 jobs in 21 min, 0.37 s each | |
| page style: full fit | 1,446 jobs in 21.6 min, 0.90 s each | |
| page style, per page | **10.6 s** | **$0.0026** |
| absolute check | 3,831 readings in 36.5 min: **0.57 s per reading** | **$0.00014** |
| contrastive check | 280 groups in 9.2 min: **1.97 s per line** | **$0.00047** |
| reader, with log-probabilities | 42–47 lines/s | – |

### Waiting on the blind readers

- **B1's real-error bars:** the 365 written candidates out of 471, with their writer scores and M's confidence.
- **B2:** 280 J lines.
  - Without the key, the writer picks Azure's reading on 178 and M's on 101, with 1 fallback.
  - On absolute fit it prefers Azure's reading on 52.9% of J lines and on 49.9% of the B1 candidates.
- Both are scored locally with `score103.py b1 | b2 ... --adapter /work/weights/M/ckpt-3125` once
  `out/b/settle/{A,B,C}` exist.
- B3 (rental 2) only if B1 or B2 passes.

## Job A — results (Phase A, local)

### A1. How Azure stores a Latin run, and how many targets it affects

**Azure's habit, measured.** Azure stores the line as it is seen, reversed. Each Latin run (Latin letter to Latin
letter) and each number (digits joined by `. , : /`) is then turned back. Brackets outside the runs are mirrored.
- Printed «(Deroy, 1955, p. 121)» is stored «(121 .Deroy, 1955, p)»; «ISSN: 1112-9751» is stored «9751-1112 :ISSN».
- In an RTL paragraph that string displays exactly as printed. Only the stored (copied, searched) order is wrong.
- `fix103.azure_style` reproduces Azure's string from its own display on **26,681 of 27,056 (98.6%)** mixed lines of
  M. Lines whose label is not Azure's line are left out: titles and judged labels, 376.

**Does Azure's string display as printed?** Each line's Azure words were placed by their boxes and compared with the
display of Azure's string (fribidi).
- **26,874 / 27,056 (99.3%)** of M's mixed lines (Arabic + a Latin letter or a digit) match.
- So the display is right. The logical order is the problem.

**The convention** (`fix103.py` docstring):
- An island is a stretch with no Arabic letter, from its first to its last Latin letter or digit. If it holds a Latin
  letter, it is one unit typed left to right, as an English typist types it.
- A digit-only stretch is split into numbers where the bidi algorithm splits them.
- A number set solid against an Arabic word («كوفيد-19») stays with that word.
- A candidate is accepted only if it displays exactly as Azure's string. Otherwise the line is left alone.

**Lines changed** (`out/diag/count103.json`):

| set | lines | Arabic + Latin | changed | share of all lines | share of Arabic + Latin | left alone: no candidate displays the same |
|---|---|---|---|---|---|---|
| M (what M trained on) | 200,000 | 3,536 | **647** | **0.32%** | 18.3% | 199 |
| DEV | 2,000 | 25 | 7 | 0.35% | – | 3 |
| L_local (the whole local pool) | 622,918 | 14,524 | **4,570** | 0.73% | 31.5% | 966 |

By kind (one line can have several):

| set | Latin citation (Latin + digits) | mixed brackets | Latin term (no digit) | percent | digit groups alone |
|---|---|---|---|---|---|
| M | 624 | 558 | 26 | 0 | 0 |
| L_local | 4,484 | 4,277 | 89 | 9 | 0 |

- **Digit groups, percent signs and Arabic-Indic numbers are not affected.** Azure turns numbers back, so their
  stored order is already the logical one. Logical «23-26» displays 26-23, as experiment 97's ruling says.
- Only Latin runs are stored out of order.
- Single Latin words («Wiki», «(STEM)») are the same in both orders. That is why only 18% of the Arabic + Latin lines
  change.

**Checked in Chromium** (headless shell 156, the judge):
- **797 / 797** lines (every changed line plus every box mismatch) show the same in Chromium before and after the fix
  (`out/diag/boxes103.json`).
  - Six of them differ only by tatweel, which training labels drop anyway.
- Chromium's order of Latin letters, digits and punctuation equals fribidi's on **1,594 / 1,594** strings.

**Of M's 646 changed lines with Azure's label, 608 (94%) display as their boxes show.**
- In the other 38, Azure's own punctuation sits on the wrong side of a run (the «,.» of «et al.,»).
- The fix keeps what Azure shows. This is a reading error of Azure's, not an order error.
- Placing the words by their boxes was tried as a second way in, and dropped. A word displayed alone loses its
  context: «29-90» alone is laid out left to right, but inside the Arabic line right to left. It changed correct
  digit groups.

**Picture** (`out/pictures/mixed_targets_1.png`, `_2.png`; looked at): 20 random changed lines of M.
- Each line shows the crop as printed; Azure's text as displayed; the fixed text as displayed (identical); and the
  Latin part as a reader would copy it. For example, Azure «(2016 ,alghamedi)» against fixed «(alghamedi, 2016)», and
  «9751-1112 :ISSN» against «ISSN: 1112-9751».

### A2. The fixer and its self-test (`fix103.py`, `selftest103.py fix` → `out/selftest/fix103.json`)

- **540 synthetic lines** from known logical strings, written by the convention: Latin citations 260, Latin terms 48,
  mixed brackets 52, digit groups 80, percent signs 60, Arabic-Indic numbers 40.
- Each line is laid out by Chromium. That layout must agree with fribidi on the order of every non-Arabic character;
  it did on all 540. The layout is put into Azure's order, then fixed.
  - **517 / 517 valid cases come back exactly.**
  - Chromium shows the fixer's output as the original on 540 / 540.
- The other 23 are not order cases. Two Latin terms joined by «،» («SPSS، Wiki») become ONE left-to-right run when
  Azure's habit is applied, so what is shown changes. No fixer can know the original there. They are counted apart.
- **Do no harm** (all of M):
  - 129,187 / 129,187 pure-Arabic lines unchanged;
  - 28,954 / 28,954 pure-Latin lines unchanged;
  - idempotent on all 647 changed lines;
  - every changed line keeps exactly its characters (brackets mirrored).

### A3. The repair plan (sets built: `pool103.py repair`, `out/sets/repair103_summary.json`)

**Continue from M's adapter** (`out/weights/M/ckpt-3125`) on a small set R, rather than retrain. Why:
- The fault is one habit on 0.3% of M's lines.
- M's reading is otherwise good: exam 0.42% on the non-Latin lines.
- A full retrain on fixed targets is 5 h and $5.4 and would re-learn everything. The continuation is about 20 minutes.

**R = 6,976 lines.**
- **3,488 affected lines with fixed targets.** They come from 80% of the 846 affected documents of L_local, split by
  document hash.
- **3,488 replay lines from M.** These are 1,162 Arabic + Latin lines that are already in logical order (so the reader
  does not start reordering everything), and the rest random M lines with the same eras as the affected ones.
- R is 90% 2000+, because citations are modern.

**Run:** 2 epochs (218 steps of 64), lr 2e-5 (M used 1e-4), 3% warm-up, cosine, checkpoints every 50 steps.
`train102.py` runs unchanged with `--resume_adapter`.

**DEV-MIXED, how the repair is measured without the exam.**
- 2,164 lines from the other 197 affected documents, none in R: 1,082 fixed lines + 1,082 unchanged Arabic + Latin
  controls.
- Split by document into a CHOOSE half (481 fixed, 428 controls) and a TEST half (601 fixed, 654 controls).
- Plus DEV with fixed labels (`dev103`, 7 lines changed).
- **The fake-data run of the whole scorer** (`selftest103.py repair`) shows what the order fault costs in the count:
  Azure-order readings of the fixed lines score **18.4%** letters wrong (folded, no punct) against the fixed targets.
  In that run the rule chose the right checkpoint.

**Estimate:**
- training 13,952 lines ÷ 11.6 lines/s = 20 min;
- DEV + DEV-MIXED for M and 5 checkpoints: 25,000 lines ÷ 58 lines/s = 7 min;
- total about 0.5 h, about $0.5.

## B0 — can the writer run today, and at what cost

Experiment 103 asked a reader agent to go through 87/95's code and logs; its findings were checked against the code
here.

**What runs.**
- `run87.run_batches`: page style, and the frozen absolute check. Output per reading: IoU, chamfer, missing and
  invented ink windows, per-word coverage.
- `contrast95.run`: anchors, gap geometry and gap fits. The pick is made by `rule95.json`.
- No neural weights at judge time: only the letter programs (95's `out/programs`, 24 MB) and the fonts (4.8 MB).
  Experiment 82's U-Net is needed only to build programs for new glyphs.

**Inputs.**
- A grey 96-px crop with experiment 77's geometry: the same as our crops.
- The binarisation and the removal of neighbouring lines' ink work inside the crop, so no page boxes are needed.
- Each page needs a style first: 3 agreed lines, every library screened (60 steps), the best 2 fitted (160 steps).

**Speed on an RTX 5090** (87/95's logs, batch 32):

| step | rate |
|---|---|
| page style | ≈ 9.2 s per page |
| absolute check | 0.47 s per reading |
| contrastive check, 2 candidates | 1.1–1.4 s per line |
| contrastive check, up to 6 candidates | 2.5 s per line |

At ~$1.0–1.3/h:

| use | cost |
|---|---|
| judging one reading (absolute) | ≈ **$0.00014** |
| a disputed pair (contrastive) | ≈ **$0.0004** |
| one page style | ≈ **$0.0026** |
| 10,000 lines judged once, styles included | ≈ **$1.6** |

The reader reads 10,000 lines for $0.05.

**What was missing, and what Phase A added** (adapters only; the writer's code is imported unchanged):
1. **No driver for new lines.** `judge103.py` replaces the two crop readers and builds jobs from our files.
2. **No style for new pages.** `pool103.py b` picks 3 agreed lines per page.
3. **No bidi step: digits would be written mirrored.** HarfBuzz shapes the line as one RTL buffer, so 2015 would
   come out as 5102.
   - `judge103.writer_text` gives the writer the line as it is seen, right to left, with brackets mirrored back. It is
     identity on Arabic-only lines.
   - It is computed locally, so the host needs no fribidi.
4. **Latin cannot be judged:** AlQalam has no Latin, and traced faces write it as nothing. B lines therefore have no
   Latin letter. On the held-out pool that leaves out about 27% of lines (with the short and token-limit ones).
5. **JPEG.** 87/95 fitted PNG crops. The writer gets lossless PNG crops (`cut103.py png`) with exactly the reader's
   geometry. The reader keeps its JPEGs.

**CPU smoke test here** (`judge103.py smoke` with 87's local venv):
- Our PNG crops, 95's programs, 87's fonts and `run87.run_batches` ran end to end on 4 style lines.
- IoU 0.34–0.39 after only 20 steps in one library. That is a wiring test, not a measurement.
- The absolute check ran the same way: 3 lines, 100 steps, 127 s per line on the CPU, IoU 0.30–0.42.
- The contrastive check also ran end to end: 1 fake-reader dispute, 10 steps; `score103.contrast_pick` read it.
- Outputs are in `out/selftest/judge/`.

**Not settled without the GPU.**
- The writer's real speed and fit on our crops. B0.5 is the rung for that.
- vLLM's log-probabilities (`logprobs=1`, `prompt_logprobs=0`) with this LoRA. It is part of vLLM's sampling API; the
  first `heldout` run is its test.

## The held-out pool and the blind readers

**The pool** (`pool103.py heldout`): 9,731 lines of the 55 DEV documents that are not among DEV's 2,000 lines, on 313
pages.
- These documents are outside every training set (S, M, L_local, R) and every locked set.
- They are the only such documents with PDF + Azure JSON on this server. Experiment 83's documents would need S3
  egress, which is money outside the cap.

**A dry run of the B builder on a FAKE reading** (`selftest103.py bsets`; 85% as Azure, 12% one letter changed, 3%
two words dropped):

| what | count |
|---|---|
| eligible correct lines | 6,044 |
| B1 candidates | 263 (189 of the planted gross lines among them) |
| non-gross disagreements | 786 |
| J (B2 lines) | 300 |
| planted | 576 |
| pages | 284 (15 without 3 style lines) |
| writer jobs | 3,741 |
| blind-reader items | 623 |

- Candidates are shuffled (azure first in 280 of 563).
- No origin is written in the readers' file.

**The blind readers (the lead runs them).** After the held-out pool is read on the host:
- `pool103.py b` writes `out/b/disputes.jsonl` in experiment 97's format (id, stem, page, line, crop, control,
  shuffled candidates, note). Which reading came from where is only in `out/b/private/witnesses.jsonl`.
- `cut103.py blind` writes the 144-px crops to `out/b/crops_blind/`.
- **Expected size: about 500–650 lines.** That is the B1 real candidates (about 150–260 by M's DEV disagreement rate),
  the 300 J lines and 60 controls.
- Two readers, A and B, read blind. A third, C, settles where they differ, exactly as experiment 97 did.
- Their files go to `out/b/settle/{A,B,C}/readings.jsonl`, which `score103.truths()` reads.
- KEYER_RULES' reading conventions apply. Mixed lines do not occur here: B lines have no Latin.
- The writer runs on the host while the readers work; scoring waits for both.

## Phase B estimate (one RTX 5090 at ≈ $1.0–1.3/h)

**Rental 1:**

| step | hours | arithmetic |
|---|---|---|
| set-up: vLLM venv + Qwen weights (as 102) and the writer venv | 0.25 | 102's set-up took 10 min |
| uploads | overlapped | 856 MB: crops 575 MB, M's adapter 248 MB, code + programs + fonts 29 MB, sets 7.5 MB |
| repair (R, 2 epochs) | 0.4 | 13,952 ÷ 11.6 lines/s = 20 min, + DEV loss and saves |
| repairdev | 0.15 | (2,000 + 2,164) × 6 adapters ÷ 58 lines/s |
| heldout read, 6 adapters, with log-probabilities | 0.3 | 58,386 ÷ 58 |
| host idle while scored here (repair choice, `pool103 b`, upload of `out/b`) | 0.3 | |
| forced log-likelihoods | 0.05 | ≈ 1,750 candidates |
| writer smoke | 0.05 | |
| page styles | 0.75 | ≈ 285 pages × 9.2 s |
| absolute check | 0.5 | ≈ 3,700 readings × 0.47 s |
| contrastive check | 0.1 | 300 × 1.3 s |
| fetch, verify, margins | 0.4 | |
| **total** | **≈ 3.3 h** | **≈ $3.5–4.5** |

**Rental 2, only if B1 or B2 passes (B3).**
- The repaired reader on the exam pages' lines, once: about 6,400 lines, 2 min.
- Styles for about 214 exam pages: 33 min. Writer on the 584 lines: 5–10 min. Set-up: 0.25 h.
- **Total ≈ 1.2 h ≈ $1.5.**
- One point for the lead: the page styles need each exam page's OTHER lines, read once by the final system. Nothing
  is chosen on them, but they are lines of exam articles. If that is not allowed, B3 needs another source of style
  for exam pages.

**Total Phase B ≈ 3.3–4.5 GPU hours, ≈ $4–6 of the $40.** The blind readers' work is agent time, not money.

## B4 — the writer as a training reward (not run; for the owner's decision)

Run this only if B1 or B2 passes.

**Method: GRPO-style continuation from the repaired reader.**
- Per training line, k = 8 sampled readings (temperature 0.7).
- Each sample's reward is −(experiment 87's frozen writer score) of its absolute fit, in the page's style.
- In B2's letter-level form, where samples differ, the contrastive pick between the two most frequent samples instead.
- A small KL term keeps the reader near its supervised self.
- Lines with a Latin letter get no writer reward (no bidi in the writer).
- Page styles are fitted once per page from lines where the greedy reading equals Azure.

**Cost per 10,000 training lines, from B0's speeds at $1/h:**

| part | hours | arithmetic |
|---|---|---|
| sampling | 0.4 | 80,000 readings ÷ 58 per s |
| writer, absolute | 10.4 | 80,000 × 0.47 s |
| styles | 0.85 | ≈ 330 pages × 9.2 s |
| policy updates | 1.9 | 80,000 ÷ 11.6 per s |
| **total** | **≈ 13.6 h ≈ $14** | |

- The contrastive form costs about 1.3 s per pair where samples differ. It is cheaper only if most samples agree.
- For comparison, supervised training on 10,000 lines costs 14 minutes, ≈ $0.25: about 55 times less.
- The writer would be the bottleneck by far. Only a B1 pass with a large margin, or a B2 pass, could justify that
  price.

## Self-tests (no GPU), all run 2026-11-25

| test | result |
|---|---|
| `selftest103.py fix` | 517/517 valid synthetic lines back exactly; do-no-harm and idempotence on all of M (A2 above) |
| `score103.py selftest` (`out/selftest/score103.json`) | every bar shown passing AND failing on fake data, all as expected. B1: strong writer PASS; weak writer FAIL; AUC 0.97 but catch 57.5% FAIL on the catch bar. B2: good writer PASS; a writer that knows nothing gives "no use" overall and FAIL for the writer alone. Repair PASS / FAIL on order / FAIL on DEV. B3 PASS / FAIL on letters, against M's real exam file. rule95's min-over-anchors pick and the missing-glyph fallback. |
| `selftest103.py repair` | the whole repair scorer on fake readings: the checkpoint that is worse on DEV is refused, the right one chosen, PASS |
| `selftest103.py bsets` | the B builder on a fake reading (above) |
| `judge103.py smoke` / `check` / `contrast` on the CPU (87's venv) | the writer runs end to end on our crops through the adapters (above) |

## Phase B commands (in order; the lead rents)

```
cd /home/appuser/inkscript/experiments/103_writer_as_judge
bash stage103.sh                                            # out/up/ (symlinks): 856 MB to upload
python3 gs103.py offers ; python3 gs103.py start RTX_5090   # lead; uploads out/up/code as one tgz
python3 gs103.py run 'bash host103.sh all' && python3 gs103.py follow '[h]ost103.sh'
python3 gs103.py upload out/up/weights_M /work/weights/M/ckpt-3125      # meanwhile, other terminal
python3 gs103.py upload out/up/sets /work/sets
for d in R devmix dev heldout heldout_png; do python3 gs103.py upload out/up/crops_$d /work/crops/$d; done
python3 gs103.py run 'bash host103.sh repair && bash host103.sh repairdev && bash host103.sh heldout && bash host103.sh wsmoke' \
  && python3 gs103.py follow '[h]ost103.sh'
python3 gs103.py get /work/out/eval out/eval ; python3 gs103.py get /work/out/weights/R out/weights/R
../81_heldout_scale/out/venv/bin/python score103.py repair out/eval/dev103_R.jsonl out/eval/devmix_R.jsonl \
  --base_adapter /work/weights/M/ckpt-3125                  # -> chosen checkpoint, REPAIR PASS/FAIL (write it here)
python3 pool103.py b out/eval/heldout_R.jsonl --adapter <the reader for job B: chosen R ckpt, or M if the repair failed>
../81_heldout_scale/out/venv/bin/python cut103.py blind out/b/disputes.jsonl out/b/crops_blind    # for the blind readers
python3 gs103.py upload out/b /work/out/b
python3 gs103.py run 'bash host103.sh force <ckpt> && bash host103.sh judge' && python3 gs103.py follow '[h]ost103.sh'
python3 gs103.py get /work/out/judge out/judge ; python3 gs103.py get /work/out/eval out/eval
python3 gs103.py stop 'exp 103: writer judged'
# after the blind readers have settled out/b/settle/{A,B,C}:
../81_heldout_scale/out/venv/bin/python score103.py b1 out/judge/check103.jsonl out/eval/heldout_R.jsonl out/eval/force_b.jsonl --adapter <ckpt>
../81_heldout_scale/out/venv/bin/python score103.py b2 out/judge/contrast_j.jsonl out/eval/force_b.jsonl out/eval/heldout_R.jsonl --adapter <ckpt>
# B3 only if B1 or B2 passed (rental 2, see the estimate)
```

`score103 b1/b2 --adapter` reads the reader rows of the same adapter that `pool103 b --adapter` used.

## Files

- `bidi103.py`: fribidi (ctypes on the system libfribidi) and headless Chromium layouts.
- `fix103.py`: the target fixer and Azure's habit (`azure_style`).
- `diag103.py`: A1's counts and the box / Chromium checks.
- `pictures103.py`: the owner's picture.
- `pool103.py`: R, DEV-MIXED, dev103, the held-out pool, and the B sets and blind-reader files.
- `cut103.py`: PNG crops for the writer and 144-px crops for the blind readers.
- `eval103.py`: the reader with log-probabilities, and forced log-likelihoods.
- `judge103.py`: the writer adapters.
- `score103.py`: every bar, with its self-test.
- `selftest103.py`: the self-tests.
- `host103.sh`, `gs103.py` (cap $40.0), `stage103.sh`.
- `out/` (gitignored):
  - `diag/`, `pictures/`, `selftest/`;
  - `sets/` (R 6,976; R_cut; devmix 2,164; dev103; heldout 9,731);
  - `crops_R/` 132 MB, `crops_devmix/` 43 MB, `crops_heldout/` 162 MB (JPEG, cut102), `crops_heldout_png/` 206 MB;
  - `up/` (symlinks).
- Nothing in `src/` or in another experiment was edited.

## The repair's failed bar, checked blind (lead, 2026-11-25; added after the bars, not pre-registered)

The repaired reader failed one bar: on the 654 unchanged Arabic + Latin lines it was 0.09 points worse than M
(1.74% against 1.65%; the bar allowed 0.05). That bar is counted against Azure's labels. One blind reader typed, from
the crop, the 141 of those lines where M and the repaired reader differ (`out/blind_repair/`), and
`repaircheck103.py` scores the three readings against that reader (folded, punctuation ignored; 139 lines, 2 unsure
left out):

| reading | letters wrong | lines fully right |
|---|---|---|
| M (experiment 102) | 6.67% | 48 |
| repaired reader (R ckpt-150) | 5.08% | 63 |
| Azure's label | 4.28% | 66 |

The repaired reader is nearer the print on 62 lines, M on 32, and 45 are ties. So the regression measured against
Azure's labels is not a regression against the print: on exactly the lines where the two models differ, the repair
is the better reader.

- The pre-registered bar stays recorded as failed; this check is one blind reader, not two with a third.
- The lead's call: the repaired reader (`out/weights/R/ckpt-150`) is the reader to carry forward. It was not read on
  the exam or the locked test.
- Seen by the blind reader on these lines: symbols and subscripts that every reading gets wrong (α, ≤, ≥, d5mC,
  H₀), the old decimal sign «ر», and 4 lines where every candidate has the parts in the wrong order.

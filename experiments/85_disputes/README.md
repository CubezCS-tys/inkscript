# Experiment 85: settling the disputed lines of our own line reader

**Question (lead, owner's plan B, 2026-11-05).** Experiment 83 held 444,265 lines out of training because v1 (our
reader) and Azure read them differently. Which side reads the print right, by kind of dispute? Can simple rules settle
some disputes for free? Can a blind Gemini judge settle a sample of the rest? Does a reader fine-tuned on the settled
lines beat v3? Labels follow the owner's rule of 2026-11-05: **transcribe as printed** (hamza, ى, ة and «» as printed).
**Caps:** Gemini $40, GPU $10.

**Status: done (2026-11-05).**
- **Gemini: $25.84 of $40.** A 50-line pilot used standard calls; 8,950 lines went through the Batch API in two
  rounds.
- **GPU: $3.21 of $10.** One RTX 5090 (Vast 59325261), cut plus three fine-tunes. The host was destroyed and none
  of our instances is left.

## Summary

- **The disputes by kind** (Azure against v1 on the 444,265 held lines):

  | kind | share of held lines |
  |---|---|
  | several characters | 35.3% |
  | one other letter | 32.6% |
  | hamza on alif | 14.2% |
  | word space | 8.6% |
  | vowel marks | 5.5% |
  | ى/ي | 1.7% |
  | mixed spellings | 1.5% |
  | ة/ه | 0.7% |

- **No free rule reaches the 98% bar.**
  - The best rule is **rule85**: the dispute is only hamza on alif, Azure writes the hamza, and v1 and v3 both write
    a bare alif. Then v1 is right. It covers 42,404 lines.
  - Measured by the judge at the disputed letter, it is right on 94.8% (exp 81's lines), 95.5% (exp 77's) and
    95.9% (a new audit of 145 lines).
  - I looked at the crop of every line where the judge disagreed (20 lines): 10 were judge errors. The rule's true
    precision is about **97.6%** (10 misses in 416 lines).
  - It is trained on only as an arm (v6r).
- **The owner's lines cannot settle hamza.** On 22 hamza disputes the owner's truth sides with Azure 59% of the time.
  I looked at 8 of them, and all 8 print a bare alif. The owner's lines were drafted from Azure, which adds hamza.
- **The judge's verdicts** (8,478 answered lines; % right):

  | kind of dispute | lines | Azure | v1 | neither | v3 |
  |---|---|---|---|---|---|
  | rule85 audit | 145 | 3 | 86 | 12 | 86 |
  | ى/ي | 387 | 17 | 70 | 13 | 71 |
  | ة/ه | 228 | 23 | 59 | 18 | 69 |
  | word space | 1,133 | 43 | 42 | 15 | 55 |
  | one other letter | 2,614 | 42 | 38 | 20 | 63 |
  | hamza, other cases | 753 | 48 | 26 | 26 | 58 |
  | vowel marks | 858 | 33 | 36 | 31 | 46 |
  | several characters | 2,026 | 25 | 27 | 48 | 42 |
  | mixed spellings | 276 | 16 | 29 | 55 | 42 |

  - Weighted to all held lines (rule85's lines left out): v3 is right on **52.8%**, Azure 35.8%, v1 34.0%, and
    none of them 30.2%.
  - Where v3 agrees with one side, that side is right 60–75% of the time.
  - Where v3 agrees with neither side, the judge mostly writes its own reading (64–69% of those lines). Those
    labels are the least reliable: the judge's blind reading equals its final answer on only 70% of all lines.
- **Retrained readers.** Each is fine-tuned from v3 for 3 epochs at 3e-4, as experiment 84 did:
  - **v6r**: the consensus lines + 8,012 judged lines + rule85's 42,280 lines;
  - **v6j**: the consensus lines + the judged lines only;
  - **ctl**: the consensus lines only. This is the control: the same extra training, without the disputes.
- **On exp 81's held-out journals** (judge truth, every letter counted, letters wrong %):

  | reader | all | pre-1950 | 1950–99 | 2000+ | lines wrong % | folded |
  |---|---|---|---|---|---|---|
  | Azure | 0.875 | 0.737 | 0.943 | 0.704 | 23.3 | 0.500 |
  | v3 | 0.849 | 0.560 | 0.820 | 1.019 | 19.1 | 0.577 |
  | ctl | 0.865 | 0.565 | 0.820 | 1.086 | 19.4 | 0.592 |
  | v6j | 0.852 | 0.587 | 0.826 | 1.005 | 19.4 | 0.578 |
  | **v6r** | **0.844** | **0.551** | **0.808** | 1.035 | **18.9** | 0.575 |

  - The v3 row is v3 re-read on the GPU host, so it goes through the same pipeline as the others. It matches exp
    81's CPU reads on 97.8% of lines: 0.849 against 0.854.
  - v6r against v3, paired: −0.010 letters (CI −0.028 to +0.003); −0.58 points of wrong lines (CI −1.33 to −0.09).
  - The control against v3: +0.012 (+0.002 to +0.024). The same extra training without the disputes is slightly
    worse.
  - So v6r is about 0.02 points better than its control. It is the best reader before 2000. Folded (hamza, ى, ة
    and marks ignored), v6r is level with v3.
  - **The gain is the hamza rule.** v6j (judged lines only) is level with v3.
  - Caveat: the judge saw the new readers' readings on only 93–94% of judged lines, against 97% for v3. Lines the
    judge never looked at count against the new readers.
- **On the owner's 20 pages:**
  - v3 0.69 / 1.61 (letters / words), v6r 0.70 / 1.66, ctl 0.71 / 1.67, v6j 0.72 / 1.65; Azure 0.60.
  - This is level within these 745 lines. The truth is Azure-drafted on hamza, which counts against rule85.
  - Lab docs 1–2: 0.16 for every arm. Doc 3 against Argon: 0.17 for every arm.
- **«» and (( ))** on the owner's 20 pages: v6r and v6j now write one «», which is correct (1 of 30). (( )) is
  unchanged, with precision 0.48 and recall 1.0. Azure's (( )) for printed «» is still in the labels, and experiment
  84 handles it.
- **Dev CER** on experiment 83's dev lines: v3 1.002%, v6r 0.982%, v6j 0.983%, ctl 0.987%.

## Method

**1. Types (`common85.py`, `types85.py`, `rules85.py`).**
- The comparison form `sform` is experiment 77's clean_label with only punctuation removed (Unicode P* and S*).
  This is experiment 81's scorer fix: `no_punct` turns vowel marks into spaces, `sform` keeps them.
- A dispute's type is the first fold that makes Azure and v1 equal: spaces, marks, alif-hamza, ى→ي, ة→ه, several
  folds together, one edit, or more. Each convention type also records which side has the space, mark, hamza, ى or
  ة.
- **v3's vote:** where v3 reads as Azure (the 101k lines of experiment 83's relabel) or as v1, from `held_v4`.
- The rules were measured on the judged lines of experiments 81 and 77 and on the owner's truth, at two levels:
  - line: the whole line equals the truth;
  - point: the side is closer to the truth than the other side. A tie counts as a miss.

**2. Judge (`sample85.py`, `presign85.py`, `cut85.py`, `judge85.py`, `est85.py`, `point85.py`).**
- **Sample.** 9,000 lines (seed 85):
  - fixed quotas per kind: one letter 2,800, several characters 2,200, space 1,200, marks 900, hamza other 800,
    ى/ي 400, mixed 300, ة/ه 250;
  - era bands weighted, with pre-1960 counted twice;
  - journals taken round-robin, at most 4 lines a document;
  - plus 150 audit lines of rule85;
  - lines with no Arabic letter or mostly Latin left out;
  - 4,364 documents from 2,311 journals.
- **The guard, in code.** Every key that is cut, judged or trained on is checked against experiment 84's
  `LOCKED_TEST.json` (20 journals) and experiment 76's held-out journals; all 444,265 held keys pass. The guard
  refuses to pass while the locked list does not exist.
- **Crops.** Cut here, niced, with 2 processes. Twelve download threads fetch from presigned URLs, or read
  experiment 80's local pull. Each page is rendered at 300 dpi and cut with exp 77's `cut_line` at 96 px, exactly
  as judge81. 0 errors, 0 text mismatches. The PDFs were deleted after cutting.
- **Judge.** judge81's prompts, verbatim: gemini-3.8-flash, thinking low, two turns of one conversation:
  1. blind reading first;
  2. then a verdict among the distinct candidates (Azure, v1, v3), shuffled and unnamed.
- **Pilot.** 50 lines with standard calls: $0.0068 a line. The other 8,950 went through the Batch API at half
  price: round 1 (blind), then round 2 (blind answer in the conversation, then the verdict).
- **Spend.** Logged per answer in `out/judge/spend.jsonl`. Before each job is sent, the spend so far plus every
  open job's expected cost (×1.5) must stay under $38.5.
- **Answers.** 522 lines got an empty blind answer twice (billed for input only) and were dropped.

Gemini spend per kind (all lines answered, both rounds):

| kind | lines | spend |
|---|---|---|
| one other letter | 2,641 | $7.73 |
| several characters | 2,055 | $7.16 |
| word space | 1,134 | $3.07 |
| vowel marks | 858 | $2.70 |
| hamza, other cases | 754 | $2.12 |
| ى/ي | 387 | $1.05 |
| mixed spellings | 276 | $0.94 |
| ة/ه | 228 | $0.69 |
| rule85 audit | 145 | $0.38 |

**3. Labels (`labels85.py`).** The trainer has only ever seen Azure's punctuation, and the judge ignored
punctuation. So a settled line's label is Azure's line with only its words' letters made to follow the settled
reading. Azure's punctuation stays, and a space split or join replaces the run. The label's comparison form must equal
the truth's; if not, the truth's own text is used (495 lines).
- A judged line is used when the judge picked a candidate, or when its "none" reading equals its own blind
  reading. That gives 8,012 lines; 404 lines where the judge changed its mind are left out.
- rule85 lines take v1's alifs, in order, into Azure's line: 42,280 lines. The audit lines the judge answered take
  the judge's label instead.
- Every other held line stays dropped, as for v3.

**4. Retraining (`train85.py`, `host85.sh`, `gs85.py`, `presign85host.py`, `read81host85.sh`).**
- `train85.py` is `train83.py`, which has the schedule slack, plus:
  - `--init`: fine-tune from a checkpoint, keeping its 463-class charset and shape;
  - `--pct`: the warm-up share;
  - `--drop_paren`: experiment 84's v5 rule, unused here.
- **Data.** Experiment 83's training data, re-cut on the host from 12-hour presigned URLs with `cut83.py`
  unchanged. The URL lists are identical to experiment 83's, and the line counts match: 513,533 + 231,012 +
  2,165,425 train, 8,198 dev.
- **The three arms:** v6r 2,515,860 training lines; v6j and ctl from the same pool minus their dropped lines. Each
  ran 3 epochs at about 3,000 lines/s, about 43 min.
- **Torch threads** follow the cgroup quota (61 CPUs; 8 torch threads, 16 loader workers).
- **Start.** From v3: experiment 84's v5 had not been scored on held-out lines by the time the cut finished, and on
  the owner's pages it was 0.71 against v3's 0.69.
- **Checkpoints.** The model is best.pt by dev CER: v6r and ctl at epoch 3, v6j at epoch 2.
- Experiment 81's held-out crops were uploaded to the host and read there; nothing else of theirs left this
  machine.

**5. Scoring.**
- `eval83.py` with `--out` here: the owner's 20 pages, lab docs, doc 3.
- `quotes85.py` (experiment 84's quotes84, imported).
- `score85.py`: experiment 84's est84, imported unchanged. It applies est81's stratified estimator, two-phase
  estimate, paired CIs and coverage, and writes here only. Run strict and with `EST81_FOLD=1`.
- `fig85.py`: the owner's picture, `out/look/disputes85.png`.

## What it changed

- **Disputes split into two groups:**
  - **Conventions** (hamza on alif, ى/ي, ة/ه): our reader reads the print, and Azure modernises. Here, v3
    agreeing with v1 is a strong signal (70–86% right).
  - **Letters and spaces:** Azure and v1 are right equally often, and about a fifth of lines are wrong on both
    sides.
- **The bare-alif rule is the one cheap win, and it is just under the bar.** As an arm it gives the best held-out
  reader so far (v6r: 0.844% letters, 18.9% lines wrong, ahead of Azure before 2000). The gain is small and within
  noise for letters; the gain in wrong lines is significant.
- **Judging 8k disputes with Gemini adds nothing measurable** (v6j ≈ v3). 8,012 labels are too few against 2.5M
  consensus lines, and the judge's own readings are its weakest labels.
- **The owner's yardstick cannot judge hamza** while it is Azure-drafted. Their spelling rule needs a truth not
  drafted from Azure.
- Nothing in `src/` changed.

## Next

1. Use v6r as the working reader, or keep v3 if the owner wants the 98% bar to hold strictly.
2. To learn the conventions, settle them in bulk without Gemini: apply rule85 together with ى/ي and ة/ه where v3
   agrees with v1, on all held lines. Check with a few hundred looked-at crops, not the judge. Gemini does not pay
   for one-letter and several-character disputes.
3. A small owner truth for hamza, drafted from the print rather than from Azure (a few hundred lines).
4. Combine with experiment 84's display-face and «» training once v5 is scored.

## Files

- Code: `common85.py`, `types85.py`, `rules85.py`, `sample85.py`, `presign85.py`, `cut85.py`, `judge85.py`, `est85.py`,
  `point85.py`, `labels85.py`, `train85.py`, `host85.sh`, `setup_gpu85.sh`, `gs85.py`, `presign85host.py`,
  `read81host85.sh`, `read85.py` (CPU alternative, unused), `score85.py`, `quotes85.py`, `fig85.py`.
- `out/` (gitignored, private):
  - `types/`: typed held lines, calibration, rules;
  - `judge/`: sample, crops, answers, spend, estimates;
  - `labels/`;
  - `host/`: runs v6r, v6j, ctl (best.pt, last.pt), logs, predictions;
  - `read/`;
  - results: `results85.json`, `eval85.txt`, `est85_heldout*.json`, `score85_*.txt`, `quotes84.json`;
  - `look/disputes85.png`;
  - `gpu/`: session and spend.

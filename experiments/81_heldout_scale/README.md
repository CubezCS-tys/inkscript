# Experiment 81: our own line readers on a large held-out test, with no human correction

**Question (lead, under the owner's go, 2026-11-05).** Experiments 77, 78 and 79 scored our from-scratch line readers
only on the owner's 745 corrected lines and 3 lab pages. That was enough to say "close to Azure" (letters 0.72–0.75%
against Azure's 0.60%), but not enough to rank them. The owner will not correct more pages. So the question is: with
the truth taken only from independent agreement plus a blind judge, how do our readers compare with Azure on about
20,000 lines of journals that none of them saw in training? Where does each one win or lose: by era, by ink, by
journal? Does the signal reader's warning work at scale? Nuqta-Arabic-OCR-4B (the best open model of experiment 75)
was added as a yardstick (lead, 2026-11-05).

**Status: done (2026-11-05).** Gemini **$19.81 of $20**: 50-line pilot, 112 calibration lines, 2,795 of the 3,000
sampled lines, 168 v3 re-asks. GPU **$1.05 of $5**: one RTX 5090, destroyed; the lead stopped it after it sat idle.
Readers v2b (exp 77) and v3 (exp 83) were added after the sample was drawn (below).

## Verdict

- **Overall, our best readers equal Azure.**
  - On 18,138 Arabic lines from 26 journals none of them saw, with every letter counted (hamza, ى/ي, ة/ه and marks
    as printed, punctuation ignored):
    - Azure: **0.88%** letters wrong;
    - v3 (exp 83): **0.85%**;
    - v1 + exp 78 (the two image readers fused): **0.88%**;
    - v1: 0.93%.
  - Paired with Azure on the same lines, v3 is −0.02 (95% CI −0.07 to +0.03) and the fusion is +0.01 (−0.03 to +0.05).
  - **Ours has fewer wrong lines:** v3 19.4% against Azure 23.3% (−3.8 points, CI −4.9 to −2.7).
- **Before 2000, ours is better.**
  - Pre-1950: v3 0.56% against Azure 0.74% (−0.18, CI −0.28 to −0.09).
  - 1950–1999: v3 0.83% against 0.94% (−0.12, CI −0.17 to −0.06).
- **On 2000+ print, ours loses letters, and the cause is one thing:** journal 0097's running header. It is the
  journal's title in a white display face on a dark textured band, printed on every page, 2.7% of 2000+ lines. Our
  readers garble it (v1 21% of its letters wrong, Azure 8%). It accounts for **98% of v1's excess letter errors on
  2000+ lines** (108% for v3).
  - **With the header**, 2000+: Azure 0.70%, v1 1.04%, v3 1.01%.
  - **Without it**, 2000+: Azure 0.505%, v1 0.510%, v3 0.473% (−0.03, CI −0.08 to +0.02). Ours also has fewer
    wrong lines there (v3 11.3% against Azure 13.7%).
  - None of our training data has light text on a dark band (white-on-dark lines: v1 47% of letters wrong, Azure 18%).
- **With the spelling conventions folded** (hamza forms, ى/ي, ة/ه and vowel marks ignored, so only letters, dots
  and word spaces count), Azure is ahead:
  - Azure 0.50%, the fusion 0.56%, v3 0.58%, v1 0.61%;
  - v1 +0.12 (CI +0.08 to +0.15), v3 +0.08 (+0.04 to +0.12).
  - Without the header, v3, v2b and the fusion are level with Azure (v3 +0.01, CI −0.02 to +0.05), and v1 is still
    behind (+0.06).
  - **So ours wins with every letter counted, but not with spellings folded. The gap is in hamza and ى/ي, where our
    readers write what the old print shows and Azure modernises.** That is also where the judge and the owner disagree
    most (below).
- **Nuqta-Arabic-OCR-4B is behind every reader of ours and Azure:**
  - 1.32% letters (folded 0.73%) and 31% of lines wrong;
  - worst on old print (pre-1950 1.75%; it writes the line in modern spelling and adds vowel marks);
  - the exception is 2000+ with spellings folded: 0.46%, between Azure and ours.
- **The signal reader:**
  - alone, p4r reads 4.9% of letters wrong (p3t 12.2%);
  - fusing it with v1 helps a little, safely: −0.022 points of letters (CI −0.029 to −0.014), −0.6 points of lines;
  - a second image reader helps twice as much (−0.048, −1.2 points of lines).
  - **As a warning it is no better than the image reader's own confidence** (PR-AUC 0.35 vs 0.32). Disagreement
    between two image readers is the far better warning (PR-AUC 0.51, 70% precision at a 10% flag rate).
  - This confirms experiment 79's rung 2 at 25 times the lines.
- **The judge is not truth, and the owner's lines are not either.**
  - On 200 owner-corrected lines, the judge marks Azure wrong far more often than the owner does: 92 vs 48 lines
    strict, 43 vs 30 folded. For our readers it agrees with the owner (v1 68 vs 75, v3 56 vs 59).
  - The owner's lines were drafted from Azure, though. I looked at 10 lines where the judge and the owner differ
    (folded):
    - the judge was right in 5 («وذك», «فد», «يشعر انه», «للغذاء», «الديمواقراطى», all as printed);
    - the owner in 3 (the judge "corrected" misprints such as «تصف» to «نصف»);
    - 2 were unclear.
  - **Azure's true error lies between the two measures. The judge's figures flatter us against Azure by up to the
    width of that gap.** On the owner's 717 lines alone: Azure 0.22% letters (folded 0.14), v3 0.26% (0.16), v1 0.34%
    (0.22).

## Method

**1. Test set (`build81.py`).** Held-out journals only.
- **Which journals.** The 27 codes of `76_finetune_pilot/out/split76.json`. 26 of them have articles on disk: 144
  articles, 3,425 pages, 128,008 Azure lines. The 27th code is lab document 1, which is not in experiment 76's
  inventory.
- **Leak check, in code, before testing.** No held-out journal appears in:
  - experiment 77's 752,743 manifest lines;
  - its `select77.json` (10,734 articles);
  - experiment 79's 440 real-training articles.
  Experiment 78's text, paper and traced faces assert the same split in `text78.py`, `bg78.py` and `common78.py`.
- **Selection.** The unit is a whole page, so each page is rendered once.
  - Every page, but no journal over 2,000 lines.
  - Journal 0097 holds 107k of the 128k lines (all 2000+): it is capped at 3,000.
  - The owner's 20 yardstick pages are always in, for calibration.
  - Seed 81.
- **Result:** 575 pages, 111 articles, 26 journals, **22,783 lines**:
  - pre-1950: 932 lines;
  - 1950–1999: 15,829;
  - 2000+: 6,022.
- **Cutting the lines.** Exactly experiment 77's way:
  - a 250-dpi pypdfium2 5.12.1 render;
  - Azure's line polygon;
  - `cut_line(test=True)` at 48 px for the image readers.
  - From the same render, a 96-px cut gives the pen signal (experiment 79's `sig79.line_signal`: skeleton, start
    "top", no flags), the input p3t and p4r were trained on.
- **Recorded per line:** journal, year, era, Azure's text, Argon's text where experiment 41's Argon read the page
  (6,789 lines), arabic_share, and the measured ink type. Ink type uses experiment 79's buckets (`fuse79.py`): median
  stroke thickness and blob share from the signal, with this set's own tercile thresholds.
- **The frame.** **18,138 lines with an Arabic letter and arabic_share ≥ 0.5.** Reported apart and not judged: 2,734
  mostly-Latin lines and 1,906 lines with no letter (numbers, rules).

**2. Readers on every line (`read81.py`).** Local CPU, nice 19, 4 threads, outside the busy hours. The CPU outputs
were checked against the GPU ones (`read81.py check`):
- v1: 209 of 216 greedy lines identical (fp16 on the GPU);
- p3t: same CER (12.60% vs 12.58%).

| name | reader |
|---|---|
| azure | Azure's line text |
| argon | Azure + Argon's fixes; only on pages Argon read |
| v1, v2, v2b | experiment 77: Azure labels / Gemini-judged labels / v2 + experiment 80's old print (77's best on the owner's pages) |
| v3 | experiment 83: v1's recipe on 4.8 times the lines (consensus lines from 7,763 more documents; no held-out journal, checked); read last, judged where it opened a new reading |
| s2r | experiment 78's syn_then_real (synthetic v1, then real; 78's best) |
| sig, sig4 | experiment 79's signal reader alone: p3t (synthetic only) and p4r (fine-tuned on 102k real lines) |
| fsig, fsig4 | v1's N best (CTC prefix beam 10, N ≤ 8) re-scored by s_v1 + λ·s_signal, with λ = 0.2 (p3t) and 0.1 (p4r), each chosen on experiment 79's dev split |
| f78 | the same with s2r, λ = 1.5: the image + image control |
| nuqta | Nuqta-Arabic-OCR-4B on the 96-px judge crops (`nuqta81.py`). Experiment 75's worker, imported unchanged: the card-default prompt "as written", greedy, bf16, the speed fix. Batched, with 15 of 16 lines identical to unbatched. It read 5,112 lines in about 7 minutes on one RTX 5090 |

p4hf (experiment 79's newest, hybrid centre line + flags, 4.42% on owner truth) needs a different signal: about 25
CPU-minutes to recompute. On experiment 79's own test it fuses the same as p4r (0.387% vs 0.381% line CER), so p4r
stands in for it.

**3. Agreement (`agree81.py map`).** Two readings agree when they are equal after:
- experiment 77's cleaning;
- one bidi form;
- punctuation removed (the experiment-77 headline, `no_punct`).

This follows the lead's convention:
- spacing before punctuation and «» vs (( )) are not counted;
- the judge is told to ignore punctuation too;
- punctuation is not measured in this experiment.

The two strata:
- **Agree:** every reader shown to the judge agrees (Azure, Argon where present, v1, v2, s2r, fsig, fsig4, f78).
- **Dispute:** any of them differs.
- The signal readers alone, v2b, v3 and Nuqta are never part of the agreement. v2b and Nuqta were added after the
  strata were drawn and shown to the judge; v3 came after the judging.

**4. Judge sample.** Seed 81, stratified by era.
- **Disputes: 2,500 of 3,870.** That is every pre-1950 one (253), every 2000+ one (485) and 1,762 of 3,132 from
  1950–1999.
- **Agreed: 500 of 14,268** (pre-1950 100, 1950–1999 200, 2000+ 200).
- **Calibration:** the 56 owner-yardstick disputes not already sampled, plus 56 agreed yardstick lines.
- **Judge:** gemini-3.8-flash, thinking low, two calls in one conversation (`judge81.py`):
  1. **blind**: the 96-px crop from a 300-dpi render → its own transcription;
  2. after that answer is in the conversation, the distinct candidate readings (about 2.8 a line; Nuqta and v2b
     included), lettered in random order with no names → which candidates match the image exactly (punctuation
     ignored), or none (with its corrected reading), or unreadable.
- **Cost:** $0.0054 a line on the 50-line pilot, so about $17 for all 3,112. Every call is logged at once in
  `out/judge/spend.jsonl`, and sending stops at $19.40.

**5. Estimates (`est81.py`).**
- **The truth of a judged line** is the candidate the judge called right, or else its corrected reading.
- **Stratified estimator:** every frame line of stratum (agree/dispute × era) carries the weight N_h / n_h of its
  judged lines.
- **Intervals:** a 95% bootstrap that resamples pages within each stratum.
- **v2b and Nuqta, two-phase:** the share of agree-stratum lines where they equal the consensus comes from every line
  they read (Nuqta: 2,556 agree lines). Their error, given equal or not, comes from the judged agree lines.
- **Checked on the owner's lines.** With the owner's truth standing in for the judge, the estimator recovers the
  owner-scored error of every reader on the yardstick lines (Azure 0.23% estimated vs 0.224% true letters; v1 0.340
  vs 0.340; s2r 0.309 vs 0.307; `out/est81_dryrun_ownerjudge.json`, yardstick part only). The exception is
  Nuqta: 0.91% estimated (interval 0.62–1.19) against 1.36% true. Nuqta was read on only 280 of the 717 lines and
  is outside the agreement, so on the yardstick alone its estimate is not trustworthy. On the full set its two-phase
  estimate is the one to use.

## Results without the judge

**Agreement map** (18,138 Arabic lines; `out/agree81.json`). The pattern is the agreement of our three image readers
(v1, v2, s2r) with Azure.

| era | lines | all three = Azure | ours agree, Azure differs | 2 of 3 = Azure | 1 of 3 = Azure | ours split, none = Azure | every shown reader agrees |
|---|---|---|---|---|---|---|---|
| all | 18,138 | 79.3% | 6.4% | 5.7% | 3.6% | 5.0% | 78.7% |
| pre-1950 | 865 | 72.0% | 8.8% | 7.5% | 5.2% | 6.5% | 70.8% |
| 1950–1999 | 13,642 | 77.6% | 6.9% | 6.6% | 4.0% | 4.9% | 77.0% |
| 2000+ | 3,631 | 87.3% | 3.7% | 2.3% | 1.6% | 5.2% | 86.6% |

- **By ink:**
  - thin/crisp: 82.9% of lines with every reader agreeing (2,605 lines);
  - even: 78.4% (5,360);
  - heavy/spread: 77.8% (10,170).
- **By journal:** from 61% (0629, 0018) to 95% (2071). The journals where all our readers agree against Azure most
  often are 0197 (17.6%), 0018 (13.0%), 0367 (11.6%), 0005 (11.2%) and 0260 (10.7%).

**Distance to Azure in letters** (a disagreement, not an error; `out/extras81.json`):

| reader | all | pre-1950 | 1950–1999 | 2000+ |
|---|---|---|---|---|
| argon | 0.17 | 0.32 | 0.14 | 0.27 |
| f78 (v1 + s2r) | 0.56 | 0.43 | 0.53 | 0.69 |
| s2r | 0.59 | 0.47 | 0.56 | 0.72 |
| fsig4 (v1 + p4r) | 0.60 | 0.49 | 0.58 | 0.72 |
| fsig (v1 + p3t) | 0.61 | 0.50 | 0.59 | 0.73 |
| v1 | 0.63 | 0.52 | 0.61 | 0.74 |
| v2 | 0.66 | 0.55 | 0.63 | 0.80 |
| nuqta (5,112 lines) | 2.19 | 1.88 | 2.37 | 2.10 |
| sig4 (p4r alone) | 4.79 | 5.12 | 5.48 | 2.54 |
| sig (p3t alone) | 11.9 | 10.0 | 13.5 | 7.4 |

**Nuqta against the consensus.** On 2,556 agree-stratum lines (where Azure and all our readers agree), Nuqta writes
the same line 75.2% of the time:
- pre-1950: 52.3%;
- 1950–1999: 73.1%;
- 2000+: 88.8%.

Part of this is convention. Nuqta writes vowel marks where the print may have none, and modern spellings. The judge
decides which.

**On the owner's yardstick lines** (717 Arabic lines that are both in this set and mapped to the owner's truth; line
CER, no punctuation):

| reader | Azure | Argon | v1 | v2 | v2b | s2r | fsig | fsig4 | f78 | Nuqta (280 lines) | p4r alone | p3t alone |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| letters wrong % | 0.224 | 0.146 | 0.340 | 0.352 | 0.301 | 0.307 | 0.316 | 0.304 | 0.290 | 1.36 | 4.43 | 10.9 |
| lines wrong % | 7.3 | 5.6 | 11.0 | 11.0 | 9.9 | 10.0 | 10.6 | 10.0 | 9.3 | 37.9 | 71.0 | 93.2 |

v3 (exp 83) on the same lines: 0.260% letters, 8.8% of lines; folded 0.155%.

## Results with the judge

**Judge spend and consistency** (`out/judge/spend.jsonl`, `out/est81*.json`).
- **Spend.** $19.81 in all, $0.0063 a line (two calls; thinking tokens dominate), plus 4–8 empty answers that were
  retried.
- **Answered:** 2,294 disputes and 473 agreed lines. A dispute: 1,963 match a candidate, 331 have none right, 31 are
  unreadable (1.4%).
- **Blind reading = final verdict:**
  - disputes: 72% strict, 84% folded;
  - agreed lines: 87% strict, 95% folded.
- **Agreed lines the judge calls wrong** (agree-but-wrong):
  - 11.6% strict, mostly marks, hamza and spaces it claims to see;
  - **3.6% folded** (pre-1950 3.2%, 1950–1999 3.7%, 2000+ 3.6%).
  - About half of the folded ones that I read were real Azure errors (القابيلن, ولق, a missed first word). The rest
    were the judge adding a space or a mark.
- **Against the owner** (yardstick lines in the sample plus 112 calibration lines; 202 lines):
  - agreed lines: the judge's truth = the owner's on 64 of 69 strict, 68 of 69 folded;
  - disputed lines: only 74 of 133 strict, 107 of 133 folded.
  - Experiment 76's "Azure = blind Gemini is right 449/450" holds for agreed lines. On disputed lines the judge is a
    weaker witness.

**Estimated error per reader** (letters wrong %, 95% page-bootstrap CI; lines wrong %).
- v2b, v3 and Nuqta use the two-phase estimator.
- v3 was added after judging. The 245 judged lines where v3 read something no shown candidate had were asked again
  with v3 among the candidates; 168 fit the cap. The other 77 count v3 as wrong, which biases against v3.

| reader | all, strict | 2000+ | 1950–1999 | pre-1950 | all, folded | lines wrong, strict |
|---|---|---|---|---|---|---|
| Azure | 0.88 (0.73–1.05) | 0.70 | 0.94 | 0.74 | 0.50 (0.34–0.69) | 23.3 |
| Azure + Argon fixes (6,551 lines) | 0.74 (0.48–1.09) | 0.66 | 0.76 | 0.78 | 0.43 | 19.1 |
| v1 (exp 77) | 0.93 (0.77–1.11) | 1.04 | 0.91 | 0.73 | 0.61 | 21.7 |
| v2 (exp 77) | 0.94 | 1.11 | 0.91 | 0.71 | 0.61 | 21.4 |
| v2b (exp 77, + old print) | 0.91 (0.74–1.11) | 1.09 | 0.88 | 0.60 | 0.58 | 20.6 |
| s2r (exp 78) | 0.94 | 1.08 | 0.91 | 0.69 | 0.62 | 21.8 |
| **v3 (exp 83)** | **0.85 (0.68–1.02)** | 1.01 | **0.83** | **0.56** | 0.58 | **19.4** |
| v1 + p3t (signal) | 0.92 | 1.04 | 0.90 | 0.71 | 0.60 | 21.3 |
| v1 + p4r (signal) | 0.91 | 1.03 | 0.89 | 0.70 | 0.59 | 21.1 |
| v1 + s2r (image + image) | 0.88 (0.72–1.07) | 1.02 | 0.86 | 0.64 | 0.56 | 20.4 |
| Nuqta-4B | 1.32 (1.18–1.54) | 0.97 | 1.40 | 1.75 | 0.73 | 31.4 |
| p4r alone | 4.90 | 2.81 | 5.56 | 5.12 | 4.21 | 69.8 |
| p3t alone | 12.2 | 7.8 | 13.8 | 10.3 | 11.1 | 91.7 |

**Without journal 0097's running header** (the same estimator, its lines left out of the frame and the sample;
`out/est81_nohdr.json`):
- all, strict: Azure 0.83, v1 0.81, v3 **0.73**, fusion 0.76;
- 2000+: Azure 0.505, v1 0.510, v3 0.473, fusion 0.491;
- paired with Azure: v3 −0.10 (CI −0.14 to −0.06), v2b −0.05, fusion −0.07;
- folded: Azure 0.50, v3 0.51, v2b 0.50, fusion 0.51, v1 0.56.

**By ink** (strict, with the header; `by_ink` in `out/est81.json`):

| ink | Azure | v1 | v3 | fusion |
|---|---|---|---|---|
| thin/crisp (2,605 lines) | 0.73 | 0.67 | 0.63 | 0.64 |
| even (5,360) | 1.02 | 1.08 | 1.03 | 1.03 |
| heavy/spread (10,170) | 0.84 | 0.91 | 0.82 | 0.86 |

Folded, Azure leads on every ink.

**By journal** (`by_jcode`). Ours is ahead of Azure in 13 of 26 journals. It is furthest behind in:
- 0084 (152 lines, 11 judged): 1.69 vs 0.09;
- 0097 (the header);
- 0408, 0407 and 0382, journals with long reference lists.

**Why 2000+ is different** (`diag81.py`, `out/diag81_v1.json`, `out/diag81_v3.json`; contact sheets
`out/look/worst_v1_2000plus.png`, `worst_v3_2000plus.png`, looked at). On the 647 judged 2000+ lines, v1 has fewer
wrong lines than Azure (13.8% vs 14.9%) but more letter errors (1.04% vs 0.70%). By line type, as each bucket's share
of v1's excess letter errors:

| bucket | share of 2000+ lines | v1 letters | Azure letters | share of v1's excess |
|---|---|---|---|---|
| 0097 running header | 2.7% | 20.6 | 8.1 | **98%** (v3: 108%) |
| everything else | 97.3% | 0.51 | 0.50 | 2% |
| light text on dark | 0.8% | 47.0 | 17.7 | 40% |
| Latin digits (mostly the header's year) | 16.5% | 2.67 | 1.17 | 92% |
| reference-like | 13.1% | 4.00 | 1.83 | 93% |
| any Latin letters | 4.8% | ≤ 0.57 | ≤ 0.55 | none |
| tilted > 3° | 1.6% | 1.31 | 0.29 | 1% |

All 20 worst lines are that header. The digit and reference buckets are the header again (its year).

**Agreement with Azure in lines** (`out/agree81.json`): v1 84.0%, v2b 84.9%, s2r 84.9%, v3 86.0%, the fusion 85.8%,
Argon 94.6%, p4r alone 32.0%.

**The warning at scale.** Target: v1's line is wrong per the judge. Weighted base rate 21.7% strict, 10.9% folded.

| warning | PR-AUC strict | precision / recall at 10% flagged | PR-AUC folded |
|---|---|---|---|
| p4r's likelihood of v1's line | 0.35 | 39% / 18% | 0.31 |
| p3t's likelihood | 0.30 | 30% / 14% | 0.23 |
| v1's own confidence | 0.32 | 36% / 17% | 0.26 |
| **v1 vs s2r disagreement** | **0.51** | **70% / 32%** | **0.57** |
| s2r's likelihood of v1's line | 0.54 | 65% / 30% | 0.53 |
| p4r + v1-vs-s2r (rank sum) | 0.48 | 60% / 28% | 0.54 |

On pre-1950 lines the signal does better (p4r 0.48), but still below the second image reader (0.57).

**Leftovers.**
- 2,734 mostly-Latin lines and 1,906 lines with no letter were not judged.
- Our readers equal Azure on 95% of the mostly-Latin lines and 93% of the no-letter lines.

## What it changed

- **The ranking of our readers on unseen journals:**
  - v3 (exp 83, 4.8 times the lines) is the best single reader;
  - then v2b, then the fusion of two image readers;
  - v1, v2 and s2r are level;
  - the signal reader adds little as a partner and nothing as a warning.
  - The 745 owner lines could not separate these readers. 18k lines with a judge can, for v3 against v1, and
    before 2000.
- **"Close to Azure" becomes "level with Azure" on held-out journals, and better than Azure on pre-2000 print**,
  when every printed letter counts. With the spellings folded, Azure stays a little ahead of all but v3, v2b and the
  fusion.
- **A concrete, cheap gap was found:** display faces and light text on a dark band (journal 0097's header, every
  page). Synthetic training lines (experiment 78) can render exactly this: white-on-dark bands and display faces.
- **The judge has a measured bias against Azure's spellings.** Hamza and ى/ي are where Azure modernises and the judge
  objects; the owner's Azure-drafted lines lean the other way. A truth not drafted from Azure, for a few hundred
  disputed lines, is the one thing that would settle the remaining gap. Experiment 77 already listed it.
- **Found in the lab scorer:** `no_punct` removes punctuation with `[^\w\s]`, which also turns every vowel mark into
  a space. A mark difference still costs one edit, so the letter scores of experiments 77–79 stand, but word counts
  split at marks. The folded measure here strips marks before punctuation for that reason.
- Nothing changed in `src/`.

## Files

- `build81.py`: selection, leak check, the 48-px crops and the signals (`out/pages81.jsonl`, `out/lines81.jsonl`,
  `out/crops48/`, `out/sig/`).
- `read81.py`: the image readers, the N best, the signal readers, one late reader, and the CPU-vs-GPU check
  (`out/read/`).
- `agree81.py`: readings, the agreement map, the judge sample, calibration, the Nuqta list, reshow, and the judge-free
  numbers (`out/readings81.jsonl`, `out/agree81.json`, `out/extras81.json`, `out/judge/sample.jsonl`).
- `judge81.py`: judge crops and the two-call blind judge (`out/judge/`).
- `nuqta81.py`, `setup_nuqta81.sh`, `gs81.py`: the Nuqta pass on the rented host (`out/read/nuqta81.jsonl`).
- `est81.py`: estimates, consistency, judge vs owner, the warning. Writes `out/est81.json`; with `EST81_FOLD=1`
  `out/est81_folded.json`; with `EST81_EXCL_HDR=1` `out/est81_nohdr.json`; the dry run with the owner as the judge
  `out/est81_dryrun_ownerjudge.json`.
- `diag81.py`: the 2000+ breakdown by line type and the worst-20 contact sheet (`out/diag81_<reader>.json`,
  `out/look/worst_<reader>_2000plus.png`).
- `plot81.py`: the reader-by-era chart (`out/look/readers_by_era.png`, sent to the owner).
- `out/venv`: CPU torch 2.15 beside the repo's `.venv` (a `.pth` file adds its site-packages).

Everything in `out/` is private (crops, texts) and gitignored. Nothing left this machine except the 5,112 line crops,
which went to the rented host and were destroyed with it.

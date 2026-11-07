# 79 — The signal reader: a printed line read as movement

**Question.** The owner's picture (2026-11-04): follow the ink the way a pen travels through it, and turn the line into a signal over time. The signal records:

- where the pen is;
- which way it moves;
- how sharply it turns;
- when it lifts;
- the dots, as small strokes of their own.

Can a network read letters from that signal, the way online handwriting recognition and speech recognition do? And does it then act as a second, independent sense beside the image line reader (experiments 77/78), raising a warning where the two disagree?

The plan, the ladder, the pre-registered pass marks and the kill criteria are in [PLAN.md](PLAN.md).

**Method.**

- **Pen signal (`sig79.py`).** It works in these steps:
  1. ink is measured against the local paper;
  2. pieces are separated from marks, and printed rules, frames and neighbour lines' ink are dropped;
  3. each piece's centre line is found with src `penpath.thin`;
  4. the centre line becomes a graph of ends, junctions and runs;
  5. one pen-down walk covers each piece. As in experiment 09, the trunk runs from the first letter to the left end. Side strokes and loops come first, and are retraced;
  6. the piece's marks follow it, right to left;
  7. points are taken at an even step, with 12 features each.
- **Real lines (`real79.py`).** 20 real training-pool lines, cut by experiment 77's cut at 96 px, with overlays.
- **Synthetic lines (`synth79.py`).** Lines are shaped by HarfBuzz in experiment 78's fonts, so every ink pixel knows its letter. They give the truth path (letter by letter) and the letter-order score of a reconstruction.
- **Test signals (`realtest79.py`).** The signals of experiment 77's 864 held-out test lines.
- **Data and rung 0 (`data79.py`).** Synthetic lines with perfect, clean-reconstructed and damage-reconstructed signals.
- **Rung-0 summary (`rung0_79.py`).** It summarises the scores of those lines.
- **Rung 1 on the GPU.** `train79.py` holds the reader: features → 1-D convolutions → BiLSTM → CTC, with experiment 77's right-to-left target. `gs79.py` and `setup_gpu79.sh` handle the rented host, under experiment 75's rules, through its `gpu_session.py`.
- **External stroke data.** Licence verdicts are in `data/DATASETS.json` and in PLAN.md. The data itself is kept in `data/`, which is gitignored.

**Results so far (2026-11-04, $0).**

- **20 real lines, judged by eye** (`out/real/*.png`, `out/real/sheet.png`):
  - 12 are plausible throughout: pieces right to left, dots after their piece, loops travelled round.
  - 5 have minor faults: a lam started at its foot, a و at its tail, a neighbour's dot taken in, merged dots.
  - 3 are unusable: heavy 1953 print with filled loops, a shadowed display face, a very faint scan.
- **20 synthetic lines with known letters** (`out/synth/`). The reconstruction meets the letters in the right order on 16 of 20. The mean letter-order error is 6.1% and every dot lands in the right piece. The error depends on line height:

  | height | mean letter-order error |
  |---|---|
  | 96 px | 6.1% |
  | 64 px | 8.3% |
  | 48 px (experiment 77's crop) | 11.6% |

  So the signal reader cuts the same line box at 96 px.
- **Rung 0, at scale on CPU (2 cores, 5 minutes): passes its pre-registered marks.** Measured on 1,604 synthetic test lines of held-out text:
  - **clean ink (1,202 lines):** mean letter-order error **4.1%**, median 0, 77.7% of lines exact, **99.5%** of dots in the right piece;
  - **mild damage (825):** 3.7%;
  - **heavy damage (377):** 4.8%, dots 97.6%;
  - **the held-out face Mirza:** 1.8% clean, 4.6% heavy.
  - Worst faces: Markazi 8.2%, Almarai 8.4%, Amiri 6.8–7.4%, mostly the lam-alef ligature and letters stacked over a neighbour. Best: Lateef, Scheherazade and Noto Naskh, 0.3–2%.
  - **Caveat:** the measure scores only the *order* in which letters are met. Broken or merged ink barely moves it, because the walk still goes right to left. Whether damaged paths are still *readable* is rung 1's question (P3), not rung 0's.
- **Rung 1** (owner approved the GPU in session; RTX 5090, instance 59169221):
  - **Speed fix.** Training first ran at 0.65 steps/s. `prof79.py` showed the input pipeline was not the bottleneck (72 batches/s). The cause was bf16 autocast: under it the BiLSTM left cuDNN's fast path, giving 1.16 steps/s against 14.7 in fp32. Training now uses fp32 + TF32 at about 15 steps/s (budget 50k padded points; a 120k budget ran out of GPU memory).
  - **p2, perfect font paths** (150k lines, 12 epochs, 24 min):
    - **8.15%** CER on held-out text; the pass mark was ≤ 5%, so this is a near miss;
    - **9.82%** for the held-out face Mirza (≤ 10%, pass);
    - read straight on reconstructed paths it fails: 33% on synthetic lines, 46% on real ones.
  - **p3t, reconstructed paths** (clean + damaged, with thickness; 100k lines × 2, 12 epochs, 31 min):
    - on synthetic held-out lines: **4.5%** clean, 4.7% mild, 9.7% heavy, 9.5% spread, 6.8% for the held-out face. P3 passes (≤ 8% clean, ≤ 15% mild);
    - **first look at real print:** **11.1% CER** on the 741 held-out test lines with owner truth, with no real line in training. By era: modern 12.1%, 1950–1999 11.3%, pre-1960 7.4%. Median line 9.3%. Typical faults: extra teeth (سس for س), dotted letters, Latin lost.
  - **p3n, the same as p3t with thickness zeroed:** 14.9% on real lines, against p3t's 11.1%. Real loop letters are misread 18.7% → 11.8% of the time with thickness, and **real و 12.7% → 6.1%** (its main confusion is ر). On synthetic spread ink loop letters go 10.5% → 7.5%; on clean ink they barely change (2.2% → 2.0%). Thickness is the owner's filled-head fix, and it works (`loops79.py` → `out/res/loops_p3t_p3n_p3tp.json`).
  - **p3tp, pretrained on ADAB + Calliar (shippable), then trained as p3t:** real 11.0% against 11.1%; synthetic heavy 9.2% against 9.7% and spread 9.0% against 9.5%. **Pretraining on handwriting adds almost nothing.** The pretrained model alone reads print at about 67%.
  - **Rung 0 again on the v2 set** (3,072 clean test lines, `out/rung0_v2/`): letter order 3.9%, dots 99.5%. Counters of loop letters still open in the ink: 83% after mild damage, 70% after heavy, **47%** after spread.
  - **GPU spend:** $3.08 of the $20 cap; the instance is destroyed. Models and logs are in `out/host/<run>/`.
  - **A consistent extraction rule beats the "true" order.** The reader of reconstructed paths reads them better (4.5%) than the reader of perfect paths reads perfect ones (8.15%).
- **Skeleton vs MCR** (Zidouri's minimum covering runs; `mcr79.py`, `mcrcmp79.py`, 240 synthetic lines):
  - MCR orders letters better: 2.75% error against 4.1%;
  - the skeleton traces open loops better: 75% against 58%;
  - at a matched 5% false-flag rate, both signal about 82% of counters closed by ink spread, and at 1% the skeleton is ahead (63% against 45%).
  - Details are in PLAN.md.
- **Licences:**
  - ADAB: CC BY 4.0, shippable. It needs an IEEE login, so the owner downloads it.
  - Calliar: MIT, downloaded. Its scraped source images are not used.
  - AOLAH: research-only until its authors confirm.
  - Online-KHATT: non-commercial, never shipped.
  - ArabicMetafont: unreleased. Its ancestor AlQalam (LPPL) is downloaded.

**Exp 79r: learned pen paths** (PLAN.md):

- The signal reader trained on exp 82's learned centre lines reads held-out real print at 4.38% CER alone, against 4.60% on skeleton paths.
- By era: modern 2.69%, pre-1960 3.43%.
- Fusion is unchanged (0.384%), the warning is slightly sharper, and there is no harm.
- The pre-registered ~2% bar is not met, so the reader stays parked as a third voter.
- GPU $0.69; exp 79 total $18.23.

**Rung 2, final** (PLAN.md, "rounds 2–3, and the rung-2 verdict"). The signal reader trained on 102k reconstructed real lines (p4r, `out/host/p4r/`):

- **Alone,** it reads held-out print at 4.6% CER.
- **Fused with exp 77,** line CER goes 0.408% → 0.381%, with no harm in any era or ink bucket; pre-1960 goes 0.291% → 0.194%.
- **A second image reader is the better partner:** 0.363%, and three-way fusion reaches 0.354%.
- **It is also the far better warning:** PR-AUC 0.51 against 0.31.
- The rasm head, structure flags and the MCR hybrid change nothing.
- **Fails** its pre-registered fusion and warning marks; **passes** do-no-harm.
- Chart: `out/fuse/rung2_chart.png`.
- Exp 79 GPU total: $17.54.

**Rung 2, first pass** (see PLAN.md, "Rung 2, first pass"):

- Fused with the synthetic-only signal reader p3t, exp 77's line CER goes 0.408% → 0.390%, with no harm in any era or ink bucket.
- The image+image control does better: 0.363%.
- As a warning, the signal reaches PR-AUC 0.24, against 0.51 for 77-vs-78 disagreement.
- The real-trained reader p4r was lost with the instance. The instance cost $9.49, inflated by a keep-alive loop.
- Exp 79 GPU total: $12.59.

**Rung 0.** The full results are in `out/rung0/summary.json`. The scored lines are `out/rung0/test-*.jsonl`, and the held-out face's are `testfont-*.jsonl`.

**What it changed.** Nothing in `src/`. Experiments 77 and 78's files are read only.

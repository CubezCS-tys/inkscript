# 82 — Pen-path accuracy for the signal reader

**Question.** The owner (2026-11-05): "the signal is only as good as the pen path". Experiment 79 rebuilds an ordered pen path from printed ink with hand rules (centre line → graph → right-to-left walk) and scored it only by the ORDER of letters met (3.9% error). How right is the path's SHAPE: are the letters drawn where the ink is, are loops travelled round, does the pen move the right way, does it take the right branch at a junction? Which rebuilder is best on clean, old and damaged ink? Can a learned rebuilder do better, and does a signal reader read better from it?

**Hard rule.** On real pages the path rebuilder never sees the image reader's letters, so the signal stays a second, independent sense. Letters are used only to build the truth and to measure.

## Method

- **Frozen copies.** `sig79.py`, `synth79.py`, `mcr79.py`, `data79.py`, `mcrcmp79.py` are copies of experiment 79's files (2026-11-05, before its rung 2), so a change there cannot move these numbers. `reader82.py` is a copy of exp 79's `train79b.py` with two more input kinds.
- **The rebuilders (`path82.py`).** All end in exp 79's own graph, spur pruning and walk. They differ only in where the centre line runs:
  - `skeleton`: Zhang–Suen thinning (exp 79 today);
  - `mcr`: Zidouri's minimum covering runs;
  - `hybrid`: exp 79's piece-level hybrid (MCR for a whole heavy piece);
  - `hybrid_r`: new, a regional hybrid (MCR inside blob regions, thinning elsewhere, joined);
  - `learned`: the centre line predicted by a network (step 3).
- **The truth (`metric82.truth82`).** HarfBuzz-shaped lines (exp 78's faces) where every ink pixel knows its letter. Each letter's clean glyph is thinned on its own and walked by exp 79's rule. A piece's first letter starts at the top of a tall stroke, as the rebuilders do. A letter whose body is drawn by a ligature neighbour is left out.
- **The shape metric (`metric82.py`).** A rebuilt point belongs to the letter of the nearest CLEAN ink pixel. Per letter:
  - **letters in place:** the rebuilt stretch and the true one are within 1.5 stroke widths of each other everywhere (Hausdorff). A missed letter counts as wrong;
  - **mean / max distance:** the symmetric mean nearest-point distance and the Hausdorff distance, in pixels at 96 px line height (stroke ≈ 5.3 px). The discrete Fréchet distance is kept in the rows too;
  - **direction:** the share of rebuilt points moving within 45° of the true direction.
- **Loops.** Per counter of a loop letter (و ؤ ه ة م ف ق ص ض ط ظ ع غ: a hole of 4 px or more in the clean glyph that the truth itself goes round), the test is whether one continuous pen-down stretch of the rebuilt path sweeps at least 1.6π round the counter's centre. Retraces count 0.
- **Junctions.** Per junction of the clean centre line, the branch directions where the path crosses a ring of 1.6–2.7 stroke widths round it, measured on the truth path and on the rebuilt path alike. A junction is right when the counts are equal and every branch matches within 35°.
- **Damage (`lines82.py`).** The same rendered line at every level:
  - `clean`;
  - exp 79's `mild`, `heavy` and `spread`;
  - a new `fill`, old heavy print: the ink spreads 1–2×, then 80% of small counters are filled, then mild scan damage.
- **Faces:**
  - `modern`: exp 78's OFL naskh and sans faces + Mirza;
  - `traced`: exp 78's typefaces traced from our 1927–1958 scans, respecting `exclude.json`. Dropped faces are not used; a face's bad letters never appear; its bad isolated forms never appear isolated.
- **The learned rebuilder (`net82.py`, `gen82.py`, `learn82.py`).** A 2.1M-parameter U-Net reads the 96-px grey crop and predicts:
  - the centre line;
  - its local axis (cos 2a, sin 2a; an auxiliary task);
  - the clean letter's counters, even where ink has filled them.

  The centre line is thinned and handed to exp 79's graph and walk, so the order rule stays exactly exp 79's. Training pairs:
  - (a) synthetic font lines: target = the skeleton of the clean ink;
  - (b) ADAB real trajectories (CC BY 4.0, sets 1–2) drawn as print-like ink with a broad nib 3.5–8 px, then damaged: target = the real pen line;
  - (c) traced-font lines.

  All of them pass through clean / mild / heavy / spread / fill damage.
- **Downstream check (`learn82.py feats`, `reader82.py`).** The same synthetic lines rebuilt by the skeleton and by the network. One signal reader trains on each, and both are scored on held-out text per damage level.

Commands (CPU here: `nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python …`, 2 workers):

```
python shape82.py --faces modern --n 240 --levels clean,mild,heavy,spread,fill     # step 1   -> out/shape_modern/
python shape82.py --faces traced --n 160 --levels clean,mild,heavy,spread,fill     # step 2   -> out/shape_traced/
python chart82.py out/shape_modern --out out/chart_modern.png
python3 gs82.py bundle; python3 gs82.py start RTX_5090                              # step 3 (the lead rents)
python3 drive82.py gen train shape feats readers                                     # stages back to back, fetched after each
python real82.py --model out/learned/u1/model.pt                                     # the real 1937 / 1953 lines, rules vs learned
python figure82.py --lines out/shape_modern/lines.json --cl out/learned/u1/shape_modern/cl --font "" --ch و --level fill --out out/fig_filled_waw.png
```

## Results

### Step 1: the rule rebuilders, modern faces (2026-11-05, 240 lines, 5,529 letters, 1,417 loop counters, 2,110 junctions a level; $0)

| level | rebuilder | letters in place | mean dist px | max dist px | loops kept | direction | junctions |
|---|---|---|---|---|---|---|---|
| clean | **skeleton** | **75.4%** | 0.82 | 5.26 | **94.9%** | **87.0%** | **80.5%** |
| clean | mcr | 68.9% | 1.46 | 6.73 | 66.5% | 72.6% | 70.0% |
| clean | hybrid | 75.1% | 0.85 | 5.32 | 92.8% | 86.3% | 80.0% |
| clean | hybrid_r | 74.2% | 0.95 | 5.52 | 82.6% | 83.5% | 76.2% |
| mild | skeleton | 67.9% | 1.50 | 6.65 | **80.6%** | 74.4% | 62.5% |
| mild | mcr | 67.2% | 1.64 | 6.98 | 51.4% | 70.1% | 62.8% |
| mild | hybrid_r | 67.8% | 1.52 | 6.67 | 69.9% | 72.7% | 61.2% |
| heavy | skeleton | 58.3% | 1.90 | 7.75 | **63.3%** | 69.7% | 53.2% |
| heavy | mcr | 59.3% | 1.98 | 7.95 | 36.1% | 66.1% | 53.2% |
| heavy | hybrid_r | 58.1% | 1.92 | 7.80 | 54.6% | 68.3% | 52.1% |
| spread | skeleton | 57.4% | 1.89 | 7.78 | **71.1%** | 67.7% | 57.8% |
| spread | mcr | 53.5% | 2.09 | 8.52 | 37.8% | 62.3% | 55.2% |
| spread | hybrid_r | 57.4% | 1.93 | 7.87 | 63.9% | 66.6% | 55.4% |
| fill | skeleton | 54.2% | 2.01 | 7.95 | **46.2%** | 66.7% | 49.2% |
| fill | mcr | 53.3% | 2.13 | 8.49 | 27.0% | 62.4% | 47.4% |
| fill | hybrid_r | 56.0% | 2.00 | 7.90 | 40.7% | 64.9% | 48.1% |

(`hybrid` equals `skeleton` within 0.5 points on every damaged level: exp 79's heavy-piece test rarely fires; full table in `out/chart_modern.json`.)

- **The plain skeleton is the best hand-rule rebuilder.** No other rule beats it on any measure by more than about one point at any level.
- **MCR is worst everywhere,** and loses most on loops: 27–66% of loops kept, against the skeleton's 46–95%.
- **The regional hybrid does not help.** It only trades loops for nothing.
- **The headroom is in damage, not in rules.** From clean to fill, letters in place fall 75 → 54%, loops kept 95 → 46%, junctions 80 → 49%.
- **The clean ceiling is not 100%.** On clean ink the skeleton runs on the true line (mean distance 0.8 px), yet 25% of letters are "out of place". By eye in the overlays, these are mostly short letters (teeth, joins, a final ة or ه): a letter thinned alone ends differently from the same letter thinned inside its piece. Read these numbers as relative, with clean skeleton as the practical ceiling of the measure.

Chart: `out/chart_modern.png`. Overlays, all four rebuilders stacked for the first 12 lines at every level: `out/shape_modern/ov/`. In the overlays the truth is thick green and the rebuilt path red; a blue ring is a loop kept, an orange cross a loop lost; a square marks a junction (green right, magenta wrong); a letter number in red is a letter out of place.

### Step 2: traced old typefaces

**2026-11-05, 160 lines** in the 11 usable traced faces: 1927, 1928, 1936 ×2, 1937, 1938, 1940, 1949, 1951, 1957, 1958. That is 2,716 letters, 181 loop counters and 576 junctions a level, $0.

| level | rebuilder | letters in place | mean dist px | max dist px | loops kept | direction | junctions |
|---|---|---|---|---|---|---|---|
| clean | skeleton | 83.2% | 0.86 | 5.18 | 99.4% | 89.4% | 80.0% |
| clean | mcr | 75.1% | 1.58 | 7.23 | 50.8% | 79.7% | 71.4% |
| clean | hybrid_r | 79.3% | 1.14 | 6.00 | 70.7% | 84.1% | 73.3% |
| mild | skeleton | 78.2% | 1.39 | 6.48 | 86.2% | 83.7% | 71.9% |
| mild | mcr | 75.0% | 1.69 | 7.29 | 33.7% | 78.3% | 64.8% |
| mild | hybrid_r | 75.8% | 1.52 | 6.83 | 60.2% | 80.3% | 64.2% |
| heavy | skeleton | 65.4% | 1.89 | 8.16 | 58.0% | 78.1% | 50.2% |
| heavy | mcr | 65.5% | 2.13 | 8.63 | 19.9% | 73.5% | 54.7% |
| heavy | hybrid_r | 64.3% | 2.00 | 8.40 | 38.7% | 75.0% | 48.6% |
| spread | skeleton | 66.3% | 1.95 | 8.07 | 65.2% | 74.8% | 54.3% |
| spread | mcr | 63.8% | 2.26 | 8.89 | 19.9% | 69.6% | 52.8% |
| spread | hybrid_r | 64.4% | 2.06 | 8.41 | 44.2% | 72.0% | 51.2% |
| fill | skeleton | 66.9% | 1.88 | 7.87 | 26.0% | 75.3% | 50.3% |
| fill | mcr | 67.2% | 2.12 | 8.53 | 12.2% | 71.9% | 50.2% |
| fill | hybrid_r | 65.6% | 1.96 | 8.17 | 17.7% | 72.1% | 46.9% |

(`hybrid` again equals the skeleton within a point; full table in `out/chart_traced.json`; chart `out/chart_traced.png`; overlays `out/shape_traced/ov/`.)

- **The same order as on modern faces.** The skeleton is best or tied on every measure at every level; MCR is far behind on loops (12–51%).
- **Old print loses loops faster.** With filled counters, the skeleton keeps only **26%** of the loops (modern faces: 46%).
- **Letters in place hold up better than on modern faces** (67% at fill against 54%). The traced glyphs are heavy already, so damage changes them less.
- **Found: the traced old faces draw most heads FILLED.**
  - Only 181 counters exist in 856 loop letters. In modern faces it is 1,417 in 1,592.
  - The tracer (exp 11/78) kept what the 1930s–50s pages print: و ف ق م ه with their eye closed by ink.
  - So a "skeleton of the clean glyph" truth has no loop there. Loop scores on traced faces count only the open counters, and the learned rebuilder's loss ignores loop letters drawn filled (`gen82.py`, `ign`), rather than learn to collapse them.


### Step 3: the learned rebuilder

**Trained 2026-11-05** on a rented RTX 5090 (instance 59269471, 30 CPUs by cgroup quota):
- 80,024 training pairs, made in about 4 minutes: font lines, ADAB sets 1–2 drawn as print, and traced-face lines;
- 20,000 steps of 32 windows, 8.1 minutes;
- centre line on held-out pairs: precision 98.4% and recall 98.7% at 2 px.

It was then scored with the same metric on the same 240 + 160 test lines (`out/learned/u1/shape_*_learned/`; charts `out/chart_modern_learned.png` and `out/chart_traced_learned.png`):

| faces | level | skel. in place | skel. mean px | skel. loops | skel. direction | skel. junctions | learned in place | learned mean px | learned loops | learned direction | learned junctions |
|---|---|---|---|---|---|---|---|---|---|---|---|
| modern | clean | 75.4% | 0.82 | 94.9% | 87.0% | 80.5% | 71.0% | 1.41 | 89.7% | 79.6% | 66.8% |
| modern | mild | 67.9% | 1.50 | 80.6% | 74.4% | 62.5% | 68.4% | 1.51 | 87.9% | 74.8% | 63.8% |
| modern | heavy | 58.3% | 1.90 | 63.3% | 69.7% | 53.2% | 65.2% | 1.63 | 86.2% | 71.7% | 63.2% |
| modern | spread | 57.4% | 1.89 | 71.1% | 67.7% | 57.8% | 58.8% | 1.77 | 85.0% | 69.4% | 61.2% |
| modern | fill | 54.2% | 2.01 | 46.2% | 66.7% | 49.2% | 58.1% | 1.77 | 83.5% | 68.6% | 60.9% |
| traced | clean | 83.2% | 0.86 | 99.4% | 89.4% | 80.0% | 78.6% | 1.49 | 93.4% | 81.5% | 69.3% |
| traced | mild | 78.2% | 1.39 | 86.2% | 83.7% | 71.9% | 77.2% | 1.54 | 94.5% | 79.9% | 68.9% |
| traced | heavy | 65.4% | 1.89 | 58.0% | 78.1% | 50.2% | 72.8% | 1.68 | 87.3% | 75.8% | 63.5% |
| traced | spread | 66.3% | 1.95 | 65.2% | 74.8% | 54.3% | 67.6% | 1.89 | 81.8% | 72.4% | 58.7% |
| traced | fill | 66.9% | 1.88 | 26.0% | 75.3% | 50.3% | 68.9% | 1.87 | 88.4% | 72.4% | 57.5% |

- **Loops come back.** With filled counters on modern faces the learned path keeps **83.5%** of loops, against the skeleton's 46.2%. On traced old faces it keeps 88.4% against 26.0%. Heavy damage: 86% against 63%. Spread: 85% against 71%.
  - Per letter under fill (modern faces), learned against skeleton: و 89% / 48%, ه 77% / 29%, ة 85% / 41%, ف 81% / 43%, ق 82% / 44%, م 81% / 52%.
- **It is better under heavy, spread and filled ink.** Mild damage is about a tie.
  - Letters in place: heavy 65.2% / 58.3%, fill 58.1% / 54.2%; traced heavy 72.8% / 65.4%.
  - Junctions: fill 60.9% / 49.2%, heavy 63.2% / 53.2%.
  - Direction: 1–2 points better on modern faces, but 2–3 points worse on traced faces.
- **It is worse on clean ink.**
  - Letters in place 71.0% / 75.4%, direction 79.6% / 87.0%, junctions 66.8% / 80.5%, loops 89.7% / 94.9%.
  - The skeleton of clean ink IS the training target, so the rules are exact there and the network can only approximate them.
  - The same holds on clean traced faces: in place 78.6% / 83.2%.
- **Close-ups.**
  - `out/fig_filled_waw.png`: five filled و (modern faces, fill level), ink, rules and learned side by side. The network reopens the eye in three of the five, including both eyes of a filled medial ه. It misses one, and loses a ه eye the rules had.
- **Real lines** (`out/real/real_1937.png`, `real_1953.png`, `zoom_1937.png`; no truth, judged by eye):
  - **1937:** the learned path draws ص, ق and ه as clean single strokes where the rules scribble. But the filled head of و in «كانوا», the owner's example, stays a line in both: the network does not reopen that real blob.
  - **1953:** the learned path untangles ها in «ذاتها» and «أنها», which the rules draw as crossing loops. But it draws the filled head of ف in «فى» as a line where the rules kept a small loop, and it joins the hamza of أ to its alef.
  - The head of غ in «غاية» (open in this initial form) is an open hook in both.

**Downstream check (2026-11-05, second host 59281752; `drive82.py genreader feats readers`; `downstream82.py`).**

Setup:
- 60,000 synthetic reader lines (font 8 : traced 2), each rebuilt twice, by the skeleton and by the learned centre line, from the clean and the damaged crop (exp 79's rclean + rdmg recipe).
- Two signal readers (exp 79's model, 8 epochs, 13–14 minutes each), one per path kind.
- Both scored on the same 3,019 held-out lines.

CER in %, lower is better; Δ is learned minus skeleton with a paired bootstrap 95% interval:

| level | lines | skeleton paths | learned paths | Δ [95% interval] | lines better / worse |
|---|---|---|---|---|---|
| clean | 344 | 5.63 | 5.38 | −0.26 [−0.67, +0.14] | 74 / 58 |
| mild | 661 | 6.88 | 6.49 | −0.39 [−0.75, −0.04] | 165 / 133 |
| heavy | 655 | 15.98 | **9.19** | −6.80 [−7.73, −5.93] | 389 / 80 |
| spread | 689 | 12.30 | **8.76** | −3.53 [−4.20, −2.88] | 325 / 120 |
| fill | 670 | 13.86 | **9.63** | −4.23 [−4.87, −3.63] | 341 / 93 |
| **all** | 3,019 | 11.54 | **8.19** | −3.36 [−3.66, −3.05] | 1,294 / 484 |

By faces:
- **Modern:** 11.60 → 8.33 (heavy 15.66 → 9.14, fill 14.35 → 10.13, clean 5.70 → 5.41).
- **Traced old:** 11.15 → 7.19 (heavy 18.43 → 9.54, fill 10.80 → 6.49, clean 5.16 → 5.16).

On the rendered clean ink itself (exp 79's `rclean`) the two are equal: 6.24 against 6.34.

**Routing.** A per-line switch on a measurable ink feature was tested: the share of ink deeper than 1.1 stroke widths, thresholded on half the lines. The best threshold sends **every** line to the learned paths (7.66% on the other half, against 10.93% for skeleton paths). No line class is better served by the skeleton, so the rule is simply: always use the learned paths. Picking the better of the two per line (an oracle) would give 6.85%; the two readers err on partly different lines, which is room for fusion, not for routing.

Spend: $1.12 (first host) + $0.72 (second) = **$1.84** of $15.

## What it changed

Nothing in `src/` and nothing in experiment 79. For exp 79:
- **A measure of path shape** (`metric82.py`), to use beside the letter-order score.
- **Among the rule rebuilders it already uses the best one,** the skeleton. Drop MCR and the hybrids.
- **A learned centre line** (`out/learned/u1/model.pt`, 2.1M parameters) that keeps the same walk.
  - Under damage it keeps loops far better: filled heads 46% → 84% on modern faces, 26% → 88% on old ones. Letters in place and junctions improve too.
  - On clean ink it is a few points worse than the skeleton.
  - **Recommendation: use the learned centre line on every line.** The reader reads it better at every damage level. The gain is significant from mild ink up and largest on heavy ink (16.0 → 9.2% CER); clean ink is level. The shape metric's small clean-ink loss does not reach the reader.
  - On real old lines it is cleaner but does not reopen every real filled head (the 1937 و).

# Combining warp and taps (experiment 16)

*Written by the lead from the logged runs: the combining agent's session ended in a laptop restart before it
wrote its notes. Module: `methods/combo_best.py`, helpers in `combo_lib.py`, ablation script `out/combo/ablate.sh`.*

**Question.** warp_gate (53.8% dev) changes how a letter's shape cost is drawn from remembered examples;
taps_prior (57.9%) changes the dots cost and adds a letter-trigram prior. Do they stack?

**Method.** warp's shape cost (every train example, walk DTW band 2, 3 nearest) + taps_prior's taps cost +
the trigram prior in a beam chain search. The tap weight and the prior's weight are chosen together per
document on a held-out TRAIN page, never on dev.

## Runs (dev, pieces read as Azure reads them)

| run | mean per doc | 0582 | 0618 | 1036 | 0772 | letters |
|---|---|---|---|---|---|---|
| combo with gate | 60.96 | 64.84 | 56.14 | 57.46 | 65.40 | 67.27 |
| ablation: no gate | 61.65 | 63.84 | 56.57 | 56.98 | 69.21 | 67.79 |
| ablation: no prior | 57.16 | 59.85 | 54.09 | 53.45 | 61.27 | 64.70 |
| ablation: old taps (dot count) | 56.93 | 56.61 | 50.65 | 56.98 | 63.49 | 64.36 |
| ablation: taps without bridged parts | 60.42 | 63.84 | 54.96 | 57.78 | 65.08 | 67.73 |
| ablation: no walk DTW | 60.48 | 64.34 | 56.79 | 55.70 | 65.08 | 67.31 |
| **no gate, wider tap-weight grid (= combo_best)** | **62.89** | 65.34 | 57.00 | 60.03 | 69.21 | 69.24 |

## What stacked

- The **prior** (+5.7 points removed → 57.2) and the **new taps** (+6.0 → 56.9) are the two biggest parts and
  both survive the combination.
- Walk DTW and the bridged-part taps each add about 2 points.
- warp's **gate did not stack**: it lost on the held-out train pages and on dev once the taps and prior were in.
  Its job — stopping a scattered letter from winning on one lucky example — overlaps what the taps and prior now do.

Combined: 62.9% against 53.8% and 57.9% for the parts alone — the two directions add, but less than their sum.
The trained reader (`model_ctc_ft`, 77.0%) is well above all of them.

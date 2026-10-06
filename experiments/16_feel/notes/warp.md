# Warp: stretch-tolerant matching for the feeler (2026-10-06)

**Question.** feel.py compares a letter's stretch with remembered letters by stretching both evenly to a fixed
length. The README guessed that long joined pieces fail because a letter written a little longer here and
shorter there cannot match. Does matching that tolerates uneven stretching (dynamic time warping) fix that?

**Short answer.** Not much, and not for that reason. Warping the stick's walk helps a little but every time:
+1.7 points on the mean over the four documents, and better on each one. The big gains came from *how a letter's
cost is taken from its remembered examples*: remember every example (+7 points), and let a letter compete only
when its examples crowd round the stretch (a nearest-neighbour vote, +1 to +3). Best module:
`methods/warp_gate.py`. It reads **53.8%** of dev pieces as Azure does (mean per document), against feel_v1's 43.9%.

## Method (warp_lib.py)

- `seqs`: the same two sequences feel.py builds (8 pooled bins of the trunk feeling, 16 samples of the walk), kept
  as sequences and not flattened, with the same weights.
- `dtw`: Euclidean distance to every example (one matrix product), then symmetric2 DTW in a Sakoe-Chiba band on the
  64 nearest. The result is divided by 2, so band 0 gives exactly feel.py's distance. We checked that: band 0
  read 80/80 dev pieces the same as feel_v1. DTW is never larger than the even distance, so examples left out of
  the 64 keep an upper bound.
- `walk_var` / `dtw_var`: the walk at its own length (12 samples per rise travelled, at most 40), compared by
  anti-diagonal DTW with a relative band and normalised by path length.
- `Memory`: every example, grouped by position form (iso/init/med/fin) so a whole piece's candidate stretches are
  scored in one vectorised call. `Feeler.read` is feel.py's chain search, unchanged.
- `gate` (in `Feeler.costs`): a letter's cost is the mean of its k = 3 nearest examples. It competes only if those
  3 examples are among the 16 nearest of its position form; if no letter qualifies, all of them compete.

Diagnostics (scripts kept out of the repo; described so they can be redone):
(a) *naming with the cutter's cuts given*: each dev letter's true stretch and form, which letter wins;
(b) *blind vs oracle cuts*: the chain search restricted to the cutter's cuts.

## Runs (dev only; `bench.py table` holds them all)

Mean per document = mean of the four documents' piece accuracy. feel_v1's four documents came from two runs:
0582 = 43.14, 0618 = 35.88, 1036 = 42.22, 0772 = 54.29, so the **mean is 43.88** and the letters' mean 54.1.

| run (method: note) | mean/doc | letters | 0582 | 0618 | 1036 | 0772 |
|---|---|---|---|---|---|---|
| feel_v1 baseline | 43.88 | 54.1 | 43.14 | 35.88 | 42.22 | 54.29 |
| warp_dtw: DTW trunk band 2 + walk band 4, knn 1, 40 per letter | — | 54.93 | 42.39 | | | |
| warp_dtw: walk band 2, all examples, knn 3 | — | 60.78 | 51.62 | | | |
| warp_dtw: ablation cap 40, knn 3, walk band 2 | — | 56.88 | 44.89 | | | |
| warp_dtw: ablation all examples, no DTW, knn 1 | — | 60.29 | 50.87 | | | |
| warp_dtw: ablation all examples, knn 3, no DTW | — | 60.41 | 51.37 | | | |
| warp_dtw: walk band 2, all examples, knn 3 (all docs) | 50.91 | 59.63 | 51.62 | 43.21 | 51.36 | 57.46 |
| warp_dtw: walk at its own length, DTW rel. band 0.25 | 51.36 | 59.60 | 49.63 | 43.75 | 54.90 | 57.14 |
| warp_dtw: + gate 16 (k = 3) | 53.81 | 61.95 | 53.37 | 46.98 | 55.22 | 59.68 |
| warp_dtw: gate 32 | 52.48 | 60.37 | 51.37 | 45.26 | 54.57 | 58.73 |
| **warp_gate** (clean module = gate 16 run) | **53.81** | **61.95** | 53.37 | 46.98 | 55.22 | 59.68 |
| warp_dtw: ablation gate 16 with NO DTW | 52.10 | 61.57 | 51.12 | 45.58 | 52.97 | 58.73 |

warp_gate against feel_v1, by piece length (all four dev sets pooled):

| letters | feel_v1 | warp_gate |
|---|---|---|
| 1 | 647/946 (68%) | 803/946 (85%) |
| 2 | 203/556 (37%) | 249/556 (45%) |
| 3 | 63/363 (17%) | 82/363 (23%) |
| 4 | 27/260 (10%) | 38/260 (15%) |
| 5+ | 0/142 | 10/142 (7%) |

Cut agreement on pieces read right (within one stroke of the cutter's cuts): 0582 96.4% (feel_v1: 94.9),
0618 76.4 (78.2), 1036 83.7 (87.5), 0772 72.8 (76.2). These are over more pieces than feel_v1's (83/203/166/92
cuts against 79/142/88/84). That is about the same; the cuts were never the problem (see below).

## What helped, and why I think so

1. **Remember every letter, not 40** (+6.7 on 0582: 44.89 → 51.62 with everything else the same). Letter forms vary in a document (joins, kashida, ink), and with nearest-neighbour matching more
   remembered examples cover more of that variety. feel.py capped them at 40 per letter-form to keep things
   fast; the vectorised scoring makes the cap unnecessary (< 0.5 GB, 25-100 s per document).
2. **The neighbourhood gate** (+1.3 to +3.9 per document over the same setup without it). With the cutter's cuts
   given, the letter named right went 61.8→67.1 (0582), 61.2→67.2 (1036), 66.3→72.4 (0772). I found it by
   accident: the shortlist for the variable-length walk DTW set every example outside it to infinity, and
   naming jumped by 7 points on 1036. A fair shortlist (a few examples of every letter) took the gain away, so it
   came from the shortlist's filtering, not from the warping. Single-nearest distance lets a scattered letter-form
   win a stretch with one lucky example. The vote asks for a crowd.
3. **DTW on the walk, band 2 of 16 samples** (+1.7 mean, + on every document: 0582 +2.3, 0618 +1.4, 1036 +2.3,
   0772 +1.0). Naming with true cuts: +1 to +3.6 on all four. The walk is the right place for it: it is the
   signal with its own clock (time spent in branches and loops varies), and band 4 was worse than 2.

## What did not help

- **Warping the trunk outline** (8 pooled bins): ±0.3 in naming at band 1–3, including at 16 bins. Pooling per
  bin already gives the tolerance; with nearest-neighbour matching, the even comparison is a good enough measure.
- **The walk at its own length** (variable-length DTW, about 6× slower): it looked like +3 to +7 in naming. That
  turned out to be the shortlist effect above; with the shortlist made fair it was −3 to −5. On blind pieces it
  added +0.45 mean, from the same effect. Dropped.
- **DTW from the first run** (trunk band 2, walk band 4, still 40 per letter): −0.75 on 0582. Warping makes
  every letter cheaper, wrong ones too. Without more examples and the vote, that only blurs.
- **Standardising every channel to the same spread**: ±0.4. The hand weights in feel.py are fine.
- **A margin of context round each stretch** (0.15 or 0.3 rise): −1.4 to +0.9, inconsistent.
- **Each letter's own spread of length** (a Gaussian cost on log length) and **LEN_W 3**: worse on 1036 blind
  (344 → 323 / 334 pieces). **LETTER_COST 0 or 0.5**: worse (0 gives too many letters, 0.5 too few).
  feel.py's three constants stay.
- **Segmental / subsequence DTW over the whole piece**: not built, on the evidence. The candidate cut places
  contain every one of the cutter's cuts (100% within a stroke, 0582 and 1036). Reading with the cutter's cuts
  *forced* is no better than reading blind (1036: 2 letters 60 vs 62, 3: 15 vs 17, 4: 7 vs 14, 5: 0 vs 6). Long
  pieces fail because each letter is named wrong (medials about 40%, finals and initials 60–68%), and those
  errors multiply along the piece. Where the cuts go is not the problem, and whole-piece warping only moves cuts.

## Constants tuned on dev

Three: gate 16 (tried 8, 12, 16, 32), walk band 2 (tried 0, 1, 2, 4), and k = 3 nearest (tried 1, 2, 3, 5).
Everything else is feel.py's, unchanged. The other settings tried (variable walk, margin, length model, letter
cost) were rejected, not tuned. The gate is the shakiest: 16 against 32 is a 1.3-point difference, and 16 was
the first value tried.

## Open risks

- The gate depends on how many examples a letter has. A rare letter (fewer than 3 examples in its position form)
  can never pass, and only competes when nothing else does. That fits 'the document is the witness', but it will
  hurt rare letters on the test pages if train has few of them.
- All dev numbers are against Azure's reading. One 0582 confusion, ا read as أ (26 times with true cuts), may be
  Azure dropping a hamza that is printed.
- Most of the remaining error is in naming medial letters, and half of it is shape (tooth against loop: م/ت,
  و/ر/د, ل/ن), not dots. Better matching of the same feeling seems near its ceiling. A learned model of the
  sequence (the model_ctc runs: about 75%) is the bigger step.

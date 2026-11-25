# Experiment 95 — the writer, round 3: contrast, learned letters, one pen

**Question (owner, approved 2026-11-09).** Experiment 87's writer redraws real clean lines (IoU 0.55–0.58), but as a
checker it sees missing or added text, not wrong letters. Four ideas, each tested on its own:
1. **Contrastive checking.** Write the competing readings and compare them on the ink of the disputed word only,
   with the rest of the line held fixed. Which reading explains that word's ink better?
2. **Learned per-journal letter programs.** Fit the letter recipes themselves (points and widths of every letter
   form, dots included) across thousands of lines of a training-pool journal.
3. **One pen.** Each connected letter piece becomes one continuous pen path that retraces where it must, instead of
   centre-line edges that all start at a junction ("two pens").
4. **Harvest** (only if 1–3 leave budget): real pen paths and letter regions from well-fitted training-pool lines.

Caps: GPU $12, no paid APIs. The code reuses experiment 87's files by importing them; none of them is edited.

## Pre-registered criteria (written 2026-11-09, BEFORE any test was run)

Rules for every idea: held-out journals (`76_finetune_pilot/out/split76.json`) are test only, never fitted or
learned on; locked journals and documents (`84_display_fonts/locked.py`, `88_truth_and_lock/locked_old.py`) are
never used. Code asserts both. Every scoring rule (which mismatch measure, any margin) is chosen on POOL pages only,
frozen in `out/rule95.json`, then applied once to held-out tests. Confidence intervals: 95%, bootstrap over pages
(1,000 draws) unless said otherwise.

### Idea 1 — contrastive checking

*Method fixed in advance.* For a line and its distinct candidate readings (strict form `agree81.form`), the common
leading and trailing words are the context; the words between are the disputed span. An anchor fit (exp 87's
frozen page style, line position, baseline and warp fitted) places the context. Each candidate's disputed span is
then written into the gap between the fixed context and fitted locally (its start and its own warp; style, size and
baseline fixed), and scored only on the gap's ink with the context's writing included. Every distinct candidate up
to three (v1's, s2r's, Azure's, in that order) serves once as the anchor and the scores are averaged over anchors.
The pick is the candidate with the best gap score; an exact tie goes to v1.

*Main test.* Exp 81's judged held-out sample lines with a truth (the judge's verdict), at least two distinct
candidates, the truth among them, every candidate writable (no glyph missing in a disputed span). Weights are exp
81's strata, as in exp 87.
- **Target subset: disputes of one or two letters** (largest edit distance between any two distinct candidates ≤ 2).
- **PASS** if the contrastive pick equals the judge's reading on **≥ 70%** (weighted) of the subset **and** the
  paired difference (contrastive − always v1) on the same lines has a 95% interval **above 0**.
- Reported beside it: chance (1 / candidates), always v1, exp 87's absolute score on the same lines, all disputes,
  by edit-distance bin, era and kind of difference (hamza, dots, ى/ي, ة/ه, space, other), and the margin-gated rule
  (switch away from v1 only when the margin beats δ, δ chosen on pool).

*Planted ladder (rungs, in order).*
- Rung 0, synthetic: font-rendered lines written with their own face; the true word against its dot / hamza siblings.
- Rung 1, pool (design only): orig against each planted kind (letter, word_sub, word_drop, word_add) and the sibling
  test. The gap measure and δ are chosen here.
- Rung 2, held-out pages (test): the same, frozen.
- **Secondary target (letter-level signal):** on held-out pages, the true reading beats its planted dot sibling in
  **≥ 80%** of pairs (exp 87's absolute checker caught ~11% at 10% false flags). Sibling test: the true word ranks
  first among all its one-letter dot / hamza / ى / ة siblings more often than chance, with an interval.

### Idea 2 — learned per-journal letter programs

*Method fixed in advance.* 3–4 training-pool journals with many pages (two modern, one or two old print), split by
DOCUMENT into learn and test documents. Labels: consensus lines (v1's reading equals Azure's under `no_punct`, every
Azure word confidence ≥ 0.9). The base library per journal is the one that wins a screening on learn lines. The
learned settings: every point of every letter program used (dx, dy, log width), dots and marks as their own strokes,
regularised toward the base shape and smooth along each stroke; the journal's style and every line's position are
fitted jointly.
- **Main test:** median IoU (96 px, exp 87's ceiling fit: true text, all style settings fitted on the line, same
  iterations) on test documents' lines, learned programs against the base library on the same lines.
- **PASS per journal** if the learned median IoU is **≥ 0.70** (base ~0.57). The idea PASSES if at least half the
  journals pass. Reported beside it: the paired gain with a document-bootstrap interval, chamfer, per era.
- **Second test** (only if the main gain is real): idea 1's contrastive test on held-out journals with the nearest
  learned library (chosen by fit on the page's style lines, as exp 87 chose libraries), against the base library on
  the same lines (paired interval).

### Idea 3 — one pen

*Method fixed in advance.* For each glyph, its strokes are joined into connected pieces (end points within 0.035 em);
each piece becomes one route that visits every edge, retracing the fewest edges needed (a Chinese-postman route on
the piece's graph); dots and marks stay separate pen lifts, written after their body. The soft order cost prefers a
start at the piece's top right and right-to-left travel (AlQalam's own stroke order where the library is AlQalam).
- **(a) Fit quality.** Without learning the ink of a route equals the ink of its edges by construction (same
  capsules), so the check is that the ceiling IoU is identical (difference 0.000). With learning (idea 2), one pen
  ties the junction points (one point for all branches) where edges let them drift apart. **PASS** if the test-line
  IoU with one pen is not worse than with edges beyond noise: the mean paired difference's interval lies above
  −0.01.
- **(b) Path shape.** The fitted paths exported as pen paths and scored with exp 82's `metric82.shape_score`
  against exp 82's synthetic truth (clean modern and traced faces), three exports of the same fits: edges ("two
  pens"), one pen, one pen + order cost; exp 82's skeleton rebuilder on the same lines as reference. **PASS** if one
  pen + order raises direction-right and junctions-right over edges, and letters-in-place drops by at most 2
  points. The continuity constraint and the order cost are reported separately, by era and font family.
- **(c)** Mid-frames of a few stroke animations, edges against one pen.

### Idea 4 — harvest

Lines of the training pool fitted with IoU ≥ 0.65 (and ≥ 0.60) export pen paths and per-letter regions. Report how
many lines qualify, by era. No retraining here.

### Kill criteria (after the ladder only: at least two rounds per idea)
- Idea 1 is dropped as a letter checker if, in both rounds, the main subset's paired difference against always v1
  has an interval that includes or lies below 0.
- Idea 2 is dropped if, in both rounds, no journal's median test IoU gains ≥ 0.03 over its base library.
- Idea 3 is dropped if one pen costs fit quality beyond the noise bound in both rounds, or adds nothing to the path
  shape in both rounds.

## Method

All fitting reuses exp 87's writer (`writer87.py`, `fit87.py`, imported unchanged) on rented GPUs; analysis is local.

**Letter programs, completed (`prog95.py`).** 87's font programs hold only the glyphs 87's texts used. A sibling,
planted variant or new journal line could need a missing glyph, and the writer would write nothing for it, so a wrong
candidate would lose for a reason unrelated to the ink. Every glyph HarfBuzz uses on our texts is built 87's way and
added (`out/programs/`). Any group where a candidate still has a missing glyph is left out and counted.

**Idea 1 (`contrast95.py`, `analyse95.py`).**
- Candidates and the disputed span: as pre-registered. AlQalam needs Persian code points (ی ک ھ) mapped to the
  Arabic letters that print the same (`common95.aq_text`). Fonts shape them with HarfBuzz as they are.
- Anchor fit: exp 87's page style (`87_writer/out/run/style_{pool,held}.jsonl`), frozen; 100 steps; 87's round-2
  warp floor (0.6).
- Gap fit: the span's start and warp (knots every 0.5 em, slope 0.6–2.0), 60 steps, blur 2 → 0.6 px. Two starts:
  fill the anchor's span, or natural width. The soft loss decides between them.
- Window: the gap ± 0.3 em. The fixed context's writing is drawn in, so context ink near the edges counts the same
  for every candidate.
- Gap scores per candidate: soft IoU loss (σ 0 and 0.6 px), hard IoU, chamfer, missing ink, invented ink.
- Sets:
  - synth: 87's 115 font-rendered lines, own face, style fitted with the true text; sibling test only.
  - pool: 375 test lines of 87's pool pages; pairs orig vs letter / word_sub / word_drop / word_add, and the
    sibling test.
  - held: a fixed 60% hash sample of 87's held-out planted test lines; pairs orig vs letter / word_sub, and siblings.
  - judged: 2,615 judged held-out lines with ≥ 2 distinct candidates (strict form), up to 6 candidates.
- Siblings: one word of the line, every one-letter change within the groups بتثنيئ, جحخ, دذ, رز, سش, صض, طظ, عغ,
  فق, هة, اأإآ, ىيئ, وؤ; 6 at most (seeded by line key). A traced face never writes its excluded letters (87's
  `lib_ok`).
- Rule design (`analyse95.py design`), on pool groups only:
  - 10 gap measures × 3 ways of combining anchors (mean; the best-fitting anchor; minimum);
  - objective: the mean of letter-pair, word_sub-pair and sibling top-1 accuracy;
  - δ: the smallest margin above which pool pairs are right ≥ 90%.
  - All of it frozen in `out/rule95.json` before any held-out or judged output was opened.

**Idea 2 (`data95.py journals`, `learn95.py`).**
- Journals: 0013 and 0523 (2010s–2020s), 0924 (1920s) and 0739 (1930s). 0690 (1920s) was tried and gave only 97
  consensus lines.
- Consensus lines: v1 = Azure under `no_punct`, every Azure word ≥ 0.9, Arabic letters only. Split by document;
  ~15% of documents are test.
- Base library: the best median IoU of a 48-line, 60-step screen among the era's candidates.
- Learning: as pre-registered (see the docstring of `learn95.py`). Offsets per program point (dx, dy, log width).
  Adam steps of 0.0012 em and 0.006 in log width, clamped. A magnitude prior and a second-difference smoothness
  prior apply only to the points the batch uses.
- Evaluation: test documents' lines, plus 96 learn lines as a train check, with 87's ceiling fit (160 steps, all
  style free). A learned library is written through `install()`: 87's shaping, then each stroke replaced by its
  learned points.

**Idea 3 (`onepen95.py`, the `onepen` variant of `learn95.py`).**
- Routes: as pre-registered. When the route joins two edges at a junction node (ends within 0.035 em), the short
  step between their end points is drawn and marked as a retrace.
- `check`: the ink of one pen + order against the edges' ink from the same fitted settings.
- Path shape: exp 82's own test-line picker (`lines82.pick_lines`, 120 modern + 120 traced, clean; 218 had a font
  with programs). Each line is fitted once with its own face (GPU, 160 steps, true text). The three routes are placed
  with those settings and scored with `metric82.shape_score` against `truth82`. Exp 82's skeleton rebuilder is scored
  on the same lines.

## Results

GPU: one RTX 5090 ($1.29/h), rented 2026-11-09 by the lead. No paid API.

### Idea 1: contrastive checking

**The frozen rule** (`out/rule95.json`, chosen on the 1,865 pool groups):
- the measure is the chamfer distance on the gap's columns, taking the best anchor (min);
- δ = 0, so the gated rule is the plain pick;
- IoU-style losses lose more often: they favour the candidate with fewer dots.

**Planted ladder** (true reading vs wrong; a tie counts as half):

| rung | dot sibling pair | word_sub pair | word_drop | word_add | true word first among ~6 siblings (chance) |
|---|---|---|---|---|---|
| 0 synthetic (115 lines, own face) | – | – | – | – | 77% (17%) |
| 1 pool (design, 375 lines) | 86% [82, 89] | 94% | 97% | **52%** | 49% (16%) |
| 2 held-out pages (frozen, 612 lines) | **86.3% [83.5, 89.1]** | 91.6% [89.3, 93.8] | – | – | **56.4% [52.3, 60.6]** (16%) |

- By era (held-out letter pairs): pre-1950 95% (40 lines), 1950–99 87%, 2000+ 84%.
- When a wrong sibling wins, it has more dots about as often as fewer (held-out 123 vs 109): no systematic bias.
- **Secondary target (≥ 80% on planted dot siblings): PASS.** Sibling ranking above chance: PASS.
- An added word is a coin flip (52%). The wrong anchor squeezes the extra word into the line, and the context
  around it then explains ink no worse.

**Main test: exp 81's judged held-out disputes** (`out/contrast_judged.json`; 2,094 lines scored).
- Left out: 187 without an answer, 295 whose truth is no candidate, 31 unreadable, 8 not writable.

| subset | lines | contrastive [CI] | always v1 | chance | exp 87 absolute | contrastive − v1 [CI] |
|---|---|---|---|---|---|---|
| **1–2 letters (MAIN)** | 1,557 | **59.6% [53.1, 65.9]** | 69.7% | 46.3% | 47.9% | **−10.1 [−17.7, −2.8]** |
| all disputes | 2,094 | 56.0% | 66.5% | 43.8% | 45.8% | −10.5 [−16.8, −4.5] |
| 3–5 letters | 466 | 41.1% | 51.4% | 31.6% | 36.9% | −10.3 [−24.5, +5.4] |
| main, pre-1950 | 155 | 66.7% | 68.9% | 45.6% | – | −2.2 [−10.8, +5.5] |
| main, 1950–99 | 1,155 | 57.2% | 68.9% | 46.1% | – | −11.6 [−20.1, −2.9] |
| main, 2000+ | 247 | 73.0% | 75.9% | 47.8% | – | −2.9 [−15.3, +10.7] |
| main, hamza | 451 | 69.8% | 74.7% | 45.8% | 57.0% | −4.9 [−22.8, +12.2] |
| main, space | 324 | 57.1% | 50.8% | 43.6% | 42.6% | +6.4 [−13.5, +24.8] |
| main, ى/ي | 237 | 56.1% | 70.8% | 48.3% | 40.9% | −14.8 [−25.9, −5.1] |
| main, dots | 134 | **38.2%** | 70.4% | 44.1% | 40.8% | −32.2 [−55.1, −12.1] |

- **Main criterion: FAIL.** 59.6% is below the 70% target. The difference from always-v1 has an interval wholly
  below 0.
- It beats chance and exp 87's absolute score (48%) on the same lines.
- The planted test and the real disputes disagree most on dots: 86% against 38%. A planted error puts a clean wrong
  dot pattern beside clean true ink. A real dispute happens where the ink itself is unclear (broken, faint or filled
  dots), which is exactly why two readers disagreed. There the writer's misfit is larger than the difference
  between the candidates.

### Idea 2: learned per-journal letter programs (and 3a)

**Round 1 learned nothing.**
- Settings: 0013, one pen, 2 epochs, batch 48. The training IoU stayed at 0.37.
- The offsets averaged 0.0005 em. A gradient check showed the cause: the priors were balanced against the data
  gradient at about 0.002 em. They held every point in place.
- The second job (0013 edges) ran out of GPU memory, and the keeper then destroyed the host as designed.

**Round 2** (2026-11-10, second host): priors × 0.01, so the clamp and the smoothness prior bound the offsets; one
epoch; batch 32. Jobs: 0013 one pen and edges, 0924 one pen. Out of budget: 0523, and 0739 (427 lines).

| journal (base library) | test lines / docs | base median IoU | learned median IoU | gain (mean) [doc CI] | chamfer px, base → learned |
|---|---|---|---|---|---|
| 0013, 2010s–20s (Noto Naskh) | 260 / 15 | 0.417 | **0.468** (edges) / 0.451 (one pen) / 0.420 (round 1) | +0.069 [+0.052, +0.088] / +0.051 [+0.036, +0.071] | 1.10 → 0.95 |
| 0924, 1920s (Amiri Bold) | 260 / 5 | 0.508 | **0.551** (one pen) | +0.042 [+0.032, +0.052] | 1.56 → 1.51 |

- **Main criterion (≥ 0.70 on unseen pages): FAIL** in both journals; the idea needs half the journals to pass.
- The gain is real and carries over to unseen documents: about +0.04 to +0.07 IoU, with intervals above 0. So the
  kill criterion (no journal gains ≥ 0.03) does not hold.
- These lines' base IoU (0.42 and 0.51) is lower than 87's pool lines (0.55–0.58). They are ordinary consensus
  lines, not 87's cleanest ones.
- The learning moves points by only 0.006–0.014 em (0.3–0.8 px) on average. It is a refinement of the font, not a
  new hand.

**Second test: the contrastive check with a learned library on held-out judged lines** (run because the gain is
real; `out/contrast_judgedL.json`).
- Deviation from the pre-registration, for budget: the "nearest" learned library was not chosen by refitting each
  page's style lines. A page whose exp 87 library is a learned library's base uses that learned library with the
  page's frozen style. Amiri Bold pages use L:0924:onepen_r2 (579 groups); Noto Naskh pages use L:0013:edges_r2
  (108 groups).
- 546 lines were scored. The comparison is paired with the base-library run on the same lines:

| subset | lines | learned | base | always v1 | learned − base [CI] |
|---|---|---|---|---|---|
| 1–2 letters | 374 | 63.0% | 65.5% | 67.4% | −2.5 [−15.2, +9.2] |
| all | 546 | 57.8% | 60.0% | 66.8% | −2.1 [−10.7, +6.5] |
| real dot disputes | 33 | 41.1% | 36.1% | 62.4% | +5.0 [−11.1, +23.9] |
| hamza | 94 | 55.0% | 76.7% | 80.6% | **−21.7 [−31.9, −12.0]** |

- **The learned library does not rescue the real disputes.** Dots move by +5 points with a wide interval on 33
  lines, still far below v1.
- Hamza gets clearly worse. 0924's programs were learned on 1920s print and moved the hamza marks toward that
  journal's placement. Amiri Bold pages of other journals and decades don't share it.

**3a, one pen against edges while learning** (0013, round 2):
- Test lines: one pen − edges = **−0.017 IoU [−0.030, −0.003]**. The pre-registered bound is that the interval lies
  above −0.01: **FAIL**.
- Learn lines: −0.004 [−0.028, +0.018].
- Tying the junction points holds the letter together, but it also removes freedom: the one-pen offsets moved
  half as far (0.0065 against 0.0138 em).

### Idea 4: harvest (from the round-2 training fits, no extra GPU)

| journal | learn lines | fit IoU ≥ 0.65 | ≥ 0.60 |
|---|---|---|---|
| 0013 (2000+), edges r2 | 1,700 | 256 (15%) | 394 (23%) |
| 0013 (2000+), one pen r2 | 1,700 | 221 (13%) | 374 (22%) |
| 0924 (pre-1950), one pen r2 | 1,700 | 415 (24%) | 900 (53%) |

- These are training-time fits (100 steps on the line, then the joint steps).
- No paths were exported: the round-2 hosts did not save per-line settings. `learn95.py` keeps them in memory
  only, so the export needs a refit.

### Idea 3: one pen

- **Ink check:** the ink of one pen + order equals the edges' ink from the same fitted settings, up to the short
  joining steps at junctions: 67 binary pixels differ over 3 full lines (`out/onepen/check.json`).
- **Path shape** (`out/onepen/shape.json`): exp 82's metric on 218 synthetic test lines (98 modern, 120 traced
  faces, clean). The writer's own fits reach median IoU 0.79 and chamfer 0.13 px.

| path | letters in place | mean d px | Fréchet | direction right | reversed | loops gone round | junctions right |
|---|---|---|---|---|---|---|---|
| edges ("two pens") | 46.9% | 2.31 | 18.1 | **51.7%** | 24.9% | 0% | 52.9% |
| one pen | 47.7% | 2.35 | 15.9 | 34.0% | 17.3% | **74.3%** | 53.4% |
| one pen + order | 47.4% | 2.35 | 15.8 | 34.5% | 16.7% | 43.6% | 53.3% |
| exp 82 skeleton rebuilder (reference) | 79.3% | 0.85 | 6.8 | 89.2% | 3.9% | 96.7% | 79.2% |

- The same holds in every traced family and for modern faces (`by_family` in shape.json).
- **3(b) criterion: FAIL.** One pen + order lowers direction-right by 17 points and leaves junctions level.
- Separately:
  - **the hard continuity constraint helps loops** (0 → 74%) and Fréchet (18.1 → 15.9);
  - **the soft order cost hurts loops** (74 → 44%) and changes nothing else.
- Fewer points travel against the truth's direction (25 → 17%). But many more travel at an angle: retraced
  joins and branch order don't follow the truth's walk.
- All three writer paths sit far from the truth (letters in place 47% against the skeleton's 79%), even though the
  ink fits. The font programs' centre lines (87's U-Net edges, smoothed and thinned out) are themselves 2 px off
  the walk that exp 82's truth takes.
- 3(c): mid-frames in `out/look/onepen_frames.png` (35/50/65% of the path; edges above, one pen + order below,
  retraces green). One pen travels a letter as one continuous trace, e.g. the ٨ and the loop of ط, where the edges
  start several strokes at one junction.

### Criteria, plainly

| idea | criterion | number | verdict |
|---|---|---|---|
| 1 | judged 1–2 letter disputes ≥ 70% and above always v1 | 59.6% [53.1, 65.9]; −10.1 [−17.7, −2.8] vs v1 | **FAIL** |
| 1 | held-out planted dot siblings ≥ 80% | 86.3% [83.5, 89.1] | PASS |
| 1 | sibling ranking above chance | 56.4% [52.3, 60.6] vs 16% | PASS |
| 2 | unseen pages' median IoU ≥ 0.70 (half the journals) | 0013 0.468, 0924 0.551 | **FAIL** |
| 2 | kill: no journal gains ≥ 0.03 | +0.069 and +0.042 (CIs above 0) | not met: the gain is real |
| 3a | one pen vs edges while learning, CI above −0.01 | −0.017 [−0.030, −0.003] | **FAIL** (small cost) |
| 3b | one pen + order: direction and junctions up, letters in place within 2 pts | direction −17 pts, junctions level | **FAIL** |

Kill criteria apply only after two rounds per idea:
- Idea 1 ran one design round (pool), the planted ladder and one judged round. The second judged round, with learned
  libraries, did not change the picture.
- Idea 2 had two rounds.
- Idea 3 had one round each for (a) and (b).

**Spend:** GPU **$8.71 of $12**, on two RTX 5090 rentals ($6.33 + $2.38). No paid API.

## What it changed

- Nothing in `src/` and nothing in another experiment's results.
- **Comparing readings on the disputed word is the right way to ask the writer.** On planted one-letter errors it
  is right 86% of the time, against about 11% for exp 87's absolute score. That makes it a measuring tool for any
  candidate pair where the ink is clean.
- **It is not a letter checker for real reader disputes.** It is right 60% of the time, against 70% for simply
  trusting v1. Real dot disputes, where the ink itself is unclear, get 38%.
- A per-journal learned library helps the fit a little (+0.04 to +0.07 IoU). It does not help the real disputes, and
  it hurts hamza on other journals.
- One pen gives paths that go round loops (0 → 74%) and look like writing. But it doesn't bring the pen path closer
  to exp 82's truth on direction or junctions, and it costs a little fit when learning.
- Reusable pieces:
  - `contrast95.py`: the gap fit, candidates written on the disputed span with the context fixed;
  - `learn95.py`: differentiable letter programs with shared per-point offsets, and `install()` for learned
    libraries;
  - `onepen95.py`: Chinese-postman pen routes and exp-82-format path export.

## Status

Done (2026-11-10). Both hosts were destroyed and checked: no instance is left.

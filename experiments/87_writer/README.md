# Experiment 87 — a reader that knows how to write (stages 1–2)

**Question (owner, 2026-11-05; approved for stages 1–2 on 2026-11-06).** Can the machine learn *how Arabic is
written*, with letters as pen-stroke programs and fonts and hands as style settings? Two parts:
1. A **writer**: letters plus style go in, ink comes out. How closely can it reproduce real clean lines?
2. **Re-write to verify**: write a candidate reading in the page's own style and compare it with the ink. Does that
   catch a reader's wrong lines?

Caps: GPU $8, no paid APIs. Plan: [PLAN.md](PLAN.md).

## Success criteria (written 2026-11-06, BEFORE any test was run)

**Stage 1, the writer (the ceiling).** The writer gets the TRUE text and fits its settings on the line itself. On
clean training-pool lines (modern, 1950–99, pre-1950), scored on 96-px crops:
- *works*: median ink IoU ≥ 0.55 and median chamfer ≤ 1.0 px on modern and 1950–99 lines, and IoU ≥ 0.45 on
  pre-1950 lines;
- *discriminates*: the true text fits clearly better than another line's text of the same length in the same
  library (the wrong-text control). Required: IoU(true) > IoU(control) on ≥ 95% of lines.
- **Kill signal (part 1 of the ladder's kill):** the median IoU of the true text is no better than the control's by
  more than 0.05, i.e. the writer cannot reproduce real lines at all.

**Stage 2, the checker.** The scoring rule is designed only on POOL pages, with planted errors. It is then frozen and
applied once to the held-out tests.
- **Main (PLAN.md):** on exp 81's judged held-out lines, flag ≥ 60% of v1's wrong lines at a 10% flag rate
  (stratified weights as exp 81). The baseline is the two-reader warning (v1 vs s2r disagreement): recall 32%
  strict / 55% folded at 10% flagged; s2r's likelihood: 30% / 49%.
- **Or a clear addition:** the checker rank-combined with the two-reader warning raises recall at 10% flagged by
  ≥ 5 points over the warning alone, with a bootstrap 95% interval above 0.
- **Planted errors on held-out pages:** report recall per kind (word_sub, letter, word_drop, block_drop, word_add)
  at the threshold that flags 10% of the right readings. PLAN.md asks that every planted omission and invention be
  caught (block_drop, word_drop, word_add ≈ 100%). We accept ≥ 90% for block_drop and word_add, and report the rest.
- **Picks the judge's verdict:** among a judged line's distinct candidates, the lowest-mismatch candidate is the
  judge's right one more often than chance (1 / number of candidates) and more often than "always v1".
- **Kill signal (part 2):** the checker adds nothing to the two-reader warning on judged lines (the combination's
  interval includes 0). Kill only if both kill signals hold after the ladder (synthetic → clean modern → old print
  → calligraphy demo), several rounds per rung.

## Method

**Letter programs (`alqalam87.py`, `fontprog87.py`).** Every letter form is a list of pen strokes. A stroke is an
ordered polyline of points (x, y, r0) in em units, where r0 is the half-width there. Three sources:
- **AlQalam 0.2** (LPPL 1.3+). Its METAFONT source is run by the real METAFONT: Ubuntu's texlive-binaries 2023,
  unpacked into `out/tex` without root. A hook file prints the pen and the path of every `draw` and `fill` to the log.
  That gives 256 char codes and 683 broad-nib pen strokes; r0 is the square nib's half-extent across the stroke. The
  50 filled shapes (the bowls of ر and ح, round dots) become medial-axis strokes. The bodies are rasm shapes: our
  joining rules pick the form, and the dots are placed at anchors computed from each body's geometry (`writer87.py`).
- **Our fonts**: exp 78's 13 OFL faces (SIL OFL 1.1; the licence files sit beside them) and the 11 usable traced faces
  (ours; exp 78's `exclude.json` is respected, and code asserts that no traced face comes from a locked journal). Every
  glyph HarfBuzz uses on our texts is rasterised at exp 82's scale. Exp 82's learned centre line
  (`out/learned/u1/model.pt`) is cut into its edges, each a stroke running right to left, and r0 comes from the
  distance transform.
  - Exp 79/82's walk was tried first. Its spur pruning drops the short teeth and tails that make up single glyphs,
    so it was replaced.
  - Coverage: 99–879 glyphs per face, 3k–32k strokes; the writer redraws Amiri almost exactly
    (`out/look/font_amiri_Amiri-Regular.png`).

**Style settings (`writer87.py`, `fit87.py`).** Per style: size, slant, pen-width multiplier, ink spread or erosion,
broad nib (angle, thin/thick ratio, width) with a contrast mix (0 = the program's own widths, 1 = a pure nib), and
mark placement (dx, dy above, dy below, scale). Per line: x offset, baseline offset, tilt and curve, plus a monotone
warp of x with a knot every 0.5 em; the warp also plays the role of kashida and spacing. Writer-only settings:
kashida insertion, pair stacking (calligraphy) and noise.

**Renderer.** Every stroke segment is a tapered capsule, and a pixel's ink is sigmoid((r - d)/0.6 px), the maximum
over segments. It is computed in 16-px column tiles, sorted by segment count and chunked with gradient checkpointing.
It is fully differentiable, batched over lines, and runs in PyTorch on the GPU.

**Fitting.**
- Target: exp 79's binarisation of the 96-px crop, with the neighbouring lines' ink removed.
- Initial size: the ink extent and the body height. Initial warp: DTW of 4-band column profiles.
- Adam on the soft IoU, blurred from coarse to fine, weighted toward sparse ink so that dots and teeth count.

**Scores.**
- IoU of written ink against real ink.
- Chamfer: the mean of the two directed mean nearest-ink distances, in px at 96 px.
- Recall: real ink within 1.5 px of writing. Precision: writing within 1.5 px of ink.
- The checker's local features: the worst 0.6-em and 1.5-em windows of ink with no writing ("missing") and of
  writing with no ink ("invented").

**Data (`data87.py`, `plant87.py`, `synth87.py`).**
- Rung 0: 115 synthetic lines drawn from the fonts' own outlines.
- Pool, for the ceiling and for designing the checker: 642 clean lines from 89 training-pool pages (exp 77/80/83's
  pool) in three eras. Every Azure word confidence is ≥ 0.95 (≥ 0.85 before 1950), and the lines are Arabic only.
- Held-out tests: exp 81's 3,112 judged lines, with the 96-px judge crops. Each judged page also gets up to 6 lines
  where Azure, v1 and s2r agree: 3 fit the page's style, and 2 are planted tests. Rules asserted in code: no split76
  page or journal in the pool, nothing locked anywhere.
- Planted errors:
  - word_sub: a real word one edit away, like لديها → لديهما;
  - letter: a dot sibling;
  - word_drop, block_drop (the last 40% of the words) and word_add.

**GPU runs (`run87.py`, `host87.sh`, `gs87.py`).**
- Rung 0.
- Ceiling: every library screened for 60 steps, then the best 3 plus AlQalam fitted for 160 steps. A wrong-text
  control: another line's text of similar length, in the page's library.
- Page style: libraries screened on one line, then the best 2 fitted jointly on 3 lines.
- Checker: the style is frozen and only the line's position, baseline and warp are fitted, for 100 steps.

## Status

In progress (2026-11-06): letter programs built, writer and fitter built and checked by eye on the CPU; the GPU runs
are waiting for a host.

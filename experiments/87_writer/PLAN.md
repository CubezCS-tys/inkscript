# Experiment 87 — a reader that knows how to write (analysis by synthesis): plan

**Status:** PLAN ONLY (2026-11-05). Starts after the reader phase meets its exit criteria (Plan page, "Reader exit
criteria"). Nothing built, nothing spent.

## Summary (for the owner)
1. **Idea (owner, 2026-11-05):** teach the machine *how Arabic is written* — each letter as a small program of pen
   strokes, fonts and hands as *settings* (nib width and angle, slant, kashida stretch, ink spread, stacking) — instead
   of showing it thousands of examples of every letter. Like a child: learn how ب is written once; a new hand is a new style of the same thing.
2. **Reading becomes explaining:** find the letters *and* the page's style settings that, when written, reproduce the
   ink on the page. A page's style can be fitted from a handful of clear letters; the damaged ones follow.
3. **First practical brick — "re-write to verify":** take any reader's text (ours, Azure's, Nuqta's), write it in the
   page's fitted style, compare with the real ink. Text that is not on the page (Nuqta's «لديهما» for printed «لديها»),
   text that is missing (a skipped column), and wrong letters all show up as ink that does not match.
4. **Why it matters for us:** the stacked calligraphic logo (0097), unfamiliar old typefaces, and a checker that does
   not depend on any reader agreeing with another.
5. **Prior art:** Lake, Salakhutdinov & Tenenbaum, *Science* 2015 (one-shot character learning with stroke programs,
   human-level on Omniglot); "analysis by synthesis" / inverse graphics; handwriting synthesis (Graves 2013); SketchRNN.
   Hard to scale to real pages so far — this is research, not a quick win.
6. **What we already have:** pen paths and the learned centre line (exp 79, 82); typefaces traced from our own scans
   (exp 11, 78); **AlQalam 0.2** (LPPL, already in `79_signal_reader/data/alqalam_lppl`) — Arabic glyphs defined as
   broad-nib METAFONT pen strokes; exp 78's renderer and damage models; exp 81's judged lines and the owner's truth.
7. **Cost:** stage 1 (the writer) and stage 2 (re-write to verify) are mostly CPU plus ≤ $15 GPU; stage 3 (style
   fitting) ≤ $15; stage 4 (read by synthesis) is open research, budget decided after stage 3.
8. **Success, stage 2:** the verifier flags ≥ 60% of a reader's wrong lines at ≤ 10% false flags on exp 81's judged
   lines, and catches every planted omission/invention in a planted-error test — beating "two image readers disagree"
   (exp 81: 49% recall at 10% flagged) or adding to it.
9. **Stop points:** after every stage the owner sees pictures (the page's ink, the re-written line, where they differ).

## Stages

### Stage 1 — the writer (letters + style → ink)
- **Letter programs.** Each letter form (isolated / initial / medial / final, ~120 forms plus lam-alif and common
  ligatures) as an ordered set of strokes with a nib. Sources, in order: AlQalam's pen-stroke definitions; strokes
  recovered from our fonts with exp 82's learned centre line; the 16 basic body shapes (rasm) + dot patterns.
- **Style settings (a few dozen numbers per page):** nib width/angle, contrast, slant, x-height, baseline curvature,
  kashida length distribution, join shapes, mark placement, ink spread/erosion, noise, and (for calligraphy)
  vertical stacking of letter pairs.
- **Renderer:** differentiable (so settings can be fitted by gradient), e.g. strokes as nib-swept splines rasterised
  with soft edges. Check by eye: write lines in AlQalam's style and in several traced typefaces.
- **Measure:** how closely the writer can reproduce real clean lines when given the true text and *fitted* settings
  (pixel IoU / chamfer distance between written and real ink), modern and old pages. This is the ceiling for stage 2.

### Stage 2 — re-write to verify (the checker)
- For a page: fit the style settings on a handful of lines where readers agree (fast, per page).
- For each line and each candidate reading: write it, align it to the real ink, score the mismatch (ink with no
  writing = missing/omitted; writing with no ink = invented; local mismatch = wrong letter).
- **Tests:** exp 81's judged lines (does the mismatch pick the judge's verdict? flag the wrong reader?); a planted-error
  set (swap a word for a plausible one, drop a word/column, change one letter) on held-out pages; the owner's truth.
- Compare with and combine into the existing warning (77-vs-78 disagreement).

### Stage 3 — fit a page's style from a few letters
- Learn settings from 5–20 clear lines of a page; show that re-written *unseen* lines of the same page match better
  than with generic settings, on modern, 1950–99, pre-1950 and the 0097 logo (stacking on).

### Stage 4 — read by synthesis (research)
- Search over readings (beam from our image reader + alternatives) for the one whose writing best explains the ink;
  later, propose letters directly from stroke fits. Decide scope and budget after stage 3, with the owner.

## Ladder and kill criteria (owner's "5 sigma" rule)
- Rungs: synthetic lines (true text, true style) → clean real modern → old print → calligraphy (0097).
- Kill only after the ladder, if: the writer cannot reproduce clean real lines at all with fitted settings (stage 1
  ceiling too low), **and** the verifier adds nothing to the two-reader warning on judged lines.

## Rules
- Never train on held-out (`76_finetune_pilot/out/split76.json`) or locked journals (`84_display_fonts/locked.py`).
- AlQalam is LPPL 1.3+; traced typefaces are ours; record every font's licence.
- GPU-first (owner, 2026-11-05: production runs on GPUs): the renderer and verifier are written to batch on GPU from the
  start; building letter programs and eyeballing renders can happen locally. Every real test runs on a rented GPU via
  the lead's rentals and `ops/lab_monitor.py`; shared box: nice 19, ≤ 2 cores, light during busy hours.

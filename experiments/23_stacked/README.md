# 23 · Stacked letters: can a highlight sit on the upper or the lower letter?

**Question.** After experiment 21, most remaining misses are on م and ل in stacked joins (لمـ, مح, فى): a highlight
that is a full-height column over a letter's stretch of the baseline cannot separate letters written one above
the other. Can a letter's highlight be shorter than the line (upper vs lower), in a real Chromium, without
breaking selection order, copying or the line rules? And does it then sit on the right letter more often?

**Answer (2026-10-06): Chromium can do it, but it makes the judge's verdicts worse and breaks lines in two of four
books. Do not apply.**

## 1 · What Chromium 153 does with a letter's box (measured, `chromium.py`, `splitfont.py`)

Scripted Chrome for Testing 153.0.8010.12 (the D18 set-up: playwright in a scratch venv; drag, screenshot, copy
pasted into a textarea). The screen is mapped to PDF points by template-matching the screenshot against a PyMuPDF
render (0.98 correlation). Probes on the fixture (`0582` p2 لمعجمه, p3 على):

- **The highlight's width is the glyph's d1 box** (llx..urx), not its advance. Widening one letter's d1 by 6 px
  each side moved its highlight's edge by 1.4 pt, which is 6 px.
- **The highlight's height is the font's FontBBox**, never d1. Shortening a letter's d1 changed nothing on screen.
  Setting the line font's FontBBox to `0 20 68 40` moved every highlight in that line to that height. Today every
  letter in a line shares the line font, so every highlight is the line's height. (The pinned pdfium's
  `FPDFText_GetRect` reports the d1 height instead: this is one more place where the pin is not Chromium.)
- **A letter gets its own height only in its own font.** We drew each letter in a copy of the line font whose
  FontBBox is that letter's box, each in its own TJ. Selecting a letter alone then shows a box of its own
  height. A drag across several letters is merged by Chromium into one rectangle per line, so it looks as it does today. Copy and
  letter-by-letter order were right in every drag.
- **Boxes that overlap in x break selection.** With d1 widened to each letter's ink, ى's box reached under ل, and
  selecting ل alone copied «لى». So widths must keep tiling the word.

## 2 · The rule tried (`stackrule.py`, applied to finished PDFs by `post.py`)

Two neighbouring cut letters of one word count as **stacked** if their bodies (the largest outline of each, so dots and holes are
left out) overlap horizontally by ≥ 40% of the narrower one and their centres are ≥ ¼ of the pair's joint height
apart. Each then gets its own copy of the line's font with FontBBox = advance × its whole ink height (not clipped
at the line above), in its own TJ. The cuts are not changed. Two more fixes were needed before the fixture passed:

- pdfium sorts a line's text objects by where their first glyph starts. If a letter is followed by a backward pen
  move inside its word, the next object starts left of it and the letters get reordered (`الاندلسيين` →
  `لس … انديين`). Such letters stay in the line's font (3 of 471 on the fixture).
- a word space that ended an object was lost (`عبد العلي` → `عبدالعلي`): the space and its pen move now go into
  the letter's object.
- pdfium starts a new line between two objects whose d1 boxes do not overlap vertically, which is exactly the case for a stacked pair
  (0618 lost 5 lines). The stacked letter's d1 now takes the line's full height. Its highlight height
  still comes from the FontBBox.

The rule found 468 letters on the fixture, 1,542 on 1036, 2,136 on 0618 and 2,552 on 0772. It was applied to
experiment 21's builds, which have the same cutter as today's src, so 0772 did not need an hour's rebuild.
`inspect.patch` lets `pdf/inspect.page_glyphs` read a line written as several TJ, which this layout needs.

## 3 · Judge: before / after (`boxes23.py`, `judge23.py`, `analyze23.py`)

Experiment 18's judge (Gemini 3.8 Flash, graded + blind, right = both, same crops, items shuffled, ids that do not
name the method). Same 230 sample words; **112 stacked letters** in 50 of them. Because a box can now be shorter
than the word, the crop tints the box's own rows and both prompts say "a rectangular region" instead of "a
vertical band". Today's boxes were asked again under that prompt, so before and after are paired. On the same
boxes it agreed with 18/21's verdicts 83 times in 112, with 15 and 14 flips each way: no bias.

| stacked letters (112) | right |
|---|---|
| today, 18/21's prompt | 50.0% (41.0–59.4) |
| today, region prompt | 49.1% (39.3–60.2) |
| **own height** | **35.7%** (27.2–44.9) |
| after − before, paired bootstrap | −23.9 to −2.8 points; 10 letters better, 25 worse |
| upper letter of the pair | 31 → 25 of 60 |
| lower letter | 24 → 15 of 52 (و 6 → 0 of 12, ل 11 → 4 of 16) |

Whole samples (other letters keep 21's verdict): A 76.7% → 75.3% letters, 42.3% → 41.5% words. B 68.5% → 65.0%,
34% → 26%. C 62.2% → 62.7%, 28% → 26%. All intervals overlap.

**Why it got worse** (`out/look_worse.png`, and the report's crops). The new height comes from the letter's own
ink *as the cutter assigned it*, and on these pairs that assignment is often wrong where the stretch of baseline
was right. A و whose loop went to the letter before it keeps only its tail, so its highlight shrinks to the tail.
A ل keeps its stem but loses its foot. Today's full-height column hid such mistakes. Many "stacked" pairs are not
letters written one above the other: they are wrong cuts whose ink overlaps.

## 4 · Did anything that worked break? (`checks.py`, `run_checks.sh` → `out/checks.jsonl`)

| doc | today: words intact / lines / coverage | stacked rule |
|---|---|---|
| 0582 (fixture) | 1,246/1,246 · 113/113 · 1,062/1,104 (96.2%) | **same** (5 lines lose a leading space in the copied text) |
| 0618 | 3,929/3,929 · 363/363 · 3,384/3,420 | same |
| 1036 | 2,677/2,677 · 238/238 · 2,618/2,645 | **2,649 · 224** (page 1, a title page with very large glyphs) |
| 0772 | 6,321/6,324 · 497/509 · 4,149/4,318 | **6,256 · 480** (13 pages) |

In real Chromium, selecting ى alone in على also copied a space («ى ») once d1 took the full line height.

## What it means

- A partial-height highlight is possible in today's Chromium, but only with one font (and one text object) per
  letter. Chromium takes a highlight's height from FontBBox, never from d1.
- Do not apply this. On the judge it is worse, because it shows the cutter's ink mistakes on these pairs. And
  splitting a line into several text objects is fragile in pdfium's line building, so two of four books lost lines.
- Widening boxes to each letter's ink, so that they overlap in x, is ruled out: it broke selecting a single letter.
- Next, for stacked joins: fix the *ink* of the stacked pair in the cutter (which letter a loop or a tail belongs
  to). Only after that is a per-letter font worth trying again, and only after finding out what pdfium uses to
  break lines between text objects (1036 p1, 0772 p38).

No src patch is proposed. `post.py` is the full implementation if this is picked up again. `inspect.patch` is only
needed with it.

**Spend: $0.60** (cap $8): 448 judge answers (224 boxes × 2 questions), Flash. Log: `out/spend.jsonl`.

Not done (rule of this task): `src/`, `docs/` and `experiments/README.md` not edited. Suggested index line:
`| 23 | Stacked letters | Chromium takes a highlight's height from the font's FontBBox (width from d1), so a letter gets its own height only in its own font; doing that for stacked letters made the judge worse (49 → 36% of 112) because it shows wrong ink, and broke lines in 1036/0772: not applied | milestone 2 |`

```
SP=<scratch>/pw/bin/python                                 # playwright venv; Chromium 153 at <scratch>/browsers/chromium-1243
$SP chromium.py PDF PAGE WORD NAME [--single|--line]       # one Chromium session -> out/chromium/
../../.venv/bin/python splitfont.py IN OUT PAGE WORD 1,2 [--ink]   # hand-made probe PDFs
../../.venv/bin/python post.py IN.pdf OUT.pdf cell|ink|same        # the rule on a finished PDF
./run_checks.sh                                            # checks on 21's builds before/after
../../.venv/bin/python boxes23.py && ../../.venv/bin/python judge23.py && ../../.venv/bin/python analyze23.py
./chromium_runs.sh && ../../.venv/bin/python make_report23.py
```
Also used for diagnosis: `look.py`, `draw.py`, `stacked.py`, `list_stacked.py`.

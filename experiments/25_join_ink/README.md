# 25 · Join ink: who owns the ink where letters stack

**Question.** Where letters stack or overlap at a join (لو، جنو، هو، لقو، لمـ), which letter owns which ink? Experiment
23 found that many "stacked" pairs are really wrong cuts: a و keeps only its tail and a ل loses its foot, and the
full-height highlights hide it. Can the cutter give each letter its own ink? This was measured, not argued.

**Answer (2026-10-06).** Yes, for the main error, with one new hard fact about **heads**. Per-letter ink on the
stacked letters, counted by eye: **52 → 76 of 95** (24 better, 0 worse). The fonts of three books get back the heads of
final و and ق and lose a lump stuck to medial ل and ط: **10 letter-forms better, 1 worse**. The full-height judge
barely moves (cells shift by only a few pixels). Words intact and lines in order are identical in all four books.
Letter coverage is equal or 1–2 words lower (0618 3,392 → 3,391, 0772 4,149 → 4,147). One 0772 page joins two rows of
chart labels into one line. Recommended: `git apply
experiments/25_join_ink/penpath.patch` when no set run is going.

## What was wrong (seen: `out/diag_today.png`, `out/zoom_*.png`)

A filled head (the round head of و, the head of ف/ق, the eye of م/ه) hangs from **one point** of the pen path. The pen
comes from the previous letter, goes round the head, and leaves into the tail from the same point, so the shortest
path (the trunk) skips the circle. The whole head is ink hanging from that one trunk point. On 0772 its mass shows as
a single spike (e.g. هو: 98 px at path position 22, against 4–8 px elsewhere). The cut was chosen at the thin place
just below it, where the tail starts, so the head went to the previous letter. Nothing in the facts forbade that.
Every final و in a document was cut the same way, so the document's atlas learned "final و = bare tail" and confirmed
it (in 0772's and 1036's fonts the final و was a dotless ز, and the final ق was a ن with two dots). A lump detector
(below) finds a head inside 19% of final و's stretches today, against 64% for an isolated و.

Other errors found and **not** addressed (they are not join ownership): the path starting too low on words larger
than their line (headings: مسئو، صفه، ميه); cuts shifted by one letter in pieces that touch other ink or are
underlined (للكتاب، الطبعة); in 0582, the medial ل of على keeps the first bit of the ى's descent and the final أ keeps
its neighbour's tooth.

## The change (`patch25.py`, as a diff to src: `penpath.patch`, verified to cut identically)

1. **Heads** (`lumps`, in `_facts_score`). A path position is a *lump* when its own ink is at least 1.6 × as thick as
   the piece's usual stroke (distance-to-paper of the thickest pixel hanging from it, against the median over the
   path). Letters with a head (و ؤ ف ق م ه ة ص ض ط ظ, and ع غ when joined on the left) get +1.5 for owning a lump.
   Letters without one (ا أ إ آ د ذ ر ز ل ك ب ت ث ن ي ى س ش ئ) get −4 for owning one. ج ح خ are left neutral (their
   wedge can look thick). On the ink: the cut moves up past the head's root, so the و's head and tail are one letter
   again and the letter before it gets back to its own shape. Open heads (with a hole) are not lumps and are
   unaffected.
2. **A stem with a flag** (`stem_foot`). Experiment 21's walk down a final alef's stem stopped at the first pixel
   step to the right, so a wiggling stem or a hamza alef with a flag at its top was not recognised. A second walk now
   looks a quarter of a rise ahead. This is a small fix: 2 boxes in the sample.

## Method

- `capture.py`: runs `inkscript native` in this process and records every `penpath.plan` call (in build order),
  stopping before any PDF is written. `replay.py` re-cuts offline as the build does (the first 1,500 plans teach
  the atlas, the rest are cut against it). For today's src the replay reproduces experiment 21's build-time cuts:
  0582 1356/1356, 1036 320/320, 0772 1337/1337, 0618 298/300 (the known 0618 word). `variants.py` replays the sample
  pages under a variant. `boxes25.py` turns plans into Chrome's boxes (21's `cells`, which reproduces 229/230 words
  of 21's PDF boxes).
- `judge25.py` / `analyze25.py`: 18's judge (Gemini Flash, graded + blind, right = both) on 18's 230 words. Boxes
  identical to earlier ones keep their cached verdicts, and only moved boxes were asked, plus 58 control re-asks.
  The bootstrap is over words and paired. `judge_heights.py`: 23's own-height judging, on the new cuts.
- `font25.py`: experiment 11's `collect` + `choose` (each form restored from its best printings) under each variant,
  with sheets of the forms that changed (IoU < 0.85). `diag.py`, `zoom.py`, `pairs.py`, `changed.py`, `forms.py`: the
  drawings (each letter's ink in its own colour, pen path, cuts) used to find the cause and to count by eye.
- `build25.py` + `checks25.py`: full builds `native … --vector --verify` in this process, today vs patch.
  `verify_patch.py`: the diff, executed into the module, gives the same cuts as `patch25` on all four documents.

## Results

**Per-letter ink by eye** (`out/pairs_a.png`, `pairs_b.png`: the 52 pieces holding 23's 112 stacked letters; 17 too
small or unclear to call): right **52/95 → 76/95**, 24 better, 0 worse. Every gain is a head going to its own letter.
Collateral: of 40 random pieces anywhere on the sample pages whose cuts changed (`out/changed_rand.png`), 6 are
clearly better, 0 clearly worse, 32 move by a pixel or two along a connector, and 2 are unclear. Pieces whose cuts
changed on the sample pages: 0582 63/1356, 0618 51/300, 1036 38/320, 0772 271/1337.

**Fonts** (`out/font_<doc>_today_lumpfoot.png`):
- 0772: 26 of 103 forms changed. Better: final و (was a dotless ز), final ق (was ن with two dots), medial ل (lump gone),
  initial ط (neighbour's stroke gone), medial ئ (lump gone). The other 21 are about the same.
- 0582: 7 of 90 changed. Better: final ق (head restored), medial ج (stray baseline gone). The other 5 are about the same.
- 1036: 23 of 103 changed. Better: final و, final ض (head restored), medial ط. **Worse: final ل** (a short extra stroke at its
  left; not traced). The other 19 are about the same.

**Judge, full-height boxes (what Chrome shows today)** — rule "both", 230 words, 85 moved boxes:

| | today | after | paired diff |
|---|---|---|---|
| all letters (981) | 71.7% (68.3–74.8) | 71.2% (67.8–74.3) | −1.6 to +0.5 (11 better, 16 worse) |
| words | 37.4% (31.3–43.0) | 35.2% (29.1–40.9) | 2 vs 7 words |
| A · 130 unseen | 76.7% | 76.3% | −1.9 to +1.0 |
| B · 50 unseen | 68.9% | 67.7% | −3.8 to +1.2 |
| C · 50 fixture | 62.2% | 62.2% | no box moved |
| 112 stacked letters | 56 (50.0%) | 58 (51.8%) | −5.0 to +8.4 |
| joined و (36) | 25 | 24 | |

Control: re-asking the same boxes changed 22 of 114 verdicts (14 right→wrong, 8 wrong→right). With about 85 moved boxes,
the 11/16 split is within that noise. The full-height judge cannot see this change: the head's root sits almost
above the tail's start, so the column moves by only a few pixels.

**Option: own-height highlights (23's method, region prompt)** on the same 112 letters: own height on today's cuts
35.7% (23) → on the new cuts **47.3%** (paired +2.8 to +20.4 points; 18 better, 5 worse; final و 0 → 11 of 12). Full
height is 49.1% today and 48.2% with the new cuts. So the new ink removes most of what made 23's option worse, but
it is still not better than full height: a joined ل gets a sliver over its stem (5–6 of 16). Not recommended (23 also
found per-letter fonts break lines in 1036 and 0772).

**Nothing that worked broke** (to within 1–2 words of coverage) (`out/checks25.json`; both builds in this process with current src):

| doc | words intact | lines in order | letter coverage today → after | copied text |
|---|---|---|---|---|
| 0582 | 1246/1246 → 1246/1246 | 113/113 → 113/113 | 1062/1104 → 1062/1104 | same |
| 1036 | 2677/2677 → 2677/2677 | 238/238 → 238/238 | 2620/2647 → 2620/2647 | same |
| 0618 | 3929/3929 → 3929/3929 | 363/363 → 363/363 | 3392/3428 → 3391/3428 | same |
| 0772 | 6321/6324 → 6321/6324 | 497/509 → 497/509 | 4149/4318 → 4147/4318 | one page (13) differs: two staggered rows of chart labels («مصر المغرب الولايات» / «سويسرا إيطاليا إسبانيا المتحدة») are read by pdfium as one line after; no word broken |

## Tried and dropped

- **"A lam keeps its foot"** (variant `lamfoot`): a joined ل is penalised when its cut is right at its stem's root.
  Judge 71.0% (B −2.4), own-height ل 6 → 5 of 16. Dropped: where a lam's foot ends is unclear in these faces.
- **The trained reader of experiment 16 as a third witness**: not used. Its boundary head was trained on this
  cutter's own cuts in 93 books, so it would repeat the و error rather than witness against it.
- **Direction/curvature continuity at every join**: at the one systematic error found, the pen arrives and leaves
  the head at the same point, so direction cannot decide. What decides is which letter has a head.

## What it means

- The head rule is the "fix the ink first" step that experiment 23 asked for. Stacked letters now mostly own their
  own ink, and the books' typefaces lose two glaring wrong glyphs (final و, final ق).
- The selection boxes users see barely change, so the judge is neutral. The gain is in the glyphs' ink: the
  typeface (restoration), and any later per-letter highlight.
- Recommended for src: `git apply experiments/25_join_ink/penpath.patch` (no set run going), then rebuild.

**Spend: $0.80** (cap $10): 79 + 2 + 16 moved boxes and 58 control re-asks (18's prompt), and 118 + ~16 own-height
crops (23's prompt). Log: `out/spend.jsonl`.

Not done (rule of this task): `src/`, `docs/` and `experiments/README.md` not edited. Suggested index line:
`| 25 | Join ink | a filled head hangs from one point of the pen path and went to the letter before (final و = bare tail in every copy); a "head" fact gives stacked letters their own ink 52→76 of 95 by eye and fixes final و/ق in three books' fonts; full-height judge neutral; checks unchanged | milestone 2 |`

```
../../.venv/bin/python capture.py 0582 0618 1036 0772        # record the build's pieces (seconds)
../../.venv/bin/python variants.py today && ../../.venv/bin/python variants.py lumpfoot
../../.venv/bin/python boxes25.py today && ../../.venv/bin/python boxes25.py lumpfoot
../../.venv/bin/python judge25.py lumpfoot && ../../.venv/bin/python analyze25.py lumpfoot
../../.venv/bin/python heights.py lumpfoot && ../../.venv/bin/python judge_heights.py lumpfoot && ../../.venv/bin/python judge_heights.py lumpfoot --analyze
../../.venv/bin/python font25.py build today|lumpfoot DOC && ../../.venv/bin/python font25.py sheet DOC today lumpfoot
../../.venv/bin/python build25.py today|lumpfoot 0582 1036 0618 0772 && ../../.venv/bin/python checks25.py
../../.venv/bin/python report_imgs.py && ../../.venv/bin/python make_report25.py
```

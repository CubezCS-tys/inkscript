# 17 · Where the feeler and Azure disagree, who is right?

**Question.** The feeler (experiment 16, `hybrid_ctc_geo`: reads a piece of ink from its pen path alone) reads
79% of unseen pieces the way Azure does. Agreement with Azure says nothing about the other 21%. If the feeler is
often right where Azure is wrong, a disagreement is the archive's "uncertain word" flag (D17). If Azure is nearly
always right, the feeler's value is its cuts, not its reading. The owner asked that Gemini judge, not them.

**Method.**

1. *The judge* (`judge.py`). Gemini is shown the scanned ink (300 dpi grey render of the scan, never our vector
   rendering): a strip of the word's own line, the word's paper tinted pale yellow, the disputed piece spanned
   by a blue bar in a margin below; nothing drawn on the ink. Two readings go out as A and B in an order fixed by a
   hash of the item (balanced, reproducible), never saying which is Azure's. Answers: A, B, NEITHER (write what it
   says), UNSURE. Temperature 0, JSON schema, thinking "low", six crops per request. Every answer is cached
   (`out/judge_cache.jsonl`), every request's tokens and cost logged (`out/spend.jsonl`), and a request that would
   cross the cap is not sent.
2. *Calibration* (`calibrate.py`) on the owner's gold pages (experiment 12; `0005-032-001-001` p2 and
   `1110-000-001-001` p1, fetched into `out/gold_docs/`). On 120 words the owner marked right: the real reading
   against a one-mark look-alike (dot group, ة/ه, ى/ي, hamza), half of the look-alikes chosen to be real words
   seen in the corpus so "pick the word" cannot win; 30 "neither" items (two look-alikes, real one absent); and the
   owner's doubtful or self-inconsistent words, unscored.
3. *Disagreements* (`extract.py`, run with `16_feel/out/torchenv`). The bench books' pages outside every split
   of `bench.SUITE`, upright and mostly Arabic: 0618 p1, 16; 1036 p1, 10; 0772 p6, 14, 16, 18, 20, 23, 25, 27
   (0582 has no unused page). Pieces extracted as `bench.build_cache` does (`reader.pieces_of` + `blind`, same
   filters; checked: on 0582 p5 it reproduces the bench's 462/582 exactly). The feeler uses its cached trained
   models. 3,109 pieces, **869 (28.0%) read differently**; 800 drawn at random and judged (`run.py`). Each is
   shown as a whole word: Azure's, and Azure's with the disputed piece read as the feeler reads it.
4. *Agreements*: 190 pieces where both read alike (same share per book), the agreed word against a one-letter
   look-alike changed inside the piece. NEITHER or the look-alike = both wrong.
5. `analyze.py` → `out/summary.json`; `make_report.py` → `out/report.html`.

```
.venv/bin/python calibrate.py gemini-3.1-pro-preview         # and gemini-3.8-flash
experiments/16_feel/out/torchenv/bin/python extract.py
.venv/bin/python run.py gemini-3.1-pro-preview --dis 800 --agree 200
.venv/bin/python analyze.py && .venv/bin/python make_report.py
```

## Result (2026-10-06)

**The judge: `gemini-3.1-pro-preview`.** Calibration, final marking:

| model | real vs look-alike | …look-alike a real word | "neither" spotted | can't tell |
|---|---|---|---|---|
| gemini-3.1-pro-preview | **119/120** (99.2%) | 58/59 | 28/30 | 0 |
| gemini-3.8-flash | 118/120 (98.3%) | 58/59 | 27/30 | 0 |

Flash was nearly as good and a third of the price; Pro was used because it was never worse and the budget
allowed. Both judges' misses are mostly one word, فى, which the owner marked right and both judges read as في
(dots below) — either the owner's mark or the judge is wrong there. The owner's two self-inconsistent words:
التكويني (a dot error on one sheet, right on the other) — the judge says right; طرح/صرح (both marked right) — the
judge says صرح. Limit: the gold pages are clean prints and a look-alike differs by exactly one mark.

**The disagreements (800 judged):**

| verdict | share |
|---|---|
| Azure right, the feeler wrong | **789 (98.6%)** |
| the feeler right, Azure wrong | 5 (0.6%) |
| both wrong | 6 (0.8%) |
| can't tell | 0 |

The same in every book (0618 98.5%, 1036 97.5%, 0772 99.0% Azure right), every length, every kind: dots 200/200
Azure, hamza 18/18, ة/ه 1/1, other one letter 127/129, several letters 306/309. The only kind with any feeler wins
is a missing or extra letter (4 of 143), which is where Azure's own language model adds or drops an alef.

Looked at by hand (the agent, not the owner), the 11 non-Azure verdicts are: **2 real Azure letter errors the
feeler caught** (the print says لمساهمة, Azure المساهمة; the print says نشاطا, Azure نشاط — that word counted
twice, once per piece), 1 likely one (التغير/التغيير), 1 encoding slip (Azure's Persian ی for ى, which breaks
search), 3 punctuation only, 2 box artefacts (an alef never attached to its word; a box spanning a title block),
1 unsettled faint header. So Azure misread the letters in about **3 of 800** disagreements.

**Agreements (190 judged):** 1 flagged, and by hand it is the judge's error (no hamza printed). Both-wrong rate
when they agree: 0 of 190, under ~1.6% at 95% — the error disagreement could never catch is also rare.

**Spend: $8.03** at list prices rounded up (Pro $2/$12, Flash $1/$5 per million tokens in/out), 490 requests,
3.35 M tokens in, 0.16 M out — three runs of everything, two of them spent on finding the right marking (below).

**On the way: how the word is marked decides what the judge reads.** First run: a red box round the word and a
blue bar just under the piece. Calibration looked perfect (119/120, 30/30), but the box's edge hid an alef that
was never attached to the word (العدد read as لعدد — "the feeler right"), and the bar under a lone alef read as a
hamza below (3 of 5 "both wrong" agreements). Second run: bars in white margins — Pro fell to 110/120, reading the
word of the line *above*, which touched the bar. Third: only the paper behind the word tinted, the strip only as
tall as the word's line. The headline did not move (98.1% → 98.6% Azure right); the artefacts did. Earlier
outputs: `out/v1/`, `out/v2/`.

## What it means

Where the feeler and Azure disagree, Azure is right ~99 times in 100; the few real Azure errors the feeler
caught are an added or dropped alef. As an "uncertain word" flag,
disagreement would mark 28% of all pieces to find about one real error in three hundred: worthless for the
archive. The feeler's value is the cuts (where the letters are), not the reading. For the archive's uncertain-word
mark (D17), this says Azure's letter errors on these faces are rare (0 in 190 agreed pieces, ~3 in 800
disagreements), so a flag must be precise to be worth showing. The judge itself (≈$0.003 a word at Pro, 99% on
one-mark look-alikes) is a better instrument for finding them than the feeler — on a sample, not every word.

Not done: the owner has not checked any verdict; `experiments/README.md` and `docs/` were not edited (rule of
this task). Suggested index line: `| [17](17_judge/README.md) | Where the feeler and Azure disagree, who is
right? | Azure 98.6% of 800 (Gemini 3.1 Pro judge, 119/120 on gold look-alikes); the feeler right in 5, ~3 real
Azure letter errors | the feeler's value is cuts, not reading |`.

# The taps and the word knowledge (experiment 16, `taps_*`)

## Question

The feeler (`feel.py`) confuses letters that share a body and differ only in their dots (ب ت ث ن ي), and reads
each piece as if it had never seen the language. Two things a back-reader has that it did not use:

1. **the taps, felt properly** — not "how many dots", but how big each tap is against the document's own single
   dot (this print merges two dots into one blob, three into a bigger one), its shape, and the hamza;
2. **knowing the language** — which letters follow which inside a piece, and which pieces occur, learned from the
   same document's train pages (Azure's readings there), used as a prior in the chain search.

The archive question behind 2: a lexicon makes the feeler agree with Azure more, but a reader is worth most where
Azure is wrong, i.e. where the word is unusual. So: how often does the prior override the feeling, and what does
it do to pieces the train pages never had?

## What was built

All in new files: `taps_lib.py` (helpers), `methods/taps_v1.py`, `taps_v2.py`, `taps_lex.py` (superseded),
`taps_prior.py` (**the best**).

**Taps (`taps_lib.Taps`, `tapped`, `dot_marks`).** Each dot-shaped mark (same shape rule as `penpath`) is
measured: ink area in units of the document's single dot (the median dot-shaped mark on the train pages), and
width/height. A letter's stretch is felt per side (above / below) as one cell: dot-ink mass bin (none / small /
one / one+ / two / three / more) × shape (no mark / one round mark / one wide mark = merged pair / several marks)
× (v2) whether a *bridged* loose part sits on that side. Per letter-form, a histogram over cells is learned on the
train pages, shrunk towards all letter-forms' histogram (2 pseudo-letters); the cost is −log P relative to the
letter-form's most usual cell (its usual taps cost nothing, as in `feel.py`), times `TAP_W`.

What the train pages showed (0582, 1036): `ي` and `ت` mostly print ONE mark, but a wide one (median w/h 1.6–1.9
against 1.0 for `ب`, `ن`); in 1036 the mass alone separates them (two-dot blobs ≈ 2 single dots). The hamza of
`أ`/`إ` is never a mark: the piece falls apart and the cutter **bridges** it into the body, so it was felt only
as a slightly taller alef. v2 takes the original ink (`q["real"]`), and every loose part other than the body
becomes a tap again at its place on the path.

**Word knowledge (`taps_lib.LM`).** From the train pages' readings: a letter trigram within pieces
(Witten-Bell interpolated, add-one at the bottom; trained on reversed pieces because the search walks from the
last letter to the first), optionally mixed with the piece lexicon: P = μ·count/N + (1−μ)·P_trigram, μ = N/(N+types)
(Witten-Bell's chance the next piece is already seen: 0.76–0.81; on dev 79–88% of pieces are in fact known, so μ
is calibrated). The prior enters the search as `lam · (−log P − H·(letters+1))`, H = the trigram's own
entropy per letter on the train pages, so on average the prior says *which* letters, not *how many* (letter
count is left to the feeler's letter and length costs).

**Search (`taps_lib.chain`).** The same grammar as `feel.read` (final, medials, initial; or one isolated
letter) but a beam: the 4 best letters per stretch, 24 partial chains per cut place. Checked on a held-out train
page: K=8/B=48 gives the same accuracy, so the beam does not limit the prior. The stretch's feeling is now cached
across letter-forms: the baseline's 79 s on 0582 became 15–25 s without the prior.

**The prior's weight `lam`** is chosen per document on a held-out TRAIN page (train minus the last page →
the last page), from 8 values, never on dev (`taps_lib.pick_lam`). It came out 0.05–0.1 everywhere; the
held-out curve is flat between 0.05 and 0.17 and falls steeply above 0.35 (at 1.0 it is below no prior).

## Every logged run (dev; pieces read as Azure reads them)

| method | note | 0582 | 0618 | 1036 | 0772 | mean per doc | letters (mean) |
|---|---|---|---|---|---|---|---|
| feel_v1 | baseline | 43.14 | 35.88 | 42.22 | 54.29 | **43.88** | 54.1 |
| taps_v1 | first try: raw −log P, mass only, TAP_W 1 | 43.39 | | | | | 52.5 |
| taps_v1 | cost relative to the usual cell (mode = 0) | 43.89 | | | | | 57.1 |
| taps_v1 | + shape cells, TAP_W 0.5 | 47.13 | 41.49 | 43.18 | 56.83 | **47.16** | 58.8 |
| taps_v2 | + bridged loose parts (hamza) | 47.13 | 43.75 | 43.66 | 58.41 | **48.24** | 58.3 |
| taps_lex | v1 + lexicon & trigram, lam grid {0,.25,.5,1,2} | 56.86 | | | | | 58.6 |
| taps_lex | finer grid (lam 0.1) | 59.60 | | | | | 65.0 |
| taps_lex | TAPS_PRIOR=ngram (trigram only) | 57.61 | | | | | 66.8 |
| taps_lex | v1 + lexicon & trigram, 8-value grid | 58.60 | 52.16 | 53.77 | 66.67 | **57.80** | 64.9 |
| taps_lex | v1 + trigram only | 57.61 | 50.75 | 54.25 | 66.67 | **57.32** | 65.3 |
| **taps_prior** | **v2 + trigram only (default)** | 60.10 | 52.80 | 50.72 | 67.94 | **57.89** | 64.0 |
| taps_prior | TAPS_PRIOR=lex: v2 + lexicon & trigram | 60.10 | 53.45 | 50.88 | 67.94 | **58.09** | 63.7 |

feel_v1's mean letter accuracy is the mean of its two logged runs' documents (56.0; 53.5 over the other three).
Cut agreement (cuts within one stroke of the cutter's, on pieces read right) stays where it was: 78–91%.

## How often the prior overrode the feeling (all four dev documents, 2,262 pieces read)

"Feeling" = the same search with lam = 0. "Novel" = Azure's piece is not in the train pages' lexicon
(402 pieces, 17.8%). From the read logs: `python taps_lib.py overrides <name> 0582 0618 1036 0772`.

| | prior changed the reading | fixed | broke | wrong → other wrong | picked outside the train lexicon (right) | novel pieces right: feeling → with prior |
|---|---|---|---|---|---|---|
| taps_prior (trigram) | 788 (34.8%) | 252 | 42 | 494 | 501 (65) | 66 → 65 |
| taps_prior, lex | 822 (36.3%) | 263 | 46 | 513 | 417 (56) | 66 → 56 |
| taps_lex (v1 taps), lex | 928 | 307 | 65 | 556 | — | 68 → 52 |
| taps_lex (v1 taps), trigram | 806 | 268 | 40 | 498 | — | 68 → 72 |

The trigram prior fixes six pieces for every one it breaks and leaves the reading of unseen pieces as good as the
feeling alone (it reads outside the train lexicon 22% of the time — about as often as dev pieces are new). The
lexicon adds 0.2–0.5 points of agreement with Azure and loses 10–16 of the ~66 unseen pieces the feeling had
right: it pulls a new word onto a known one. **For the archive the default is the trigram alone.**

## What helped, what didn't, and why

- **Taps by size and shape: +3.3 points** (43.9 → 47.2), **hamza found again: +1.1** (→ 48.2). On a held-out
  train page the dot/hamza-only errors fell from 45 to 30–33 (0582) and 61 to 25 (1036). After the prior, errors
  that differ from Azure only in dots or hamza are 61 of 1,001 (6%); with the feeling alone 159 of 1,211.
- **What a cost is relative to matters more than the evidence.** The first version charged −log P raw: a letter
  with a spread-out tap histogram paid on every stretch, which worked like an extra letter cost and wrecked
  4-letter pieces (8 → 1 right). Making the usual cell cost nothing fixed it.
- **Mass alone (no shape) did not help** (held-out 0582: 39–40% vs 40.6% baseline): in 0582 a merged pair is
  not bigger than a single dot, only wider. The shape cell was the step that paid.
- **The trigram prior: +9.7 points** (48.2 → 57.9). Most of it is not "words": it is the letter frequencies the
  nearest-neighbour feeler ignores (an isolated `ا` is 8–10× commoner than `أ`; the feeler, matching examples, had
  no notion of that), and `ر`→`و`/`ت`→`ئ`-type picks of rare letter-forms whose few examples made them look
  cheap.
- **What neither touches: the number of letters.** Half of the remaining errors have the wrong length (500 of
  1,001) — a segmentation problem (warp_*'s direction). The prior changed almost no lengths.

## Choices tuned, and where

- On held-out TRAIN pages: TAP_W ∈ {0.5, 1, 2} (two documents), shape cells on/off, bridged parts on/off, beam
  K/B (no effect), lam (8 values, automatic per document).
- By eye from train histograms: the mass bin edges (0.3, 0.75, 1.3, 1.8, 2.5, 3.5 single dots), WIDE = 1.4.
- On DEV (0582 only): the mode-relative tap cost (one choice); the default trigram-not-lexicon was decided from the
  dev override statistics (the archive argument), not from accuracy, where the lexicon is 0.2 ahead.

## Open risks

- **The truth is Azure.** "Fixed" means "now agrees with Azure"; the prior is learned from Azure's readings, so
  it also learns Azure's habits (e.g. how it spells hamzas). The novel-piece numbers are the only guard here,
  and they rest on ~400 pieces.
- **1036 went down with v2 + prior (54.3 → 50.7)** while the others went up: v2's bridged-part cell hurt its
  long pieces (letters 51.3 → 47.6 without the prior). A bridged part is not always a hamza (sometimes a whole
  neighbouring letter); the cell is only "present / absent". Worth splitting by size before trusting it.
- **lam is chosen on one held-out train page** (400–600 pieces); the curve is flat near the optimum, so the
  choice is stable, but the steep fall above 0.35 means a document whose train pages are unlike its other pages
  could get too strong a prior.
- Each read runs the search twice (with and without the prior) only to log the override; reading time is
  ~1.5–2.5 min per document including the lam choice.

## Where this goes next

The trigram prior is independent of how a letter is felt: it should stack with the DTW feeler (warp_*) and
with any chain search over letter hypotheses (it is `taps_lib.LM.step` / `final` per letter). The taps model is a
cost per stretch and stacks the same way.

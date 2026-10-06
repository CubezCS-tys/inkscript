"""The feeler with both directions put together: warp's shape cost, taps' taps cost, and the letter-trigram prior.

What it does (experiment 16; helpers in ../combo_lib.py, every run and the ablations in ../notes/combo.md):

- SHAPE (from warp_gate): every letter the cutter cut on the train pages is remembered; a stretch of the path is
  compared with them by the pooled trunk outline (even) and the stick's walk (DTW, band 2 of 16 samples); a
  letter-form's cost is the mean of its 3 nearest examples. warp_gate's neighbourhood gate is NOT used: in the combination it
  lost on the held-out train page of every document and on dev (notes/combo.md). Plus feel.py's length and
  letter costs.
- TAPS (from taps_prior): dot-ink measured in the document's own single dot, the mark's shape (round / wide =
  merged pair / several), and the loose parts a bridged piece lost (hamzas) felt again; a per-letter-form
  likelihood learned on the train pages; the usual taps cost nothing. Replaces feel.py's dot count.
- PRIOR (from taps_prior): a letter trigram within pieces, learned from the train pages' readings (Azure's),
  added in a beam chain search (4 letters per stretch, 24 chains per cut place) as lam * (-log P - H * letters).
- The tap weight and lam are chosen TOGETHER per document on a held-out TRAIN page (train minus its last page
  -> the last page), from {0, 1/16, 1/8, 1/4, 1/2, 1} x {0, 0.05, 0.1, 0.17, 0.25, 0.35, 0.5, 1}; never on dev.

Picked on the held-out train pages: tap weight 1/8 (0772: 1/4), lam 0.05 in every document.

Dev (2026-10-06, `bench.py run combo_best`): mean per-document piece accuracy 62.89% (0582 65.34, 0618 57.00,
1036 60.03, 0772 69.21; letters 69.2%), against feel_v1 43.9, warp_gate 53.8, taps_prior 57.9.
2.5-4 min per document (including the choice of the two weights), 0.45 GB peak.
"""
import combo_lib as C
import taps_lib as T

TAP_WS = (0.0, 0.0625, 0.125, 0.25, 0.5, 1.0)    # 0 = no taps at all
LAMS = (0.0, 0.05, 0.1, 0.17, 0.25, 0.35, 0.5, 1.0)


def _scorer(train):
    mem = C.learn_memory(train, T.doc_unit(train), cap=1000, bridged=True)
    return C.Scorer(mem, taps="new", band=0, wband=2, knn=3, gate=0, short=64)


def _lm(train):
    return T.LM(T.pieces_text(train), False)


def learn(train):
    (tw, lam), _ = C.pick(train, _scorer, _lm, TAP_WS, LAMS)
    return dict(sc=_scorer(train), lm=_lm(train), tw=tw, lam=lam)


def read(m, r):
    q = r["q"]; f = C.FE.feeling(q, r["rise"]); parts = m["sc"].score_piece(q, f, r["rise"]); q.pop("_walk", None)
    return C.read_parts(q, parts, m["tw"], m["lm"], m["lam"])

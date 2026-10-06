"""The research version of the combination (combo_lib.py); every switch from the environment, for the ablations:

COMBO_GATE   warp's neighbourhood gate (16; 0 = off)          COMBO_WBAND  walk DTW band (2; 0 = even walk)
COMBO_TAPS   "new" (taps_lib's taps, bridged parts) / "v1" (no bridged parts) / "count" (feel.py's dot count)
COMBO_PRIOR  1 = trigram prior, 0 = none                       COMBO_CAP    examples per letter-form (1000 = all)
COMBO_TAPW   fixed tap weight, or "pick" (chosen with lam on a held-out train page; default)
COMBO_LAMS   the prior's grid; COMBO_TAPWS the tap weight's grid (when picked)
Every run is in notes/combo.md.
"""
import os
import combo_lib as C
import taps_lib as T

E = os.environ.get
GATE = int(E("COMBO_GATE", 16)); WBAND = int(E("COMBO_WBAND", 2)); CAP = int(E("COMBO_CAP", 1000))
TAPS = E("COMBO_TAPS", "new"); PRIOR = E("COMBO_PRIOR", "1") == "1"; TAPW = E("COMBO_TAPW", "pick")
LAMS = tuple(float(x) for x in E("COMBO_LAMS", "0,0.05,0.1,0.17,0.25,0.35,0.5,1").split(","))
TAPWS = tuple(float(x) for x in E("COMBO_TAPWS", "0.25,0.5,1").split(","))


def _scorer(train):
    unit = T.doc_unit(train)
    mem = C.learn_memory(train, unit, cap=CAP, bridged=TAPS == "new")
    return C.Scorer(mem, taps="count" if TAPS == "count" else "new", band=0, wband=WBAND, knn=3, gate=GATE, short=64)


def _lm(train):
    return T.LM(T.pieces_text(train), False)


def learn(train):
    tg = (1.0,) if TAPS == "count" else (TAPWS if TAPW == "pick" else (float(TAPW),))
    lg = LAMS if PRIOR else (0.0,)
    if len(tg) * len(lg) > 1: (tw, lam), _ = C.pick(train, _scorer, _lm, tg, lg)
    else: tw, lam = tg[0], lg[0]
    print(f"  tap_w {tw}, lam {lam}, gate {GATE}, walk band {WBAND}, taps {TAPS}, cap {CAP}", flush=True)
    return dict(sc=_scorer(train), lm=_lm(train), tw=tw, lam=lam)


def read(m, r):
    q = r["q"]; f = C.FE.feeling(q, r["rise"]); parts = m["sc"].score_piece(q, f, r["rise"]); q.pop("_walk", None)
    return C.read_parts(q, parts, m["tw"], m["lm"], m["lam"])

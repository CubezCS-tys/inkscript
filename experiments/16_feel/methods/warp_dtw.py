"""The research version of warp_gate: every setting from the environment (WARP_BAND, WARP_WBAND, WARP_KNN,
WARP_GATE, WARP_CAP, WARP_PR = samples per rise for the walk at its own length, WARP_RBAND, WARP_VSHORT,
WARP_LC/DOT/LEN). The defaults are the run "walk DTW band 2, all examples, knn 3". Every run is in notes/warp.md."""
import os
import warp_lib as WL
import feel as FE

E = lambda k, d, t=int: t(os.environ.get(k, d))
CFG = dict(band=E("WARP_BAND", 0), wband=E("WARP_WBAND", 2), knn=E("WARP_KNN", 3), letter_cost=E("WARP_LC", FE.LETTER_COST, float),
           dot_w=E("WARP_DOT", FE.DOT_W, float), len_w=E("WARP_LEN", FE.LEN_W, float), rband=E("WARP_RBAND", 0.25, float), gate=E("WARP_GATE", 0), vshort=E("WARP_VSHORT", 64))
CAP = E("WARP_CAP", 1000); PR = E("WARP_PR", 0)


def learn(train):
    return WL.Feeler(WL.learn_memory(train, cap=CAP, per_rise=PR), **CFG)


def read(fe, r):
    q = r["q"]; f = FE.feeling(q, r["rise"]); seq, cuts = fe.read(q, f, r["rise"])
    return [k[0] for k in seq], cuts

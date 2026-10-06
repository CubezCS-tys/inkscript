"""The trained reader says WHAT the letters are; the feeling says WHERE they split (2026-10-06).

model_ctc_ft reads the piece (77% on dev) but places its cuts poorly (71-82% within a stroke of the cutter's).
Here its letters are kept and the cuts are chosen again from the geometry: among the piece's candidate cut
places (the thin joins of the pen path), the split whose stretches best match this document's remembered
letters of exactly those letter-forms (feel_v1's memory, cost as in feel.py). Same reading as model_ctc_ft by
construction; only the cuts change. Run with out/torchenv/bin/python.
"""
import numpy as np
import feel as FE
from methods import model_ctc_ft as FT, feel_v1 as V1


def learn(train):
    return dict(m=FT.learn(train), mem=V1.learn(train))


def forms_of(n):
    return ["iso"] if n == 1 else ["init"] + ["med"] * (n - 2) + ["fin"]


def read(model, r):
    letters, cuts = FT.read(model["m"], r)
    n = len(letters); q = r["q"]
    if n < 2: return letters, cuts
    mem = model["mem"]; keys = [(FE.P._base(l), f) for l, f in zip(letters, forms_of(n))]
    if any(k not in mem.X for k in keys): return letters, cuts
    W = q["G"]["W"]; pos = [0] + sorted(set(q["cand"])) + [W]; m = len(pos)
    f = FE.feeling(q, r["rise"]); rise = r["rise"]
    # letter k (reading order) spans [b[n-1-k], b[n-k]); go from the left end: the last letter first
    INF = np.inf; best = {(0, 0): (0.0, [])}                       # (letters placed from the left, boundary index) -> cost, cuts
    for j in range(n):
        key = keys[n - 1 - j]; nxt = {}
        for (jj, i), (c, cs) in best.items():
            for i2 in range(i + 1, m):
                if j < n - 1 and i2 == m - 1: continue
                if j == n - 1 and i2 != m - 1: continue
                if pos[i2] - pos[i] < 2: continue
                t = c + mem.cost(key, f, q, pos[i], pos[i2], rise)
                if t < nxt.get((j + 1, i2), (INF,))[0]: nxt[(j + 1, i2)] = (t, cs + ([pos[i2]] if i2 < m - 1 else []))
        best = nxt
    end = best.get((n, m - 1))
    return (letters, sorted(end[1])) if end else (letters, cuts)

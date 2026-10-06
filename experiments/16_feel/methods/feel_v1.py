"""Experiment 16 as first built (2026-10-05): remembered letters, evenly stretched; the walk + pooled outline;
dots as taps after the word; a cheapest chain under the script's grammar. The baseline every later method beats."""
import feel as FE


def learn(train):
    mem = FE.Memory()
    for r in train:
        q, rise = r["q"], r["rise"]
        if q is None: continue
        f = FE.feeling(q, rise)
        if len(r["units"]) == 1:
            mem.add((FE.P._base(r["units"][0]), "iso"), f, q, 0, q["G"]["W"], rise)
        elif r.get("cuts"):
            n = len(r["units"]); b = [0] + r["cuts"] + [q["G"]["W"]]
            for k in range(n):
                a, bb = b[n - 1 - k], b[n - k]
                if bb - a >= 2: mem.add((FE.P._base(r["units"][k]), r["forms"][k]), f, q, a, bb, rise)
    mem.freeze()
    return mem


def read(mem, r):
    q = r["q"]; f = FE.feeling(q, r["rise"]); seq, cuts = FE.read(q, f, mem, r["rise"])
    return [k[0] for k in seq], cuts

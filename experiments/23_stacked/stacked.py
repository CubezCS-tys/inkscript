"""Which letters of experiment 18's sample are STACKED — sitting above or below a neighbour of the same piece, so a
full-height column over its stretch of the baseline also takes in the neighbour — and how today's cutter does on
them (experiment 21's verdicts for today's src, rule "both").

A letter's body: its ink in the stored plan (21's plans of today's cutter), without connecting strokes and dots.
Stacked with a neighbour (previous or next letter of the piece) if their bodies overlap horizontally by at least 40%
of the narrower one AND their vertical centres differ by at least a quarter of the piece's height.

    ../../.venv/bin/python stacked.py      -> out/stacked.json  {word id: {k: {...}}}
"""
import sys, json
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; E21 = HERE.parent / "21_better_boxes"
sys.path.insert(0, str(E21))
import cells as C
P = C.P


def bodies(p):
    out = []; marks = np.zeros(p["ink_s"].shape, bool)
    for ds, above, lab in p["G"]["marks"]: marks |= p["F"]["lab"] == lab
    for k, (a, b) in enumerate(P.intervals(p)):
        m = P._mask(p, a, b, connectors=False, owner=k) & ~marks
        if m.sum() < 4: m = P._mask(p, a, b, owner=k)
        ys, xs = np.where(m); x0, y0 = p["off"]
        full = P._mask(p, a, b, owner=k); fy, fx = np.where(full)
        out.append(dict(x0=int(xs.min() + x0), x1=int(xs.max() + 1 + x0), y0=int(ys.min() + y0), y1=int(ys.max() + 1 + y0), cy=float(ys.mean() + y0),
                        ix0=int(fx.min() + x0), ix1=int(fx.max() + 1 + x0), iy0=int(fy.min() + y0), iy1=int(fy.max() + 1 + y0)))
    return out


def stacked_pairs(p, bs):
    ys, _ = np.where(p["ink_s"] >= 0); ph = ys.max() - ys.min() + 1; res = {}
    for k in range(len(bs) - 1):
        a, b = bs[k], bs[k + 1]
        ov = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"]); nw = min(a["x1"] - a["x0"], b["x1"] - b["x0"])
        if ov >= 0.4 * nw and abs(a["cy"] - b["cy"]) >= 0.25 * ph:
            up, lo = (k, k + 1) if a["cy"] < b["cy"] else (k + 1, k)
            res[k] = res[k + 1] = (up, lo)
    return res


def main():
    S = json.load(open(C.E18 / "out/sample.json")); rows = json.load(open(E21 / "out/summary21.json"))["rows"]
    ok = {(r["w"], r["k"]): r["ok"] for r in rows if r["m"] == "cutter_new"}
    out = {}; tally = {}
    for s, ws in S.items():
        for w in ws:
            wid = C.R18.wid(w); m = C.match(w, w["doc"], "new"); info = {}
            for pk, (idx, p) in m.items():
                bs = bodies(p); st = stacked_pairs(p, bs)
                for j, i in enumerate(idx):
                    info[i + 1] = dict(body=bs[j], stacked=j in st, role=("upper" if st[j][0] == j else "lower") if j in st else None,
                                       partner=(idx[st[j][1]] + 1 if st[j][0] == j else idx[st[j][0]] + 1) if j in st else None,
                                       cell=w["cutter"][i] if False else None)
            out[wid] = dict(sample=s, doc=w["doc"], text=w["text"], letters=info)
            for k, v in info.items():
                key = ("stacked" if v["stacked"] else "joined", s); o = ok.get((wid, k))
                if o is None: continue
                t = tally.setdefault(key, [0, 0]); t[0] += o; t[1] += 1
    json.dump(out, open(HERE / "out/stacked.json", "w"), ensure_ascii=False)
    for k, (a, n) in sorted(tally.items()): print(k, f"{a}/{n} = {100 * a / n:.0f}% right (today)")
    from collections import Counter
    c = Counter((v["text"][int(k) - 1], v["letters"][k]["role"]) for v in out.values() for k in v["letters"] if v["letters"][k]["stacked"])
    print(c.most_common(20))
    print([ (wid, v["text"]) for wid, v in out.items() if any(l["stacked"] for l in v["letters"].values())][:60])


if __name__ == "__main__":
    main()

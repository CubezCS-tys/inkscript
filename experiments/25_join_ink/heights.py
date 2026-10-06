"""Experiment 23's option on top of a variant's cuts: each of the 112 stacked letters highlighted only over its own
ink's rows (what Chromium 153 draws when the letter is in its own font with FontBBox = its ink box; 23, section 1).
ys from the replayed plan: the letter's ink with its marks, as the PDF draws it.

    ../../.venv/bin/python heights.py VARIANT     -> out/heights_<variant>.json {wid: {k: [y0, y1]}}
"""
import sys, json
from common import *


def ys_of(variant):
    out = {}; W = words()
    rows = stacked_rows()
    for r in rows:
        s, w = W[r["w"]]; m = match(w, variant)
        for pk, (idx, p) in m.items():
            if r["k"] - 1 not in idx: continue
            j = idx.index(r["k"] - 1); a, b = P.intervals(p)[j]
            yy, xx = np.where(P._mask(p, a, b, owner=j))
            if len(yy): out.setdefault(r["w"], {})[str(r["k"])] = [int(yy.min() + p["off"][1]), int(yy.max() + 1 + p["off"][1])]
    return out


if __name__ == "__main__":
    v = sys.argv[1]; Y = ys_of(v); json.dump(Y, open(HERE / f"out/heights_{v}.json", "w"))
    if v == "today":
        B = json.load(open(E23 / "out/boxes_cell.json")); d = []
        for wid, ks in Y.items():
            for k, (y0, y1) in ks.items():
                ref = B[wid]["ys"][int(k) - 1]
                if ref: d.append(max(abs(y0 - ref[0]), abs(y1 - ref[1])))
        print("vs 23's FontBBox heights: n", len(d), "within 2px", sum(x <= 2 for x in d), "median", np.median(d))
    print(sum(len(v) for v in Y.values()), "letters")

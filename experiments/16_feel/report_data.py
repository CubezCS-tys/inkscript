"""Data for the visual report: the held-out TEST pieces read by the first feeler (feel_v1) and the best one
(hybrid_ctc_geo), with the ink, the letters coloured, and the stick's walk for the live page.

    out/torchenv/bin/python report_data.py        # writes out/report_data.json
"""
import json, random
import numpy as np
import bench, feel as FE
from methods import feel_v1 as V1, hybrid_ctc_geo as H


def ink_of(q):
    m = q["real"] if q.get("real") is not None else q["F"]["main"]; m = m.copy()
    for _, _, lab in q["G"]["marks"]: m |= q["F"]["lab"] == lab
    return m


def row(rec, letters, cuts, right):
    q = rec["q"]; f = FE.feeling(q, rec["rise"]); m = ink_of(q)
    return dict(doc=rec["doc"], page=rec["page"], truth="".join(rec["units"]), got="".join(letters), right=right,
                n=len(rec["units"]), w=int(m.shape[1]), h=int(m.shape[0]), ink=FE.png_b64(m), seg=FE.seg_map(q, cuts, len(letters)),
                letters=list(letters), cuts=[int(c) for c in cuts], ref=rec.get("ref_cuts"), base=float(q["base"]),
                rise=float(rec["rise"]), W=int(q["G"]["W"]), **FE.walk_out(q))


def same(rec, letters):
    return [bench.base(u) for u in rec["units"]] == [bench.base(x) for x in letters]


out = dict(docs={}, live=[])
rng = random.Random(7)
for doc in bench.SUITE:
    data = bench.load(doc); tr = data["train"]; m1 = V1.learn(tr); mh = H.learn(tr)
    rows = []
    for rec in data["test"]:
        if rec["q"] is None: continue
        l1, c1 = V1.read(m1, rec); lh, ch = H.read(mh, rec)
        rows.append((rec, (l1, c1, same(rec, l1)), (lh, ch, same(rec, lh))))
    fixed = [r for r in rows if r[2][2] and not r[1][2] and r[0]["units"].__len__() >= 2]
    longok = [r for r in rows if r[2][2] and len(r[0]["units"]) >= 4]
    wrong = [r for r in rows if not r[2][2] and len(r[0]["units"]) >= 2]
    pick = lambda xs, k: rng.sample(xs, min(k, len(xs)))
    ex = []
    for kind, xs, k in (("fixed", fixed, 10), ("long", longok, 6), ("wrong", wrong, 8)):
        for rec, a, b in pick(xs, k):
            r = row(rec, b[0], b[1], b[2]); r["kind"] = kind; r["v1"] = "".join(a[0]); r["v1_seg"] = FE.seg_map(rec["q"], a[1], len(a[0])); ex.append(r)
    out["docs"][doc] = ex
    live = rows if doc == "0582" else pick(rows, 80)
    out["live"] += [row(rec, b[0], b[1], b[2]) for rec, a, b in live]
    print(doc, len(rows), "fixed", len(fixed), "long right", len(longok), "wrong", len(wrong), flush=True)
json.dump(out, open(bench.OUT / "report_data.json", "w"), ensure_ascii=False)

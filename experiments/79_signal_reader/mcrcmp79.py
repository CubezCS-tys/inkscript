"""Experiment 79: skeleton vs MCR centre line (mcr79.py) on synthetic lines with known letters and counters.

    PYTHONPATH=data/pylib nice -n 19 ionice -c3 python mcrcmp79.py [N=240]   -> out/mcrcmp/rows.jsonl, summary.json

Per line (exp 78's text and faces; damage clean / mild / heavy / spread, a quarter each) and per extractor:
  letter-order error and dot ownership (synth79.score, rung 0's measure);
  for every closed counter of the clean glyphs (a loop letter's hole):
    ink_open  - the damaged ink still leaves it open (data79.loops_kept's test);
    traced    - the extracted pen path goes round it (the path, drawn as lines, encloses the counter's centre);
    blob      - a path point inside that letter's ink carries the blob flag (thickness >= 1.8 x the stroke);
    signalled - traced or blob: the reader is told "a closed head was here";
  false blobs - the share of path points inside letters WITHOUT a counter that carry the blob flag.
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict

import cv2
import numpy as np

import synth79 as S
from data79 import ARABIC, TRAIN_FONTS, cut, damage
from sig79 import BLOB, OUT, binarise, line_signal

cv2.setNumThreads(1)
LOOP = set("وفقمهةصضطظعغؤ")


def counters(owner, text):
    out = []
    for c in sorted({int(c) for c in np.unique(owner) if c >= 0}):
        m = (owner == c).astype(np.uint8)
        cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        if hier is None:
            continue
        for j, h in enumerate(hier[0]):
            if h[3] < 0:
                continue
            hole = np.zeros_like(m)
            cv2.drawContours(hole, cs, j, 1, -1)
            hole &= (1 - m)
            if hole.sum() < 4:
                continue
            ys, xs = np.where(hole > 0)
            out.append(dict(c=c, ch=text[c] if c < len(text) else "?", hole=hole > 0, cy=float(ys.mean()), cx=float(xs.mean()),
                            r=float(np.sqrt(hole.sum() / np.pi))))
    return out


def traced(sig, shape, cy, cx, r_hole: float = 3.0) -> bool:
    """The pen path goes round the counter: its main-stroke points within a ring around the counter's centre
    (out to 2.5 x the counter's radius plus 3 px) surround the centre with no angular gap over 90 degrees."""
    P = np.vstack([st["pts"] for st in sig["strokes"] if st["kind"] == "main" and len(st["pts"])]) if sig["strokes"] else np.zeros((0, 2))
    if not len(P):
        return False
    d = np.hypot(P[:, 0] - cy, P[:, 1] - cx)
    near = P[(d <= 2.5 * r_hole + 3) & (d >= 0.3)]
    if len(near) < 4:
        return False
    ang = np.sort(np.arctan2(near[:, 0] - cy, near[:, 1] - cx))
    gaps = np.diff(np.r_[ang, ang[0] + 2 * np.pi])
    return bool(gaps.max() <= np.pi / 2)


def main(n=240, seed=7911):
    import gzip
    rng = random.Random(seed)
    texts = []
    with gzip.open(S.TEXT, "rt", encoding="utf-8") as f:
        for i, l in enumerate(f):
            if i % 50 == 7:
                texts.append(json.loads(l)["t"])
            if len(texts) > 4000:
                break
    od = OUT / "mcrcmp"
    od.mkdir(parents=True, exist_ok=True)
    fonts = [f for f in TRAIN_FONTS if not f.startswith("traced")]
    rows = []
    fo = open(od / "rows.jsonl", "w", encoding="utf-8")
    levels = ["clean", "mild", "heavy", "spread"]
    while len(rows) < n:
        t = cut(rng.choice(texts), rng)
        if len(t) < 8 or not (set(t) & LOOP):
            continue
        fp = S.FONTS / rng.choice(fonts)
        if not S.covers(fp, t):
            continue
        S.H = 96
        grey, owner, ink = S.render(t, fp, px_per_em=62.0 * rng.uniform(0.85, 1.15))
        lv = levels[len(rows) % 4]
        g = grey if lv == "clean" else damage(grey, rng, lv)
        ink_d = ink if lv == "clean" else binarise(g)
        C = counters(owner, t)
        rec = dict(text=t, font=fp.stem, level=lv, counters=[c["ch"] for c in C])
        loopless = np.isin(owner, [c for c in np.unique(owner) if c >= 0 and c < len(t) and t[c] not in LOOP and t[c] in ARABIC])
        for ext in ("skeleton", "mcr"):
            sig = line_signal(g, start_rule="top", ink=None if lv != "clean" else ink, centre=ext)
            sc = S.score(sig, owner, t, ink)
            per = []
            for c in C:
                lm = cv2.dilate((owner == c["c"]).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
                blob = False
                mx = 0.0
                for st in sig["strokes"]:
                    p = np.round(st["pts"]).astype(int)
                    y = np.clip(p[:, 0], 0, lm.shape[0] - 1)
                    x = np.clip(p[:, 1], 0, lm.shape[1] - 1)
                    if lm[y, x].any():
                        mx = max(mx, float(st["thick"][lm[y, x]].max()))
                    if (lm[y, x] & (st["thick"] >= BLOB)).any():
                        blob = True
                tr = traced(sig, ink.shape, c["cy"], c["cx"], c["r"])
                per.append(dict(ch=c["ch"], max_thick=round(mx, 3), ink_open=bool((~ink_d[c["hole"]]).mean() > 0.5), traced=tr, blob=blob,
                                signalled=tr or blob))
            fb = tot = 0
            lt = []
            for st in sig["strokes"]:
                p = np.round(st["pts"]).astype(int)
                y = np.clip(p[:, 0], 0, ink.shape[0] - 1)
                x = np.clip(p[:, 1], 0, ink.shape[1] - 1)
                inl = loopless[y, x]
                tot += int(inl.sum())
                fb += int((inl & (st["thick"] >= BLOB)).sum())
                lt.extend(np.round(st["thick"][inl], 3).tolist())
            rec[ext] = dict(order_err=sc["order_err"], dot_own=sc["dot_own"], counters=per, false_blob=fb / max(1, tot),
                            loopless_thick=lt)
        rows.append(rec)
        fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fo.flush()
        if len(rows) % 40 == 0:
            print(len(rows), flush=True)
    summ = {}
    for lv in levels + ["all"]:
        R = [r for r in rows if lv == "all" or r["level"] == lv]
        for ext in ("skeleton", "mcr"):
            per = [c for r in R for c in r[ext]["counters"]]
            closed = [c for c in per if not c["ink_open"]]
            d = dict(lines=len(R), order_err=round(float(np.mean([r[ext]["order_err"] for r in R])), 4),
                     dot_own=round(float(np.mean([r[ext]["dot_own"] for r in R if r[ext]["dot_own"] is not None])), 4),
                     counters=len(per), traced=round(float(np.mean([c["traced"] for c in per])), 3) if per else None,
                     signalled=round(float(np.mean([c["signalled"] for c in per])), 3) if per else None,
                     closed_counters=len(closed),
                     closed_signalled=round(float(np.mean([c["signalled"] for c in closed])), 3) if closed else None,
                     false_blob=round(float(np.mean([r[ext]["false_blob"] for r in R])), 4))
            by = defaultdict(list)
            for c in per:
                by[c["ch"]].append(c["signalled"])
            allt = np.array([v for r in R for v in r[ext]["loopless_thick"]] or [0.0])
            for fr in (0.01, 0.05):
                thr = float(np.quantile(allt, 1 - fr))
                cl_ = closed or per
                d[f"at_false_{fr}"] = dict(threshold=round(thr, 2),
                                           closed_signalled=round(float(np.mean([c["traced"] or c["max_thick"] > thr for c in cl_])), 3))
            d["signalled_by_letter"] = {k: f"{sum(v)}/{len(v)}" for k, v in sorted(by.items()) if k in LOOP}
            summ[f"{lv}/{ext}"] = d
    (od / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1))
    for k, v in summ.items():
        print(k, {a: b for a, b in v.items() if a != "signalled_by_letter"})


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 240)

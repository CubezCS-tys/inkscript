"""Experiment 79, rung 0: is the reconstructed pen path right?  Summarise data79's scored test lines.

    python rung0_79.py out/rung0        -> out/rung0/summary.json (+ printed table)

Letter-order error per line (synth79.score): edit distance between the letters met along the reconstructed path
(first visits, retraces skipped) and the true letter sequence, over the number of letters with a body.  Judged
against PLAN.md's pre-registered pass marks: clean mean <= 8% and median <= 5%, dots in the right piece >= 95%,
mild damage mean <= 12% (heavy reported, not judged).
"""
from __future__ import annotations

import glob
import json
import sys
from collections import defaultdict

import numpy as np


def main(d: str):
    rows = []
    for sp in ("test", "testfont"):
        for f in sorted(glob.glob(f"{d}/{sp}-*.jsonl")):
            for l in open(f, encoding="utf-8"):
                r = json.loads(l)
                r["split"] = sp
                rows.append(r)
    out = {}
    for sp in ("test", "testfont"):
        R = [r for r in rows if r["split"] == sp]
        if not R:
            continue
        groups = {"clean": [r["s_clean"] for r in R]}
        for lv in ("mild", "heavy"):
            groups[lv] = [r["s_dmg"] for r in R if r["level"] == lv]
        for g, S in groups.items():
            e = np.array([s["order_err"] for s in S])
            dots = [s["dot_own"] for s in S if s["dot_own"] is not None]
            out[f"{sp}/{g}"] = dict(lines=len(S), mean=round(float(e.mean()), 4), median=round(float(np.median(e)), 4),
                                    exact=round(float((e == 0).mean()), 3), p90=round(float(np.percentile(e, 90)), 3),
                                    back_steps_per_line=round(float(np.mean([s["back_steps"] for s in S])), 2),
                                    dot_own=round(float(np.mean(dots)), 4) if dots else None)
        byf = defaultdict(list)
        for r in R:
            byf[r["font"]].append(r["s_clean"]["order_err"])
        out[f"{sp}/clean_by_font"] = {k: dict(lines=len(v), mean=round(float(np.mean(v)), 4)) for k, v in sorted(byf.items())}
    t = out.get("test/clean", {})
    m = out.get("test/mild", {})
    out["verdict"] = dict(clean_mean_ok=t.get("mean", 1) <= 0.08, clean_median_ok=t.get("median", 1) <= 0.05,
                          dots_ok=(t.get("dot_own") or 0) >= 0.95, mild_mean_ok=m.get("mean", 1) <= 0.12,
                          lines_ok=t.get("lines", 0) >= 1000)
    out["verdict"]["pass"] = all(out["verdict"].values())
    with open(f"{d}/summary.json", "w") as f:
        json.dump(out, f, indent=1)
    for k, v in out.items():
        if "by_font" not in k:
            print(k, v)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out/rung0")

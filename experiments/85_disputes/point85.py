"""Experiment 85, step 2e: the free rules re-measured on the new judged lines, at the disputed point.

    .venv/bin/python experiments/85_disputes/point85.py      -> out/judge/point85.json (+ table)

For each cell (type, direction, v3's vote) and each side (Azure / v1): line = the side equals the judge's truth; point =
the side is closer to the truth than the other side (edit distance in the comparison form; a tie is a miss).  Wilson
95% lower bound on point.  Includes the audit lines of rule85.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rapidfuzz.distance import Levenshtein

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common85 import OUT, sform  # noqa: E402
from est85 import jl, truth_of  # noqa: E402
from rules85 import wilson_lo  # noqa: E402

J = OUT / "judge"


def rows():
    S = {d["key"]: d for d in jl(J / "sample.jsonl")}
    for a in jl(J / "answers.jsonl"):
        t = truth_of(a)
        if t is None:
            continue
        s = S[a["key"]]
        ft, fa, fb = sform(t), sform(s["azure"]), sform(s["v1"])
        da, db = Levenshtein.distance(fa, ft), Levenshtein.distance(fb, ft)
        yield dict(s, line="az" if fa == ft else "v1" if fb == ft else "none",
                   point="az" if da < db else "v1" if db < da else "tie")


def main():
    C = defaultdict(Counter)
    for r in rows():
        for k in [(r["type"], r["dir"], r["vote"]), (r["type"], r["dir"], "*"), (r["group"], "*", r["vote"]),
                  (r["type"], r["dir"], r["vote"], r["band"])]:
            C[k]["n"] += 1
            C[k]["l_" + r["line"]] += 1
            C[k]["p_" + r["point"]] += 1
    out = []
    for k, c in C.items():
        n = c["n"]
        for side in ("az", "v1"):
            out.append(dict(cell="|".join(k), side=side, n=n, line=round(100 * c["l_" + side] / n, 1),
                            point=round(100 * c["p_" + side] / n, 1), point_lo=round(100 * wilson_lo(c["p_" + side], n), 1)))
    out.sort(key=lambda r: -r["point"])
    (J / "point85.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{'cell':42s} side   n   line  point  lo95")
    for r in out:
        if r["n"] >= 25 and r["point"] >= 80:
            print(f"{r['cell']:42s} {r['side']:4s} {r['n']:5d} {r['line']:5.1f} {r['point']:5.1f} {r['point_lo']:5.1f}")


if __name__ == "__main__":
    main()

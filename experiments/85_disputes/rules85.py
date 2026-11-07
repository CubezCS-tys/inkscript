"""Experiment 85, step 1b: candidate free rules, their precision on the judged lines, and the lines they settle.

    .venv/bin/python experiments/85_disputes/rules85.py          -> out/types/rules85.json (+ table)

A rule is (type, direction, era or *, v3's vote or *) -> a side (Azure or v1).  Two precisions:
  line   the chosen side equals the truth exactly (sform);
  point  on the disputed point: the chosen side is closer to the truth than the other side (edit distance); lines
         where both sides are equally far from the truth (the truth is a third reading at that point) count as wrong.
Judged sources as in types85.py: j81 (blind-first judge), j77 (A/B judge), own81 (the owner's Azure-drafted truth).
"""
from __future__ import annotations

import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rapidfuzz.distance import Levenshtein

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common85 import OUT, sform  # noqa: E402

T = OUT / "types"


def wilson_lo(k, n, z=1.96):
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d


def point(d):
    t, a, b = sform(d["truth"]), sform(d["azure"]), sform(d["v1"])
    da, db = Levenshtein.distance(a, t), Levenshtein.distance(b, t)
    return "az" if da < db else "v1" if db < da else "tie"


def cells(key):
    t, di, e, vt = key
    return [(t, di, e2, v2) for e2 in (e, "*") for v2 in (vt, "*")]


def main():
    cal = [json.loads(l) for l in open(T / "calib.jsonl", encoding="utf-8")]
    stat = defaultdict(lambda: defaultdict(Counter))
    for d in cal:
        p = point(d)
        for c in cells((d["type"], d["dir"], d["era"], d.get("vote", "-"))):
            stat[c][d["src"]][("line", d["side"])] += 1
            stat[c][d["src"]][("point", p)] += 1
    held = Counter()
    with gzip.open(T / "held_typed.jsonl.gz", "rt", encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            for c in cells((d["type"], d["dir"], d["era"], d["vote"])):
                held[c] += 1
    rows = []
    for c, S in stat.items():
        for side in ("v1", "az"):
            r = dict(rule="|".join(c), side=side, held=held.get(c, 0))
            for src in ("j81", "j77", "own81"):
                s = S.get(src, Counter())
                n = sum(v for (k, _), v in s.items() if k == "line")
                kl, kp = s[("line", side)], s[("point", side)]
                r[src] = dict(n=n, line=round(100 * kl / n, 1) if n else None, point=round(100 * kp / n, 1) if n else None,
                              point_lo=round(100 * wilson_lo(kp, n), 1) if n else None)
            rows.append(r)
    (T / "rules85.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    rows = [r for r in rows if r["j81"]["n"] >= 10 and (r["j81"]["point"] or 0) >= 85]
    rows.sort(key=lambda r: -r["j81"]["point"])
    print(f"{'rule':38s} side  held    | j81 n  line point lo   | j77 n  line point | own n line point")
    for r in rows:
        a, b, o = r["j81"], r["j77"], r["own81"]
        print(f"{r['rule']:38s} {r['side']:4s} {r['held']:7d} | {a['n']:5d} {a['line']:5} {a['point']:5} {a['point_lo']:5} | "
              f"{b['n']:5d} {b['line']} {b['point']} | {o['n']:3d} {o['line']} {o['point']}")


if __name__ == "__main__":
    main()

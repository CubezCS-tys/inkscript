"""Experiment 82: loops kept per loop letter, per level and rebuilder (from shape rows).

    python analyse82.py out/shape_modern [more dirs]  -> printed table + <first dir>/loops_by_letter.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

acc = defaultdict(lambda: [0, 0])
for d in sys.argv[1:]:
    for l in open(Path(d) / "rows.jsonl", encoding="utf-8"):
        r = json.loads(l)
        for x in r["loops"]:
            k = (r["level"], r["method"], x["ch"])
            acc[k][0] += x["loop"]
            acc[k][1] += 1
out = {"/".join(k): f"{a}/{n} = {100 * a / n:.0f}%" for k, (a, n) in sorted(acc.items())}
Path(sys.argv[1], "loops_by_letter.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
levels = sorted({k[0] for k in acc})
methods = sorted({k[1] for k in acc})
chars = sorted({k[2] for k in acc}, key=lambda c: -sum(acc[k][1] for k in acc if k[2] == c))
for m in methods:
    print(m)
    print("    " + " ".join(f"{c:>6}" for c in chars))
    for lv in levels:
        print(f"{lv:>7} " + " ".join(f"{100 * acc[(lv, m, c)][0] / acc[(lv, m, c)][1]:5.0f}%" if acc[(lv, m, c)][1] >= 10 else "     -" for c in chars))

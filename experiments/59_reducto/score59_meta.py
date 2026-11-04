"""Experiment 59: metadata from page 1 -- Reducto Extract (std, deep) against the proof pack's metadata gold.

    /home/appuser/inkscript/.venv/bin/python score59_meta.py   -> out/meta_scores.json

Verdicts are in judge59_meta.json (judged by looking at each page; ours = the proof pack's verdict after fix round 3).
A page-1 article is fully right when every field page 1 prints is right.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
J = json.loads((HERE / "judge59_meta.json").read_text())
res = {}
for k, who in enumerate(("ours", "std", "deep")):
    c, full, n = Counter(), 0, 0
    per = {}
    for stem, f in J.items():
        if stem.startswith("_"):
            continue
        n += 1
        ok = True
        for field, v in f.items():
            if field.startswith("_") or v[k] == "n/a":
                continue
            c[v[k]] += 1
            per.setdefault(field, Counter())[v[k]] += 1
            ok &= v[k] == "right"
        full += ok
    res[who] = dict(articles=n, fully_right=full, fields=dict(c), per_field={x: dict(y) for x, y in per.items()})
(HERE / "out" / "meta_scores.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
for who, x in res.items():
    print(who, "fully right", x["fully_right"], "/", x["articles"], x["fields"], x["per_field"])

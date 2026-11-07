"""Experiment 84: «» and (( )) as printed, on the owner's 20 yardstick pages (kept apart from the headline).

    python3 quotes84.py NAME=PRED.jsonl ...        (azure is always included)  -> out/quotes84.json

Each Azure line of the yardstick pages is paired with the owner's truth line it maps to (pages.json gold_pos, as
eval77 does).  Per line and per mark kind, matched = min(count in the reading, count in the truth), counting each
character « » and each pair-half (( / )) once.  Precision = matched / marks the reader wrote; recall = matched /
marks in the truth.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGES = HERE.parent / "77_scratch_reader/out/test/pages.json"
KINDS = {"«»": re.compile("[«»]"), "(( ))": re.compile(r"\(\(|\)\)")}


def lit(x):
    return ast.literal_eval(x) if isinstance(x, str) else x


def main(specs):
    preds = {}
    for s in specs:
        n, f = s.split("=", 1)
        preds[n] = {d["key"]: d["pred"] for d in map(json.loads, open(f, encoding="utf-8"))}
    pages = [p for p in json.loads(PAGES.read_text(encoding="utf-8")) if p["set"] == "yardstick"]
    res = {}
    for name in ["azure"] + list(preds):
        c = {k: [0, 0, 0] for k in KINDS}        # matched, written, in truth
        for p in pages:
            truth, gp = lit(p["truth"]), lit(p["gold_pos"])
            for ln in lit(p["lines"]):
                j = gp.get(str(ln["i"]), gp.get(ln["i"]))
                if j is None:
                    continue
                t = truth[j]
                r = ln["azure"] if name == "azure" else preds[name].get(ln["key"])
                if r is None:
                    continue
                for k, rx in KINDS.items():
                    a, b = len(rx.findall(r)), len(rx.findall(t))
                    c[k][0] += min(a, b)
                    c[k][1] += a
                    c[k][2] += b
        res[name] = {k: dict(matched=v[0], written=v[1], in_truth=v[2],
                             precision=round(v[0] / v[1], 3) if v[1] else None,
                             recall=round(v[0] / v[2], 3) if v[2] else None) for k, v in c.items()}
    (HERE / "out/quotes84.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for n, v in res.items():
        print(n, json.dumps(v, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])

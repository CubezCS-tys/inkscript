"""Experiment 85, step 2d: what the judge says about the held disputes, per type, era band and v3's vote.

    .venv/bin/python experiments/85_disputes/est85.py        -> out/judge/est85.json (+ tables)

Truth of a judged line: the candidate the judge called right (if several distinct ones, the one equal to its reading,
else the first), else its own corrected reading; "unreadable" lines are left out (counted).  Side: Azure, v1 or v3
right (each may be right with another), or none.  Population shares: each stratum's judged lines carry weight N/n
(the sample's strata, out/judge/strata.json); the audit of rule85 is reported apart.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common85 import OUT, sform  # noqa: E402

J = OUT / "judge"


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if Path(p).exists() else []


def truth_of(a: dict) -> str | None:
    if a["verdict"] == "unreadable":
        return None
    sh = a["shown"]
    if a["verdict"] == "match" and a.get("right_idx"):
        R = [sh[j] for j in a["right_idx"] if j < len(sh)]
        fs = {sform(x) for x in R}
        if len(fs) == 1:
            return R[0]
        return next((x for x in R if sform(x) == sform(a["reading"])), R[0])
    return a["reading"]


def judged_truths() -> dict[str, str]:
    out = {}
    for a in jl(J / "answers.jsonl"):
        t = truth_of(a)
        if t is not None and sform(t):
            out[a["key"]] = t
    return out


def main():
    S = {d["key"]: d for d in jl(J / "sample.jsonl")}
    strata = json.loads((J / "strata.json").read_text())["strata"]
    A = {a["key"]: a for a in jl(J / "answers.jsonl")}
    rows = []
    unread = Counter()
    for k, a in A.items():
        s = S[k]
        t = truth_of(a)
        if t is None:
            unread[s["stratum"]] += 1
            continue
        ft = sform(t)
        r = dict(key=k, stratum=s["stratum"], group=s["group"], type=s["type"], dir=s["dir"], band=s["band"],
                 vote=s["vote"], az=sform(s["azure"]) == ft, v1=sform(s["v1"]) == ft, v3=sform(s["v3"]) == ft,
                 blind_eq=sform(a["blind"]) == ft)
        r["side"] = "az" if r["az"] and not r["v1"] else "v1" if r["v1"] and not r["az"] else \
            "both" if r["az"] and r["v1"] else "none"
        rows.append(r)
    res = dict(answered=len(A), unreadable=sum(unread.values()), cells={})

    def tab(keyf, name):
        C = defaultdict(Counter)
        for r in rows:
            C[keyf(r)][r["side"]] += 1
            C[keyf(r)]["v3ok"] += r["v3"]
            C[keyf(r)]["n"] += 1
        res["cells"][name] = {str(k): dict(v) for k, v in sorted(C.items())}
        print(f"\n== by {name}: n, Azure right, v1 right, neither (%), v3 right")
        for k, v in sorted(C.items()):
            n = v["n"]
            print(f"  {str(k):45s} {n:5d}  az {100 * v['az'] / n:5.1f}  v1 {100 * v['v1'] / n:5.1f}  "
                  f"none {100 * v['none'] / n:5.1f}  v3 {100 * v['v3ok'] / n:5.1f}")
    tab(lambda r: r["group"] if r["stratum"] != "audit_rule85" else "AUDIT rule85", "group")
    tab(lambda r: (r["group"], r["band"]), "group_band")
    tab(lambda r: (r["type"], r["dir"], r["vote"]), "type_dir_vote")
    tab(lambda r: (r["group"], r["vote"]), "group_vote")
    # population-weighted overall (strata weights N/n of judged lines)
    W = Counter()
    for r in rows:
        if r["stratum"] != "audit_rule85":
            W[r["stratum"]] += 1
    tot = Counter()
    for r in rows:
        if r["stratum"] == "audit_rule85":
            continue
        w = strata[r["stratum"]]["N"] / W[r["stratum"]]
        tot[r["side"]] += w
        tot["v3"] += w * r["v3"]
        tot["n"] += w
    res["population"] = {k: round(100 * v / tot["n"], 1) for k, v in tot.items() if k != "n"}
    res["blind_eq_truth"] = round(100 * sum(r["blind_eq"] for r in rows) / max(1, len(rows)), 1)
    print("\npopulation-weighted (frame minus rule85):", res["population"], "blind = final", res["blind_eq_truth"])
    (J / "est85.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

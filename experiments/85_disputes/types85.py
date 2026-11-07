"""Experiment 85, step 1 (free, CPU): the 444,265 held disputes by type, and which side tends to be right per type.

    nice -n 19 ionice -c3 .venv/bin/python experiments/85_disputes/types85.py

Writes out/types/held_typed.jsonl.gz (every held line with its type, direction and v3's vote), out/types/calib.jsonl
(the judged lines used to measure the rules) and out/types/types85.json (counts and per-cell verdict shares).

v3's vote: v3 (exp 83) read every held line again; on 101,091 it reads as Azure does (they left held_v4), on the
343,174 others held_v4 has its reading.  vote = 'az' (v3 = Azure), 'v1' (v3 = v1), 'other'.

Judged lines (the truth for measuring rules; none of them is trained on here):
  j81    experiment 81: blind-first judge, held-out journals, punctuation ignored (answers.jsonl, answers_pilot.jsonl;
         candidates from sample / calib / pilot.jsonl).  v1, v3 and Azure from readings81.jsonl.
  own81  the owner's truth on the same experiment-81 yardstick lines (drafted from Azure: leans to Azure).
  j77    experiment 77: A/B judge (not blind; v1 vs Azure only) on v1's own training journals.  No v3 vote.
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common85 import E, HELD3, HELD4, OUT, dtype, era3, sform  # noqa: E402

T = OUT / "types"
E81 = E / "81_heldout_scale/out"
E77 = E / "77_scratch_reader/out/judge"


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def vote(az, v1, v3):
    f3 = sform(v3)
    if f3 == sform(az):
        return "az"
    if f3 == sform(v1):
        return "v1"
    return "other"


def side(az, v1, t):
    ft = sform(t)
    return "az" if ft == sform(az) else "v1" if ft == sform(v1) else "neither"


def truth81(s, a):
    if a["verdict"] == "unreadable":
        return None
    if a["verdict"] == "match" and a.get("right_idx"):
        R = [s["shown"][j] for j in a["right_idx"] if j < len(s["shown"])]
        fs = {sform(x) for x in R}
        if len(fs) == 1:
            return R[0]
        return a["reading"] if sform(a["reading"]) in fs else R[0]
    return a["reading"]


def calib():
    rows = {d["key"]: d for d in jl(E81 / "readings81.jsonl")}
    shown = {}
    for f in ("sample", "calib", "pilot", "nuqta_extra"):
        if (E81 / f"judge/{f}.jsonl").exists():
            for d in jl(E81 / f"judge/{f}.jsonl"):
                shown.setdefault(d["key"], d)
    ans = {}
    for f in ("answers_pilot.jsonl", "answers.jsonl"):
        for a in jl(E81 / "judge" / f):
            if a["key"] in shown:
                ans[a["key"]] = a
    out = []
    for k, r in rows.items():
        R = r["readings"]
        if r["kind"] != "arabic" or "v3" not in R:
            continue
        az, v1, v3 = R["azure"], R["v1"], R["v3"]
        ty, di = dtype(az, v1)
        if ty == "same":
            continue
        base = dict(key=k, era=r["era"], jcode=r["jcode"], type=ty, dir=di, vote=vote(az, v1, v3), azure=az, v1=v1,
                    v3=v3)
        if k in ans:
            t = truth81(shown[k], ans[k])
            if t is not None:
                out.append(dict(base, src="j81", truth=t, side=side(az, v1, t), v3ok=sform(v3) == sform(t)))
        if r.get("truth") is not None:
            t = r["truth"]
            out.append(dict(base, src="own81", truth=t, side=side(az, v1, t), v3ok=sform(v3) == sform(t)))
    S = {d["key"]: d for d in jl(E77 / "sample.jsonl")}
    for a in jl(E77 / "answers.jsonl"):
        s = S.get(a["key"])
        if not s or a["winner"] == "unreadable":
            continue
        az, v1 = s["azure"], s["v1"]
        t = v1 if a["winner"] == "v1" else az if a["winner"] in ("azure", "both") else a["reading"]
        ty, di = dtype(az, v1)
        if ty == "same":
            continue
        out.append(dict(key=a["key"], era=era3(s["year"]), jcode=s["jcode"], type=ty, dir=di, vote="-", azure=az,
                        v1=v1, src="j77", truth=t, side=side(az, v1, t)))
    return out


def main():
    T.mkdir(parents=True, exist_ok=True)
    v3r = {}
    with gzip.open(HELD4, "rt", encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            v3r[d["key"]] = d["reader"]
    C = Counter()
    by = defaultdict(Counter)
    with gzip.open(HELD3, "rt", encoding="utf-8") as f, gzip.open(T / "held_typed.jsonl.gz", "wt", encoding="utf-8") as g:
        for l in f:
            d = json.loads(l)
            ty, di = dtype(d["azure"], d["reader"])
            v3 = v3r.get(d["key"], d["azure"])
            vt = vote(d["azure"], d["reader"], v3) if d["key"] in v3r else "az"
            e = era3(d["year"])
            g.write(json.dumps(dict(key=d["key"], year=d["year"], era=e, jcode=d["jcode"], type=ty, dir=di, vote=vt,
                                    azure=d["azure"], v1=d["reader"], v3=v3, cmin=d["cmin"], cmean=d["cmean"]),
                               ensure_ascii=False) + "\n")
            C[(ty, di)] += 1
            by[(ty, di)][(e, vt)] += 1
    cal = calib()
    with open(T / "calib.jsonl", "w", encoding="utf-8") as f:
        for d in cal:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    n = sum(C.values())
    print(f"held lines {n:,}")
    for (ty, di), c in C.most_common():
        vs = Counter()
        for (e, vt), x in by[(ty, di)].items():
            vs[vt] += x
        print(f"  {ty:11s} {di:5s} {c:8,d} {100 * c / n:5.1f}%  v3 votes", dict(vs))
    cell = defaultdict(Counter)
    for d in cal:
        for k in [(d["src"], d["type"], d["dir"], "*", "*"), (d["src"], d["type"], d["dir"], d["era"], "*"),
                  (d["src"], d["type"], d["dir"], "*", d["vote"]), (d["src"], d["type"], d["dir"], d["era"], d["vote"])]:
            cell[k][d["side"]] += 1
    res = dict(held={f"{t}|{d}": c for (t, d), c in C.most_common()},
               held_by_era_vote={f"{t}|{d}": {f"{e}|{v}": x for (e, v), x in sorted(by[(t, d)].items())} for (t, d) in C},
               calib={"|".join(k): dict(v) for k, v in sorted(cell.items())},
               calib_n=Counter(d["src"] for d in cal))
    (T / "types85.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("calib lines:", res["calib_n"])
    for src in ("j81", "own81", "j77"):
        print(f"\n== {src}: type dir (all eras, all votes): az / v1 / neither")
        for k, v in sorted(cell.items()):
            if k[0] == src and k[3] == "*" and k[4] == "*":
                t = sum(v.values())
                print(f"  {k[1]:11s} {k[2]:5s} n={t:5d}  az {100 * v['az'] / t:5.1f}  v1 {100 * v['v1'] / t:5.1f}  "
                      f"neither {100 * v['neither'] / t:5.1f}")


if __name__ == "__main__":
    main()

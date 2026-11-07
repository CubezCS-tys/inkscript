"""Experiment 85, step 2a: the judge's sample of held disputes, stratified by dispute group, era band and journal.

    .venv/bin/python experiments/85_disputes/sample85.py      -> out/judge/sample.jsonl, pilot.jsonl, strata.json

Frame: the 444,265 held lines (types85.py), minus lines with no Arabic letter or mostly Latin (Arabic share < 0.5),
minus the lines settled by the free rule (rule85: hamza on alif, Azure writes the hamza, v1 and v3 both write a bare
alif), of which AUDIT lines are sampled apart to check the rule with the same judge.
Strata: dispute group x era band (pre-1960 / 1960-1999 / 2000+).  Each group gets a fixed quota (QUOTA); inside a group
the bands get their share of the group's lines, pre-1960 counted twice (extra weight on old print).  Inside a stratum
journals are taken round-robin in random order (one line a journal a round), at most 4 lines a document.
Seed 85.  Every key is checked against experiment 84's locked journals and experiment 76's held-out journals.
"""
from __future__ import annotations

import gzip
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common85 import OUT, guard  # noqa: E402

J = OUT / "judge"
QUOTA = {"one_letter": 2800, "multi": 2200, "space": 1200, "marks": 900, "hamza_other": 800, "ya": 400,
         "conv_mixed": 300, "ta": 250}
AUDIT = 150
PILOT = 50
ARABIC = re.compile("[ؠ-يٱ-ۓۺ-ۿ]")
LATIN = re.compile("[A-Za-z]")


def rule85(d) -> bool:
    """The free rule: hamza on alif only, Azure writes the hamza, v1 a bare alif, and v3 reads as v1."""
    return d["type"] == "hamza_alif" and d["dir"] == "az" and d["vote"] == "v1"


def group(d) -> str:
    t = d["type"]
    return "hamza_other" if t == "hamza_alif" else t


def band(year) -> str:
    y = int(str(year)[:4])
    return "pre-1960" if y < 1960 else "1960-1999" if y < 2000 else "2000+"


def arabic_ok(s: str) -> bool:
    a, l = len(ARABIC.findall(s)), len(LATIN.findall(s))
    return a > 0 and a / (a + l) >= 0.5


def rr_pick(rows, n, rng, per_doc):
    byj = defaultdict(list)
    for r in rows:
        byj[r["jcode"]].append(r)
    for L in byj.values():
        rng.shuffle(L)
    js = sorted(byj)
    rng.shuffle(js)
    out = []
    while len(out) < n and any(byj[j] for j in js):
        for j in js:
            while byj[j]:
                r = byj[j].pop()
                doc = r["key"].split("_p")[0]
                if per_doc[doc] < 4:
                    per_doc[doc] += 1
                    out.append(r)
                    break
            if len(out) >= n:
                break
    return out


def main():
    rng = random.Random(85)
    J.mkdir(parents=True, exist_ok=True)
    frame, audit_pool, c = defaultdict(list), [], Counter()
    with gzip.open(OUT / "types/held_typed.jsonl.gz", "rt", encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            c["held"] += 1
            if not arabic_ok(d["azure"]):
                c["not_arabic"] += 1
                continue
            r = dict(key=d["key"], jcode=d["jcode"], year=d["year"], band=band(d["year"]), type=d["type"], dir=d["dir"],
                     vote=d["vote"], group=group(d), azure=d["azure"], v1=d["v1"], v3=d["v3"])
            if rule85(d):
                c["rule85"] += 1
                audit_pool.append(r)
                continue
            frame[(r["group"], r["band"])].append(r)
            c["frame"] += 1
    per_doc = Counter()
    sample, strata = [], {}
    for g, q in QUOTA.items():
        sizes = {b: len(frame[(g, b)]) for b in ("pre-1960", "1960-1999", "2000+")}
        w = {b: n * (2 if b == "pre-1960" else 1) for b, n in sizes.items()}
        tw = sum(w.values())
        for b, n in sizes.items():
            k = min(n, round(q * w[b] / tw))
            got = rr_pick(frame[(g, b)], k, rng, per_doc)
            for r in got:
                r["stratum"] = f"{g}|{b}"
            sample += got
            strata[f"{g}|{b}"] = dict(N=n, n=len(got))
    aud = rr_pick(audit_pool, AUDIT, rng, per_doc)
    for r in aud:
        r["stratum"] = "audit_rule85"
    strata["audit_rule85"] = dict(N=len(audit_pool), n=len(aud))
    sample += aud
    try:
        guard([r["key"] for r in sample], "judge sample")
    except RuntimeError as e:          # the locked list not written yet: cut85 / judge85 check again and refuse
        print("WARNING:", e)
    rng.shuffle(sample)
    with open(J / "sample.jsonl", "w", encoding="utf-8") as f:
        for r in sample:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(J / "pilot.jsonl", "w", encoding="utf-8") as f:
        for r in sample[:PILOT]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    docs = {r["key"].split("_p")[0] for r in sample}
    (J / "strata.json").write_text(json.dumps(dict(counts=c, strata=strata, docs=len(docs), lines=len(sample)), indent=1))
    print(dict(c), "\nsample", len(sample), "lines from", len(docs), "documents,",
          len({r["jcode"] for r in sample}), "journals")
    for k, v in strata.items():
        print(f"  {k:28s} N={v['N']:7d} n={v['n']}")


if __name__ == "__main__":
    main()

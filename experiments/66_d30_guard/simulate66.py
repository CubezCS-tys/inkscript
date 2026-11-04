"""Experiment 66, phase 2: the guard over every Gemini fix of the four current runs (no masters written).

    simulate66.py run        out/decisions.jsonl (every fix + keep / refuse + reason), out/simulate.json (counts
                             per run, per article, per edit kind), and how the masters' text would change
    simulate66.py validate   out/validate.jsonl + out/vsheets/: 40 refused fixes NOT in the labelled sample, drawn at
                             random, for a clean check of the guard's precision by eye (labels: out/vlabels.tsv)
The decision is d30guard43.decide on the features collect66.py saved (Azure's word confidences from Azure's JSON, the
word test of wordlist43): the same inputs the hook sees in rules43.normalize.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict

import common66 as C

C.e43_path()
import d30guard43 as G  # noqa: E402


def real(ks):
    ks = [k for k in ks if k is not None]
    return None if not ks else all(ks)


def decide(r):
    cs = [x for x in r["confs"] if x is not None]
    f = dict(cls=G.edit_class(r["frm"], r["to"]), conf_min=min(cs) if cs else None, from_real=real(r["from_known"]),
             to_real=real(r["to_known"]), al=G.al_prefix(r["frm"], r["to"]), added=G.adds_tokens(r["frm"], r["to"]),
             code=str(r.get("why") or "").startswith("code:"))
    if not r["found"] or not r["to"]:
        return True, "not applied today either (from not in the line, or a deletion)", f
    keep, why = G.decide(f)
    return keep, why, f


def run():
    tot = defaultdict(Counter)
    arts = defaultdict(Counter)
    kinds = Counter()
    ex = defaultdict(list)
    with open(C.OUT / "decisions.jsonl", "w", encoding="utf-8") as fo:
        for i, r in enumerate(C.jlines(C.OUT / "fixes.jsonl")):
            keep, why, f = decide(r)
            fo.write(json.dumps(dict(idx=i, run=r["run"], stem=r["stem"], line=r["line"], frm=r["frm"], to=r["to"],
                                     why=r["why"], keep=keep, reason=why, cls=f["cls"], conf=f["conf_min"],
                                     in_master=r["in_master"]), ensure_ascii=False) + "\n")
            t = tot[r["run"]]
            t["fixes"] += 1
            t["in_master"] += r["in_master"]
            if not keep:
                t["refused"] += 1
                t["refused_in_master"] += r["in_master"]
                arts[r["run"]][r["stem"]] += 1
                kinds[f["cls"]] += 1
                if len(ex[r["run"]]) < 12:
                    ex[r["run"]].append(f"{r['stem']} {r['line']}: «{r['frm']}» stays, «{r['to']}» beside it "
                                        f"(Azure {f['conf_min']:.3f}; Gemini: {r['why']})")
    out = {}
    for run, t in tot.items():
        a = arts[run]
        out[run] = dict(t, articles_touched=len(a), max_per_article=max(a.values()) if a else 0, examples=ex[run])
    allr = sum(t["refused"] for t in tot.values())
    out["total"] = dict(fixes=sum(t["fixes"] for t in tot.values()), refused=allr, kinds=dict(kinds))
    C.jdump(C.OUT / "simulate.json", out)
    for run, t in tot.items():
        print(f"{run:28} fixes {t['fixes']:>6}  refused {t['refused']:>4} ({t['refused'] / t['fixes']:.1%})  "
              f"in {len(arts[run])} articles, at most {max(arts[run].values()) if arts[run] else 0} in one")
    print("total", out["total"])


def validate():
    import sample66
    labelled = {r["idx"] for r in C.jlines(C.OUT / "sample.jsonl")}
    R = list(C.jlines(C.OUT / "fixes.jsonl"))
    pool = [i for i, r in enumerate(R) if i not in labelled and not decide(r)[0]]
    rng = random.Random(6602)
    take = sorted(rng.sample(pool, min(40, len(pool))))
    rows = []
    for k, i in enumerate(take, 1):
        rows.append(dict(R[i], idx=i, sid=1000 + k, stratum="V_refused", pop=len(pool), weight=1, split="validate"))
    with open(C.OUT / "validate.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    sample66.sheets(src=C.OUT / "validate.jsonl", dst=C.OUT / "vsheets")
    print(len(pool), "refused fixes outside the sample;", len(rows), "drawn")


if __name__ == "__main__":
    {"run": run, "validate": validate}[sys.argv[1]]()

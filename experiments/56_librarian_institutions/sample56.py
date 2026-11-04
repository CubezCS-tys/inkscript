"""Experiment 56, step 5a: the owner's review sample — 30 of the librarian's decisions drawn at random, stratified by
kind, each with its evidence (the printed affiliations, where they sit on the scan for the ink crop, the machine rows,
the catalogue hits), written to out/sample56.json for the Desk's /librarian page.

Strata (seed 56): merges 6 (same_institution), splits 4 (not_same_institution), parent fixes 5 (set_parent), countries
5 (set_country), affiliation fixes 5 (affiliation_institution where the machine linked something else), not an
institution 2, unsure 3.

    python3 sample56.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from decisions56 import latest  # noqa: E402

STRATA = [("merge", 6, lambda d: d["kind"] == "same_institution"),
          ("split", 4, lambda d: d["kind"] == "not_same_institution"),
          ("parent", 5, lambda d: d["kind"] == "set_parent"),
          ("country", 5, lambda d: d["kind"] == "set_country"),
          ("affiliation fix", 5, lambda d: d["kind"] == "affiliation_institution" and d["decision"].get("machine_agrees") is False),
          ("not an institution", 2, lambda d: d["kind"] == "not_an_institution"),
          ("unsure", 3, lambda d: d["kind"] == "unsure")]


def evidence(keys: list, P: dict) -> list:
    out = []
    for k in keys:
        p = P.get(k)
        if not p:
            continue
        ink = p.get("ink") or {}
        out.append(dict(key=k, stem=p["stem"], journal=p["journal"], year=p["year"], author=p["author"]["printed"],
                        printed=p["printed"], parts=p["parts"], byline_anchor=p["author"].get("byline_anchor"),
                        page=ink.get("page"), lines=ink.get("alto_lines") or [], ink_share=ink.get("share"),
                        machine={lvl: dict(inst_id=m["inst_id"], names=m["names"][:2], country=m["country"])
                                 for lvl, m in p["machine"].items()},
                        catalogue=[t for c in p["catalogue"].values() for t in c["thesis"]][:2],
                        same_article=[x["printed"] for x in p["same_article"]][:3]))
        if len(out) >= 4:
            break
    return out


def main():
    P = {json.loads(l)["key"]: json.loads(l) for l in open(OUT / "packets56.jsonl", encoding="utf-8")}
    L = [d for d in latest().values() if d["kind"] != "retired"]
    L.sort(key=lambda d: d["decision_id"])
    rnd = random.Random(56)
    sample = []
    for name, n, pred in STRATA:
        pool = [d for d in L if pred(d)]
        for d in rnd.sample(pool, min(n, len(pool))):
            keys = [k for k in d["evidence_ids"] if k.startswith("aff:")]
            if d["decision"].get("affiliations"):
                keys = d["decision"]["affiliations"] + keys
            if d["kind"] == "same_institution":       # one printed affiliation per machine row first
                rows = set(d["decision"]["machine_rows"])
                first = {}
                for k in keys:
                    m = P.get(k, {}).get("machine", {}).get("org") or {}
                    if m.get("inst_id") in rows:
                        first.setdefault(m["inst_id"], k)
                keys = list(first.values()) + keys
            if d["kind"] == "not_same_institution":
                keys = [ks[0] for ks in d["decision"]["groups"].values()] + keys
            keys = list(dict.fromkeys(keys))
            sample.append(dict(stratum=name, decision_id=d["decision_id"], kind=d["kind"], level=d["level"],
                               question=d.get("question"), decision=d["decision"], reason=d.get("reason"),
                               confidence=d["confidence"], basis=d["basis"], trivial=d["trivial"],
                               printed=d.get("printed"), evidence=evidence(keys, P)))
    (OUT / "sample56.json").write_text(json.dumps(dict(seed=56, n=len(sample), strata=[(s, n) for s, n, _ in STRATA],
                                                       items=sample), ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(sample), "sampled;", {s: sum(1 for x in sample if x["stratum"] == s) for s, _, _ in STRATA})


if __name__ == "__main__":
    main()

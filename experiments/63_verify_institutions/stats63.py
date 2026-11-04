"""Experiment 63, step 5: agreement, precision with 95% intervals, the census count, and the apply rule's numbers.

Reads out/sample63_key.json, out/adjudication63.json, out/openreview63_findings.json, exp 56's decisions (read-only).
Writes out/numbers63.json and prints the tables.

Definitions
- blind agreement: my blind answer = exp 56's (same body / status / country / parent / merge / type).
- precision, lenient: exp 56's decision is not wrong (agree, both acceptable, or exp 56 withheld a link it could have
  made: 'conservative' never makes a false link).
- precision, strict: also counts a wrong secondary field (S107's one country for a two-country statement, S182's
  merge record) as an error.
- intervals: Wilson 95% on the blind sample of the stratum (n drawn); a kind's figure weights its strata by their size.
- census: the blind sample + the open read-through cover all 908; errors found in either are counted per kind.

    python3 stats63.py
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
E56 = HERE.parent / "56_librarian_institutions" / "out"
Z = 1.959964


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + Z * Z / n
    c = p + Z * Z / (2 * n)
    r = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def main():
    key = json.loads((OUT / "sample63_key.json").read_text(encoding="utf-8"))
    adj = json.loads((OUT / "adjudication63.json").read_text(encoding="utf-8"))
    openf = json.loads((OUT / "openreview63_findings.json").read_text(encoding="utf-8"))
    latest = {}
    for line in open(E56 / "decisions56.jsonl", encoding="utf-8"):
        d = json.loads(line)
        latest[d["qkey"]] = d
    S = [d for d in latest.values() if d["kind"] != "retired"]
    pop = defaultdict(int)
    for d in S:
        pop[(d["kind"], d["confidence"])] += 1

    rows = defaultdict(lambda: dict(n=0, agree=0, lenient=0, strict=0, conservative=0, both_ok=0, minor=0,
                                    agree_unexposed=0, n_unexposed=0))
    for sid, a in adj.items():
        r = rows[(a["kind"], a["confidence"])]
        r["n"] += 1
        r["agree"] += a["verdict"] == "agree"
        r["lenient"] += a["verdict"] != "56_wrong"
        r["strict"] += a["verdict"] not in ("56_wrong", "56_minor_error")
        r["conservative"] += a["verdict"] == "56_conservative"
        r["both_ok"] += a["verdict"] == "both_ok"
        r["minor"] += a["verdict"] == "56_minor_error"
        if not a["exposed"]:
            r["n_unexposed"] += 1
            r["agree_unexposed"] += a["verdict"] == "agree"

    open_err = defaultdict(int)
    for e in openf["errors"]:
        open_err[(e["kind"], e["confidence"])] += 1

    table = []
    for (kind, conf), N in sorted(pop.items()):
        r = rows.get((kind, conf), dict(n=0, agree=0, lenient=0, strict=0, conservative=0, both_ok=0, minor=0,
                                         agree_unexposed=0, n_unexposed=0))
        lo_l, hi_l = wilson(r["lenient"], r["n"])
        lo_s, hi_s = wilson(r["strict"], r["n"])
        census_err = (r["n"] - r["strict"]) + open_err.get((kind, conf), 0)
        table.append(dict(kind=kind, confidence=conf, population=N, sampled=r["n"], census=r["n"] == N,
                          blind_agree=r["agree"], agree_rate=r["agree"] / r["n"] if r["n"] else None,
                          agree_unexposed=f"{r['agree_unexposed']}/{r['n_unexposed']}",
                          conservative=r["conservative"], both_ok=r["both_ok"], minor=r["minor"],
                          precision_lenient=r["lenient"] / r["n"] if r["n"] else None, ci_lenient=[lo_l, hi_l],
                          precision_strict=r["strict"] / r["n"] if r["n"] else None, ci_strict=[lo_s, hi_s],
                          open_review_errors=open_err.get((kind, conf), 0), census_errors=census_err,
                          census_precision_strict=1 - census_err / N))
    # per kind, strata weighted by size
    kinds = defaultdict(list)
    for t in table:
        kinds[t["kind"]].append(t)
    per_kind = []
    for kind, ts in kinds.items():
        N = sum(t["population"] for t in ts)
        n = sum(t["sampled"] for t in ts)
        ag = sum(t["blind_agree"] for t in ts)
        w_l = sum(t["population"] * (t["precision_lenient"] or 0) for t in ts if t["sampled"]) / \
            sum(t["population"] for t in ts if t["sampled"])
        w_s = sum(t["population"] * (t["precision_strict"] or 0) for t in ts if t["sampled"]) / \
            sum(t["population"] for t in ts if t["sampled"])
        # conservative interval: the size-weighted mean of the strata's Wilson lower bounds
        lo = sum(t["population"] * t["ci_strict"][0] for t in ts if t["sampled"]) / \
            sum(t["population"] for t in ts if t["sampled"])
        ce = sum(t["census_errors"] for t in ts)
        per_kind.append(dict(kind=kind, population=N, sampled=n, blind_agree=ag, agree_rate=ag / n,
                             precision_lenient=w_l, precision_strict=w_s, ci_strict_low_weighted=lo,
                             census_errors=ce, census_precision_strict=1 - ce / N))
    pooled_n = sum(t["sampled"] for t in table)
    pooled_err = sum(t["sampled"] - round((t["precision_strict"] or 0) * t["sampled"]) for t in table)
    res = dict(standing=len(S), sampled=pooled_n, strata=table, per_kind=per_kind,
               pooled_blind=dict(n=pooled_n, strict_errors=pooled_err, ci=wilson(pooled_n - pooled_err, pooled_n)),
               census=dict(errors=sum(t["census_errors"] for t in table),
                           precision=1 - sum(t["census_errors"] for t in table) / len(S)))
    # by basis (census), and blind agreement overall / without exposed items
    basis_pop = defaultdict(int)
    for d in S:
        basis_pop["rule" if d["basis"] == "rule" else "judgement/world/context/catalogue"] += 1
    basis_err = defaultdict(int)
    for a in adj.values():
        if a["verdict"] in ("56_wrong", "56_minor_error"):
            basis_err["rule" if a["basis"] == "rule" else "judgement/world/context/catalogue"] += 1
    for e in openf["errors"]:
        basis_err["rule" if e["basis"] == "rule" else "judgement/world/context/catalogue"] += 1
    res["by_basis"] = {b: dict(population=n, census_errors=basis_err[b], precision=1 - basis_err[b] / n)
                       for b, n in basis_pop.items()}
    ua = [a for a in adj.values() if not a["exposed"]]
    res["blind_agreement"] = dict(all=f"{sum(a['blind_agree'] for a in adj.values())}/{len(adj)}",
                                  unexposed=f"{sum(a['blind_agree'] for a in ua)}/{len(ua)}",
                                  exposed=f"{sum(a['blind_agree'] for a in adj.values() if a['exposed'])}/"
                                          f"{sum(1 for a in adj.values() if a['exposed'])}")
    print(res["by_basis"], res["blind_agreement"])
    (OUT / "numbers63.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    f = lambda x: "  -  " if x is None else f"{100 * x:5.1f}"
    print(f"{'kind':24s} {'conf':6s} {'N':>4s} {'n':>4s} {'agree':>6s} {'prec(strict)':>12s} {'95% CI':>13s} "
          f"{'cons':>4s} {'minor':>5s} {'open err':>8s} {'census':>7s}")
    for t in table:
        print(f"{t['kind']:24s} {t['confidence']:6s} {t['population']:4d} {t['sampled']:4d} "
              f"{f(t['agree_rate']):>6s} {f(t['precision_strict']):>12s} "
              f"{f(t['ci_strict'][0])}-{f(t['ci_strict'][1])} {t['conservative']:4d} {t['minor']:5d} "
              f"{t['open_review_errors']:8d} {f(t['census_precision_strict']):>7s}")
    print()
    for k in per_kind:
        print(f"{k['kind']:24s} N={k['population']:4d} n={k['sampled']:3d} agree={f(k['agree_rate'])} "
              f"strict={f(k['precision_strict'])} (weighted low {f(k['ci_strict_low_weighted'])}) "
              f"census errors={k['census_errors']} -> {f(k['census_precision_strict'])}")
    print("pooled blind", res["pooled_blind"], "census", res["census"])


if __name__ == "__main__":
    main()

"""Experiment 79: does the thickness feature help the loop letters?  Compares readers run for run.

    python loops79.py p3t p3n [p3tp]      (reads out/<name>_results.json and out/res/<name>_pred_real.jsonl)

Synthetic: train79b's loop_letters (per loop letter: occurrences, share read wrong, what it became) on clean,
heavy and spread reconstructions.  Real: the same measure on the held-out lines with the owner's truth (alignment of
truth and reading, no_punct).  Writes out/res/loops_<names>.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rapidfuzz.distance import Levenshtein

from analyse79 import np_

HERE = Path(__file__).resolve().parent
LOOP = "وفقمهةصضطظعغ"


def real_loops(f):
    occ, wrong, as_ = Counter(), Counter(), defaultdict(Counter)
    for l in open(f, encoding="utf-8"):
        r = json.loads(l)
        if not r.get("truth"):
            continue
        a, b = np_(r["truth"]), np_(r["pred"])
        for ch in a:
            if ch in LOOP:
                occ[ch] += 1
        for op in Levenshtein.editops(a, b):
            if op.tag in ("replace", "delete") and a[op.src_pos] in LOOP:
                wrong[a[op.src_pos]] += 1
                as_[a[op.src_pos]][b[op.dest_pos] if op.tag == "replace" else "∅"] += 1
    return {ch: dict(n=occ[ch], err=round(wrong[ch] / max(1, occ[ch]), 3), top=as_[ch].most_common(2)) for ch in LOOP if occ[ch]}


def main(names):
    out = {}
    for n in names:
        res = json.loads((HERE / "out" / f"{n}_results.json").read_text())
        out[n] = {k: res["loop_letters"].get(k, {}) for k in ("syn_rclean", "syn_rdmg_heavy", "syn_rdmg_spread")}
        f = HERE / "out/res" / f"{n}_pred_real.jsonl"
        if f.exists():
            out[n]["real"] = real_loops(f)
    (HERE / "out/res" / f"loops_{'_'.join(names)}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for k in ("syn_rclean", "syn_rdmg_heavy", "syn_rdmg_spread", "real"):
        print(k)
        for ch in LOOP:
            row = []
            for n in names:
                d = out[n].get(k, {}).get(ch)
                row.append(f"{n} {d['err']:.3f} (n {d['n']}, as {d['top'][0][0] if d['top'] else '-'})" if d else f"{n} -")
            print("  ", ch, " | ".join(row))
        tot = {n: (sum(d["err"] * d["n"] for d in out[n].get(k, {}).values()), sum(d["n"] for d in out[n].get(k, {}).values())) for n in names}
        print("   all loop letters:", {n: round(a / max(1, b), 3) for n, (a, b) in tot.items()})


if __name__ == "__main__":
    main(sys.argv[1:])

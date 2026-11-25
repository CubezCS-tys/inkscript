#!/usr/bin/env python3
"""The repair's failed bar, checked against a blind reader instead of Azure's labels (lead, 2026-11-25).

out/blind_repair/disputes.jsonl: the 141 unchanged Arabic + Latin lines of the DEV-MIXED test half where M and the
repaired reader (R ckpt-150) differ.  One blind reader typed each from the crop (settle/R1/readings.jsonl).
Run:  nice -n 19 ../../.venv/bin/python repaircheck103.py
"""
import json, sys, unicodedata
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pool103 import fold  # noqa: E402

jl = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def nop(s):
    """folded, punctuation and spaces ignored: the experiment's usual space"""
    return "".join(c for c in fold(s) if not unicodedata.category(c).startswith(("P", "Z")) and not c.isspace())


def lev(a, b):
    p = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        q = [i]
        for j, y in enumerate(b, 1):
            q.append(min(p[j] + 1, q[-1] + 1, p[j - 1] + (x != y)))
        p = q
    return p[-1]


def main():
    D = {d["id"]: d for d in jl(HERE / "out/blind_repair/disputes.jsonl")}
    W = {d["id"]: d["witnesses"] for d in jl(HERE / "out/b/private/repair_witnesses.jsonl")}
    T = {d["id"]: d for d in jl(HERE / "out/blind_repair/settle/R1/readings.jsonl")}
    tot, right, near, n, N = dict(M=0, R150=0, azure=0), dict(M=0, R150=0, azure=0), dict(M=0, R150=0, tie=0), 0, 0
    for k, d in D.items():
        t = T[k]
        if t.get("unsure") or t.get("unreadable"):
            continue
        src = {w: d["candidates"][int(c)]["text"] for c, ws in W[k].items() for w in ws}
        tt = nop(t["printed"]); n += 1; N += len(tt)
        e = {w: lev(nop(src[w]), tt) for w in src}
        for w in e:
            tot[w] += e[w]; right[w] += e[w] == 0
        near["M" if e["M"] < e["R150"] else "R150" if e["R150"] < e["M"] else "tie"] += 1
    out = dict(lines=n, truth_letters=N, letters_wrong_pct={w: round(100 * tot[w] / N, 2) for w in tot},
               lines_fully_right=right, nearer_the_truth=near)
    (HERE / "out/scores").mkdir(parents=True, exist_ok=True)
    (HERE / "out/scores/repair_blind.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

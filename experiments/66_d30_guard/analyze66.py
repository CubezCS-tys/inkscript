"""Experiment 66: the hand labels against the features; rates per stratum (weighted to all 24,528 fixes) and the
guard's variants scored on the tune and test halves (split by article).

    analyze66.py            prints the tables; out/analysis.json
Labels (out/labels.tsv): G good fix (Azure misread) / B bad fix (the print was right) / M the print's own misprint
overwritten (should have been a sic) / U unclear (left out of every rate).
"""
from __future__ import annotations

import json
import math
import random
import re
from collections import Counter, defaultdict

import common66 as C

C.e43_path()
import d30guard43 as G  # noqa: E402

AR_LETTER = {"dots", "ar_swap", "ar_indel"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def load():
    lab = {}
    for ln in open(C.OUT / "labels.tsv", encoding="utf-8"):
        sid, l, note = ln.rstrip("\n").split("\t", 2)
        lab[int(sid)] = (l, note)
    S = []
    for r in C.jlines(C.OUT / "sample.jsonl"):
        r["label"], r["note"] = lab[r["sid"]]
        r["_f"] = feats(r)
        S.append(r)
    return S


def real(ks):
    ks = [k for k in ks if k is not None]
    return None if not ks else all(ks)


def feats(r):
    cs = [x for x in r["confs"] if x is not None]
    return dict(cls=G.edit_class(r["frm"], r["to"]), conf=min(cs) if cs else None, from_real=real(r["from_known"]),
                to_real=real(r["to_known"]), al=G.al_prefix(r["frm"], r["to"]), added=G.adds_tokens(r["frm"], r["to"]))


def guard_rule(f):
    keep, _ = G.decide(dict(cls=f["cls"], conf_min=f["conf"], from_real=f["from_real"], to_real=f["to_real"],
                            al=f["al"], added=f["added"], code=False))
    return not keep


VARIANTS = {
    "GUARD d30guard43.decide": guard_rule,
    # name: refuse(f) -> bool
    "V0 none": lambda f: False,
    "V1 Arabic letter edit, Azure >= 0.95": lambda f: f["cls"] in AR_LETTER and (f["conf"] or 0) >= 0.95,
    "V2 = V1, not al-/l- prefix, not added words": lambda f: f["cls"] in AR_LETTER and (f["conf"] or 0) >= 0.95
    and not f["al"] and not f["added"],
    "V3 = V2 and the fix's word is a known word": lambda f: f["cls"] in AR_LETTER and (f["conf"] or 0) >= 0.95
    and not f["al"] and not f["added"] and f["to_real"] is True,
    "V4 = V3 and Azure's word is not a known word": lambda f: f["cls"] in AR_LETTER and (f["conf"] or 0) >= 0.95
    and not f["al"] and not f["added"] and f["to_real"] is True and f["from_real"] is False,
    "V5 = V2 and Azure's word is a known word": lambda f: f["cls"] in AR_LETTER and (f["conf"] or 0) >= 0.95
    and not f["al"] and not f["added"] and f["from_real"] is True,
    "V6 = V3 at Azure >= 0.97": lambda f: f["cls"] in AR_LETTER and (f["conf"] or 0) >= 0.97
    and not f["al"] and not f["added"] and f["to_real"] is True,
    "V7 = V3 at Azure >= 0.90": lambda f: f["cls"] in AR_LETTER and (f["conf"] or 0) >= 0.90
    and not f["al"] and not f["added"] and f["to_real"] is True,
}


def score(rows, refuse, weighted=True):
    """Estimated counts over all fixes (each sampled fix stands for `weight` fixes of its stratum)."""
    t = Counter()
    for r in rows:
        if r["label"] == "U":
            continue
        w = r["weight"] if weighted else 1
        bad = r["label"] in "BM"
        ref = refuse(r["_f"])
        t["bad"] += w * bad
        t["good"] += w * (not bad)
        t["bad_blocked"] += w * (bad and ref)
        t["good_blocked"] += w * ((not bad) and ref)
        t["B"] += w * (r["label"] == "B")
        t["M"] += w * (r["label"] == "M")
        t["B_blocked"] += w * (r["label"] == "B" and ref)
        t["M_blocked"] += w * (r["label"] == "M" and ref)
    return t


def boot(rows, refuse, n=2000, seed=66):
    """Stratified bootstrap of the weighted recall / good-blocked rate / precision."""
    rng = random.Random(seed)
    by = defaultdict(list)
    for r in rows:
        if r["label"] != "U":
            by[r["stratum"]].append(r)
    rec, gb, pr = [], [], []
    for _ in range(n):
        rs = []
        for s, v in by.items():
            rs += [rng.choice(v) for _ in v]
        t = score(rs, refuse)
        if t["bad"]:
            rec.append(t["bad_blocked"] / t["bad"])
        gb.append(t["good_blocked"] / t["good"] if t["good"] else 0)
        if t["bad_blocked"] + t["good_blocked"]:
            pr.append(t["bad_blocked"] / (t["bad_blocked"] + t["good_blocked"]))
    q = lambda xs: (round(sorted(xs)[int(.025 * len(xs))], 3), round(sorted(xs)[int(.975 * len(xs)) - 1], 3)) if xs else None  # noqa
    return dict(recall_ci=q(rec), good_blocked_ci=q(gb), precision_ci=q(pr))


def main():
    S = load()
    out = {}
    lab = Counter(r["label"] for r in S)
    print("labels:", dict(lab))
    # per stratum
    st = defaultdict(Counter)
    pop = {}
    for r in S:
        st[r["stratum"]][r["label"]] += 1
        pop[r["stratum"]] = r["pop"]
    print("\nstratum (fixes in it): G / B / M / U   bad share (B+M) of the judged, 95% Wilson")
    est = Counter()
    per = {}
    for s in sorted(st):
        c = st[s]
        n = c["G"] + c["B"] + c["M"]
        p, lo, hi = wilson(c["B"] + c["M"], n)
        pb, pm = c["B"] / n, c["M"] / n
        est["B"] += pb * pop[s]
        est["M"] += pm * pop[s]
        est["fixes"] += pop[s]
        per[s] = dict(pop=pop[s], G=c["G"], B=c["B"], M=c["M"], U=c["U"], bad=round(p, 3), lo=round(lo, 3), hi=round(hi, 3))
        print(f"  {s:28} ({pop[s]:>6})  {c['G']:>3} / {c['B']:>2} / {c['M']:>2} / {c['U']:>2}   "
              f"{p:.0%} [{lo:.0%}, {hi:.0%}]")
    allfix = sum(1 for _ in C.jlines(C.OUT / "fixes.jsonl"))
    print(f"  estimated over the {est['fixes']:.0f} stratified fixes (of {allfix}): bad B ≈ {est['B']:.0f}, "
          f"misprints overwritten M ≈ {est['M']:.0f}")
    out["strata"] = per
    out["estimate"] = dict(B=round(est["B"]), M=round(est["M"]), fixes=est["fixes"], all=allfix)
    print("\nvariants (weighted to all fixes; tune / test halves split by article):")
    out["variants"] = {}
    for name, f in VARIANTS.items():
        row = {}
        for part in ("tune", "test", "all"):
            rows = [r for r in S if part == "all" or r["split"] == part]
            t = score(rows, f)
            u = score(rows, f, weighted=False)
            rec = t["bad_blocked"] / t["bad"] if t["bad"] else float("nan")
            gb = t["good_blocked"] / t["good"] if t["good"] else float("nan")
            prec = t["bad_blocked"] / (t["bad_blocked"] + t["good_blocked"]) if t["bad_blocked"] + t["good_blocked"] else float("nan")
            row[part] = dict(recall=round(rec, 3), good_blocked=round(gb, 4), precision=round(prec, 3),
                             unweighted=dict(bad=u["bad"], bad_blocked=u["bad_blocked"], B_blocked=u["B_blocked"],
                                             M_blocked=u["M_blocked"], good=u["good"], good_blocked=u["good_blocked"]),
                             est_blocked_bad=round(t["bad_blocked"]), est_blocked_good=round(t["good_blocked"]))
        row["test_ci"] = boot([r for r in S if r["split"] == "test"], f)
        row["all_ci"] = boot(S, f)
        out["variants"][name] = row
        a, te = row["all"], row["test"]
        print(f"  {name:48} all: blocks {a['recall']:.0%} of bad (est {a['est_blocked_bad']}), "
              f"{a['good_blocked']:.1%} of good (est {a['est_blocked_good']}), precision {a['precision']:.0%} | "
              f"test: {te['recall']:.0%} / {te['good_blocked']:.1%} / {te['precision']:.0%}  "
              f"unweighted test {te['unweighted']}  CI(all) {row['all_ci']}")
    C.jdump(C.OUT / "analysis.json", out)


if __name__ == "__main__":
    main()

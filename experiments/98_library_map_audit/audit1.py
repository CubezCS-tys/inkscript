#!/usr/bin/env python3
"""Audit step 1 and 6: recompute the library map's headline figures with our own code (read-only on their files)."""
import json, sys, collections, math
L = "/home/appuser/ai-search-eval-archive/2026-11-23-library-map"
def load(p): return [json.loads(l) for l in open(p, encoding="utf-8")]
def score(set_path, ref_path, lab_path, name):
    S = {r["doc_id"]: r for r in load(set_path)}
    R = {r["doc_id"]: r for r in load(ref_path)}
    Lb = {}
    dup = 0
    for r in load(lab_path):
        k = r.get("doc_id") or r.get("id")
        dup += k in Lb
        Lb[k] = r
    print(f"== {name}: set {len(S)} ref {len(R)} labels {len(Lb)} dup labels {dup}; in set not ref {len(set(S)-set(R))}; in set not labelled {len(set(S)-set(Lb))}; labelled not in set {len(set(Lb)-set(S))}")
    one = next(iter(Lb.values())); print("   label keys:", list(one.keys())[:22])
    print("   status values:", collections.Counter(r.get("status") for r in Lb.values()).most_common(8))
    rows = []
    for k, s in S.items():
        ref, lab = R.get(k), Lb.get(k)
        w = float(s.get("weight") or 1)
        g = s.get("group")
        classified = bool(lab) and lab.get("status") == "classified"
        unclear_ref = bool(ref and ref.get("unclear"))
        acc_set = set(ref.get("acceptable_l1") or []) if ref else set()
        strict = ref.get("strict_primary_l1") if ref else None
        p = lab.get("primary_l1") if lab else None
        rows.append(dict(k=k, w=w, g=g, classified=classified, unclear_ref=unclear_ref, ok=classified and p in acc_set, strict_ok=classified and p == strict, nacc=len(acc_set), p=p))
    def rep(sel, label):
        sel = list(sel)
        if not sel: return
        for wname, wf in (("weighted", lambda r: r["w"]), ("unweighted", lambda r: 1.0)):
            tot = sum(wf(r) for r in sel)
            cls = [r for r in sel if r["classified"]]
            cov = sum(wf(r) for r in cls) / tot
            # accuracy among classified, two conventions for records whose reference is 'unclear'
            den_all = sum(wf(r) for r in cls)
            acc_all = sum(wf(r) for r in cls if r["ok"]) / den_all if den_all else float("nan")
            strict_all = sum(wf(r) for r in cls if r["strict_ok"]) / den_all if den_all else float("nan")
            cls2 = [r for r in cls if not r["unclear_ref"]]
            den2 = sum(wf(r) for r in cls2)
            acc2 = sum(wf(r) for r in cls2 if r["ok"]) / den2 if den2 else float("nan")
            print(f"   {label:28s} {wname:10s} n={len(sel):5d} classified={len(cls):5d} coverage={cov:.3f} acceptable={acc_all:.3f} strict={strict_all:.3f} | excluding ref-unclear: acceptable={acc2:.3f} (n={len(cls2)})")
    rep(rows, "all")
    for g in sorted({r["g"] for r in rows}): rep([r for r in rows if r["g"] == g], str(g))
    print("   reference: unclear", sum(r["unclear_ref"] for r in rows), "| acceptable-set size mean %.2f, share with exactly one %.2f" % (sum(r["nacc"] for r in rows)/len(rows), sum(1 for r in rows if r["nacc"]==1)/len(rows)), "| size dist", sorted(collections.Counter(r["nacc"] for r in rows).items()))
    return rows
score(f"{L}/pilot/sets/test.jsonl", f"{L}/pilot/reference/test_SEALED/test_reference.jsonl", f"{L}/pilot/runs/test_frozen/labels.jsonl", "TEST (frozen run)")
import glob
can = sorted(glob.glob(f"{L}/runs/full-v0.1/canary/labels_canary_*.jsonl"))
print(can)
for c in can[-2:]:
    score(f"{L}/pilot/sets/dev.jsonl", f"{L}/pilot/reference/dev_reference.jsonl", c, "DEV canary " + c.split("_")[-1])

"""Experiment 103: B1 / B2 after the blind key.  The STRICT scoring is score103.py b1 / b2 (pre-registered; it decides
the bars).  This file adds, clearly labelled "added after seeing the key, not pre-registered":

  folded   the same B1 and B2 tables in the experiment's usual space: score97.r1_fold + no_punct (digit sets alike,
           vowel marks and tatweel removed, punctuation ignored, whitespace collapsed).
           B1: the gross / correct call made in that space (pool103.gross on folded strings);
           B2: lines where one reading is STRICTLY nearer the truth than the other (character Levenshtein in that
               space; ties out); each rule scored by how often it picks the nearer one.
  breakdown what the 471 B1 candidates turned out to be (real gross error of the reader, reader right and Azure wrong,
           both wrong, unreadable crop), and on the unreadable crops what the reader wrote and whether the writer and
           the confidence flag them.

    nice -n 19 ../81_heldout_scale/out/venv/bin/python analyse103.py      -> out/scores/b_after_key.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(E / "97_extraction_evals"))
import score97  # noqa: E402
import score103 as S  # noqa: E402
from pool103 import gross  # noqa: E402

M_AD = "/work/weights/M/ckpt-3125"
OUT = HERE / "out/scores"


def fnp(s):
    return score97.no_punct(score97.r1_fold(" ".join((s or "").split())))


def lev(a, b):
    from common97 import lev as L
    return L(a, b)


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def load():
    T = S.truths()
    rows = jl(HERE / "out/judge/check103.jsonl")
    ws = S.writer_score_87(rows)
    for r, w in zip(rows, ws):
        r["w"] = float(w)
    read = {d["key"]: d for d in jl(HERE / "out/eval/heldout_M.jsonl") if d["adapter"] == M_AD}
    force = {(d["key"], d["cid"]): d for d in jl(HERE / "out/eval/force_b.jsonl")}
    held = {d["key"]: d for d in jl(HERE / "out/sets/heldout.jsonl")}
    priv = {d["id"]: d for d in jl(HERE / "out/b/private/witnesses.jsonl")}
    settle = {w: {d["id"]: d for d in jl(HERE / f"out/b/settle/{w}/readings.jsonl")} for w in ("A", "B", "C")}
    return T, rows, read, force, held, priv, settle


def unreadable_ids(settle):
    A, B, C = settle["A"], settle["B"], settle["C"]
    out = set()
    for k in A:
        if A[k].get("unreadable") and B[k].get("unreadable"):
            out.add(k)
        elif k in C and C[k].get("unreadable"):
            out.add(k)
    return out


def b1_folded(T, rows, read):
    pos, neg = [], []
    for r in rows:
        k = r["key"]
        if r["kind"] == "real_reader" and k in T:
            (pos if gross(fnp(T[k]), fnp(r["text"])) else neg).append(r)
        elif r["kind"] == "correct" and (k not in T or fnp(T[k]) == fnp(r["text"])):
            neg.append(r)
    R = pos + neg
    y = np.array([1] * len(pos) + [0] * len(neg))
    conf = {"-lp_min": [-(read[r["key"]]["lp_min"] or 0) for r in R], "-lp_mean": [-(read[r["key"]]["lp_mean"] or 0) for r in R]}
    return S.b1_bars([r["w"] for r in R], conf, y, [r["page"] for r in R])


def b2_folded(T, read, force):
    G = {g["key"]: g for g in jl(HERE / "out/b/contrast_groups.jsonl")}
    C = {r["key"]: r for r in jl(HERE / "out/judge/contrast_j.jsonl")}
    L, c = [], Counter()
    for k, g in G.items():
        if k not in T:
            c["no settled truth"] += 1
            continue
        t = fnp(T[k])
        dr, da = lev(fnp(g["cands"][0]), t), lev(fnp(g["cands"][1]), t)
        if dr == da:
            c["tie: both equally near the truth (incl. both equal to it)"] += 1
            continue
        wp, ch = (S.contrast_pick(C[k], default=0) if k in C else (None, None))
        fr, fa = force[(k, "reader")], force[(k, "azure")]
        L.append(dict(page=g["page"], truth_is=int(da < dr), writer_pick=wp, chamfer=ch, lp_mean=[fr["lp_mean"], fa["lp_mean"]],
                      lp_min_reader=read[k]["lp_min"] or 0.0, key=k))
    res = S.b2_bars(L)
    res["left_out"] = dict(c)
    return res, L


def breakdown(T, rows, read, held, priv, settle, thr_w, thr_c):
    unread = unreadable_ids(settle)
    b1ids = [k for k, p in priv.items() if p["set"] == "b1"]
    scored = {r["key"]: r for r in rows if r["kind"] == "real_reader"}
    c = Counter(candidates=len(b1ids))
    sub = []
    for k in b1ids:
        rd, az = read[k]["text"], held[k]["label"]
        if k in unread:
            c["unreadable crop (both blind readers, or C)"] += 1
            w = scored.get(k)
            sub.append(dict(key=k, reader=rd, azure=az, writer_scored=w is not None,
                            writer_flag=(w["w"] > thr_w) if w else None,
                            conf_flag=(-read[k]["lp_mean"]) > thr_c, lp_mean=read[k]["lp_mean"]))
            continue
        if k not in T:
            c["no settled truth"] += 1
            continue
        t = T[k]
        if gross(t, rd):
            c["real gross error of the reader (strict)"] += 1
            if " ".join(az.split()) == t:
                c["  ... and Azure exactly right"] += 1
        elif " ".join(rd.split()) == t:
            c["reader exactly right (Azure wrong)"] += 1
        else:
            c["reader near the truth but not exact (Azure far)"] += 1
        if gross(fnp(t), fnp(rd)):
            c["real gross error of the reader (folded)"] += 1
    c["writer could score (page had a style)"] = sum(1 for k in b1ids if k in scored)
    us = [x for x in sub if x["writer_scored"]]
    c["unreadable: writer scored"] = len(us)
    c["unreadable: writer flags (99%-keep threshold)"] = sum(1 for x in us if x["writer_flag"])
    c["unreadable: confidence flags (its 99%-keep threshold, -lp_mean)"] = sum(1 for x in sub if x["conf_flag"])
    c["unreadable: confidence flags, among the writer-scored"] = sum(1 for x in us if x["conf_flag"])
    return dict(c), sub


def main():
    T, rows, read, force, held, priv, settle = load()
    strict_b1 = json.loads((OUT / "b1.json").read_text())
    strict_b2 = json.loads((OUT / "b2.json").read_text())
    f1 = b1_folded(T, rows, read)
    f2, L2 = b2_folded(T, read, force)
    thr_c = strict_b1["confidence"]["-lp_mean"]["threshold"]
    bd, sub = breakdown(T, rows, read, held, priv, settle, strict_b1["writer_threshold"], thr_c)
    out = dict(note="folded tables: added after seeing the key, not pre-registered; the strict ones decide the bars",
               b1_strict={k: strict_b1[k] for k in ("n_real", "n_correct", "writer_auc", "writer_catch", "confidence",
                                                     "best_confidence", "gain_points", "writer_auc_ci", "gain_ci", "B1",
                                                     "writer_plus_confidence_cv", "chamfer_only")},
               b1_folded={k: f1[k] for k in ("n_real", "n_correct", "writer_auc", "writer_catch", "confidence",
                                             "best_confidence", "gain_points", "writer_auc_ci", "gain_ci", "B1")},
               b2_strict=strict_b2, b2_folded=f2, b1_breakdown=bd, unreadable_lines=sub)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "b_after_key.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "unreadable_lines"}, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()

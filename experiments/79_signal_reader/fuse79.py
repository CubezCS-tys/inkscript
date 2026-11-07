"""Experiment 79, rung 2: fusion, the warning, do-no-harm (per era and per measured ink type) and calibration.

    python fuse79.py out/fuse/<run>      (reads dev.jsonl and test.jsonl from score79.py; writes summary.json there)

Fusion never invents a reading: it picks among experiment 77's own N best (the image reader's candidates) by
    score = s77 + lambda * s_other        (CTC log-likelihoods; a candidate the other reader cannot score keeps s77
                                           plus the other reader's worst score on that line)
with lambda chosen on the dev split (Azure / v2 labels, held-in articles) to minimise line CER.  Two partners:
the signal reader (the second SENSE) and experiment 78's image reader (the CONTROL: a second pair of eyes).
Test: experiment 77's held-out pages; lines with the owner's truth (yardstick map); CER under no_punct.
Do no harm: fused - image CER per era and per ink bucket, with a 95% bootstrap over pages.
Warning on experiment 77's chosen line (target: it differs from the truth, no_punct):
  sig_dis  = edit distance(greedy image, greedy signal) / length;      sig_ll = -s_sig(image line) / length;
  ctl_conf = 1 - img77's lowest frame confidence;  ctl_dis = edit(greedy 77, greedy 78) / length;
  ctl_ll   = -s78(image line) / length.
Reported: PR-AUC, and precision / recall when the top 10% of lines are flagged.
Ink buckets (measured from each line's signal; thresholds = terciles on dev): thin/crisp, even/medium, heavy/spread/broken
(median thickness x blob share x pieces per letter).
"""
from __future__ import annotations

import json
import random
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
from rapidfuzz.distance import Levenshtein

HERE = Path(__file__).resolve().parent
_P = re.compile(r"[^\w\s]|_", re.UNICODE)
_W = re.compile(r"\s+")


def np_(s):
    return _W.sub(" ", _P.sub(" ", unicodedata.normalize("NFC", s or ""))).strip()


def load(f):
    return [json.loads(l) for l in open(f, encoding="utf-8")]


def pick(r, part, lam):
    s77 = np.array([x if x is not None else -1e9 for x in r["s77"]])
    o = r.get(part)
    if not o or lam == 0:
        return r["cands"][int(np.argmax(s77))]
    ok = [x for x in o if x is not None]
    if not ok:
        return r["cands"][int(np.argmax(s77))]
    worst = min(ok)
    so = np.array([x if x is not None else worst for x in o])
    return r["cands"][int(np.argmax(s77 + lam * so))]


def pick3(r, l78, lsig):
    """77 + 78 + signal: the image reader's candidates scored by all three readers."""
    s77 = np.array([x if x is not None else -1e9 for x in r["s77"]])
    tot = s77.copy()
    for part, lam in (("s78", l78), ("ssig", lsig)):
        o = r.get(part)
        if not o or lam == 0:
            continue
        ok = [x for x in o if x is not None]
        if not ok:
            continue
        tot = tot + lam * np.array([x if x is not None else min(ok) for x in o])
    return r["cands"][int(np.argmax(tot))]


def cer_lines(R, ref, choose):
    e = n = 0
    for r in R:
        t = np_(r[ref])
        if not t:
            continue
        e += Levenshtein.distance(np_(choose(r)), t)
        n += len(t)
    return 100 * e / max(1, n)


def prauc(scores, y):
    o = np.argsort(-np.asarray(scores))
    y = np.asarray(y)[o]
    tp = np.cumsum(y)
    prec = tp / np.arange(1, len(y) + 1)
    return float((prec * y).sum() / max(1, y.sum()))


def at_rate(scores, y, rate=0.10):
    o = np.argsort(-np.asarray(scores))
    k = max(1, int(round(rate * len(o))))
    y = np.asarray(y)
    hit = y[o[:k]].sum()
    return dict(flagged=k, precision=round(float(hit / k), 3), recall=round(float(hit / max(1, y.sum())), 3))


def ink_features(keys, sig_npz):
    z = np.load(sig_npz)
    out = {}
    for k in keys:
        if k in z.files:
            F = z[k].astype(np.float32)
            out[k] = (float(np.median(F[:, 11])), float(F[:, 12].mean()), float(F[:, 7].sum()))
    return out


def main(d):
    d = Path(d)
    dev, test = load(d / "dev.jsonl"), load(d / "test.jsonl")
    # lambda on dev (labels = Azure / v2)
    grid = [0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5]
    lam = {}
    for part in ("ssig", "s78"):
        res = {l: cer_lines(dev, "label", lambda r, l=l: pick(r, part, l)) for l in grid}
        lam[part] = min(res, key=res.get)
        print("dev", part, {k: round(v, 3) for k, v in res.items()}, "-> lambda", lam[part])
    res3 = {(a_, b_): cer_lines(dev, "label", lambda r, a_=a_, b_=b_: pick3(r, a_, b_))
            for a_ in (0.5, 1.0, 1.5) for b_ in (0, 0.05, 0.1, 0.2, 0.3)}
    lam["three"] = min(res3, key=res3.get)
    print("dev 77+78+signal", {f"{k[0]}/{k[1]}": round(v, 3) for k, v in res3.items()}, "->", lam["three"])
    # test lines with truth, eras, ink
    pages = json.loads((HERE.parent / "77_scratch_reader/out/test/pages.json").read_text(encoding="utf-8"))
    truth, era, page_of = {}, {}, {}
    for P in pages:
        dec = P.get("decade")
        e = "modern" if dec == "2000s" else ("pre-1960" if dec == "pre-1960" else ("1960-1999" if dec else "?"))
        gp = {int(k): v for k, v in (P.get("gold_pos") or {}).items()}
        for r in P["lines"]:
            if P["set"] == "yardstick" and r["i"] in gp and P.get("truth"):
                truth[r["key"]] = P["truth"][gp[r["i"]]]
                era[r["key"]] = e
                page_of[r["key"]] = P["page_id"]
    T = [dict(r, truth=truth[r["key"]], era=era[r["key"]], page=page_of[r["key"]]) for r in test if r["key"] in truth]
    ink = ink_features([r["key"] for r in T], HERE / "out/realtest/signals.npz")
    feats = np.array([ink.get(r["key"], (1, 0, 0)) for r in T])
    th_q = np.quantile(feats[:, 0], [1 / 3, 2 / 3])
    for r, f in zip(T, feats):
        heavy = f[0] >= th_q[1] or f[1] >= 0.02
        thin = f[0] <= th_q[0] and f[1] < 0.005
        r["ink"] = "heavy/spread" if heavy else ("thin/crisp" if thin else "even/medium")
    readers = {"image77": lambda r: r["g77"], "image78": lambda r: r["g78"] or "", "signal": lambda r: r["gsig"],
               "fused_signal": lambda r: pick(r, "ssig", lam["ssig"]), "fused_image78": lambda r: pick(r, "s78", lam["s78"]),
               "fused_78_and_signal": lambda r: pick3(r, *lam["three"])}

    def table(R):
        return {k: round(cer_lines(R, "truth", f), 3) for k, f in readers.items()}

    out = dict(lambda_={k: list(v) if isinstance(v, tuple) else v for k, v in lam.items()}, lines=len(T), all=table(T))
    rng = random.Random(79)
    for split in ("era", "ink"):
        out[split] = {}
        for b in sorted({r[split] for r in T}):
            R = [r for r in T if r[split] == b]
            row = table(R)
            pg = sorted({r["page"] for r in R})
            diffs = defaultdict(list)
            for _ in range(1000):
                S = [r for p in [rng.choice(pg) for _ in pg] for r in R if r["page"] == p]
                base = cer_lines(S, "truth", readers["image77"])
                for k in ("fused_signal", "fused_image78", "fused_78_and_signal"):
                    diffs[k].append(cer_lines(S, "truth", readers[k]) - base)
            row["lines"] = len(R)
            for k, v in diffs.items():
                lo, hi = np.percentile(v, [2.5, 97.5])
                row[f"{k}_minus_image_ci95"] = [round(float(lo), 3), round(float(hi), 3)]
                row[f"{k}_do_no_harm"] = bool(hi <= 0.05)
            out[split][b] = row
    # warning
    y = [int(np_(r["g77"]) != np_(r["truth"])) for r in T]

    def best_ll(r, part):
        i = r["cands"].index(r["g77"]) if r["g77"] in r["cands"] else 0
        v = (r.get(part) or [None])[i]
        return -(v if v is not None else -1e3) / max(1, len(r["g77"]))
    W = {"sig_dis": [Levenshtein.distance(np_(r["g77"]), np_(r["gsig"])) / max(1, len(np_(r["g77"]))) for r in T],
         "sig_ll": [best_ll(r, "ssig") for r in T],
         "ctl_conf": [1 - r["cmin77"] for r in T],
         "ctl_dis": [Levenshtein.distance(np_(r["g77"]), np_(r["g78"] or "")) / max(1, len(np_(r["g77"]))) for r in T],
         "ctl_ll": [best_ll(r, "s78") for r in T]}
    W["sig_combo"] = list(np.argsort(np.argsort(W["sig_ll"])) + np.argsort(np.argsort(W["ctl_conf"])))
    rk = lambda v: np.argsort(np.argsort(v))
    W["ctl_dis+sig_ll"] = list(rk(W["ctl_dis"]) + rk(W["sig_ll"]))
    W["ctl_ll+sig_ll"] = list(rk(W["ctl_ll"]) + rk(W["sig_ll"]))
    W["ctl_dis+ctl_ll"] = list(rk(W["ctl_dis"]) + rk(W["ctl_ll"]))
    W["ctl_combo"] = list(np.argsort(np.argsort(W["ctl_ll"])) + np.argsort(np.argsort(W["ctl_conf"])))
    out["warning"] = dict(image_errors=int(sum(y)), lines=len(y), base_rate=round(sum(y) / len(y), 3),
                          scores={k: dict(pr_auc=round(prauc(v, y), 3), **at_rate(v, y)) for k, v in W.items()})
    # calibration: signal's per-char likelihood of the TRUE line vs reconstruction health (blob share / thickness)
    out["calibration"] = {}
    for b in ("thin/crisp", "even/medium", "heavy/spread"):
        R = [r for r in T if r["ink"] == b]
        out["calibration"][b] = dict(lines=len(R), signal_cer=round(cer_lines(R, "truth", readers["signal"]), 2),
                                     mean_sig_ll_of_image_line=round(float(np.mean([best_ll(r, "ssig") for r in R])), 3))
    (d / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])

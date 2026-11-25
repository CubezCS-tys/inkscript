"""Experiment 103's scorer: the repair (A3) and the writer-as-judge ladder (B1, B2, B3), bars fixed 2026-11-25 before
any GPU output (README "The ladder").  Every bar is a function here; selftest() shows each can pass and fail.

    python3 score103.py repair DEV_PRED DEVMIX_PRED --base_adapter M_PATH              -> out/scores/repair.json
    python3 score103.py b1 out/judge/check103.jsonl READ.jsonl FORCE.jsonl            -> out/scores/b1.json
    python3 score103.py b2 out/judge/contrast_j.jsonl FORCE.jsonl READ.jsonl          -> out/scores/b2.json
    (B1 / B2 read the blind readers' settled truths from out/b/settle/C/readings.jsonl + the A/B files, 97's format)

Definitions.
  writer score (B1): experiment 87 round 2's frozen logistic checker (87_writer/out/checker87_r2.json "model", its
      20 features), applied unchanged to the absolute fit of the reading; higher = more suspect.  Reported beside it,
      not used for the bar: the single feature chamfer.
  confidence (B1): the reader's own token log-probabilities from the generation; the free baseline is the BETTER of
      -lp_min and -lp_mean on the same lines (the strongest free score we have, chosen after the fact in its favour).
  threshold (B1): the score that keeps 99% of the CORRECT lines unflagged (their 99th percentile); catch = share of
      real gross errors above it.
  B1 bars: writer AUC >= 0.90 on real gross errors (vs correct lines) AND catch >= 60% AND catch(writer) -
      catch(confidence) >= 5 points.  Planted errors are reported on the same threshold, not part of the bar.
  B2 rules (J, lines whose settled truth is one of the two readings):
      always_reader, always_azure;
      confidence: the reading with the higher forced mean log-probability under the reader (threshold-free);
      confidence_cv: reader unless its lp_min is below tau, tau by 5-fold page-grouped cross-validation;
      writer: experiment 95's frozen rule (rule95.json: chamfer on the gap, min over anchors, delta 0; a group with a
          missing glyph or no scored anchor falls back to the reader); an exact tie keeps the reader;
      writer_conf: logistic on [chamfer(reader) - chamfer(azure), lp_mean(reader) - lp_mean(azure)], 5-fold
          page-grouped cross-validation.
  B2 bar: each writer rule against the best free rule: >= +5 points -> PASS; within 5 points either side -> "no use
      at letter level"; below by more than 5 -> FAIL (experiment 95's finding was this, -10 points).  B2 = PASS when
      either writer rule passes (letter-level use), else "no use at letter level", with the writer-alone verdict
      reported.  95% interval: paired bootstrap over pages.
  Repair bars (A3): on DEV-MIXED's fixed lines, letters wrong (score102's folded, no punctuation, against the fixed
      targets) <= 0.5 x M's; ORDER right (logical string = target, among lines whose display equals the target's)
      >= 90%; DEV (dev103) letters wrong <= M's + 0.05 points; DEV-MIXED controls <= M's + 0.05 points.
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(HERE))
OUT = HERE / "out/scores"
CHECKER87 = E / "87_writer/out/checker87_r2.json"
RULE95 = E / "95_writer3/out/rule95.json"


# ------------------------------------------------------------------------------------------------ small tools

def auc(s, y):
    s, y = np.asarray(s, float), np.asarray(y, int)
    o = np.argsort(s, kind="mergesort")
    r = np.empty(len(s))
    r[o] = np.arange(1, len(s) + 1)
    for v in np.unique(s):                              # mid-ranks for ties
        m = s == v
        r[m] = r[m].mean()
    n1, n0 = y.sum(), (1 - y).sum()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / max(1, n1 * n0))


def catch_at_keep(s, y, keep=0.99):
    s, y = np.asarray(s, float), np.asarray(y, int)
    thr = float(np.quantile(s[y == 0], keep, method="higher"))
    return float((s[y == 1] > thr).mean()) if (y == 1).any() else float("nan"), thr


def boot(fn, groups, n=1000, seed=103):
    """95% interval of fn(index list) over a bootstrap of groups (pages)."""
    rng = random.Random(seed)
    by = defaultdict(list)
    for i, g in enumerate(groups):
        by[g].append(i)
    keys = sorted(by)
    vals = []
    for _ in range(n):
        idx = [i for k in (rng.choice(keys) for _ in keys) for i in by[k]]
        try:
            vals.append(fn(idx))
        except (ValueError, ZeroDivisionError, IndexError):
            continue
    vals = [v for v in vals if not (isinstance(v, float) and math.isnan(v))]
    return [round(float(np.quantile(vals, 0.025)), 4), round(float(np.quantile(vals, 0.975)), 4)] if vals else None


def logit_cv(X, y, groups, k=5, seed=103, l2=1e-2, it=2000, lr=0.1):
    """Page-grouped k-fold logistic regression -> out-of-fold scores."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    g = sorted(set(groups))
    random.Random(seed).shuffle(g)
    fold = {p: i % k for i, p in enumerate(g)}
    s = np.zeros(len(y))
    for f in range(k):
        tr = np.array([fold[p] != f for p in groups])
        te = ~tr
        if te.sum() == 0 or tr.sum() == 0:
            continue
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        Z = (X - mu) / sd
        w, b = np.zeros(X.shape[1]), 0.0
        for _ in range(it):
            p = 1 / (1 + np.exp(-(Z[tr] @ w + b)))
            w -= lr * (Z[tr].T @ (p - y[tr]) / tr.sum() + l2 * w)
            b -= lr * float((p - y[tr]).mean())
        s[te] = Z[te] @ w + b
    return s


def writer_score_87(rows):
    """Experiment 87 round 2's frozen logistic checker on check rows (higher = more suspect)."""
    m = json.loads(CHECKER87.read_text())["model"]
    X = np.array([[r[f] for f in m["feats"]] for r in rows], float)
    # A crop whose binarisation holds no ink at all (show-through) gives an infinite chamfer.  Numerical handling,
    # added 2026-11-25 when 4 such fits appeared: set to twice the largest finite value of that feature, so the
    # reading stays among the most suspect (chamfer's weight is positive) and the logistic stays finite.
    for j in range(X.shape[1]):
        bad = ~np.isfinite(X[:, j])
        if bad.any():
            X[bad, j] = 2 * np.nanmax(np.where(bad, np.nan, X[:, j]))
    return (X - np.array(m["mu"])) / np.array(m["sd"]) @ np.array(m["w"]) + m["b"]


# ------------------------------------------------------------------------------------------------ B1

def b1_bars(writer, conf_scores: dict, y, pages):
    """writer: scores (higher = suspect); conf_scores: {name: scores}; y: 1 = real gross error, 0 = correct line."""
    y = np.asarray(y, int)
    w_auc = auc(writer, y)
    w_catch, w_thr = catch_at_keep(writer, y)
    conf = {}
    for name, s in conf_scores.items():
        c, t = catch_at_keep(s, y)
        conf[name] = dict(auc=round(auc(s, y), 4), catch=round(c, 4), threshold=t)
    best = max(conf, key=lambda n: (conf[n]["catch"], conf[n]["auc"]))
    gain = w_catch - conf[best]["catch"]
    idx_all = list(range(len(y)))
    res = dict(n_real=int(y.sum()), n_correct=int((1 - y).sum()), writer_auc=round(w_auc, 4), writer_catch=round(w_catch, 4),
               writer_threshold=w_thr, confidence=conf, best_confidence=best, gain_points=round(100 * gain, 2),
               writer_auc_ci=boot(lambda ix: auc(np.asarray(writer)[ix], y[ix]), [pages[i] for i in idx_all]),
               gain_ci=boot(lambda ix: catch_at_keep(np.asarray(writer)[ix], y[ix])[0]
                            - catch_at_keep(np.asarray(conf_scores[best])[ix], y[ix])[0], [pages[i] for i in idx_all]))
    res["bars"] = dict(auc_ge_0_90=w_auc >= 0.90, catch_ge_60=w_catch >= 0.60, beats_confidence_by_5=gain >= 0.05)
    res["B1"] = "PASS" if all(res["bars"].values()) else "FAIL"
    return res


# ------------------------------------------------------------------------------------------------ B2

def contrast_pick(row, default=0):
    """rule95: chamfer on the gap, min over anchors, delta 0; None-safe: no scored anchor or a missing glyph -> None."""
    A = [a for a in row["scores"] if all(x is not None for x in row["scores"][a])]
    if not A or any(x["n_missing"] for a in A for x in row["scores"][a]):
        return None, None
    M = np.array([[x["chamfer"] for x in row["scores"][a]] for a in A]).min(0)
    m = M.min()
    best = [i for i, s in enumerate(M) if s == m]
    return (default if default in best else best[0]), list(M)


def b2_bars(lines):
    """lines: [{page, truth_is: 0 reader | 1 azure, writer_pick: 0/1/None, chamfer: [r, a] or None,
                 lp_mean: [r, a], lp_min_reader}]  (only lines whose truth is one of the two readings)."""
    n = len(lines)
    y = np.array([l["truth_is"] for l in lines])            # 1 = Azure right
    pages = [l["page"] for l in lines]
    picks = {}
    picks["always_reader"] = np.zeros(n, int)
    picks["always_azure"] = np.ones(n, int)
    lp = np.array([l["lp_mean"] for l in lines], float)
    picks["confidence"] = (lp[:, 1] > lp[:, 0]).astype(int)
    lmin = np.array([l["lp_min_reader"] for l in lines], float)
    s_cv = logit_cv(lmin[:, None], y, pages)
    picks["confidence_cv"] = (s_cv > 0).astype(int)
    wp = np.array([0 if l["writer_pick"] is None else l["writer_pick"] for l in lines], int)
    picks["writer"] = wp
    ch = np.array([l["chamfer"] if l["chamfer"] else [0.0, 0.0] for l in lines], float)
    X = np.c_[ch[:, 0] - ch[:, 1], lp[:, 0] - lp[:, 1]]
    picks["writer_conf"] = (logit_cv(X, y, pages) > 0).astype(int)
    acc = {k: float((v == y).mean()) for k, v in picks.items()}
    free = ["always_reader", "always_azure", "confidence", "confidence_cv"]
    best_free = max(free, key=lambda k: acc[k])
    per = {}
    for w in ("writer", "writer_conf"):
        d = acc[w] - acc[best_free]
        per[w] = dict(difference_points=round(100 * d, 2),
                      difference_ci=boot(lambda ix: float((picks[w][ix] == y[ix]).mean() - (picks[best_free][ix] == y[ix]).mean()), pages),
                      verdict="PASS" if d >= 0.05 else ("no use at letter level" if d > -0.05 else "FAIL"))
    verdict = "PASS" if any(v["verdict"] == "PASS" for v in per.values()) else "no use at letter level"
    return dict(n=n, accuracy={k: round(v, 4) for k, v in acc.items()}, best_free=best_free, rules=per,
                writer_fell_back=int(sum(l["writer_pick"] is None for l in lines)), B2=verdict,
                writer_alone=per["writer"]["verdict"])


# ------------------------------------------------------------------------------------------------ B3

def b3_bars(m_exam: dict, sys_exam: dict, flagged_share: float, changed_share: float):
    """score102.exam outputs for M and for the system (repaired reader + the passing writer rule).  Invented words per
    100 = faults.invented.words_per_100; letters wrong = reading.folded_no_punct.letter_error."""
    inv_m, inv_s = m_exam["faults"]["invented"]["words_per_100"], sys_exam["faults"]["invented"]["words_per_100"]
    lw_m = m_exam["reading"]["folded_no_punct"]["letter_error"]
    lw_s = sys_exam["reading"]["folded_no_punct"]["letter_error"]
    ok = inv_s < inv_m and lw_s <= lw_m
    return dict(invented_per_100=dict(M=inv_m, system=inv_s), letters_wrong=dict(M=lw_m, system=lw_s),
                flagged_share=flagged_share, changed_share=changed_share, B3="PASS" if ok else "FAIL")


# ------------------------------------------------------------------------------------------------ repair

def order_measure(preds: dict, rows):
    from fix103 import display_key
    shown = exact = 0
    for r in rows:
        p = preds.get(r["key"])
        if p is None:
            continue
        if display_key(" ".join(p.split())) == display_key(r["label"]):
            shown += 1
            exact += " ".join(p.split()) == r["label"]
    return dict(display_right=shown, order_right=exact, order_right_share=round(exact / max(1, shown), 4))


def repair_bars(lw: dict, order_fixed_share: float):
    """lw: letters wrong (folded, no punct, %) {devmix_fixed: (M, R), devmix_controls: (M, R), dev: (M, R)}."""
    b = dict(devmix_halved=lw["devmix_fixed"][1] <= 0.5 * lw["devmix_fixed"][0],
             order_right_90=order_fixed_share >= 0.90,
             dev_not_worse=lw["dev"][1] <= lw["dev"][0] + 0.05,
             controls_not_worse=lw["devmix_controls"][1] <= lw["devmix_controls"][0] + 0.05)
    return dict(bars=b, REPAIR="PASS" if all(b.values()) else "FAIL")


def _lw(res):
    """letters wrong, folded, punctuation ignored, in % (score99.r1_rates' letter_error is a fraction)."""
    return round(100 * (res["reading"]["folded_no_punct"]["letter_error"] or 0.0), 3)


def _half(stem):
    import hashlib
    return "choose" if int(hashlib.md5(f"103|half|{stem}".encode()).hexdigest()[:8], 16) % 2 == 0 else "test"


def repair(dev_pred, devmix_pred, base_adapter):
    """Choose R's checkpoint on DEV + the CHOOSE half of DEV-MIXED (documents split by hash), then apply the repair
    bars on the TEST half (never used to choose).  Checkpoint rule: among checkpoints whose DEV letters wrong is
    <= M's + 0.05 points, the lowest letters wrong on DEV-MIXED-choose's fixed lines; within 0.05 points of it the
    latest checkpoint."""
    sys.path.insert(0, str(E / "102_qwen_line_reader"))
    import score102
    sets = HERE / "out/sets"
    dev = [json.loads(l) for l in open(sets / "dev103.jsonl", encoding="utf-8")]
    dm = [json.loads(l) for l in open(sets / "devmix.jsonl", encoding="utf-8")]
    part = {(h, kind): [r for r in dm if _half(r["stem"]) == h and r["devmix"] == kind]
            for h in ("choose", "test") for kind in ("fixed", "control")}
    ads = sorted({json.loads(l)["adapter"] for l in open(devmix_pred, encoding="utf-8")} - {base_adapter},
                 key=lambda a: int(a.rsplit("-", 1)[-1]))
    lw_dev = {a: _lw(score102.dev(dev_pred, adapter=a, rows=dev)) for a in [base_adapter] + ads}
    lw_ch = {a: _lw(score102.dev(devmix_pred, adapter=a, rows=part[("choose", "fixed")])) for a in [base_adapter] + ads}
    ok = [a for a in ads if lw_dev[a] <= lw_dev[base_adapter] + 0.05]
    out = dict(dev=lw_dev, devmix_choose_fixed=lw_ch, eligible=ok)
    if not ok:
        out.update(chosen=None, REPAIR="FAIL", why="every checkpoint is worse on DEV than M by more than 0.05 points")
    else:
        best = min(lw_ch[a] for a in ok)
        chosen = [a for a in ok if lw_ch[a] <= best + 0.05][-1]
        lw = {}
        for name, rows, path in (("dev", dev, dev_pred), ("devmix_fixed", part[("test", "fixed")], devmix_pred),
                                 ("devmix_controls", part[("test", "control")], devmix_pred)):
            lw[name] = tuple(_lw(score102.dev(path, adapter=ad, rows=rows)) for ad in (base_adapter, chosen))
        P, _, _ = score102.read_pred(devmix_pred, chosen)
        Pm, _, _ = score102.read_pred(devmix_pred, base_adapter)
        om = order_measure(P, part[("test", "fixed")])
        out.update(chosen=chosen, letters_wrong_test_half=lw, order=dict(repaired=om, M=order_measure(Pm, part[("test", "fixed")])),
                   sizes={f"{h}_{k}": len(v) for (h, k), v in part.items()})
        out.update(repair_bars(lw, om["order_right_share"]))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "repair.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1))


# ------------------------------------------------------------------------------------------------ B1 / B2 on real data

def _jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def truths(settle=HERE / "out/b/settle"):
    """Experiment 97's settling: A and B read blind; where they agree (and neither is unsure) that is the truth,
    otherwise C's reading.  Unreadable or unsure-in-C lines have no truth."""
    rd = {w: {d["id"]: d for d in _jl(settle / w / "readings.jsonl")} for w in ("A", "B", "C") if (settle / w / "readings.jsonl").exists()}
    T = {}
    for k in set(rd.get("A", {})) | set(rd.get("B", {})):
        a, b = rd.get("A", {}).get(k), rd.get("B", {}).get(k)
        if a and b and not a.get("unsure") and not b.get("unsure") and " ".join(a["printed"].split()) == " ".join(b["printed"].split()):
            T[k] = " ".join(a["printed"].split())
        elif k in rd.get("C", {}) and not rd["C"][k].get("unsure") and not rd["C"][k].get("unreadable"):
            T[k] = " ".join(rd["C"][k]["printed"].split())
    return T


def b1(check_path, read_path, force_path, adapter=None):
    from pool103 import gross
    T = truths()
    rows = _jl(check_path)
    ws = writer_score_87(rows)
    for r, w in zip(rows, ws):
        r["w"] = float(w)
    by = {r["id"]: r for r in rows}
    read = {d["key"]: d for d in _jl(read_path) if adapter is None or d.get("adapter") == adapter}
    force = {(d["key"], d["cid"]): d for d in _jl(force_path)} if Path(force_path).exists() else {}
    pos, neg = [], []
    for r in rows:
        k = r["key"]
        if r["kind"] == "real_reader" and k in T:
            (pos if gross(T[k], r["text"]) else neg).append(r)
        elif r["kind"] == "correct" and (k not in T or T[k] == " ".join(r["text"].split())):
            neg.append(r)
    R = pos + neg
    y = np.array([1] * len(pos) + [0] * len(neg))
    conf = {"-lp_min": [-(read[r["key"]]["lp_min"] or 0) for r in R], "-lp_mean": [-(read[r["key"]]["lp_mean"] or 0) for r in R]}
    pages = [r["page"] for r in R]
    res = b1_bars([r["w"] for r in R], conf, y, pages)
    chf = np.array([r["chamfer"] for r in R], float)
    chf[~np.isfinite(chf)] = 2 * np.nanmax(np.where(np.isfinite(chf), chf, np.nan))
    res["chamfer_only"] = dict(auc=round(auc(chf, y), 4), catch=round(catch_at_keep(chf, y)[0], 4))
    res["writer_plus_confidence_cv"] = None
    s_cv = logit_cv(np.c_[[r["w"] for r in R], conf["-lp_min"], conf["-lp_mean"]], y, pages)
    res["writer_plus_confidence_cv"] = dict(auc=round(auc(s_cv, y), 4), catch=round(catch_at_keep(s_cv, y)[0], 4))
    # planted, on the same threshold (the 99%-keep threshold of the correct lines)
    thr = res["writer_threshold"]
    for kind in ("planted_sub", "planted_drop"):
        P = [r for r in rows if r["kind"] == kind]
        O = [by.get(r["id"].rsplit("|", 1)[0] + "|orig") for r in P]
        res[kind] = dict(n=len(P), writer_catch=round(float(np.mean([r["w"] > thr for r in P])), 4) if P else None,
                         paired_writer_prefers_true=round(float(np.mean([o["w"] < r["w"] for r, o in zip(P, O) if o])), 4) if P else None)
        if force:
            pr = [(force.get((r["key"], kind)), force.get((r["key"], "orig"))) for r in P]
            pr = [(a, b) for a, b in pr if a and b and a["lp_mean"] is not None and b["lp_mean"] is not None]
            res[kind]["paired_confidence_prefers_true"] = round(float(np.mean([b["lp_mean"] > a["lp_mean"] for a, b in pr])), 4) if pr else None
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "b1.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


def b2(contrast_path, force_path, read_path, adapter=None):
    T = truths()
    read = {d["key"]: d for d in _jl(read_path) if adapter is None or d.get("adapter") == adapter}
    force = {(d["key"], d["cid"]): d for d in _jl(force_path)}
    G = {g["key"]: g for g in _jl(HERE / "out/b/contrast_groups.jsonl")}
    C = {r["key"]: r for r in _jl(contrast_path)}
    L, c = [], defaultdict(int)
    for k, g in G.items():
        if k not in T:
            c["no settled truth"] += 1
            continue
        rd, az = (" ".join(x.split()) for x in g["cands"])
        if (T[k] == rd) == (T[k] == az):
            c["truth is neither or both"] += 1
            continue
        wp, ch = (None, None)
        if k in C:
            wp, ch = contrast_pick(C[k], default=0)
        else:
            c["writer could not write the pair (falls back to the reader)"] += 1
        fr, fa = force.get((k, "reader")), force.get((k, "azure"))
        if not (fr and fa) or fr["lp_mean"] is None or fa["lp_mean"] is None:
            c["no forced confidence"] += 1
            continue
        L.append(dict(page=g["page"], truth_is=int(T[k] == az), writer_pick=wp, chamfer=ch,
                      lp_mean=[fr["lp_mean"], fa["lp_mean"]], lp_min_reader=read[k]["lp_min"] or 0.0))
    res = b2_bars(L)
    res["left_out"] = dict(c)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "b2.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))

def planted(check_path, read_path, force_path, adapter=None):
    """B1's planted set, scored now (it needs no blind key) against B1's bars, read the same way: planted readings
    (wrong plausible word / missing word) as the errors, the 1,500 CORRECT lines (reader = Azure) as the right lines.
    The planted readings' confidence is the reader's forced log-likelihood of the planted text; the correct lines'
    is their generation log-probabilities (the same quantity for a greedy reading).  Also: paired, does the writer
    score the planted text worse than the true text on the same line, and does the confidence?"""
    rows = _jl(check_path)
    ws = writer_score_87(rows)
    for r, w in zip(rows, ws):
        r["w"] = float(w)
    by = {r["id"]: r for r in rows}
    read = {d["key"]: d for d in _jl(read_path) if adapter is None or d.get("adapter") == adapter}
    force = {(d["key"], d["cid"]): d for d in _jl(force_path)}
    neg = [r for r in rows if r["kind"] == "correct" and r["key"] in read and read[r["key"]]["lp_min"] is not None]
    out = {}
    for kind in ("planted_sub", "planted_drop", "planted_all"):
        P = [r for r in rows if (r["kind"] == kind or (kind == "planted_all" and r["kind"].startswith("planted_") and r["kind"] != "planted_orig"))]
        P = [r for r in P if force.get((r["key"], r["kind"])) and force[(r["key"], r["kind"])]["lp_min"] is not None]
        R = P + neg
        y = np.array([1] * len(P) + [0] * len(neg))
        conf = {"-lp_min": [-(force[(r["key"], r["kind"])]["lp_min"]) for r in P] + [-read[r["key"]]["lp_min"] for r in neg],
                "-lp_mean": [-(force[(r["key"], r["kind"])]["lp_mean"]) for r in P] + [-read[r["key"]]["lp_mean"] for r in neg]}
        res = b1_bars([r["w"] for r in R], conf, y, [r["page"] for r in R])
        pw = [(r["w"], by[r["id"].rsplit("|", 1)[0] + "|orig"]["w"]) for r in P if r["id"].rsplit("|", 1)[0] + "|orig" in by]
        pc = [(force[(r["key"], r["kind"])]["lp_mean"], force[(r["key"], "orig")]["lp_mean"]) for r in P
              if force.get((r["key"], "orig")) and force[(r["key"], "orig")]["lp_mean"] is not None]
        res["paired_writer_prefers_true"] = round(float(np.mean([a > b for a, b in pw])), 4) if pw else None
        res["paired_confidence_prefers_true"] = round(float(np.mean([b > a for a, b in pc])), 4) if pc else None
        res["chamfer_only"] = dict(auc=round(auc([r["chamfer"] for r in R], y), 4),
                                   catch=round(catch_at_keep([r["chamfer"] for r in R], y)[0], 4))
        out[kind] = res
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "b1_planted.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: {x: v[x] for x in ("n_real", "n_correct", "writer_auc", "writer_catch", "confidence", "best_confidence",
                                            "gain_points", "B1", "paired_writer_prefers_true", "paired_confidence_prefers_true",
                                            "chamfer_only")} for k, v in out.items()}, indent=1, default=float))



# ------------------------------------------------------------------------------------------------ self-test

def selftest(outdir: Path):
    """Fake data on which each bar passes and fails; writes outdir/score103.json."""
    rng = np.random.default_rng(103)
    res = {}
    # B1: 120 real gross errors, 1,500 correct lines, 300 pages
    y = np.r_[np.ones(120, int), np.zeros(1500, int)]
    pages = [f"p{i % 300}" for i in range(len(y))]
    conf = {"lp_min": rng.normal(0, 1, len(y)) + 1.0 * y, "lp_mean": rng.normal(0, 1, len(y)) + 0.8 * y}
    strong = rng.normal(0, 1, len(y)) + 4.0 * y           # separates: AUC ~0.998, catch ~0.85
    weak = rng.normal(0, 1, len(y)) + 1.0 * y             # like the confidence: AUC ~0.76
    res["B1_strong_writer"] = b1_bars(strong, conf, y, pages)
    res["B1_weak_writer"] = b1_bars(weak, conf, y, pages)
    mid = rng.normal(0, 1, len(y)) + 2.6 * y             # AUC ~0.97 but catch ~0.4: fails on the catch bar only
    res["B1_mid_writer"] = b1_bars(mid, conf, y, pages)
    # B2: 300 lines; Azure right on 35%
    n = 300
    truth = (rng.random(n) < 0.35).astype(int)
    lp = rng.normal(-0.2, 0.1, (n, 2))
    lp[np.arange(n), truth] += 0.05                       # confidence slightly informative
    def lines(writer_acc, independent=False):
        L = []
        for i in range(n):
            if independent:                               # a pick that knows nothing about the truth
                wp = int(rng.random() < 0.5)
            else:
                wp = truth[i] if rng.random() < writer_acc else 1 - truth[i]
            ch = [1.0, 1.0]
            ch[1 - wp] = 1.3
            L.append(dict(page=f"p{i % 60}", truth_is=int(truth[i]), writer_pick=int(wp), chamfer=ch,
                          lp_mean=list(lp[i]), lp_min_reader=float(lp[i, 0] - 0.5)))
        return L
    res["B2_good_writer"] = b2_bars(lines(0.92))
    res["B2_useless_writer"] = b2_bars(lines(0.0, independent=True))
    res["B2_bad_writer"] = res["B2_useless_writer"]          # the same lines: the writer ALONE is the FAIL case
    # repair bars
    res["repair_pass"] = repair_bars(dict(devmix_fixed=(6.7, 2.0), devmix_controls=(0.8, 0.8), dev=(1.22, 1.24)), 0.95)
    res["repair_fail_order"] = repair_bars(dict(devmix_fixed=(6.7, 2.0), devmix_controls=(0.8, 0.8), dev=(1.22, 1.24)), 0.70)
    res["repair_fail_dev"] = repair_bars(dict(devmix_fixed=(6.7, 2.0), devmix_controls=(0.8, 0.8), dev=(1.22, 1.40)), 0.95)
    # B3 bars
    m = json.loads((E / "102_qwen_line_reader/out/scores/exam_M.json").read_text())       # M's real exam score
    def sysx(inv, le):
        return dict(faults=dict(invented=dict(words_per_100=inv)), reading=dict(folded_no_punct=dict(letter_error=le)))
    res["B3_pass"] = b3_bars(m, sysx(0.30, 0.0068), 0.02, 0.01)
    res["B3_fail_letters"] = b3_bars(m, sysx(0.30, 0.0075), 0.02, 0.01)
    # rule95 pick, None-safety
    row = dict(scores={"0": [dict(chamfer=1.0, n_missing=0), dict(chamfer=1.2, n_missing=0)],
                       "1": [dict(chamfer=1.1, n_missing=0), dict(chamfer=0.9, n_missing=0)]})
    res["rule95_pick_min_over_anchors"] = contrast_pick(row)[0]          # min: reader 1.0, azure 0.9 -> 1
    row["scores"]["1"][0]["n_missing"] = 1
    res["rule95_missing_glyph"] = contrast_pick(row)[0]                  # None: falls back to the reader
    verdicts = {k: v.get("B1") or v.get("B2") or v.get("REPAIR") or v.get("B3") for k, v in res.items() if isinstance(v, dict)}
    verdicts["B2_bad_writer"] = res["B2_bad_writer"]["writer_alone"]
    verdicts["B2_good_writer_alone"] = res["B2_good_writer"]["writer_alone"]
    res["verdicts"] = verdicts
    expect = {"B1_strong_writer": "PASS", "B1_weak_writer": "FAIL", "B1_mid_writer": "FAIL", "B2_good_writer": "PASS",
              "B2_useless_writer": "no use at letter level", "B2_bad_writer": "FAIL", "B2_good_writer_alone": "PASS", "repair_pass": "PASS",
              "repair_fail_order": "FAIL", "repair_fail_dev": "FAIL", "B3_pass": "PASS", "B3_fail_letters": "FAIL"}
    res["all_as_expected"] = all(verdicts[k] == v for k, v in expect.items()) and res["rule95_pick_min_over_anchors"] == 1 \
        and res["rule95_missing_glyph"] is None
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "score103.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(dict(verdicts=verdicts, all_as_expected=res["all_as_expected"],
                          B1_mid=dict(auc=res["B1_mid_writer"]["writer_auc"], catch=res["B1_mid_writer"]["writer_catch"]),
                          B2_acc={k: res[k]["accuracy"] for k in ("B2_good_writer", "B2_useless_writer", "B2_bad_writer")}),
                     indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "repair":
        a = sys.argv
        repair(a[2], a[3], a[a.index("--base_adapter") + 1])
    elif cmd == "selftest":
        selftest(HERE / "out/selftest")
    elif cmd == "planted":
        a = sys.argv
        planted(a[2], a[3], a[4], adapter=a[a.index("--adapter") + 1] if "--adapter" in a else None)
    elif cmd in ("b1", "b2"):
        a = sys.argv
        ad = a[a.index("--adapter") + 1] if "--adapter" in a else None
        (b1 if cmd == "b1" else b2)(a[2], a[3], a[4], adapter=ad)

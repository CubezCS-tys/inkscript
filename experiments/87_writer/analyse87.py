"""Experiment 87: the numbers and pictures from the GPU runs (local CPU, light).

    python analyse87.py ceiling          -> out/ceiling87.json + out/look/ceiling_*.png
    python analyse87.py design           the checker's score, designed on POOL planted variants only -> out/checker87.json
    python analyse87.py held [--fold]    the frozen checker on the held-out tests -> out/held87[_folded].json
"""
from __future__ import annotations

import json
import os
import random
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
RUN = Path(os.environ.get("RUN87", OUT / "run"))
D = OUT / "data"
FEATS = ["iou", "recall", "precision", "chamfer", "miss_s", "inv_s", "miss_l", "inv_l", "missa_s", "inva_s",
         "missa_l", "inva_l", "miss_all", "inv_all"]
if os.environ.get("ROUND87") == "2":
    FEATS = FEATS + ["word_prec_min", "word_prec_min2", "word_rec_min", "word_rec_min2", "glyph_prec_min", "glyph_prec_min3"]
SUF = "_r2" if os.environ.get("ROUND87") == "2" else ""


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if Path(p).exists() else []


def q(v, p=50):
    return round(float(np.percentile(v, p)), 3) if len(v) else None


# ------------------------------------------------------------------------------------------------ stage 1
def ceiling():
    R = jl(RUN / "ceiling.jsonl")
    C = {r["key"]: r for r in jl(RUN / "ceiling_ctl.jsonl")}
    Sy = jl(RUN / "ceiling_synth.jsonl")
    out = {}
    by = defaultdict(list)
    for r in R:
        by[r["key"]].append(r)
    best = {k: max(v, key=lambda r: r["iou"]) for k, v in by.items()}
    # page library (true text): the library with the best mean IoU over the page's lines
    pl = defaultdict(lambda: defaultdict(list))
    for r in R:
        pl[r["key"].rsplit("_l", 1)[0]][r["lib"]].append(r["iou"])
    plib = {p: max(d, key=lambda l: np.mean(d[l])) for p, d in pl.items()}
    for era in ("2000+", "1950-1999", "pre-1950"):
        B = [b for b in best.values() if b["era"] == era]
        T = [r for k, v in by.items() for r in v if r["era"] == era and r["lib"] == plib[k.rsplit("_l", 1)[0]]]
        same = {(r["key"], r["lib"]): r for k, v in by.items() for r in v}
        pairs = [(same[(c["key"], c["lib"])]["iou"], c["iou"]) for c in C.values()
                 if c["era"] == era and (c["key"], c["lib"]) in same]
        out[era] = dict(lines=len(B),
                        best_lib=dict(iou=q([b["iou"] for b in B]), iou_q25=q([b["iou"] for b in B], 25),
                                      chamfer=q([b["chamfer"] for b in B]), recall=q([b["recall"] for b in B]),
                                      precision=q([b["precision"] for b in B])),
                        page_lib=dict(iou=q([t["iou"] for t in T]), chamfer=q([t["chamfer"] for t in T])),
                        control=dict(n=len(pairs), iou=q([c for _, c in pairs]),
                                     true_beats_control=round(float(np.mean([a > c for a, c in pairs])), 3) if pairs else None,
                                     true_iou_same_lib=q([a for a, _ in pairs]),
                                     chamfer=q([c["chamfer"] for c in C.values() if c["era"] == era])),
                        libs_won=Counter(b["lib"] for b in B).most_common(6))
        per = defaultdict(list)
        for k, v in by.items():
            for r in v:
                if r["era"] == era:
                    per[r["lib"]].append(r["iou"])
        out[era]["per_lib_median_iou"] = {l: q(v) for l, v in sorted(per.items(), key=lambda x: -np.median(x[1]))}
    if Sy:
        own = [r for r in Sy if r["lib"] != "alqalam"]
        aq = [r for r in Sy if r["lib"] == "alqalam"]
        out["synthetic"] = dict(lines=len(own), own_face=dict(iou=q([r["iou"] for r in own]), chamfer=q([r["chamfer"] for r in own]),
                                                              recall=q([r["recall"] for r in own]), precision=q([r["precision"] for r in own])),
                                alqalam=dict(iou=q([r["iou"] for r in aq]), chamfer=q([r["chamfer"] for r in aq])))
    (OUT / "ceiling87.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))
    figures_ceiling(best, by, C)


def _ov(grey, written, target):
    sys.path.insert(0, str(HERE))
    import fit87 as F
    return F.overlay(grey, written / 255.0, target.astype(np.float32))


def _crop(key, where):
    return cv2.imread(str(D / f"crops/{where}/{key}.png"), 0)


def _label(img, text):
    bar = np.full((22, img.shape[1], 3), 255, np.uint8)
    cv2.putText(bar, text, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 60), 1, cv2.LINE_AA)
    return np.vstack([bar, img])


def stack(rows, gap=6):
    Wm = max(r.shape[1] for r in rows)
    out = []
    for r in rows:
        if r.ndim == 2:
            r = cv2.cvtColor(r, cv2.COLOR_GRAY2BGR)
        out += [np.hstack([np.full((r.shape[0], Wm - r.shape[1], 3), 255, np.uint8), r]), np.full((gap, Wm, 3), 255, np.uint8)]
    return np.vstack(out)


def figures_ceiling(best, by, C):
    mp = RUN / "ceiling.maps"
    for era in ("2000+", "1950-1999", "pre-1950"):
        rows = []
        ks = sorted([k for k, b in best.items() if b["era"] == era], key=lambda k: zlib.crc32(k.encode()))
        for k in ks:
            b = best[k]
            f = mp / f"{k}__{b['lib'].replace('/', '_')}.npz"
            if not f.exists():
                continue
            z = np.load(f)
            g = _crop(k, "pool")
            if g is None or g.shape[1] != z["written"].shape[1]:
                continue
            w = 255 - z["written"]
            rows += [_label(cv2.cvtColor(g, cv2.COLOR_GRAY2BGR), f"real  {k}"),
                     _label(cv2.cvtColor(w, cv2.COLOR_GRAY2BGR), f"written: {b['lib']}  IoU {b['iou']:.2f}  chamfer {b['chamfer']:.2f}px"),
                     _label(_ov(g, z["written"], z["target"]), "black: ink explained   red: ink not written   blue: written, no ink")]
            if len(rows) >= 15:
                break
        if rows:
            cv2.imwrite(str(OUT / f"look/ceiling_{era}.png"), stack(rows))
            print("figure", OUT / f"look/ceiling_{era}.png")


# ------------------------------------------------------------------------------------------------ stage 2 design
def _X(rows):
    return np.array([[r[f] for f in FEATS] for r in rows], float)


def _fit_logit(X, y, l2=1e-2, it=3000, lr=0.1):
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd
    w = np.zeros(Z.shape[1])
    b = 0.0
    for _ in range(it):
        p = 1 / (1 + np.exp(-(Z @ w + b)))
        g = Z.T @ (p - y) / len(y) + l2 * w
        w -= lr * g
        b -= lr * float((p - y).mean())
    return dict(mu=mu.tolist(), sd=sd.tolist(), w=w.tolist(), b=b)


def score_of(model, rows):
    X = _X(rows)
    Z = (X - np.array(model["mu"])) / np.array(model["sd"])
    return Z @ np.array(model["w"]) + model["b"]


def _auc(s, y):
    s, y = np.asarray(s), np.asarray(y)
    o = np.argsort(s)
    r = np.empty(len(s))
    r[o] = np.arange(len(s))
    n1, n0 = y.sum(), (1 - y).sum()
    return float((r[y == 1].sum() - n1 * (n1 - 1) / 2) / max(1, n1 * n0))


def recall_at_false(s, kinds, rate=0.10):
    s = np.asarray(s)
    o = np.array([k == "orig" for k in kinds])
    thr = np.quantile(s[o], 1 - rate)
    out = {"threshold": float(thr), "false_flags": round(float((s[o] > thr).mean()), 3)}
    for k in sorted(set(kinds) - {"orig"}):
        m = np.array([x == k for x in kinds])
        out[k] = round(float((s[m] > thr).mean()), 3)
    m = ~o
    out["all_wrong"] = round(float((s[m] > thr).mean()), 3)
    return out


def design():
    R = jl(RUN / "check_pool.jsonl")
    y = np.array([r["kind"] != "orig" for r in R], float)
    kinds = [r["kind"] for r in R]
    pages = sorted({r["page"] for r in R})
    res = dict(rows=len(R), kinds=dict(Counter(kinds)))
    res["single_features"] = {}
    for f in FEATS:
        s = np.array([r[f] for r in R]) * (-1 if f in ("iou", "recall", "precision") or f.startswith(("word_", "glyph_")) else 1)
        res["single_features"][f] = dict(auc=round(_auc(s, y), 3), **recall_at_false(s, kinds))
    # page-grouped 5-fold cross-validation of the logistic score
    rng = random.Random(87)
    rng.shuffle(pages)
    fold = {p: i % 5 for i, p in enumerate(pages)}
    s_cv = np.zeros(len(R))
    for k in range(5):
        tr = [i for i, r in enumerate(R) if fold[r["page"]] != k]
        te = [i for i, r in enumerate(R) if fold[r["page"]] == k]
        m = _fit_logit(_X([R[i] for i in tr]), y[tr])
        s_cv[te] = score_of(m, [R[i] for i in te])
    res["logistic_cv"] = dict(auc=round(_auc(s_cv, y), 3), **recall_at_false(s_cv, kinds))
    model = _fit_logit(_X(R), y)
    model["feats"] = FEATS
    res["model"] = model
    for era in ("2000+", "1950-1999", "pre-1950"):
        idx = [i for i, r in enumerate(R) if r["era"] == era]
        if idx:
            res.setdefault("logistic_cv_by_era", {})[era] = dict(auc=round(_auc(s_cv[idx], y[idx]), 3),
                                                                  **recall_at_false(s_cv[idx], [kinds[i] for i in idx]))
    (OUT / f"checker87{SUF}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "model"}, indent=1))


# ------------------------------------------------------------------------------------------------ stage 2 held-out
def held(fold: bool):
    if fold:
        os.environ["EST81_FOLD"] = "1"
    sys.path.insert(0, str(E / "81_heldout_scale"))
    import est81
    from rapidfuzz.distance import Levenshtein
    model = json.loads((OUT / f"checker87{SUF}.json").read_text())["model"]
    res = {}
    # planted on held-out pages
    P = jl(RUN / "check_held.jsonl")
    if P:
        s = score_of(model, P)
        kinds = [r["kind"] for r in P]
        y = np.array([k != "orig" for k in kinds], float)
        res["planted"] = dict(rows=len(P), auc=round(_auc(s, y), 3), **recall_at_false(s, kinds))
        res["planted_by_era"] = {}
        for era in ("2000+", "1950-1999", "pre-1950"):
            idx = [i for i, r in enumerate(P) if r["era"] == era]
            if idx:
                res["planted_by_era"][era] = dict(rows=len(idx), **recall_at_false(s[idx], [kinds[i] for i in idx]))
    # judged lines
    J = jl(RUN / "check_judged.jsonl")
    by = defaultdict(dict)
    for r, sc in zip(J, score_of(model, J) if J else []):
        by[r["key"]][r["cand"]] = (float(sc), r)
    rows, S, C, ans = est81.load()
    frame = json.loads((E / "81_heldout_scale/out/judge/frame.json").read_text())
    frame_n = {h: v["frame"] for h, v in frame.items()}
    form = est81.form
    cells = defaultdict(list)
    ncell = Counter()
    for k, s_ in S.items():
        if k not in ans:
            continue
        T, why = est81.truth_of(s_, ans[k])
        if T is None:
            continue
        ncell[f"{s_['stratum']}|{s_['era']}"] += 1          # est81's weight: frame / judged lines of the cell
        if k in by:
            cells[f"{s_['stratum']}|{s_['era']}"].append(k)
    ys, ws, sc_ours, sc_dis, sc_ll, eras, pages, picks = [], [], [], [], [], [], [], []
    img = {}
    want = {k for L in cells.values() for k in L}
    for l in open(E / "81_heldout_scale/out/read/image.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if d["key"] in want:
            img[d["key"]] = d
    for h, L in cells.items():
        w = frame_n[h] / ncell[h]
        for k in L:
            s_, a, r = S[k], ans[k], rows[k]
            T, _ = est81.truth_of(s_, a)
            v1 = r["readings"]["v1"]
            ys.append(int(form(v1) != T))
            ws.append(w)
            eras.append(r["era"])
            pages.append(f"{r['stem']}_{r['page']}")
            shown_f = [form(x) for x in s_["shown"]]
            ci = shown_f.index(form(v1)) if form(v1) in shown_f else None
            cand = by[k]
            if ci is None or ci not in cand:
                sc_ours.append(np.nan)
            else:
                sc_ours.append(cand[ci][0])
            sc_dis.append(Levenshtein.distance(form(v1), form(r["readings"]["s2r"])) / max(1, len(form(v1))))
            d = img.get(k)
            if d is not None:
                i = d["cands"].index(v1) if v1 in d["cands"] else 0
                s78 = d["s78"][i] if d["s78"][i] is not None else -1e3
                sc_ll.append(-s78 / max(1, len(v1)))
            else:
                sc_ll.append(0.0)
            # does the lowest mismatch pick the judge's reading?
            distinct = {}
            for j, f in enumerate(shown_f):
                if j in cand:
                    distinct.setdefault(f, []).append(cand[j][0])
            if len(distinct) >= 2 and T in distinct:
                best = min(distinct, key=lambda f: min(distinct[f]))
                picks.append(dict(ok=best == T, n=len(distinct), v1_ok=form(v1) == T, w=w))
    ys, ws = np.array(ys), np.array(ws)
    sc_ours = np.array(sc_ours)
    ok = ~np.isnan(sc_ours)
    res["judged"] = dict(lines=int(len(ys)), scored=int(ok.sum()), weighted_error_rate=round(float(np.dot(ys, ws) / ws.sum()), 4))
    m = ok
    rk = lambda v: np.argsort(np.argsort(np.asarray(v)[m]))
    comb = rk(sc_ours) + rk(sc_dis)
    comb3 = rk(sc_ours) + rk(sc_dis) + rk(sc_ll)
    base2 = rk(sc_ll) + rk(sc_dis)
    res["warning"] = {
        "checker (ours)": est81.wprauc(sc_ours[m], ys[m], ws[m]),
        "v1 vs s2r disagreement": est81.wprauc(np.asarray(sc_dis)[m], ys[m], ws[m]),
        "s2r likelihood": est81.wprauc(np.asarray(sc_ll)[m], ys[m], ws[m]),
        "checker + disagreement": est81.wprauc(comb, ys[m], ws[m]),
        "s2r likelihood + disagreement": est81.wprauc(base2, ys[m], ws[m]),
        "checker + disagreement + s2r likelihood": est81.wprauc(comb3, ys[m], ws[m]),
    }
    # bootstrap over pages: recall at 10% of (checker + disagreement) minus disagreement alone
    pg = np.array(pages)[m]
    up = sorted(set(pg))
    ix = {p: np.nonzero(pg == p)[0] for p in up}
    g = np.random.default_rng(87)
    diffs = []
    yy, ww, dd = ys[m], ws[m], np.asarray(sc_dis)[m]
    for _ in range(300):
        samp = np.concatenate([ix[p] for p in g.choice(up, len(up))])
        a = est81.wprauc(comb[samp], yy[samp], ww[samp])["recall_at10"]
        b = est81.wprauc(dd[samp], yy[samp], ww[samp])["recall_at10"]
        diffs.append(a - b)
    res["combination_minus_disagreement_recall10"] = dict(point=round(res["warning"]["checker + disagreement"]["recall_at10"]
                                                                      - res["warning"]["v1 vs s2r disagreement"]["recall_at10"], 3),
                                                          ci=[round(float(np.percentile(diffs, 2.5)), 3), round(float(np.percentile(diffs, 97.5)), 3)])
    res["by_era"] = {}
    for e in ("pre-1950", "1950-1999", "2000+"):
        mm = np.array([x == e for x in eras]) & m
        if mm.sum() > 20:
            res["by_era"][e] = {"checker": est81.wprauc(sc_ours[mm], ys[mm], ws[mm]),
                                "disagreement": est81.wprauc(np.asarray(sc_dis)[mm], ys[mm], ws[mm])}
    if picks:
        wsum = sum(p["w"] for p in picks)
        res["picks_judge"] = dict(lines=len(picks), checker=round(sum(p["w"] * p["ok"] for p in picks) / wsum, 3),
                                  always_v1=round(sum(p["w"] * p["v1_ok"] for p in picks) / wsum, 3),
                                  chance=round(sum(p["w"] / p["n"] for p in picks) / wsum, 3))
    name = ("held87_folded" if fold else "held87") + SUF + ".json"
    (OUT / name).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "ceiling":
        ceiling()
    elif c == "design":
        design()
    elif c == "held":
        held("--fold" in sys.argv)

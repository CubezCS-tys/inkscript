"""Experiment 95: the numbers (local CPU, light).

    python analyse95.py design          idea 1's rule, chosen on POOL groups only -> out/rule95.json (frozen)
    python analyse95.py contrast SET    the frozen rule on SET (synth | pool | held | judged) -> out/contrast_<SET>.json
    python analyse95.py learn           idea 2 / 3a -> out/learn95.json
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from common95 import E, OUT, jl

RUN = Path(os.environ.get("RUN95", OUT / "run"))
METRICS = {
    "loss": lambda s: s["loss"], "loss6": lambda s: s["loss6"], "1-iou": lambda s: 1 - s["iou"],
    "chamfer": lambda s: s["chamfer"], "miss": lambda s: s["miss"], "inv": lambda s: s["inv"],
    "miss+inv": lambda s: s["miss"] + s["inv"], "2miss+inv": lambda s: 2 * s["miss"] + s["inv"],
    "miss+2inv": lambda s: s["miss"] + 2 * s["inv"], "loss6+miss": lambda s: s["loss6"] + 0.1 * s["miss"],
}
AGGS = ("mean", "best_anchor", "min")


def cand_scores(r, metric, agg):
    """-> per candidate a score (lower = explains the ink better), or None if any candidate could not be scored."""
    f = METRICS[metric]
    A = [a for a in r["scores"] if all(x is not None for x in r["scores"][a])]
    if not A:
        return None
    if any(x["n_missing"] for a in A for x in r["scores"][a]):
        return None
    if agg == "best_anchor":
        a = max(A, key=lambda a: r["anchors_meta"][a]["anchor_iou"])
        return [f(x) for x in r["scores"][a]]
    M = np.array([[f(x) for x in r["scores"][a]] for a in A])
    return list(M.mean(0) if agg == "mean" else M.min(0))


def pick(S, default=0):
    """argmin; an exact tie keeps the default (v1 for judged lines, the first candidate otherwise)."""
    m = min(S)
    best = [i for i, s in enumerate(S) if s == m]
    return default if default in best else best[0]


def planted_acc(R, metric, agg):
    """Per test kind: share of groups where the true reading (candidate 0) wins.  A tie counts as half."""
    out = defaultdict(list)
    for r in R:
        S = cand_scores(r, metric, agg)
        if S is None:
            continue
        m = min(S)
        win = [i for i, s in enumerate(S) if s == m]
        out[r["test"]].append((1.0 / len(win)) if 0 in win else 0.0)
    return {k: (round(float(np.mean(v)), 4), len(v)) for k, v in out.items()}


def chance(R):
    out = defaultdict(list)
    for r in R:
        out[r["test"]].append(1 / len(r["cands"]))
    return {k: round(float(np.mean(v)), 4) for k, v in out.items()}


def design():
    R = jl(RUN / "contrast_pool.jsonl")
    tab = {}
    for m in METRICS:
        for a in AGGS:
            acc = planted_acc(R, m, a)
            obj = np.mean([acc.get(k, (0, 0))[0] for k in ("letter", "word_sub", "sibling")])
            tab[f"{m}|{a}"] = dict(objective=round(float(obj), 4), **{k: v[0] for k, v in acc.items()})
    best = max(tab, key=lambda k: tab[k]["objective"])
    m, a = best.split("|")
    # the gating margin delta: the smallest margin above which pool pairs (letter, word_sub) are right >= 90%
    marg = []
    for r in R:
        if r["test"] not in ("letter", "word_sub"):
            continue
        S = cand_scores(r, m, a)
        if S is None:
            continue
        marg.append((abs(S[0] - S[1]), S[0] < S[1]))
    marg.sort()
    delta = None
    for d in sorted({round(x, 4) for x, _ in marg}):
        sel = [ok for x, ok in marg if x > d]
        if len(sel) >= 20 and np.mean(sel) >= 0.9:
            delta = d
            break
    rule = dict(frozen="2026-11-09, on POOL groups only, before any held-out or judged result was looked at",
                metric=m, agg=a, delta=delta, pool_table=tab, pool_groups=len(R), chance=chance(R),
                objective="mean of pool accuracy on letter pairs, word_sub pairs and sibling top-1")
    (OUT / "rule95.json").write_text(json.dumps(rule, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in rule.items() if k != "pool_table"}, indent=1, ensure_ascii=False))
    for k in sorted(tab, key=lambda k: -tab[k]["objective"])[:12]:
        print(k, tab[k])


def _boot_ci(vals, pages, B=1000, seed=95):
    vals, pages = np.asarray(vals, float), np.asarray(pages)
    up = sorted(set(pages))
    ix = {p: np.nonzero(pages == p)[0] for p in up}
    g = np.random.default_rng(seed)
    bs = []
    for _ in range(B):
        s = np.concatenate([ix[p] for p in g.choice(up, len(up))])
        bs.append(vals[s].mean())
    return [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]


def contrast(which):
    rule = json.loads((OUT / "rule95.json").read_text())
    m, a, delta = rule["metric"], rule["agg"], rule["delta"]
    R = jl(RUN / f"contrast_{which}.jsonl")
    res = dict(rule={k: rule[k] for k in ("metric", "agg", "delta")}, groups=len(R))
    if which != "judged":
        res["accuracy"] = {k: v for k, v in planted_acc(R, m, a).items()}
        res["chance"] = chance(R)
        # by era, and the pages' bootstrap interval of the letter pairs
        for kind in ("letter", "word_sub", "sibling"):
            v, pg = [], []
            for r in R:
                if r["test"] != kind:
                    continue
                S = cand_scores(r, m, a)
                if S is None:
                    continue
                mn = min(S)
                win = [i for i, s in enumerate(S) if s == mn]
                v.append(1 / len(win) if 0 in win else 0)
                pg.append(r.get("page", r["key"]))
            if v:
                res.setdefault("ci", {})[kind] = _boot_ci(v, pg)
        by = defaultdict(lambda: defaultdict(list))
        for r in R:
            S = cand_scores(r, m, a)
            if S is None:
                continue
            by[r.get("era", "?")][r["test"]].append(float(np.argmin(S) == 0))
        res["by_era"] = {e: {k: (round(float(np.mean(v)), 3), len(v)) for k, v in d.items()} for e, d in by.items()}
        # sibling: which way the wrong winners go (more or fewer dots / marks than the truth)
        res["sibling_wrong_kinds"] = sibling_kinds(R, m, a)
    else:
        res.update(judged(R, m, a, delta))
    (OUT / f"contrast_{which}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))


DOTS = {"ب": 1, "ت": 2, "ث": 3, "ن": 1, "ي": 2, "ئ": 0, "ى": 0, "ج": 1, "ح": 0, "خ": 1, "د": 0, "ذ": 1, "ر": 0, "ز": 1,
        "س": 0, "ش": 3, "ص": 0, "ض": 1, "ط": 0, "ظ": 1, "ع": 0, "غ": 1, "ف": 1, "ق": 2, "ه": 0, "ة": 2, "ا": 0, "أ": 0,
        "إ": 0, "آ": 0, "و": 0, "ؤ": 0}
MARK = {"أ": 1, "إ": 1, "آ": 1, "ؤ": 1, "ئ": 1}


def _ink_marks(w):
    return sum(DOTS.get(c, 0) for c in w), sum(MARK.get(c, 0) for c in w)


def sibling_kinds(R, m, a):
    c = Counter()
    for r in R:
        if r["test"] != "sibling":
            continue
        S = cand_scores(r, m, a)
        if S is None:
            continue
        j = int(np.argmin(S))
        if j == 0:
            c["right"] += 1
            continue
        t, w = r["cands"][0].split(" ")[r["word"]], r["cands"][j].split(" ")[r["word"]]
        (d0, k0), (d1, k1) = _ink_marks(t), _ink_marks(w)
        c["winner has fewer dots/marks" if d1 + k1 < d0 + k0 else ("more" if d1 + k1 > d0 + k0 else "same count")] += 1
    return dict(c)


def _kind_of(a, b):
    """The kind of a 1-2 letter difference between two strict forms."""
    from rapidfuzz.distance import Levenshtein
    ks = set()
    for op in Levenshtein.editops(a, b):
        x = a[op.src_pos] if op.tag != "insert" else ""
        y = b[op.dest_pos] if op.tag != "delete" else ""
        p = {x, y} - {""}
        if " " in p:
            ks.add("space")
        elif p <= set("اأإآء") or p <= set("ؤو") or p <= set("ئيى") and "ئ" in p:
            ks.add("hamza")
        elif p <= set("يىی"):
            ks.add("ى/ي")
        elif p <= set("هةھ"):
            ks.add("ة/ه")
        elif len(p) == 2 and any(p <= set(g) for g in ("بتثني", "جحخ", "دذ", "رز", "سش", "صض", "طظ", "عغ", "فق")):
            ks.add("dots")
        elif any(ch.isdigit() for ch in p):
            ks.add("digit")
        else:
            ks.add("other")
    return "+".join(sorted(ks)) if len(ks) > 1 else (ks.pop() if ks else "none")


def judged(R, m, a, delta):
    sys.path.insert(0, str(E / "81_heldout_scale"))
    import est81
    from rapidfuzz.distance import Levenshtein
    rows, S, C, ans = est81.load()
    frame = json.loads((E / "81_heldout_scale/out/judge/frame.json").read_text())
    frame_n = {h: v["frame"] for h, v in frame.items()}
    ncell = Counter()
    for k, s_ in S.items():
        if k in ans and est81.truth_of(s_, ans[k])[0] is not None:
            ncell[f"{s_['stratum']}|{s_['era']}"] += 1
    abs87 = abs87_scores()
    L = []
    n_skip = Counter()
    for r in R:
        k = r["key"]
        if k not in ans:
            n_skip["no answer"] += 1
            continue
        T, _ = est81.truth_of(S[k], ans[k])
        if T is None:
            n_skip["unreadable"] += 1
            continue
        forms = [est81.form(c) for c in r["cands"]]
        if T not in forms:
            n_skip["truth not a candidate"] += 1
            continue
        sc = cand_scores(r, m, a)
        if sc is None:
            n_skip["a candidate not writable / not scored"] += 1
            continue
        v1i = r["srcs"].index("v1") if "v1" in r["srcs"] else 0
        p = pick(sc, v1i)
        pg = p if sc[v1i] - min(sc) > (delta if delta is not None else 1e9) else v1i
        md = max(Levenshtein.distance(x, y) for x in forms for y in forms)
        w = frame_n[f"{S[k]['stratum']}|{S[k]['era']}"] / ncell[f"{S[k]['stratum']}|{S[k]['era']}"]
        wrong = [f for f in forms if f != T]
        kind = _kind_of(T, min(wrong, key=lambda f: Levenshtein.distance(T, f))) if md <= 2 else "3+"
        a87 = abs87.get(k)
        p87 = None
        if a87:
            s87 = [a87.get(f) for f in forms]
            if all(x is not None for x in s87):
                p87 = int(forms[int(np.argmin(s87))] == T)
        L.append(dict(key=k, page=f"{rows[k]['stem']}_{rows[k]['page']}", era=rows[k]["era"], w=w, n=len(forms), md=md,
                      kind=kind, ok=int(forms[p] == T), ok_gated=int(forms[pg] == T), v1=int(forms[v1i] == T),
                      abs87=p87))
    out = dict(skipped=dict(n_skip), lines=len(L))

    def summ(sel, name):
        if not sel:
            return None
        w = np.array([x["w"] for x in sel])
        f = lambda key: round(float(np.dot(w, [x[key] for x in sel]) / w.sum()), 4)
        d = dict(lines=len(sel), contrastive=f("ok"), gated=f("ok_gated"), always_v1=f("v1"),
                 chance=round(float(np.dot(w, [1 / x["n"] for x in sel]) / w.sum()), 4))
        s87 = [x for x in sel if x["abs87"] is not None]
        if s87:
            w8 = np.array([x["w"] for x in s87])
            d["abs87_same_lines"] = round(float(np.dot(w8, [x["abs87"] for x in s87]) / w8.sum()), 4)
            d["abs87_lines"] = len(s87)
        # paired difference contrastive - always v1 (weighted mean of per-line differences), page bootstrap
        diff = np.array([(x["ok"] - x["v1"]) for x in sel])
        dg = np.array([(x["ok_gated"] - x["v1"]) for x in sel])
        pages = np.array([x["page"] for x in sel])
        up = sorted(set(pages))
        ix = {p: np.nonzero(pages == p)[0] for p in up}
        g = np.random.default_rng(95)
        bs, bg, ba = [], [], []
        for _ in range(1000):
            s = np.concatenate([ix[p] for p in g.choice(up, len(up))])
            bs.append(np.dot(w[s], diff[s]) / w[s].sum())
            bg.append(np.dot(w[s], dg[s]) / w[s].sum())
            ba.append(np.dot(w[s], [sel[i]["ok"] for i in s]) / w[s].sum())
        d["diff_vs_v1"] = round(float(np.dot(w, diff) / w.sum()), 4)
        d["diff_vs_v1_ci"] = [round(float(np.percentile(bs, q)), 4) for q in (2.5, 97.5)]
        d["gated_diff_vs_v1"] = round(float(np.dot(w, dg) / w.sum()), 4)
        d["gated_diff_vs_v1_ci"] = [round(float(np.percentile(bg, q)), 4) for q in (2.5, 97.5)]
        d["contrastive_ci"] = [round(float(np.percentile(ba, q)), 4) for q in (2.5, 97.5)]
        out[name] = d
        return d
    summ([x for x in L if x["md"] <= 2], "MAIN one or two letters")
    summ(L, "all disputes")
    for b, f in (("md 3-5", lambda x: 3 <= x["md"] <= 5), ("md 6+", lambda x: x["md"] >= 6)):
        summ([x for x in L if f(x)], b)
    for e in ("pre-1950", "1950-1999", "2000+"):
        summ([x for x in L if x["md"] <= 2 and x["era"] == e], f"main, {e}")
    for kd in sorted({x["kind"] for x in L if x["md"] <= 2}):
        sel = [x for x in L if x["md"] <= 2 and x["kind"] == kd]
        if len(sel) >= 15:
            summ(sel, f"main, kind {kd}")
    (OUT / f"contrast_{os.environ.get('JTAG95', 'judged')}_lines.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in L))
    return out


def abs87_scores():
    """Exp 87's absolute checker score (round 2, its frozen logistic model) per judged line and candidate form."""
    sys.path.insert(0, str(E / "87_writer"))
    os.environ["ROUND87"] = "2"
    import importlib
    import analyse87
    importlib.reload(analyse87)
    sys.path.insert(0, str(E / "81_heldout_scale"))
    import est81
    model = json.loads((E / "87_writer/out/checker87_r2.json").read_text())["model"]
    J = jl(E / "87_writer/out/run2/check_judged.jsonl")
    if not J:
        return {}
    sc = analyse87.score_of(model, J)
    out = defaultdict(dict)
    for r, s in zip(J, sc):
        f = est81.form(r["text"])
        out[r["key"]][f] = min(out[r["key"]].get(f, 1e9), float(s))
    return out


def learn():
    """Idea 2 / 3a: per journal, the test documents' IoU with the base library and each learned variant."""
    LD = Path(os.environ.get("LEARN95", OUT / "learn"))
    res = {}
    for f in sorted(LD.glob("eval_*.jsonl")):
        J = f.stem.split("_")[1]
        R = jl(f)
        scr = json.loads((LD / f"screen_{J}.json").read_text())
        base = scr["best"]
        d = dict(base=base, screen={k: v.get("median_iou") for k, v in scr["libs"].items()})
        for role in ("test", "learn"):
            by = defaultdict(dict)
            for r in R:
                if r["role"] == role and r["n_missing"] == 0:
                    by[r["lib"]][r["key"]] = r
            keys = set(by.get(base, {}))
            for lib in by:
                keys &= set(by[lib])
            keys = sorted(keys)
            stems = np.array([by[base][k]["stem"] for k in keys])
            dd = dict(lines=len(keys), docs=len(set(stems)))
            for lib in by:
                v = np.array([by[lib][k]["iou"] for k in keys])
                c = np.array([by[lib][k]["chamfer"] for k in keys])
                name = "base" if lib == base else lib.split(":")[-1]
                dd[name] = dict(median_iou=round(float(np.median(v)), 4), mean_iou=round(float(v.mean()), 4),
                                median_chamfer=round(float(np.median(c)), 3))
                if lib != base:
                    diff = v - np.array([by[base][k]["iou"] for k in keys])
                    dd[name]["gain_mean"] = round(float(diff.mean()), 4)
                    dd[name]["gain_ci_docs"] = _boot_ci(diff, stems)
            # 3a: one pen against edges, paired
            for suf in ("", "_r2"):
                lo = [l for l in by if l.endswith(":onepen" + suf)]
                le = [l for l in by if l.endswith(":edges" + suf)]
                if not (lo and le):
                    continue
                lo, le = lo[0], le[0]
                diff = np.array([by[lo][k]["iou"] - by[le][k]["iou"] for k in keys])
                dd["onepen_minus_edges" + suf] = dict(mean=round(float(diff.mean()), 4), ci_docs=_boot_ci(diff, stems))
            d[role] = dd
        for v in ("edges", "onepen", "edges_r2", "onepen_r2"):
            p = LD / f"{J}_{v}.json"
            if p.exists():
                m = json.loads(p.read_text())
                ti = list(m["train_iou"].values())
                d[f"trained_{v}"] = dict(learn_lines=m["learn_lines"], points=m["n_points"], params=m["n_params"],
                                         off_abs_mean_em=round(m["off_abs_mean"], 5),
                                         harvest_iou_ge_0_65=int(sum(x >= 0.65 for x in ti)),
                                         harvest_iou_ge_0_60=int(sum(x >= 0.60 for x in ti)))
        res[J] = d
    (OUT / "learn95.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "design":
        design()
    elif c == "contrast":
        contrast(sys.argv[2])
    elif c == "learn":
        learn()

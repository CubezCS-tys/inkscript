"""Experiment 81, step 5: estimated error rates of every reader on the held-out lines, from the agreement strata and
the blind judge; the judge's own consistency and its agreement with the owner; the warning at scale.

    out/venv/bin/python est81.py            -> out/est81.json (+ printed tables)

Truth of a judged line T: the candidate(s) the judge called right (verdict "match"), else the judge's own corrected
reading (verdict "none"); "unreadable" lines are left out of their stratum (reported).  A reader is wrong on a line
when its comparison form (agree81.form: no_punct) differs from T's; its letter errors are the edit distance.
Estimator (stratified, two strata x three eras): every frame line of stratum h carries weight N_h / n_h of the
judged lines of h.  Line error = weighted share of wrong lines; letters = weighted edit distance / weighted length of
T.  95% intervals: 1,000 bootstrap draws resampling PAGES within each stratum (lines of one page are not independent).
By ink type and journal: the same weights restricted to the judged lines of that domain (a domain-stratum cell with
no judged line borrows the stratum's mean; the count of such cells is reported).
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from rapidfuzz.distance import Levenshtein

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from agree81 import form  # noqa: E402

FOLD = os.environ.get("EST81_FOLD") == "1"
if FOLD:
    # the contested spelling conventions folded away (the lab scorer's `folded`: marks, hamza / alef forms, ى->ي,
    # ة->ه), after the no_punct form: what is left is letters, dots and word spaces
    sys.path.insert(0, str(HERE.parent.parent / "src"))
    import re as _re
    from inkscript.gold.text import folded as _folded
    from common77 import clean_label as _cl, to_visual as _tv

    def form(s):  # noqa: F811
        # folded BEFORE punctuation is removed: `no_punct`'s [^\w\s] would turn every vowel mark into a space
        return _re.sub(r"\s+", " ", _folded(_tv(_cl(s or "")))).strip()

READERS = ["azure", "argon", "v1", "v2", "v2b", "v3", "s2r", "fsig", "fsig4", "f78", "nuqta", "sig", "sig4"]
B = 1000
TWO_PHASE = ("v2b", "v3", "nuqta")


def load():
    rows = {d["key"]: d for d in map(json.loads, open(OUT / "readings81.jsonl", encoding="utf-8"))}
    S = {d["key"]: d for d in map(json.loads, open(OUT / "judge/sample.jsonl", encoding="utf-8"))}
    C = {}
    if (OUT / "judge/calib.jsonl").exists():
        C = {d["key"]: d for d in map(json.loads, open(OUT / "judge/calib.jsonl", encoding="utf-8"))}
    ans = {}
    for l in open(os.environ.get("EST81_ANSWERS", OUT / "judge/answers.jsonl"), encoding="utf-8"):
        d = json.loads(l)
        ans[d["key"]] = d                                  # last answer wins (none repeated)
    return rows, S, C, ans


def truth_of(s: dict, a: dict):
    """(T form or None, info)."""
    if a["verdict"] == "unreadable":
        return None, "unreadable"
    shown_f = [form(x) for x in s["shown"]]
    rf = form(a["reading"])
    if a["verdict"] == "match" and a["right_idx"]:
        R = sorted({shown_f[j] for j in a["right_idx"]})
        if len(R) == 1:
            return R[0], "match"
        return (rf if rf in R else R[0]), "match_several"
    if a["verdict"] == "match":                           # said match but named no candidate: use its reading
        return rf, "match_unnamed"
    return rf, "none"


V3T: dict[str, str] = {}     # lines re-judged with v3's reading shown: v3 is scored against that answer's truth


def line_eval(r: dict, T: str):
    out = {}
    for k in READERS:
        if k in r["readings"]:
            f = form(r["readings"][k])
            t = V3T.get(r["key"], T) if k == "v3" else T
            out[k] = (int(f != t), Levenshtein.distance(f, t))
    return out, len(T)


def _agg(cells, readers):
    """Per stratum: page-level sums, arrays [pages, readers] of (count with the reader, wrong, dist, len T)."""
    A = {}
    for h, L in cells.items():
        pages = sorted({x[0] for x in L})
        ix = {p: j for j, p in enumerate(pages)}
        S = np.zeros((4, len(pages), len(readers)))
        for pg, ev, n, _ in L:
            for r, k in enumerate(readers):
                if k in ev:
                    S[:, ix[pg], r] += (1, ev[k][0], ev[k][1], n)
        A[h] = S
    return A


def _boot_weights(A, rng, B_):
    """Multinomial page counts per stratum: h -> [B_, pages] (row 0 = the point estimate: all ones)."""
    g = np.random.default_rng(rng.randrange(1 << 30))
    W = {}
    for h, S in A.items():
        P = S.shape[1]
        w = g.multinomial(P, np.full(P, 1 / P), size=B_) if P else np.zeros((B_, 0))
        W[h] = np.vstack([np.ones((1, P)), w])
    return W


def _totals(A, W, frame_n):
    """-> arrays [B_+1, readers]: weighted wrong, dist, count, len (each stratum scaled to its frame size)."""
    tot = None
    for h, S in A.items():
        if not frame_n.get(h) or S.shape[1] == 0:
            continue
        c = W[h] @ S[0]                                   # [B, R] lines with the reader
        scale = frame_n[h] / np.maximum(c, 1e-9)
        t = np.stack([scale * (W[h] @ S[q]) for q in range(4)])   # [4, B, R]
        tot = t if tot is None else tot + t
    return tot


def estimate(cells, frame_n, key=None, boot=True, rng=None, readers=None):
    """cells: h -> list of (page, evals, n_T, line).  frame_n: h -> N_h.  Returns reader -> dict(line, letters, ci).
    Stratified weights N_h / n_h; the 95% interval resamples pages within each stratum (B draws)."""
    readers = readers or [k for k in READERS if any(k in x[1] for L in cells.values() for x in L)]
    A = _agg(cells, readers)
    W = _boot_weights(A, rng or random.Random(81), B if boot else 0)
    t = _totals(A, W, frame_n)
    res = {}
    if t is None:
        return res
    line = 100 * t[1] / np.maximum(t[0], 1e-9)
    let = 100 * t[2] / np.maximum(t[3], 1e-9)
    for r, k in enumerate(readers):
        if t[0][0, r] <= 0:
            continue
        res[k] = dict(line=round(float(line[0, r]), 3), letters=round(float(let[0, r]), 3))
        if boot:
            res[k]["line_ci"] = [round(float(np.percentile(line[1:, r], q)), 3) for q in (2.5, 97.5)]
            res[k]["letters_ci"] = [round(float(np.percentile(let[1:, r], q)), 3) for q in (2.5, 97.5)]
    return res


def paired(cells, frame_n, a, b, rng):
    """Difference a - b in letters and lines, on the lines both read, with the same page bootstrap."""
    sub = {h: [x for x in L if a in x[1] and b in x[1]] for h, L in cells.items()}
    A = _agg(sub, [a, b])
    W = _boot_weights(A, rng, B)
    t = _totals(A, W, frame_n)
    let = 100 * (t[2][:, 0] - t[2][:, 1]) / np.maximum(t[3][:, 0], 1e-9)
    line = 100 * (t[1][:, 0] - t[1][:, 1]) / np.maximum(t[0][:, 0], 1e-9)
    return dict(letters_diff=round(float(let[0]), 3), letters_ci=[round(float(np.percentile(let[1:], q)), 3) for q in (2.5, 97.5)],
                line_diff=round(float(line[0]), 3), line_ci=[round(float(np.percentile(line[1:], q)), 3) for q in (2.5, 97.5)])


def wprauc(score, y, w):
    o = np.argsort(-np.asarray(score), kind="stable")
    y, w = np.asarray(y, float)[o], np.asarray(w, float)[o]
    tp = np.cumsum(w * y)
    fl = np.cumsum(w)
    prec = tp / fl
    ap = float((prec * w * y).sum() / max(1e-9, (w * y).sum()))
    k = np.searchsorted(fl, 0.10 * fl[-1])
    return dict(pr_auc=round(ap, 3), precision_at10=round(float(tp[k] / fl[k]), 3),
                recall_at10=round(float(tp[k] / max(1e-9, tp[-1])), 3))


def main():
    rows, S, C, ans = load()
    frame = json.loads((OUT / "judge/frame.json").read_text())
    frame_n = {h: v["frame"] for h, v in frame.items()}
    if (OUT / "judge/answers_v3.jsonl").exists():
        X = {d["key"]: d for d in map(json.loads, open(OUT / "judge/v3extra.jsonl", encoding="utf-8"))}
        for d in map(json.loads, open(OUT / "judge/answers_v3.jsonl", encoding="utf-8")):
            T3, _ = truth_of(X[d["key"]], d)
            if T3 is not None:
                V3T[d["key"]] = T3
    EXCL = set()
    if os.environ.get("EST81_EXCL_HDR") == "1":
        # sensitivity: journal 0097's running header (a display face, light on a dark band, on every page) left out
        from diag81 import HDR, _fold
        for r in rows.values():
            if r["kind"] == "arabic" and r["jcode"] == "0097" and HDR.search(_fold(r["readings"]["azure"])):
                EXCL.add(r["key"])
                frame_n[f"{'agree' if r['agree_all'] else 'dispute'}|{r['era']}"] -= 1
        for k in EXCL:
            S.pop(k, None)
            C.pop(k, None)
            rows[k]["kind"] = "excluded"
    cells = defaultdict(list)
    info = Counter()
    judged = {}
    for k, s in S.items():
        if k not in ans:
            continue
        a = ans[k]
        T, why = truth_of(s, a)
        info[f"{s['stratum']}|{why}"] += 1
        if T is None:
            continue
        r = rows[k]
        ev, n = line_eval(r, T)
        h = f"{s['stratum']}|{s['era']}"
        cells[h].append((f"{r['stem']}_{r['page']}", ev, n, r))
        judged[k] = (T, a, s, r)
    rng = random.Random(81)
    out = dict(judged=dict(info), frame=frame, sampled_answered={h: len(v) for h, v in cells.items()})
    out["all"] = estimate(cells, frame_n, rng=rng)
    out["by_era"] = {}
    for e in ("pre-1950", "1950-1999", "2000+"):
        sub = {h: v for h, v in cells.items() if h.endswith("|" + e)}
        out["by_era"][e] = estimate(sub, frame_n, rng=rng)
    # domains (ink, journal): restrict the frame count and the judged lines to the domain
    A = [r for r in rows.values() if r["kind"] == "arabic"]
    for dom in ("ink", "jcode"):
        out[f"by_{dom}"] = {}
        borrowed = 0
        for v in sorted({r[dom] for r in A}):
            fn = Counter(f"{'agree' if r['agree_all'] else 'dispute'}|{r['era']}" for r in A if r[dom] == v)
            sub = {}
            for h in fn:
                L = [x for x in cells.get(h, []) if x[3][dom] == v]
                if not L and cells.get(h):
                    L = cells[h]
                    borrowed += 1
                sub[h] = L
            est = estimate(sub, dict(fn), boot=dom == "ink", rng=rng)
            est["_lines"] = sum(fn.values())
            est["_judged"] = sum(len([x for x in cells.get(h, []) if x[3][dom] == v]) for h in fn)
            out[f"by_{dom}"][v] = est
        out[f"by_{dom}_borrowed_cells"] = borrowed
    # two-phase estimate for the readers added after the strata were drawn (v2b: every line; Nuqta: the 3,000 judged
    # lines + 2,000 extra agree lines): within each AGREE stratum, the share of lines where the reader equals the
    # consensus comes from every line it read, the error given equal / not equal from the judged agree lines.
    out["two_phase"] = {}
    PEQ = {}
    for k in TWO_PHASE:
        for e in ("pre-1950", "1950-1999", "2000+"):
            P1 = [r for r in A if r["era"] == e and r["agree_all"] and k in r["readings"]]
            PEQ[(k, f"agree|{e}")] = sum(form(r["readings"][k]) == form(r["readings"]["azure"]) for r in P1) / max(1, len(P1))
    out["two_phase_peq"] = {f"{k}|{h}": round(v, 4) for (k, h), v in PEQ.items()}
    for k in TWO_PHASE:
        out["two_phase"][k] = {}
        for e in ("all", "pre-1950", "1950-1999", "2000+"):
            def point(C):
                num = den = dist = ln = 0.0
                for h, L in C.items():
                    if e != "all" and not h.endswith("|" + e):
                        continue
                    N = frame_n.get(h, 0)
                    J_ = [x for x in L if k in x[1]]
                    if not J_ or not N:
                        continue
                    if h.startswith("agree"):
                        peq = PEQ[(k, h)]
                        for eq, share in ((True, peq), (False, 1 - peq)):
                            G = [x for x in J_ if (form(x[3]["readings"][k]) == form(x[3]["readings"]["azure"])) == eq]
                            if not G:
                                G = J_
                            w = N * share / len(G)
                            for _, ev, n, _ in G:
                                num += w * ev[k][0]
                                dist += w * ev[k][1]
                                den += w
                                ln += w * n
                    else:
                        w = N / len(J_)
                        for _, ev, n, _ in J_:
                            num += w * ev[k][0]
                            dist += w * ev[k][1]
                            den += w
                            ln += w * n
                return (100 * num / max(1e-9, den), 100 * dist / max(1e-9, ln))
            est = point(cells)
            bypage = {h: defaultdict(list) for h in cells}
            for h, L in cells.items():
                for x in L:
                    bypage[h][x[0]].append(x)
            D = []
            for _ in range(300):
                Cb = {h: [x for q in (rng.choice(list(P)) for _ in P) for x in P[q]] if P else [] for h, P in bypage.items()}
                D.append(point(Cb))
            D = np.array(D)
            out["two_phase"][k][e] = dict(line=round(est[0], 3), letters=round(est[1], 3),
                                          line_ci=[round(float(np.percentile(D[:, 0], q)), 3) for q in (2.5, 97.5)],
                                          letters_ci=[round(float(np.percentile(D[:, 1], q)), 3) for q in (2.5, 97.5)])
    # paired differences: ours vs Azure
    out["paired_vs_azure"] = {}
    for k in ("v1", "v2", "v2b", "v3", "s2r", "fsig", "fsig4", "f78", "argon", "nuqta"):
        out["paired_vs_azure"][k] = {"all": paired(cells, frame_n, k, "azure", rng)}
        for e in ("pre-1950", "1950-1999", "2000+"):
            sub = {h: v for h, v in cells.items() if h.endswith("|" + e)}
            out["paired_vs_azure"][k][e] = paired(sub, frame_n, k, "azure", rng)
    out["paired_fusion"] = {"fsig_minus_v1": paired(cells, frame_n, "fsig", "v1", rng),
                            "fsig4_minus_v1": paired(cells, frame_n, "fsig4", "v1", rng),
                            "f78_minus_v1": paired(cells, frame_n, "f78", "v1", rng)}
    # ---- the judge's own consistency
    cons = Counter()
    for k, (T, a, s, r) in judged.items():
        st = s["stratum"]
        b = form(a["blind"])
        cons[f"{st}|n"] += 1
        cons[f"{st}|blind_eq_final"] += b == form(a["reading"])
        cons[f"{st}|blind_eq_T"] += b == T
        cons[f"{st}|blind_eq_azure"] += b == form(r["readings"]["azure"])
        cons[f"{st}|blind_eq_v1"] += b == form(r["readings"]["v1"])
        cons[f"{st}|verdict_none"] += a["verdict"] == "none"
        cons[f"{st}|blind_in_shown"] += b in {form(x) for x in s["shown"]}
        if a["verdict"] == "match":
            cons[f"{st}|final_reading_eq_right"] += form(a["reading"]) == T
            cons[f"{st}|match"] += 1
    out["judge_consistency"] = {k: v for k, v in sorted(cons.items())}
    agr = [x for x in judged.values() if x[2]["stratum"] == "agree"]
    out["agree_but_wrong"] = {e: dict(n=len([x for x in agr if x[3]["era"] == e]),
                                      wrong=sum(form(x[3]["readings"]["azure"]) != x[0] for x in agr if x[3]["era"] == e))
                              for e in ("pre-1950", "1950-1999", "2000+")}
    # ---- judge vs owner (yardstick lines, main sample + calibration sample)
    cal = []
    for k, s in list(S.items()) + list(C.items()):
        r = rows.get(k)
        if not r or r["truth"] is None or k not in ans:
            continue
        a = ans[k]
        T, why = truth_of(s, a)
        O = form(r["truth"])
        sh = [form(x) for x in s["shown"]]
        owner_right = [j for j, f in enumerate(sh) if f == O]
        cal.append(dict(key=k, stratum=s["stratum"], why=why, T_eq_owner=T == O if T is not None else None,
                        blind_eq_owner=form(a["blind"]) == O, owner_in_shown=bool(owner_right),
                        judge_right=a["right_idx"], owner_right=owner_right,
                        reader_wrong_owner={kk: int(form(r["readings"][kk]) != O) for kk in READERS if kk in r["readings"]},
                        reader_wrong_judge={kk: int(form(r["readings"][kk]) != T) for kk in READERS if kk in r["readings"]} if T is not None else None))
    (OUT / ("judge/calib_rows_folded.jsonl" if FOLD else "judge/calib_rows.jsonl")).write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cal), encoding="utf-8")
    cc = Counter()
    for c in cal:
        g = "agree" if c["stratum"].endswith("agree") else "dispute"
        cc[f"{g}|n"] += 1
        cc[f"{g}|T_eq_owner"] += bool(c["T_eq_owner"])
        cc[f"{g}|blind_eq_owner"] += c["blind_eq_owner"]
        cc[f"{g}|owner_in_shown"] += c["owner_in_shown"]
        cc[f"{g}|unreadable"] += c["T_eq_owner"] is None
        # per-candidate verdict vs the owner, when the owner's line is among the candidates or none is right
        cc[f"{g}|same_right_set"] += sorted(c["judge_right"]) == sorted(c["owner_right"])
    out["judge_vs_owner"] = dict(cc)
    # per reader: judge-truth error vs owner-truth error on the same yardstick lines
    jo = defaultdict(lambda: [0, 0, 0])
    for c in cal:
        if c["reader_wrong_judge"] is None:
            continue
        for kk, v in c["reader_wrong_owner"].items():
            jo[kk][0] += v
            jo[kk][1] += c["reader_wrong_judge"][kk]
            jo[kk][2] += 1
    out["judge_vs_owner_per_reader"] = {k: dict(lines=v[2], wrong_by_owner=v[0], wrong_by_judge=v[1]) for k, v in jo.items()}
    # ---- the estimate validated: estimated vs true error on the yardstick lines (owner truth)
    Y = [r for r in rows.values() if r["truth"] is not None and r["kind"] == "arabic"]
    true = {}
    for kk in READERS:
        L = [r for r in Y if kk in r["readings"]]
        if L:
            O = [form(r["truth"]) for r in L]
            F = [form(r["readings"][kk]) for r in L]
            true[kk] = dict(lines=len(L), line=round(100 * sum(f != o for f, o in zip(F, O)) / len(L), 3),
                            letters=round(100 * sum(Levenshtein.distance(f, o) for f, o in zip(F, O)) / sum(map(len, O)), 3))
    # estimate on the yardstick lines alone: agreed lines by the measured agree-but-wrong rate, disputes by the judge
    ycells, yframe = defaultdict(list), Counter()
    for r in Y:
        h = "agree" if r["agree_all"] else "dispute"
        yframe[h] += 1
        s = S.get(r["key"]) or C.get(r["key"])
        if s and r["key"] in ans:
            T, _ = truth_of(s, ans[r["key"]])
            if T is not None:
                ev, n = line_eval(r, T)
                ycells[h].append((f"{r['stem']}_{r['page']}", ev, n, r))
    out["yardstick_true"] = true
    out["yardstick_estimated"] = estimate(ycells, dict(yframe), rng=rng) if ycells else None
    out["yardstick_frame"] = dict(yframe)
    out["yardstick_judged"] = {h: len(v) for h, v in ycells.items()}
    # ---- the warning at scale: does a flag find v1's judged errors?
    W = defaultdict(list)
    ys, ws, eras = [], [], []
    for h, L in cells.items():
        w = frame_n[h] / len(L)
        for _, ev, n, r in L:
            ys.append(ev["v1"][0])
            ws.append(w)
            eras.append(r["era"])
            W["keys"].append(r["key"])
    img = {}
    want = set(W["keys"])
    for l in open(OUT / "read/image.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if d["key"] in want:
            img[d["key"]] = d
    sg = {}
    for l in open(OUT / "read/signal_p3t.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if d["key"] in want:
            sg[d["key"]] = d
    sg4 = {}
    for l in open(OUT / "read/signal_p4r.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if d["key"] in want:
            sg4[d["key"]] = d
    sc = defaultdict(list)
    for k in W["keys"]:
        d, r = img[k], rows[k]
        v1, g = r["readings"]["v1"], sg.get(k)
        i = d["cands"].index(v1) if v1 in d["cands"] else 0
        n = max(1, len(v1))
        ssig = (g["ssig"][i] if g and g["ssig"][i] is not None else -1e3)
        s78 = d["s78"][i] if d["s78"][i] is not None else -1e3
        sc["sig_ll"].append(-ssig / n)
        sc["sig_dis"].append(Levenshtein.distance(form(v1), form(r["readings"]["sig"])) / max(1, len(form(v1))))
        g4 = sg4.get(k)
        ssig4 = (g4["ssig"][i] if g4 and g4["ssig"][i] is not None else -1e3)
        sc["sig4_ll"].append(-ssig4 / n)
        sc["sig4_dis"].append(Levenshtein.distance(form(v1), form(r["readings"].get("sig4", ""))) / max(1, len(form(v1))))
        sc["ctl_conf"].append(1 - d["cmin77"])
        sc["ctl_dis"].append(Levenshtein.distance(form(v1), form(r["readings"]["s2r"])) / max(1, len(form(v1))))
        sc["ctl_ll"].append(-s78 / n)
    rk = {k: np.argsort(np.argsort(v)) for k, v in sc.items()}
    sc["sig_ll+ctl_dis"] = list(rk["sig_ll"] + rk["ctl_dis"])
    sc["ctl_ll+ctl_dis"] = list(rk["ctl_ll"] + rk["ctl_dis"])
    sc["sig4_ll+ctl_dis"] = list(rk["sig4_ll"] + rk["ctl_dis"])
    out["warning"] = dict(target="v1 greedy line wrong (judged truth)", judged_lines=len(ys),
                          weighted_error_rate=round(float(np.dot(ys, ws) / np.sum(ws)), 4),
                          scores={k: wprauc(v, ys, ws) for k, v in sc.items()},
                          by_era={e: {k: wprauc([x for x, ee in zip(v, eras) if ee == e], [y for y, ee in zip(ys, eras) if ee == e],
                                                [w for w, ee in zip(ws, eras) if ee == e]) for k, v in sc.items()}
                                  for e in ("pre-1950", "1950-1999", "2000+")})
    (OUT / os.environ.get("EST81_OUT", "est81.json")).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{'reader':8s} {'line%':>7s} {'95%':>16s} {'letters%':>9s} {'95%':>16s}")
    for k, v in sorted(out["all"].items(), key=lambda kv: kv[1]["letters"]):
        print(f"{k:8s} {v['line']:7.2f} {str(v['line_ci']):>16s} {v['letters']:9.3f} {str(v['letters_ci']):>16s}")
    for e, R in out["by_era"].items():
        print("==", e, {k: (v["letters"], v["letters_ci"]) for k, v in R.items()})
    print("paired vs azure", json.dumps(out["paired_vs_azure"], indent=0)[:1500])
    print("fusion", out["paired_fusion"])
    print("judge consistency", out["judge_consistency"])
    print("agree but wrong", out["agree_but_wrong"])
    print("judge vs owner", out["judge_vs_owner"])
    print("yard true", true)
    print("yard est", out["yardstick_estimated"])
    print("warning", json.dumps(out["warning"]["scores"]))


if __name__ == "__main__":
    main()

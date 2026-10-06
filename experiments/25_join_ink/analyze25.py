"""Before (today's src = experiment 21's after-boxes) / after (a variant) on 18's samples, rule "both"; the 112 stacked
letters of experiment 23; the control. 95% intervals: bootstrap over words (paired for differences).

    ../../.venv/bin/python analyze25.py VARIANT [VARIANT...]     -> out/summary25_<variant>.json
"""
import sys, json
from collections import Counter, defaultdict
import numpy as np
import judge25 as Q
J, R = Q.J, Q.R


def verdicts():
    g = J.cached(R.MODEL)
    return {k[:-3]: v for k, v in g.items() if k.endswith(":b2")}, {k[:-3]: v for k, v in g.items() if k.endswith(":b3")}


def ok(G, B, iid, letters, k):
    if iid not in G or iid not in B: return None
    b = dict(B[iid]); b["pos"] = J.marked_letters(b["marked"], letters)
    return bool(J.right(G[iid]) and J.right(b, k, True))


def boot(per, f, n=2000, seed=0):
    rnd = np.random.default_rng(seed); idx = np.arange(len(per)); v = [f([per[i] for i in rnd.choice(idx, len(idx))]) for _ in range(n)]
    return [round(100 * float(np.percentile(v, 2.5)), 1), round(100 * float(np.percentile(v, 97.5)), 1)]


def lr(ws): return sum(sum(x) for x in ws) / max(1, sum(len(x) for x in ws))
def wr(ws): return sum(all(x) for x in ws) / max(1, len(ws))


def paired(pb, pa, n=2000, seed=1):
    rnd = np.random.default_rng(seed); idx = np.arange(len(pb)); d = []
    for _ in range(n):
        ii = rnd.choice(idx, len(idx)); d.append(lr([pa[i] for i in ii]) - lr([pb[i] for i in ii]))
    return [round(100 * float(np.percentile(d, 2.5)), 1), round(100 * float(np.percentile(d, 97.5)), 1)]


def analyze(variant):
    S = json.load(open(Q.E18 / "out/sample.json")); G, B = verdicts()
    items, ref = Q.items_of(S, {"before": Q.before_cells(), "after": Q.after_cells(variant)})
    rows = []
    for s, ws in S.items():
        for w in ws:
            wid = R.wid(w)
            for k in range(1, len(w["text"]) + 1):
                ib, ia = ref.get((s, wid, "before", k)), ref.get((s, wid, "after", k))
                rows.append(dict(s=s, w=wid, doc=w["doc"], k=k, letter=w["text"][k - 1], ib=ib, ia=ia, moved=ib != ia,
                                 b=ok(G, B, ib, w["text"], k) if ib else None, a=ok(G, B, ia, w["text"], k) if ia else None))
    byw = defaultdict(list)
    for r in rows: byw[(r["s"], r["w"])].append(r)
    out = dict(variant=variant, samples={}, all={})
    def block(keys):
        keys = [kk for kk in keys if all(r["b"] is not None and r["a"] is not None for r in byw[kk])]
        pb = [[r["b"] for r in byw[kk]] for kk in keys]; pa = [[r["a"] for r in byw[kk]] for kk in keys]
        rr = [r for kk in keys for r in byw[kk]]
        return dict(words=len(keys), letters=len(rr),
                    before=dict(letter=round(100 * lr(pb), 1), letter_ci=boot(pb, lr), word=round(100 * wr(pb), 1), word_ci=boot(pb, wr)),
                    after=dict(letter=round(100 * lr(pa), 1), letter_ci=boot(pa, lr), word=round(100 * wr(pa), 1), word_ci=boot(pa, wr)),
                    diff_ci=paired(pb, pa), moved=sum(r["moved"] for r in rr),
                    better=sum(1 for r in rr if r["a"] and not r["b"]), worse=sum(1 for r in rr if r["b"] and not r["a"]),
                    words_better=sum(all(a) and not all(b) for a, b in zip(pa, pb)), words_worse=sum(all(b) and not all(a) for a, b in zip(pa, pb)))
    for s in S: out["samples"][s] = block([kk for kk in byw if kk[0] == s])
    out["all"] = block(list(byw))
    # the 112 stacked letters (experiment 23)
    st = json.load(open(Q.HERE.parent / "23_stacked/out/summary23.json"))["rows"]; idx = {(r["s"], r["w"], r["k"]): r for r in rows}
    sr = [dict(idx[(x["s"], x["w"], x["k"])], role=x["role"]) for x in st]; sr = [r for r in sr if r["a"] is not None and r["b"] is not None]
    sw = defaultdict(list)
    for r in sr: sw[r["w"]].append(r)
    pb = [[r["b"] for r in v] for v in sw.values()]; pa = [[r["a"] for r in v] for v in sw.values()]
    out["stacked"] = dict(n=len(sr), before=sum(r["b"] for r in sr), after=sum(r["a"] for r in sr), before_ci=boot(pb, lr), after_ci=boot(pa, lr), diff_ci=paired(pb, pa),
                          better=sum(1 for r in sr if r["a"] and not r["b"]), worse=sum(1 for r in sr if r["b"] and not r["a"]), moved=sum(r["moved"] for r in sr),
                          by_letter={L: dict(n=n, before=sum(r["b"] for r in sr if r["letter"] == L), after=sum(r["a"] for r in sr if r["letter"] == L)) for L, n in Counter(r["letter"] for r in sr).most_common(8)},
                          by_role={ro: dict(n=sum(1 for r in sr if r["role"] == ro), before=sum(r["b"] for r in sr if r["role"] == ro), after=sum(r["a"] for r in sr if r["role"] == ro)) for ro in ("upper", "lower")})
    wv = [r for r in rows if r["letter"] == "و" and r["k"] > 1 and r["a"] is not None and r["b"] is not None]
    out["waw_joined"] = dict(n=len(wv), before=sum(r["b"] for r in wv), after=sum(r["a"] for r in wv))
    # control: 21's boxes asked again
    ctl = [(r["ib"], r) for r in rows if r["ib"] and r["ib"] + "#r" in G and r["ib"] + "#r" in B]
    S_ = {R.wid(w): w for s, ws in S.items() for w in ws}
    c = Counter((r["b"], ok(G, B, i + "#r", S_[r["w"]]["text"], r["k"])) for i, r in ctl)
    out["control"] = dict(n=sum(c.values()), same=c[(True, True)] + c[(False, False)], right_then_wrong=c[(True, False)], wrong_then_right=c[(False, True)])
    out["rows"] = rows
    json.dump(out, open(Q.OUT / f"summary25_{variant}.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    for v in sys.argv[1:]: analyze(v)

"""Experiment 23's question again on top of a variant's cuts: the 112 stacked letters, highlighted full height vs
only over their own ink rows, with 23's judge set-up (18's judge; region wording; versions :r2/:r3; crop tinting
the box's own rows). 23's verdicts (today's cuts) are reused from its cache; only new crops are asked.

    ../../.venv/bin/python judge_heights.py VARIANT [--dry]      cap: this experiment's $10 (out/spend.jsonl)
    ../../.venv/bin/python judge_heights.py VARIANT --analyze    -> out/heights_summary_<variant>.json
"""
import sys, json, shutil
from collections import defaultdict
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; E23 = HERE.parent / "23_stacked"
sys.path.insert(0, str(E23))
import judge23 as Q23
J, R = Q23.J, Q23.R
J.CACHE = HERE / "out/judge_cache_region.jsonl"; J.SPEND = HERE / "out/spend.jsonl"; J.CAP = 10.0
if not J.CACHE.exists(): shutil.copy(E23 / "out/judge_cache.jsonl", J.CACHE)
import judge25 as Q25
J.CACHE = HERE / "out/judge_cache_region.jsonl"; J.SPEND = HERE / "out/spend.jsonl"; J.CAP = 10.0; J.VERSIONS = {"graded": ":r2", "blind": ":r3"}


def items(variant):
    S = json.load(open(Q23.E18 / "out/sample.json")); W = {R.wid(w): w for s, ws in S.items() for w in ws}
    cells = Q25.after_cells(variant); Y = json.load(open(HERE / f"out/heights_{variant}.json"))
    rows = json.load(open(E23 / "out/summary23.json"))["rows"]; out = {}; ref = []
    for r in rows:
        w = W[r["w"]]; c = cells[r["w"]][r["k"] - 1]; a, b = int(round(c[0])), int(round(c[1])); y0, y1 = Y[r["w"]][str(r["k"])]
        base = dict(doc=w["doc"], page=w["page"], box=w["box"], cell=[a, b], letters=list(w["text"]), k=r["k"])
        i0 = f"{r['w']}-{r['k']}-{a}-{b}"; i1 = f"{i0}-y{y0}-{y1}"
        out[i0] = dict(base, id=i0); out[i1] = dict(base, id=i1, ys=[y0, y1]); ref.append((r, i0, i1))
    return out, ref


def analyze(variant):
    its, ref = items(variant); c = J.cached(R.MODEL); res = []
    import analyze23 as A
    S = json.load(open(Q23.E18 / "out/sample.json")); W = {R.wid(w): w for s, ws in S.items() for w in ws}
    for r, i0, i1 in ref:
        L = list(W[r["w"]]["text"])
        res.append(dict(w=r["w"], k=r["k"], letter=r["letter"], role=r["role"], today_full=r["before"], today_own=r["after"],
                        full=A.verdict(c, i0, L, r["k"]), own=A.verdict(c, i1, L, r["k"])))
    ok = [x for x in res if None not in (x["full"], x["own"], x["today_full"], x["today_own"])]
    byw = defaultdict(list)
    for x in ok: byw[x["w"]].append(x)
    def rate(m):
        per = [[bool(x[m]) for x in v] for v in byw.values()]
        return dict(right=sum(map(sum, per)), n=sum(map(len, per)), rate=round(100 * A.lr(per), 1), ci=A.boot(per, A.lr))
    out = dict(n=len(ok), **{m: rate(m) for m in ("today_full", "today_own", "full", "own")})
    rnd = np.random.default_rng(1); Wl = list(byw); d = []
    for _ in range(2000):
        ii = rnd.choice(len(Wl), len(Wl)); xs = [x for i in ii for x in byw[Wl[i]]]
        d.append((sum(x["own"] for x in xs) - sum(x["today_full"] for x in xs)) / len(xs))
    out["own_minus_today_full_ci"] = [round(100 * float(np.percentile(d, 2.5)), 1), round(100 * float(np.percentile(d, 97.5)), 1)]
    out["by_role"] = {ro: {m: sum(bool(x[m]) for x in ok if x["role"] == ro) for m in ("today_full", "today_own", "full", "own")} | dict(n=sum(1 for x in ok if x["role"] == ro)) for ro in ("upper", "lower")}
    out["by_letter"] = {L: {m: sum(bool(x[m]) for x in ok if x["letter"] == L) for m in ("today_full", "today_own", "full", "own")} | dict(n=sum(1 for x in ok if x["letter"] == L)) for L in ("و", "ل", "ى", "ح", "ر", "ي")}
    out["rows"] = res
    json.dump(out, open(HERE / f"out/heights_summary_{variant}.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    v = sys.argv[1]
    if "--analyze" in sys.argv: analyze(v); sys.exit()
    its, ref = items(v); done = J.cached(R.MODEL)
    todo = [it for it in its.values() if not (it["id"] + ":r2" in done and it["id"] + ":r3" in done)]
    print(f"{v}: crops to ask {len(todo)} of {len(its)}; estimate ~${len(todo) * 0.0028:.2f}; spent so far ${J.spent():.3f}")
    if "--dry" in sys.argv or not todo: sys.exit()
    for mode in ("graded", "blind"):
        J.judge(todo, R.MODEL, tag=f"e25-heights-{v}-{mode}", mode=mode, max_usd=min(2.0, 9.5 - J.spent()))
    print("spent", J.spent())

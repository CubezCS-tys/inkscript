"""Before / after on stacked letters (judge23's verdicts, rule "both": graded EXACT and blind brackets exactly that
letter, clean), and over whole samples (every other letter keeps experiment 21's verdict for today's src, which is
the same box before and after). 95% intervals: bootstrap over words. -> out/summary23.json
    ../../.venv/bin/python analyze23.py
"""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; E21 = HERE.parent / "21_better_boxes"
import judge23 as Q
J, R = Q.J, Q.R


def boot(per, f, n=2000, seed=0):
    rnd = np.random.default_rng(seed); idx = np.arange(len(per))
    v = [f([per[i] for i in rnd.choice(idx, len(idx))]) for _ in range(n)]
    return [round(100 * float(np.percentile(v, 2.5)), 1), round(100 * float(np.percentile(v, 97.5)), 1)]


def lr(ws): return sum(sum(x) for x in ws) / max(1, sum(len(x) for x in ws))
def wr(ws): return sum(all(x) for x in ws) / max(1, len(ws))


def verdict(c, iid, letters, k, g="r2", b="r3"):
    G, B = c.get(f"{iid}:{g}"), c.get(f"{iid}:{b}")
    if not G or not B: return None
    bb = dict(B); bb["pos"] = J.marked_letters(bb["marked"], letters)
    return J.right(G) and J.right(bb, k, True)


def main():
    its, ref = Q.items(); c = J.cached(R.MODEL); c21 = {}
    for l in open(E21 / "out/judge_cache.jsonl"):
        d = json.loads(l)
        if d["model"] == R.MODEL: c21[d["id"]] = d
    S = json.load(open(Q.E18 / "out/sample.json")); Bx = json.load(open(Q.OUT / "boxes_cell.json"))
    rows21 = json.load(open(E21 / "out/summary21.json"))["rows"]; ok21 = {(r["s"], r["w"], r["k"]): r["ok"] for r in rows21 if r["m"] == "cutter_new"}
    st = []
    for (s, wid, k), (i0, i1) in ref.items():
        w = next(x for x in S[s] if R.wid(x) == wid); L = list(w["text"]); ys = Bx[wid]["ys"]
        # upper / lower: against the stacked neighbour (the adjacent stacked letter of the same word)
        nb = [j for j in (k - 1, k + 1) if 1 <= j <= len(L) and ys[j - 1]]
        cy = (ys[k - 1][0] + ys[k - 1][1]) / 2; ncy = min(((ys[j - 1][0] + ys[j - 1][1]) / 2 for j in nb), key=lambda v: abs(v - cy)) if nb else cy
        st.append(dict(s=s, w=wid, k=k, letter=L[k - 1], role="upper" if cy < ncy else "lower",
                       old=ok21.get((s, wid, k)), before=verdict(c, i0, L, k), after=verdict(c, i1, L, k), i0=i0, i1=i1, ys=ys[k - 1], doc=w["doc"]))
    ok = [r for r in st if r["before"] is not None and r["after"] is not None]
    out = dict(stacked=dict(letters=len(st), judged=len(ok)))
    words = sorted({r["w"] for r in ok})
    for m in ("old", "before", "after"):
        per = [[bool(r[m]) for r in ok if r["w"] == w and r[m] is not None] for w in words]
        out["stacked"][m] = dict(rate=round(100 * lr(per), 1), ci=boot(per, lr), right=sum(map(sum, per)), n=sum(map(len, per)))
    pa = Counter((r["before"], r["after"]) for r in ok)
    out["stacked"]["paired"] = dict(only_after=pa[(False, True)], only_before=pa[(True, False)], both=pa[(True, True)], neither=pa[(False, False)])
    rnd = np.random.default_rng(1); diffs = []
    byw = defaultdict(list)
    for r in ok: byw[r["w"]].append(r)
    W = list(byw)
    for _ in range(2000):
        ii = rnd.choice(len(W), len(W)); a = [byw[W[i]] for i in ii]
        diffs.append(sum(r["after"] for x in a for r in x) / sum(len(x) for x in a) - sum(r["before"] for x in a for r in x) / sum(len(x) for x in a))
    out["stacked"]["after_minus_before_ci"] = [round(100 * float(np.percentile(diffs, 2.5)), 1), round(100 * float(np.percentile(diffs, 97.5)), 1)]
    for role in ("upper", "lower"):
        rr = [r for r in ok if r["role"] == role]
        out["stacked"][role] = dict(n=len(rr), before=sum(r["before"] for r in rr), after=sum(r["after"] for r in rr), old=sum(bool(r["old"]) for r in rr))
    out["stacked"]["by_letter"] = {L: dict(n=n, before=sum(r["before"] for r in ok if r["letter"] == L), after=sum(r["after"] for r in ok if r["letter"] == L))
                                   for L, n in Counter(r["letter"] for r in ok).most_common(10)}
    # agreement of the changed prompt with 18/21's prompt on the same (before) boxes
    ag = Counter((bool(r["old"]), r["before"]) for r in ok if r["old"] is not None)
    out["stacked"]["prompt_agreement"] = dict(same=ag[(True, True)] + ag[(False, False)], old_only=ag[(True, False)], new_only=ag[(False, True)])
    # whole samples: other letters keep 21's verdict
    stk = {(r["s"], r["w"], r["k"]): r for r in ok}
    out["samples"] = {}
    for s, ws in S.items():
        per_b, per_a = [], []
        for w in ws:
            wid = R.wid(w); n = len(w["text"]); vb, va = [], []
            for k in range(1, n + 1):
                o = ok21.get((s, wid, k)); r = stk.get((s, wid, k))
                if r: vb.append(r["before"]); va.append(r["after"])
                elif o is not None: vb.append(o); va.append(o)
                else: vb = None; break
            if vb is None or len(vb) != n: continue
            per_b.append(vb); per_a.append(va)
        out["samples"][s] = dict(words=len(per_b), before=dict(letter=round(100 * lr(per_b), 1), letter_ci=boot(per_b, lr), word=round(100 * wr(per_b), 1), word_ci=boot(per_b, wr)),
                                 after=dict(letter=round(100 * lr(per_a), 1), letter_ci=boot(per_a, lr), word=round(100 * wr(per_a), 1), word_ci=boot(per_a, wr)),
                                 words_only_after=sum(all(a) and not all(b) for a, b in zip(per_a, per_b)), words_only_before=sum(all(b) and not all(a) for a, b in zip(per_a, per_b)))
    out["rows"] = st
    json.dump(out, open(HERE / "out/summary23.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

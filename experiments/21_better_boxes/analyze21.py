"""Before / after / equal slices on 18's sample words, rule "both" (graded EXACT and blind brackets exactly that
letter — 18's calibrated strict judge). 95% intervals: bootstrap over words. -> out/summary21.json

    ../../.venv/bin/python analyze21.py
"""
import json
from collections import Counter, defaultdict
import numpy as np
import judge21 as Q
J, R = Q.J, Q.R

NAMES = {"cutter": "before", "cutter_new": "after", "equal": "equal", "feeler": "feeler"}


def boot(per, f, n=2000, seed=0):
    rnd = np.random.default_rng(seed); idx = np.arange(len(per))
    v = [f([per[i] for i in rnd.choice(idx, len(idx))]) for _ in range(n)]
    return [round(100 * float(np.percentile(v, 2.5)), 1), round(100 * float(np.percentile(v, 97.5)), 1)]


def lr(ws): return sum(sum(x) for x in ws) / max(1, sum(len(x) for x in ws))
def wr(ws): return sum(all(x) for x in ws) / max(1, len(ws))


def verdicts():
    g = J.cached(R.MODEL)
    G = {k[:-3]: v for k, v in g.items() if k.endswith(":b2")}; B = {k[:-3]: v for k, v in g.items() if k.endswith(":b3")}
    return G, B


def ok(G, B, iid, letters, k):
    if iid not in G or iid not in B: return None
    b = dict(B[iid]); b["pos"] = J.marked_letters(b["marked"], letters)
    return J.right(G[iid]) and J.right(b, k, True)


def main():
    S = Q.sample_with_new(); items, ref = Q.items_of(S); G, B = verdicts()
    out = dict(samples={}, alef={}, control={}, changed={})
    rows = []
    for s, ws in S.items():
        for w in ws:
            for m in Q.METHODS[s]:
                if w.get(m) is None: continue
                for k in range(1, len(w["text"]) + 1):
                    iid = ref[(s, R.wid(w), m, k)]
                    rows.append(dict(s=s, w=R.wid(w), doc=w["doc"], m=m, k=k, n=len(w["text"]), letter=w["text"][k - 1], joined=w["joined"][k - 1],
                                     alef=(w["text"][k - 1] in "اأإآ" and k > 1 and w["piece_of"][k - 2] == w["piece_of"][k - 1]),
                                     iid=iid, ok=ok(G, B, iid, w["text"], k)))
    by = defaultdict(list)
    for r in rows: by[(r["s"], r["w"], r["m"])].append(r)
    complete = {key for key, v in by.items() if len(v) == v[0]["n"] and all(r["ok"] is not None for r in v)}
    for s in S:
        ms = [m for m in Q.METHODS[s]]
        wids = sorted({w for (ss, w, m) in complete if ss == s and all((s, w, mm) in complete for mm in ("cutter", "cutter_new", "equal"))})
        res = dict(words=len(wids))
        for m in ms:
            ww = [w for w in wids if (s, w, m) in complete]
            if len(ww) < len(wids): continue
            per = [[r["ok"] for r in sorted(by[(s, w, m)], key=lambda r: r["k"])] for w in wids]
            res[NAMES[m]] = dict(letters=sum(map(len, per)), letter=round(100 * lr(per), 1), letter_ci=boot(per, lr), word=round(100 * wr(per), 1), word_ci=boot(per, wr))
        pair = {}
        for m1, m2 in (("cutter_new", "cutter"), ("cutter_new", "equal"), ("cutter", "equal")):
            wa = Counter(); la = Counter()
            for w in wids:
                A = {r["k"]: r["ok"] for r in by[(s, w, m1)]}; Bk = {r["k"]: r["ok"] for r in by[(s, w, m2)]}
                wa[(all(A.values()), all(Bk.values()))] += 1
                for k in A: la[(A[k], Bk[k])] += 1
            pair[f"{NAMES[m1]}_vs_{NAMES[m2]}"] = dict(words_only_first=wa[(True, False)], words_only_second=wa[(False, True)],
                                                       letters_only_first=la[(True, False)], letters_only_second=la[(False, True)])
        # paired bootstrap of the letter-rate difference after - before
        rnd = np.random.default_rng(1); diffs = []
        pa = [[r["ok"] for r in by[(s, w, "cutter_new")]] for w in wids]; pb = [[r["ok"] for r in by[(s, w, "cutter")]] for w in wids]
        for _ in range(2000):
            ii = rnd.choice(len(wids), len(wids)); diffs.append(lr([pa[i] for i in ii]) - lr([pb[i] for i in ii]))
        res["after_minus_before_letters_ci"] = [round(100 * float(np.percentile(diffs, 2.5)), 1), round(100 * float(np.percentile(diffs, 97.5)), 1)]
        res["paired"] = pair
        res["by_doc"] = {d: {NAMES[m]: round(100 * lr([[r["ok"] for r in by[(s, w, m)]] for w in wids if w.startswith(d)]), 1) for m in ("cutter", "cutter_new", "equal")}
                         | dict(words=sum(w.startswith(d) for w in wids)) for d in sorted({w.split("-")[0] for w in wids})}
        nb = sum(1 for w in wids for rb, ra in zip(sorted(by[(s, w, "cutter")], key=lambda r: r["k"]), sorted(by[(s, w, "cutter_new")], key=lambda r: r["k"])) if rb["iid"] != ra["iid"])
        out["changed"][s] = dict(boxes_moved=nb, words_with_a_moved_box=sum(1 for w in wids if any(a["iid"] != b["iid"] for a, b in zip(sorted(by[(s, w, "cutter")], key=lambda r: r["k"]), sorted(by[(s, w, "cutter_new")], key=lambda r: r["k"])))))
        out["samples"][s] = res
        out["samples"][s]["word_ids"] = wids
    good = {(r["s"], r["w"]) for r in rows if all((r["s"], r["w"], m) in complete for m in ("cutter", "cutter_new", "equal"))}
    for m in ("cutter", "cutter_new", "equal"):
        rs = [r for r in rows if r["m"] == m and (r["s"], r["w"]) in good]
        out["alef"][NAMES[m]] = [sum(1 for r in rs if r["alef"] and r["ok"]), sum(1 for r in rs if r["alef"])]
        out.setdefault("worst", {})[NAMES[m]] = sorted(((l, sum(1 for r in rs if r["letter"] == l and not r["ok"]), sum(1 for r in rs if r["letter"] == l)) for l in {r["letter"] for r in rs}), key=lambda t: -t[1])[:8]
        out.setdefault("wrong", {})[NAMES[m]] = [sum(1 for r in rs if not r["ok"]), len(rs)]
    # control: 18's boxes asked again
    agree = Counter()
    for iid in [k for k in G if k.endswith("#r")]:
        o = iid[:-2]; it = items.get(o)
        if it is None or o not in G or o not in B or iid not in B: continue
        a = ok(G, B, o, it["letters"], it["k"]); b = ok(G, B, iid, it["letters"], it["k"])
        agree[(a, b)] += 1
    out["control"] = dict(n=sum(agree.values()), same=agree[(True, True)] + agree[(False, False)], right_then_wrong=agree[(True, False)], wrong_then_right=agree[(False, True)])
    out["rows"] = [{k: r[k] for k in ("s", "w", "m", "k", "ok", "iid", "letter", "alef")} for r in rows]
    json.dump(out, open(Q.OUT / "summary21.json", "w"), ensure_ascii=False, indent=1)
    for s, res in out["samples"].items():
        print(s, res["words"], "words;", {k: (v["letter"], v["letter_ci"], v["word"], v["word_ci"]) for k, v in res.items() if isinstance(v, dict) and "letter" in v})
        print("   after-before letters CI", res["after_minus_before_letters_ci"], res["paired"]); print("   by doc", res["by_doc"])
    print("alef", out["alef"]); print("wrong", out["wrong"]); print("changed", out["changed"]); print("control", out["control"])
    print("worst", out["worst"])


if __name__ == "__main__":
    main()

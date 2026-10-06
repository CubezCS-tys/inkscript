"""Score the judged boxes: per letter and per word, per method, with intervals; failures by kind. -> out/summary.json

A box is RIGHT when both questions say so (calibrated as the strictest combination, README): the graded question
answers EXACT, and the blind question brackets exactly that letter. The two questions alone are reported too.
Intervals: 95%, bootstrap over words (letters of one word are not independent), 2000 resamples.

    .venv/bin/python analyze.py
"""
import json
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
import judge18 as J, run18 as R

HERE = Path(__file__).resolve().parent; OUT = HERE / "out"
RULES = {"both": lambda g, b, k: J.right(g) and J.right(b, k, True),
         "graded": lambda g, b, k: J.right(g),
         "blind": lambda g, b, k: J.right(b, k, True)}


def boot(per_word, f, n=2000, seed=0):
    rnd = np.random.default_rng(seed); idx = np.arange(len(per_word)); vals = []
    for _ in range(n):
        s = [per_word[i] for i in rnd.choice(idx, len(idx))]; vals.append(f(s))
    return [round(100 * float(np.percentile(vals, 2.5)), 1), round(100 * float(np.percentile(vals, 97.5)), 1)]


def letter_rate(ws): return sum(sum(x) for x in ws) / max(1, sum(len(x) for x in ws))
def word_rate(ws): return sum(all(x) for x in ws) / max(1, len(ws))


def main():
    S = json.load(open(OUT / "sample.json")); items, ref = R.items_of(S)
    g = J.cached(R.MODEL); G = {k[:-3]: v for k, v in g.items() if k.endswith(":b2")}; B = {k[:-3]: v for k, v in g.items() if k.endswith(":b3")}
    for iid, v in B.items():                                                     # re-parse with the current marked_letters (tatweel fix)
        it = items.get(iid)
        if it is not None: v["pos"] = J.marked_letters(v["marked"], it["letters"])
    import calibrate as C
    for it in C.build(30):
        if it["id"] in B: B[it["id"]]["pos"] = J.marked_letters(B[it["id"]]["marked"], it["letters"])
    summary = dict(model=R.MODEL, samples={}, failures={}, words={})
    rows = []                                                                     # one per (sample, word, method, letter)
    for s, ws in S.items():
        for w in ws:
            for m in R.methods_of(s):
                for k in range(1, len(w["text"]) + 1):
                    iid = ref[(s, R.wid(w), m, k)]
                    if iid not in G or iid not in B: continue
                    rows.append(dict(s=s, w=R.wid(w), doc=w["doc"], m=m, k=k, n=len(w["text"]), letter=w["text"][k - 1], joined=w["joined"][k - 1],
                                     nchar=w["nchar"][k - 1], iid=iid, g=G[iid]["verdict"], b=B[iid].get("pos"), clean=B[iid].get("clean"),
                                     ok={r: f(G[iid], B[iid], k) for r, f in RULES.items()}))
    by = defaultdict(list)
    for r in rows: by[(r["s"], r["w"], r["m"])].append(r)
    complete = {key for key, v in by.items() if len(v) == int(v[0]["n"])}
    for s in S:
        res = {}
        wids = sorted({w for (ss, w, m) in complete if ss == s and all((s, w, mm) in complete for mm in R.methods_of(s))})
        for m in R.methods_of(s):
            res[m] = {}
            for rule in RULES:
                per = [[r["ok"][rule] for r in sorted(by[(s, w, m)], key=lambda r: r["k"])] for w in wids]
                jn = [[r["ok"][rule] for r in by[(s, w, m)] if r["joined"]] for w in wids]; jn = [x for x in jn if x]
                res[m][rule] = dict(words=len(per), letters=sum(map(len, per)), letter=round(100 * letter_rate(per), 1), letter_ci=boot(per, letter_rate),
                                    word=round(100 * word_rate(per), 1), word_ci=boot(per, word_rate),
                                    joined_letters=sum(map(len, jn)), joined_letter=round(100 * letter_rate(jn), 1), joined_ci=boot(jn, letter_rate) if jn else None)
        # paired: cutter vs equal (and feeler vs cutter) on the same words, rule "both"
        pair = {}
        for m1, m2 in (("cutter", "equal"), ("feeler", "equal"), ("feeler", "cutter")):
            if m1 not in R.methods_of(s): continue
            wa = Counter()
            for w in wids:
                a = all(r["ok"]["both"] for r in by[(s, w, m1)]); b = all(r["ok"]["both"] for r in by[(s, w, m2)])
                wa[(a, b)] += 1
            la = Counter()
            for w in wids:
                A = {r["k"]: r["ok"]["both"] for r in by[(s, w, m1)]}; Bk = {r["k"]: r["ok"]["both"] for r in by[(s, w, m2)]}
                for k in A: la[(A[k], Bk[k])] += 1
            pair[f"{m1}_vs_{m2}"] = dict(words_only_first=wa[(True, False)], words_only_second=wa[(False, True)], words_both=wa[(True, True)], words_neither=wa[(False, False)],
                                         letters_only_first=la[(True, False)], letters_only_second=la[(False, True)])
        res["paired"] = pair; res["word_ids"] = wids
        # by book
        res["by_doc"] = {}
        for d in sorted({w.split("-")[0] for w in wids}):
            dw = [w for w in wids if w.startswith(d)]
            res["by_doc"][d] = {m: dict(words=len(dw), letter=round(100 * letter_rate([[r["ok"]["both"] for r in by[(s, w, m)]] for w in dw]), 1),
                                        word=round(100 * word_rate([[r["ok"]["both"] for r in by[(s, w, m)]] for w in dw]), 1)) for m in R.methods_of(s)}
        summary["samples"][s] = res
    # failures, pooled over samples, rule "both"
    for m in ("cutter", "feeler", "equal"):
        rs = [r for r in rows if r["m"] == m and (r["s"], r["w"], r["m"]) in complete]
        bad = [r for r in rs if not r["ok"]["both"]]
        pos = lambda r: "first" if r["k"] == 1 else "last" if r["k"] == r["n"] else "middle"
        summary["failures"][m] = dict(
            letters=len(rs), wrong=len(bad),
            graded_verdict_of_wrong=dict(Counter(r["g"] for r in bad)),
            by_position={p: [sum(1 for r in bad if pos(r) == p), sum(1 for r in rs if pos(r) == p)] for p in ("first", "middle", "last")},
            joined=[sum(1 for r in bad if r["joined"]), sum(1 for r in rs if r["joined"])],
            separate=[sum(1 for r in bad if not r["joined"]), sum(1 for r in rs if not r["joined"])],
            uncut_glyph=[sum(1 for r in bad if r["nchar"] > 1), sum(1 for r in rs if r["nchar"] > 1)],
            worst_letters=sorted(((l, sum(1 for r in bad if r["letter"] == l), sum(1 for r in rs if r["letter"] == l)) for l in {r["letter"] for r in rs}),
                                 key=lambda t: -t[1] / max(8, t[2]))[:10])
    import calibrate as C
    cal = {}
    for it in C.build(30):
        gg, bb = G.get(it["id"]), B.get(it["id"])
        if gg is None or bb is None: continue
        d = cal.setdefault(it["kind"], dict(n=0, **{r: 0 for r in RULES}))
        d["n"] += 1
        for r, f in RULES.items(): d[r] += bool(f(gg, bb, it["k"]))
    summary["calibration"] = cal; summary["date"] = "2026-10-06"
    summary["words"] = {f"{r['s']}|{r['w']}|{r['m']}|{r['k']}": dict(ok=r["ok"]["both"], g=r["g"], b=r["b"], clean=r["clean"]) for r in rows}
    json.dump(summary, open(OUT / "summary.json", "w"), ensure_ascii=False, indent=1)
    for s, res in summary["samples"].items():
        print(s, {m: (res[m]["both"]["words"], res[m]["both"]["letter"], res[m]["both"]["letter_ci"], res[m]["both"]["word"], res[m]["both"]["word_ci"], res[m]["both"]["joined_letter"])
                  for m in R.methods_of(s)})
        print("  graded only", {m: (res[m]["graded"]["letter"], res[m]["graded"]["word"]) for m in R.methods_of(s)},
              " blind only", {m: (res[m]["blind"]["letter"], res[m]["blind"]["word"]) for m in R.methods_of(s)})
        print("  paired", res["paired"]); print("  by doc", res["by_doc"])
    for m, f in summary["failures"].items(): print(m, {k: v for k, v in f.items()})
    print("calibration (accepted as right):", cal)


if __name__ == "__main__":
    main()

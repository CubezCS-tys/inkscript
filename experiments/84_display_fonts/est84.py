"""Experiment 84, step B4b/c: new readers on experiment 81's held-out lines, scored with experiment 81's existing judged
truths (est81's machinery, imported unchanged; nothing in experiment 81's folder is written).

    ../81_heldout_scale/out/venv/bin/python est84.py NAME[=FILE] ...      -> out/est84.json (+ printed tables)

NAME=FILE: a reading file {key, NAME: text} (default out/read/image_NAME.jsonl).  "v3" is experiment 81's own.
- Truth of a judged line: est81.truth_of (the candidate the blind judge called right, else its corrected reading);
  where experiment 81 re-judged a line with v3's reading shown (answers_v3), that later truth is used for v3 AND for
  the new readers (est81 does the same for v3).
- Estimates: est81.estimate (stratified, agree/dispute x era, weights N_h / n_h, 95% page bootstrap) and the
  two-phase estimate for readers added after the strata (as est81 does for v2b, v3, Nuqta); paired differences
  against Azure and v3 (est81.paired).
- COVERAGE: a judged line is "covered" for a reader when its reading equals (est81's form) a candidate the judge saw
  (sample shown, v3extra shown) or the judged truth; otherwise its error is still measured against the truth, but the
  judge never looked at that reading.  On the whole frame: the share of lines whose reading equals one of the
  readings of experiment 81's readers (Azure, Argon, v1, v2, v2b, s2r, fsig, fsig4, f78, v3) or, for agree lines,
  the consensus.
- 2000+ diagnosis (diag81's buckets): journal 0097's running header (diag81.HDR) vs other lines, and dark-ground
  lines (diag81.polarity) vs others; letters wrong of each reader and of Azure, judged lines weighted as diag81.
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rapidfuzz.distance import Levenshtein

HERE = Path(__file__).resolve().parent
E81 = HERE.parent / "81_heldout_scale"
sys.path.insert(0, str(E81))
import est81  # noqa: E402
from est81 import form, truth_of  # noqa: E402

OUT = HERE / "out"
OLD = ["azure", "argon", "v1", "v2", "v2b", "s2r", "fsig", "fsig4", "f78", "v3"]


def main(specs):
    new = {}
    for s in specs:
        name, _, f = s.partition("=")
        new[name] = Path(f) if f else OUT / f"read/image_{name}.jsonl"
    rows, S, C, ans = est81.load()
    for name, f in new.items():
        if name in OLD:
            continue
        got = 0
        for d in map(json.loads, open(f, encoding="utf-8")):
            if d["key"] in rows:
                rows[d["key"]]["readings"][name] = d[name]
                got += 1
        print(name, got, "readings")
    names = [n for n in new if n not in OLD]
    est81.READERS = list(dict.fromkeys(est81.READERS + names))
    est81.TWO_PHASE = tuple(dict.fromkeys(list(est81.TWO_PHASE) + names))
    frame = json.loads((E81 / "out/judge/frame.json").read_text())
    frame_n = {h: v["frame"] for h, v in frame.items()}
    X = {d["key"]: d for d in map(json.loads, open(E81 / "out/judge/v3extra.jsonl", encoding="utf-8"))}
    LATE = {}
    for d in map(json.loads, open(E81 / "out/judge/answers_v3.jsonl", encoding="utf-8")):
        T3, _ = truth_of(X[d["key"]], d)
        if T3 is not None:
            LATE[d["key"]] = T3
    est81.V3T.update(LATE)
    late_readers = set(["v3"] + names)

    def line_eval(r, T):
        o = {}
        for k in est81.READERS:
            if k in r["readings"]:
                f = form(r["readings"][k])
                t = LATE.get(r["key"], T) if k in late_readers else T
                o[k] = (int(f != t), Levenshtein.distance(f, t))
        return o, len(T)
    est81.line_eval = line_eval

    cells, judged = defaultdict(list), {}
    for k, s in S.items():
        if k not in ans:
            continue
        T, why = truth_of(s, ans[k])
        if T is None:
            continue
        r = rows[k]
        ev, n = line_eval(r, T)
        cells[f"{s['stratum']}|{s['era']}"].append((f"{r['stem']}_{r['page']}", ev, n, r))
        judged[k] = (T, s, r)
    rng = random.Random(84)
    out = dict(readers=names, all=est81.estimate(cells, frame_n, rng=rng), by_era={})
    for e in ("pre-1950", "1950-1999", "2000+"):
        out["by_era"][e] = est81.estimate({h: v for h, v in cells.items() if h.endswith("|" + e)}, frame_n, rng=rng)
    # two-phase (est81's code path, re-run here for v3 and the new readers)
    A = [r for r in rows.values() if r["kind"] == "arabic"]
    out["two_phase"] = {}
    for k in ["v3"] + names:
        out["two_phase"][k] = {}
        PEQ = {}
        for e in ("pre-1950", "1950-1999", "2000+"):
            P1 = [r for r in A if r["era"] == e and r["agree_all"] and k in r["readings"]]
            PEQ[f"agree|{e}"] = sum(form(r["readings"][k]) == form(r["readings"]["azure"]) for r in P1) / max(1, len(P1))
        for e in ("all", "pre-1950", "1950-1999", "2000+"):
            num = den = dist = ln = 0.0
            for h, L in cells.items():
                if e != "all" and not h.endswith("|" + e):
                    continue
                N = frame_n.get(h, 0)
                J_ = [x for x in L if k in x[1]]
                if not J_ or not N:
                    continue
                groups = [(None, 1.0, J_)]
                if h.startswith("agree"):
                    groups = []
                    for eq, share in ((True, PEQ[h]), (False, 1 - PEQ[h])):
                        G = [x for x in J_ if (form(x[3]["readings"][k]) == form(x[3]["readings"]["azure"])) == eq] or J_
                        groups.append((eq, share, G))
                for _, share, G in groups:
                    w = N * share / len(G)
                    for _, ev, n, _ in G:
                        num += w * ev[k][0]
                        dist += w * ev[k][1]
                        den += w
                        ln += w * n
            out["two_phase"][k][e] = dict(line=round(100 * num / max(1e-9, den), 3), letters=round(100 * dist / max(1e-9, ln), 3))
        out["two_phase"][k]["peq_agree"] = {h: round(v, 4) for h, v in PEQ.items()}
    out["paired"] = {}
    for k in names:
        out["paired"][k] = {}
        for b in ("azure", "v3"):
            out["paired"][k][f"minus_{b}"] = {"all": est81.paired(cells, frame_n, k, b, rng)}
            for e in ("pre-1950", "1950-1999", "2000+"):
                out["paired"][k][f"minus_{b}"][e] = est81.paired({h: v for h, v in cells.items() if h.endswith("|" + e)},
                                                                frame_n, k, b, rng)
    # coverage
    cov = {}
    for k in ["v3"] + names:
        c = Counter()
        for key, (T, s, r) in judged.items():
            if k not in r["readings"]:
                continue
            seen = {form(x) for x in s["shown"]} | {T}
            if key in X:
                seen |= {form(x) for x in X[key]["shown"]}
            if key in LATE:
                seen.add(LATE[key])
            f = form(r["readings"][k])
            c[f"judged|{s['era']}|n"] += 1
            c[f"judged|{s['era']}|covered"] += f in seen
            c[f"judged|{s['era']}|eq_truth"] += f == LATE.get(key, T)
        for r in A:
            if k not in r["readings"]:
                continue
            f = form(r["readings"][k])
            others = {form(r["readings"][o]) for o in OLD if o in r["readings"] and o != k}
            c[f"frame|{r['era']}|n"] += 1
            c[f"frame|{r['era']}|eq_an_old_reader"] += f in others
            c[f"frame|{r['era']}|eq_v3"] += f == form(r["readings"].get("v3", ""))
        tot = defaultdict(lambda: [0, 0])
        res = {}
        for kk, v in c.items():
            part, era, what = kk.split("|")
            if what == "n":
                continue
            n = c[f"{part}|{era}|n"]
            res[f"{part}|{era}|{what}"] = round(100 * v / max(1, n), 2)
            tot[f"{part}|all|{what}"][0] += v
            tot[f"{part}|all|{what}"][1] += n
        for kk, (v, n) in tot.items():
            res[kk] = round(100 * v / max(1, n), 2)
        res["judged_lines"] = sum(v for kk, v in c.items() if kk.startswith("judged") and kk.endswith("|n"))
        res["frame_lines"] = sum(v for kk, v in c.items() if kk.startswith("frame") and kk.endswith("|n"))
        cov[k] = res
    out["coverage"] = cov
    out["diag"] = diag(rows, S, ans, frame, ["azure", "v3"] + names, LATE, late_readers)
    (OUT / os.environ.get("EST84_OUT", "est84.json")).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{'reader':10s} {'line%':>7s} {'letters%':>9s}  95%")
    for k, v in sorted(out["all"].items(), key=lambda kv: kv[1]["letters"]):
        if k in ["azure", "argon", "v1", "v3"] + names:
            print(f"{k:10s} {v['line']:7.2f} {v['letters']:9.3f}  {v['letters_ci']}")
    for k in ["v3"] + names:
        print("two-phase", k, {e: out["two_phase"][k][e]["letters"] for e in ("all", "pre-1950", "1950-1999", "2000+")})
    for k in names:
        print("paired", k, json.dumps(out["paired"][k])[:600])
        print("coverage", k, {kk: v for kk, v in cov[k].items() if "|all|" in kk or "lines" in kk})
    print("diag", json.dumps(out["diag"], ensure_ascii=False)[:3000])


def diag(rows, S, ans, frame, readers, LATE, late_readers):
    """diag81's weighting (judged lines of an era, weight frame / judged per stratum), letters wrong per bucket."""
    from diag81 import HDR, _fold, polarity
    res = {}
    for era in ("pre-1950", "1950-1999", "2000+"):
        cells = defaultdict(list)
        for k, s in S.items():
            if s["era"] != era or k not in ans:
                continue
            T, _ = truth_of(s, ans[k])
            if T is None:
                continue
            cells[f"{s['stratum']}|{era}"].append((k, T))
        B = defaultdict(lambda: defaultdict(float))
        for h, L in cells.items():
            w = frame[h]["frame"] / len(L)
            for k, T in L:
                r = rows[k]
                az = r["readings"]["azure"]
                b = []
                if era == "2000+":
                    b.append("header" if HDR.search(_fold(az)) else "other")
                    b.append("dark ground" if polarity(k) == "light text on dark" else "light ground")
                b.append("all")
                for bb in b:
                    for rd in readers:
                        if rd not in r["readings"]:
                            continue
                        t = LATE.get(k, T) if rd in late_readers else T
                        B[bb][rd] += w * Levenshtein.distance(form(r["readings"][rd]), t)
                        B[bb][rd + "|lines"] += w * (form(r["readings"][rd]) != t)
                    B[bb]["_len"] += w * len(T)
                    B[bb]["_w"] += w
                    B[bb]["_judged"] += 1
        res[era] = {bb: dict({rd: round(100 * v[rd] / max(1e-9, v["_len"]), 3) for rd in readers if rd in v},
                             **{rd + " lines%": round(100 * v[rd + "|lines"] / max(1e-9, v["_w"]), 2) for rd in readers if rd in v},
                             judged=int(v["_judged"]), frame_lines_est=round(v["_w"]))
                    for bb, v in B.items()}
    return res


if __name__ == "__main__":
    main(sys.argv[1:])

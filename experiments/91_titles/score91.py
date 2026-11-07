"""Experiment 91: score the new reader (t91) against the final reader (l28 = v7-28M) and Azure, the same ways as
experiments 89 and 90 (their code imported; nothing written in their folders).

    PY=../81_heldout_scale/out/venv/bin/python
    nice -n 19 ionice -c3 $PY score91.py heldout     experiment 81's held-out lines by era: est84 (est81's estimator,
                    two-phase) through score89's wrapper, strict / folded x with / without 0097's running header, with
                    the paired difference t91 - l28 (est81.paired)               -> out/heldout/est91_*.json
    nice -n 19 ionice -c3 $PY score91.py owner       the owner's 20 pages, original truth and rev2 (score88 via
                    score89.owner)                                              -> out/owner91.json
    nice -n 19 ionice -c3 $PY score91.py titles      experiment 89's held-out title test (250 judged lines): letters /
                    words / lines wrong, document-bootstrap CIs, paired t91 - l28 and t91 - Azure; truth = the latest
                    answer (exp 81, exp 89's rounds, then this experiment's judge91 answers) -> out/score91_titles.json
    nice -n 19 ionice -c3 $PY score91.py locked      experiment 90's LOCKED title lines (674), a SECOND READ (nothing
                    was tuned on them): est81's stratified estimator over experiment 90's title strata, with lines
                    where t91 or l28 (this folder's CPU read) differs from the agreed reading moved out of the agree
                    strata into census strata (every such line judged, by exp 90 or judge91) -> out/score91_locked.json
PRED files come from the host (out/host/pred/*_t91.jsonl) and from experiment 89 (l28).
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
E81 = E / "81_heldout_scale"
O89 = E / "89_final_reader/out"
O90 = E / "90_locked_final/out"
OUT = HERE / "out"
sys.path.insert(0, str(E / "89_final_reader"))
import score89  # noqa: E402

PRED = OUT / "host/pred"


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if Path(p).exists() else []


# ------------------------------------------------------------------------------------------------ held-out by era

def heldout():
    score89.OUT = OUT
    args = []
    for n, f in (("l28", O89 / "host/pred/t81_l28.jsonl"), ("t91", PRED / "t81_t91.jsonl")):
        args.append(f"{n}={score89.to_reading(n, str(f))}")
    for fold in ("0", "1"):
        for hdr in ("0", "1"):
            tag = ("folded" if fold == "1" else "strict") + ("_nohdr" if hdr == "1" else "")
            env = dict(os.environ, EST81_FOLD=fold, EST89_NOHDR=hdr, EST84_OUT=f"est91_{tag}.json")
            r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "_est", *args], env=env,
                               capture_output=True, text=True)
            (OUT / "heldout" / f"est91_{tag}.txt").write_text(r.stdout + r.stderr[-3000:])
            print(tag, "exit", r.returncode)


def _est(args):
    """score89._est with the extra paired difference t91 - l28."""
    score89.OUT = OUT
    sys.path.insert(0, str(E / "84_display_fonts"))
    sys.path.insert(0, str(E81))
    import est81
    orig = est81.paired
    EXTRA = {}

    def paired(cells, frame_n, a, b, rng):
        r = orig(cells, frame_n, a, b, rng)
        if b == "v3" and a == "t91":
            eras = {h.split("|")[1] for h in cells}
            e = eras.pop() if len(eras) == 1 else "all"
            names = {n for L in cells.values() for x in L for n in x[1]}
            if "l28" in names:
                EXTRA.setdefault("t91_minus_l28", {})[e] = orig(cells, frame_n, "t91", "l28", rng)
        return r
    est81.paired = paired
    score89._est(args)                              # its own wrapper (header rule, est84.main); our paired hook first
    f = OUT / "heldout" / os.environ.get("EST84_OUT", "est84.json")
    d = json.loads(f.read_text())
    d["paired_t91"] = EXTRA
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    print("paired_t91", json.dumps(EXTRA))


# ------------------------------------------------------------------------------------------------ owner's pages

def owner():
    score89.OUT = OUT
    score89.owner([f"l28={O89 / 'host/pred/test_l28.jsonl'}", f"t91={PRED / 'test_t91.jsonl'}"])
    (OUT / "owner89.json").rename(OUT / "owner91.json")


# ------------------------------------------------------------------------------------------------ held-out titles

def titles():
    from rapidfuzz.distance import Levenshtein
    strict, fold = score89.title_forms()
    T = score89.title_truths(strict)
    for a in jl(OUT / "judge/answers.jsonl"):                # this experiment's answers win (latest)
        s = {x["key"]: x for x in jl(OUT / "judge/sample.jsonl")}.get(a["key"])
        if not s or s["set"] != "heldout" or a["verdict"] == "unreadable":
            continue
        shown = s["shown"]
        if a["verdict"] == "match" and a["right_idx"]:
            R = [shown[j] for j in a["right_idx"] if j < len(shown)]
            Rf = {strict(x) for x in R}
            t = a["reading"] if (len(Rf) > 1 and strict(a["reading"]) in Rf) else R[0]
        else:
            t = a["reading"]
        T[a["key"]] = (t, shown, "judge91")
    rows = {d["key"]: d for d in jl(O89 / "titles/titles89.jsonl")}
    bad = {d["key"] for d in json.loads((O89 / "titles/not_titles.json").read_text())["lines"]}
    rd = {k: {"azure": d["azure"]} for k, d in rows.items() if k not in bad}
    for n, f in (("l28", O89 / "pred/titles_l28.jsonl"), ("t91", PRED / "titles_t91.jsonl")):
        for x in jl(f):
            if x["key"] in rd:
                rd[x["key"]][n] = x["pred"]
    readers = ("azure", "l28", "t91")
    rng = random.Random(91)
    res = dict(lines_in_test=len(rd), with_truth=sum(k in T for k in rd),
               truth_source=dict(Counter(T[k][2] for k in rd if k in T)))
    groups = {"all": lambda d: True, "pre-1950": lambda d: d["era"] == "pre-1950",
              "1950-1999": lambda d: d["era"] == "1950-1999", "2000+": lambda d: d["era"] == "2000+",
              "without 0097": lambda d: d["jcode"] != "0097", "journal 0097": lambda d: d["jcode"] == "0097"}
    for fname, F in (("strict", strict), ("folded", fold)):
        out = {}
        for g, sel in groups.items():
            keys = [k for k in rd if k in T and sel(rows[k]) and all(n in rd[k] for n in readers)]
            if not keys:
                continue
            docs = defaultdict(list)
            for k in keys:
                docs[rows[k]["stem"]].append(k)
            dl = list(docs)
            draws = [[k for dd in (rng.choice(dl) for _ in dl) for k in docs[dd]] for _ in range(1000)]
            E_ = {n: {k: (Levenshtein.distance(F(rd[k][n]), F(T[k][0])), len(F(T[k][0])),
                          Levenshtein.distance(F(rd[k][n]).split(), F(T[k][0]).split()), len(F(T[k][0]).split()),
                          int(F(rd[k][n]) != F(T[k][0])),
                          int(strict(rd[k][n]) in {strict(x) for x in T[k][1]} | {strict(T[k][0])}))
                      for k in keys} for n in readers}

            def let(n, kk):
                return 100 * sum(E_[n][k][0] for k in kk) / max(1, sum(E_[n][k][1] for k in kk))
            out[g] = {}
            for n in readers:
                bs = sorted(let(n, kk) for kk in draws)
                out[g][n] = dict(lines=len(keys), docs=len(docs), letters=round(let(n, keys), 3),
                                 letters_ci=[round(bs[25], 3), round(bs[974], 3)],
                                 words=round(100 * sum(E_[n][k][2] for k in keys) / max(1, sum(E_[n][k][3] for k in keys)), 3),
                                 lines_wrong=round(100 * sum(E_[n][k][4] for k in keys) / len(keys), 2),
                                 coverage=round(100 * sum(E_[n][k][5] for k in keys) / len(keys), 1))
            out[g]["paired"] = {}
            for a, b in (("t91", "l28"), ("t91", "azure"), ("l28", "azure")):
                bs = sorted(let(a, kk) - let(b, kk) for kk in draws)
                out[g]["paired"][f"{a}-{b}"] = dict(letters_diff=round(let(a, keys) - let(b, keys), 3),
                                                    ci=[round(bs[25], 3), round(bs[974], 3)])
        res[fname] = out
    (OUT / "score91_titles.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for fname in ("strict", "folded"):
        print(f"== held-out titles, {fname}: letters % (CI) / words / lines wrong / coverage")
        for g, v in res[fname].items():
            print(" ", g, {n: (x["letters"], x["letters_ci"], x["words"], x["lines_wrong"], x["coverage"], x["lines"])
                           for n, x in v.items() if n != "paired"}, v["paired"])
    return res


# ------------------------------------------------------------------------------------------------ locked titles

def locked():
    sys.path.insert(0, str(E / "90_locked_final"))
    sys.path.insert(0, str(E81))
    import est90
    import est81
    readers = ["azure", "final", "l28", "t91"]
    keys = set(json.loads((O90 / "title90.json").read_text()))
    rows = {d["key"]: d for d in jl(O90 / "readings90.jsonl")}
    for n in ("l28", "t91"):
        for x in jl(OUT / f"locked/image_{n}.jsonl"):
            rows[x["key"]]["readings"][n] = x[n]
    S = {d["key"]: d for d in jl(O90 / "judge/sample.jsonl")}
    A = {d["key"]: d for d in jl(O90 / "judge/answers.jsonl")}
    S91 = {d["key"]: d for d in jl(OUT / "judge/sample.jsonl") if d["set"] == "locked"}
    A91 = {d["key"]: d for d in jl(OUT / "judge/answers.jsonl") if d["key"] in S91}
    frame = json.loads((O90 / "judge/frame.json").read_text())
    res = {}
    for measure in ("strict", "folded"):
        est81.form = est90.sform if measure == "strict" else est90.fform
        est81.READERS = readers
        form = est81.form
        title_h = [h for h in frame if h.endswith("|title") or h.endswith("|title_x")]
        frame_n = {h: frame[h]["frame"] for h in title_h}
        cells = defaultdict(list)
        moved = Counter()
        unjudged_moved = 0
        for k in keys:
            r = rows.get(k)
            if r is None or r["kind"] != "arabic":
                continue
            rr = r["readings"]
            h = f"{'agree' if r['agree_all'] else 'dispute'}|{r['era']}|{r['group']}"
            if h not in frame_n:
                continue
            new_diff = r["agree_all"] and any(form(rr[n]) != form(rr["azure"]) for n in ("l28", "t91") if n in rr)
            if new_diff:                                    # census stratum: every such line is judged
                hh = h.replace("agree|", "agreeNEW|")
                frame_n[h] -= 1
                frame_n[hh] = frame_n.get(hh, 0) + 1
                moved[hh] += 1
                h = hh
            if k in A91:
                T, _ = est81.truth_of(S91[k], A91[k])
            elif k in S and k in A:
                T, _ = est81.truth_of(S[k], A[k])
            else:
                T = None
                unjudged_moved += new_diff
            if T is None:
                continue
            ev, n_ = est81.line_eval(r, T)
            cells[h].append((f"{r['stem']}_{r['page']}", ev, n_, r))
        rng = random.Random(91)
        o = dict(all=est81.estimate(dict(cells), frame_n, rng=rng, readers=readers),
                 paired={f"{a}-{b}": est81.paired(dict(cells), frame_n, a, b, rng)
                         for a, b in (("t91", "l28"), ("t91", "azure"), ("l28", "azure"), ("l28", "final"))},
                 by_set={}, judged=sum(len(v) for v in cells.values()), frame=sum(frame_n.values()),
                 moved_to_census=dict(moved), census_lines_without_truth=unjudged_moved)
        for st_, eras in (("journals", ("1980-1999", "2000+")), ("old", ("pre-1950", "1950-1979"))):
            sub = {h: v for h, v in cells.items() if any(f"|{e}|" in h for e in eras)}
            if sub:
                o["by_set"][st_] = dict(est=est81.estimate(sub, frame_n, rng=rng, readers=readers),
                                        paired=est81.paired(sub, frame_n, "t91", "l28", rng))
        res[measure] = o
    (OUT / "score91_locked.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for m in res:
        print("== locked titles", m, {k: (v["letters"], v.get("letters_ci"), v["line"]) for k, v in res[m]["all"].items()})
        print("   paired", res[m]["paired"])
        print("   judged", res[m]["judged"], "frame", res[m]["frame"], "moved", res[m]["moved_to_census"],
              "census without truth", res[m]["census_lines_without_truth"])
    return res


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "_est":
        _est(sys.argv[2:])
    else:
        {"heldout": heldout, "owner": owner, "titles": titles, "locked": locked}[c]()

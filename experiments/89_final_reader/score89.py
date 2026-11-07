"""Experiment 89, task 4: score every reader the same way.

    PY=../81_heldout_scale/out/venv/bin/python
    nice -n 19 ionice -c3 $PY score89.py heldout NAME=PRED ...   (b) exp 81's 22,783 held-out lines: experiment 84's
            est84 (est81's stratified estimator, two-phase, paired CIs, coverage) imported unchanged, run four ways:
            strict / folded (EST81_FOLD=1, set by this script in a subprocess), each with and without journal 0097's
            running header (est81's own EST81_EXCL_HDR rule: diag81.HDR on Azure's folded text; the header lines leave
            the frame AND the sample).  -> out/heldout/est89_{strict,folded}{,_nohdr}.json
    nice -n 19 ionice -c3 $PY score89.py titles                   (c) the title test -> out/titles/score89_titles.json
PRED files: train89.py infer output ({key, pred}) or a reading file ({key, NAME}).
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
E81 = E / "81_heldout_scale"
OUT = HERE / "out"


def to_reading(name: str, f: str) -> Path:
    """{key, pred} -> out/heldout/read/image_NAME.jsonl ({key, NAME})."""
    d = OUT / "heldout/read"
    d.mkdir(parents=True, exist_ok=True)
    dst = d / f"image_{name}.jsonl"
    with open(f, encoding="utf-8") as fi, open(dst, "w", encoding="utf-8") as fo:
        for l in fi:
            x = json.loads(l)
            fo.write(json.dumps({"key": x["key"], name: x.get(name, x.get("pred", ""))}, ensure_ascii=False) + "\n")
    return dst


def heldout(specs):
    args = []
    for s in specs:
        n, _, f = s.partition("=")
        args.append(f"{n}={to_reading(n, f)}")
    for fold in ("0", "1"):
        for hdr in ("0", "1"):
            tag = ("folded" if fold == "1" else "strict") + ("_nohdr" if hdr == "1" else "")
            env = dict(os.environ, EST81_FOLD=fold, EST89_NOHDR=hdr, EST84_OUT=f"est89_{tag}.json")
            r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "_est", *args], env=env,
                               capture_output=True, text=True)
            (OUT / "heldout" / f"est89_{tag}.txt").write_text(r.stdout + r.stderr[-3000:])
            print(tag, "exit", r.returncode)


def _est(args):
    """est84.main, writing to out/heldout; with EST89_NOHDR=1 the 0097 running-header lines leave frame and sample
    (est81's EST81_EXCL_HDR rule, which est84 does not have)."""
    sys.path.insert(0, str(E / "84_display_fonts"))
    sys.path.insert(0, str(E81))
    import est81
    import est84
    est84.OUT = OUT / "heldout"
    if os.environ.get("EST89_NOHDR") == "1":
        from diag81 import HDR, _fold
        load0 = est81.load
        tmp = Path(tempfile.mkdtemp(prefix="e81x", dir=OUT / "heldout"))
        (tmp / "out/judge").mkdir(parents=True)
        for f in ("v3extra.jsonl", "answers_v3.jsonl"):
            (tmp / "out/judge" / f).symlink_to(E81 / "out/judge" / f)
        frame = json.loads((E81 / "out/judge/frame.json").read_text())

        def load():
            rows, S, C, ans = load0()
            n = 0
            for r in rows.values():
                if r["kind"] == "arabic" and r["jcode"] == "0097" and HDR.search(_fold(r["readings"]["azure"])):
                    frame[f"{'agree' if r['agree_all'] else 'dispute'}|{r['era']}"]["frame"] -= 1
                    S.pop(r["key"], None)
                    C.pop(r["key"], None)
                    r["kind"] = "excluded"
                    n += 1
            (tmp / "out/judge/frame.json").write_text(json.dumps(frame))
            print("0097 header lines left out:", n)
            return rows, S, C, ans
        est81.load = load
        est84.E81 = tmp
    # extra paired differences est84 does not compute: l28 - v7 and v7 - v6r (est81.paired, same cells and bootstrap)
    EXTRA = {}
    orig = est81.paired
    want = {"l28": "v7", "v7": "v6r"}

    def paired(cells, frame_n, a, b, rng):
        r = orig(cells, frame_n, a, b, rng)
        if b == "v3" and a in want:
            eras = {h.split("|")[1] for h in cells}
            e = eras.pop() if len(eras) == 1 else "all"
            names = {n for L in cells.values() for x in L for n in x[1]}
            if want[a] in names:
                EXTRA.setdefault(f"{a}_minus_{want[a]}", {})[e] = orig(cells, frame_n, a, want[a], rng)
        return r
    est81.paired = paired
    est84.main(args)
    f = OUT / "heldout" / os.environ.get("EST84_OUT", "est84.json")
    d = json.loads(f.read_text())
    d["paired_extra"] = EXTRA
    f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    print("paired_extra", json.dumps(EXTRA))


# ------------------------------------------------------------------------------------------------ (a)+(d) owner's pages

def owner(specs):
    """The owner's 20 pages, original truth (rev1) and experiment 88's rev2 (printed «» restored): experiment 88's
    score88 functions imported (quote_counts as quotes84; cer = eval83's page scorer), written HERE
    (out/owner89.json), never in 88's folder.  Argon = Azure + Argon's fixes (pages.json), as eval83."""
    sys.path.insert(0, str(E / "88_truth_and_lock"))
    import score88
    files = {}
    for x in specs:
        n, f = x.split("=", 1)
        files[n] = Path(f)
    preds = {n: {d["key"]: d for d in map(json.loads, open(f, encoding="utf-8"))} for n, f in files.items()}
    base = score88.yardstick_pages("rev1")
    readings = {"azure": {l["key"]: l["azure"] for p in base for l in p["lines"]},
                "argon": {l["key"]: (l.get("argon") or l["azure"]) for p in base for l in p["lines"]}}
    readings.update({n: {k: d["pred"] for k, d in P.items()} for n, P in preds.items()})
    preds = {"argon": {k: {"key": k, "pred": v} for k, v in readings["argon"].items()}, **preds}
    out = {}
    for rev in ("rev1", "rev2"):
        pages = score88.yardstick_pages(rev)
        out[rev] = dict(quotes=score88.quote_counts(pages, readings), cer=score88.cer(pages, preds))
        print(f"== owner's 20 pages, truth {rev}")
        print(f"{'reader':8s} {'«» P':>8s} {'«» R':>8s} {'(( )) P':>8s} {'(( )) R':>8s} {'let%':>6s} {'wrd%':>6s} "
              f"{'let+p%':>7s}")
        for n in readings:
            q = out[rev]["quotes"][n]
            c = out[rev]["cer"].get(n, {})
            f = lambda d, w: f"{d['matched']}/{d[w]}"
            print(f"{n:8s} {f(q['«»'], 'written'):>8s} {f(q['«»'], 'in_truth'):>8s} {f(q['(( ))'], 'written'):>8s} "
                  f"{f(q['(( ))'], 'in_truth'):>8s} {c.get('letters', 0):6.2f} {c.get('words', 0):6.2f} "
                  f"{c.get('letters_punct', 0):7.2f}")
    (OUT / "owner89.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


# ------------------------------------------------------------------------------------------------ (c) titles

def title_forms():
    """est81's two comparison forms: strict (agree81.form = no_punct) and folded (est81 with EST81_FOLD=1)."""
    sys.path.insert(0, str(E81))
    sys.path.insert(0, str(E.parent / "src"))
    import re
    from agree81 import form as strict
    from common77 import clean_label, to_visual
    from inkscript.gold.text import folded

    def fold(s):
        return re.sub(r"\s+", " ", folded(to_visual(clean_label(s or "")))).strip()
    return strict, fold


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if Path(p).exists() else []


def title_truths(strict):
    """Per line: (truth text, shown candidates, source).  The latest judge89 round that answered the line, else
    experiment 81's answer.  Truth = the candidate the judge called right (if several differ, its own reading when it is
    one of them, else the first), else its corrected reading; unreadable -> no truth."""
    S81 = {x["key"]: x for x in jl(E81 / "out/judge/sample.jsonl")}
    ans = {}
    for a in jl(E81 / "out/judge/answers.jsonl"):
        if a["key"] in S81:
            ans[a["key"]] = (a, S81[a["key"]]["shown"], "exp81")
    for r in sorted(p.name for p in (OUT / "judge").iterdir() if p.is_dir()):
        for a in jl(OUT / "judge" / r / "answers.jsonl"):
            ans[a["key"]] = (a, a["shown"], f"judge89_{r}")
    T = {}
    for k, (a, shown, src) in ans.items():
        if a["verdict"] == "unreadable":
            continue
        if a["verdict"] == "match" and a["right_idx"]:
            R = [shown[j] for j in a["right_idx"] if j < len(shown)]
            Rf = {strict(x) for x in R}
            t = a["reading"] if (len(Rf) > 1 and strict(a["reading"]) in Rf) else R[0]
        else:
            t = a["reading"]
        T[k] = (t, shown, src)
    return T


def titles(readers=("azure", "argon", "v3", "v5", "v6r", "v7", "l28")):
    from rapidfuzz.distance import Levenshtein
    strict, fold = title_forms()
    rows = {d["key"]: d for d in jl(OUT / "titles/titles89.jsonl")}
    bad = {d["key"] for d in json.loads((OUT / "titles/not_titles.json").read_text())["lines"]}
    rd = {k: {"azure": d["azure"], **({"argon": d["argon"]} if d.get("argon") else {})} for k, d in rows.items()
          if k not in bad}
    for n in readers:
        for x in jl(OUT / f"pred/titles_{n}.jsonl"):
            if x["key"] in rd:
                rd[x["key"]][n] = x["pred"]
    T = title_truths(strict)
    res = {"lines_in_test": len(rd), "with_truth": sum(k in T for k in rd),
           "truth_source": dict(__import__("collections").Counter(T[k][2] for k in rd if k in T))}
    rng = random.Random(89)

    def words(a, b):
        return Levenshtein.distance(a.split(), b.split()), len(b.split())

    for fname, F in (("strict", strict), ("folded", fold)):
        out = {}
        groups = {"all": lambda d: True, "pre-1950": lambda d: d["era"] == "pre-1950",
                  "1950-1999": lambda d: d["era"] == "1950-1999", "2000+": lambda d: d["era"] == "2000+",
                  "2000+ without 0097": lambda d: d["era"] == "2000+" and d["jcode"] != "0097",
                  "journal 0097": lambda d: d["jcode"] == "0097", "all without 0097": lambda d: d["jcode"] != "0097"}
        for g, sel in groups.items():
            keys = [k for k in rd if k in T and sel(rows[k])]
            out[g] = {}
            for n in readers:
                ks = [k for k in keys if n in rd[k]]
                if not ks:
                    continue
                per = {}
                for k in ks:
                    t, shown, _ = T[k]
                    tf, rf = F(t), F(rd[k][n])
                    we, wn = words(rf, tf)
                    per[k] = (Levenshtein.distance(rf, tf), len(tf), we, wn, int(rf != tf),
                              int(strict(rd[k][n]) in {strict(x) for x in shown} | {strict(t)}))
                docs = defaultdict(list)
                for k in ks:
                    docs[rows[k]["stem"]].append(k)

                def agg(kk):
                    a = [per[k] for k in kk]
                    return (100 * sum(x[0] for x in a) / max(1, sum(x[1] for x in a)),
                            100 * sum(x[2] for x in a) / max(1, sum(x[3] for x in a)), 100 * sum(x[4] for x in a) / len(a))
                L, W, Ln = agg(ks)
                boot = []
                dl = list(docs)
                for _ in range(1000):
                    kk = [k for dd in (rng.choice(dl) for _ in dl) for k in docs[dd]]
                    boot.append(agg(kk)[0])
                boot.sort()
                out[g][n] = dict(lines=len(ks), docs=len(docs), letters=round(L, 3), words=round(W, 3),
                                 lines_wrong=round(Ln, 2), letters_ci=[round(boot[25], 3), round(boot[974], 3)],
                                 coverage=round(100 * sum(per[k][5] for k in ks) / len(ks), 1))
            # paired differences (same lines), page = document bootstrap
            pairs = [("v7", "azure"), ("v7", "v6r"), ("v7", "v3"), ("l28", "v7"), ("l28", "azure"), ("v6r", "azure")]
            out[g]["paired"] = {}
            for a, b in pairs:
                ks = [k for k in keys if a in rd[k] and b in rd[k]]
                if not ks:
                    continue
                docs = defaultdict(list)
                for k in ks:
                    docs[rows[k]["stem"]].append(k)

                def diff(kk):
                    ea = sum(Levenshtein.distance(F(rd[k][a]), F(T[k][0])) for k in kk)
                    eb = sum(Levenshtein.distance(F(rd[k][b]), F(T[k][0])) for k in kk)
                    n_ = sum(len(F(T[k][0])) for k in kk)
                    return 100 * (ea - eb) / max(1, n_)
                d0 = diff(ks)
                dl = list(docs)
                bs = sorted(diff([k for dd in (rng.choice(dl) for _ in dl) for k in docs[dd]]) for _ in range(1000))
                out[g]["paired"][f"{a}-{b}"] = dict(letters_diff=round(d0, 3), ci=[round(bs[25], 3), round(bs[974], 3)])
        res[fname] = out
    (OUT / "titles/score89_titles.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for fname in ("strict", "folded"):
        print(f"== titles, {fname} (letters % / words % / lines wrong % / coverage %)")
        for g, v in res[fname].items():
            print(" ", g, {n: (x["letters"], x["words"], x["lines_wrong"], x["coverage"], x["lines"])
                           for n, x in v.items() if n != "paired"})
    return res


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "heldout":
        heldout(sys.argv[2:])
    elif c == "owner":
        owner(sys.argv[2:])
    elif c == "titles":
        titles()
    elif c == "_est":
        _est(sys.argv[2:])

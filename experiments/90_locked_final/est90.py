"""Experiment 90, step 5: estimated error of every reader on the LOCKED lines (experiment 81's estimator, imported
unchanged), the judge's consistency, and the verdict against the reader exit criteria.

    ../81_heldout_scale/out/venv/bin/python est90.py      -> out/est90.json (strict and folded) + printed tables

Truth of a judged line: est81.truth_of (the candidate the judge called right, else its own reading; "unreadable" left
out).  Two measures, both after experiment 77's cleaning:
  strict = experiment 85's sform: punctuation removed, every letter, dot, hamza, ى/ي, ة/ه, vowel mark, digit and word
           space counted (experiment 81's strict measure with the scorer fix: marks stay marks);
  folded = experiment 81's EST81_FOLD form: marks, hamza / alef forms, ى->ي, ة->ه folded before punctuation goes.
Estimator: est81.estimate / est81.paired (stratified N_h / n_h, 1,000 page-bootstrap draws within each stratum);
strata = stratum (dispute / agree) x era x group (masthead / title / other), agree90.sample.
Views:
  masthead IN   every frame line;
  masthead OUT  the masthead strata dropped from frame and sample (the owner's decision: mastheads are layout's job);
  titles        the title strata alone;
  line types    domain estimates (est81's by_ink method: each stratum's frame count and judged lines restricted to the
                domain; a cell with no judged line borrows its stratum's lines, counted), masthead OUT.
Verdict (Plan m31, with m34: mastheads excluded, titles count):
  C1  ours <= Azure in letters AND lines overall (point estimate; the paired CI is reported), and not clearly worse in
      any era (the paired 95% CI of ours - Azure includes or is below 0);
  C2  no line type with ours' letter error more than 2x Azure's (display titles, light-on-dark, Latin, digits,
      rotated; point estimates, CIs reported).
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
sys.path.insert(0, str(E / "81_heldout_scale"))
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E / "85_disputes"))
sys.path.insert(0, str(E.parent / "src"))
import est81  # noqa: E402
from common77 import clean_label, to_visual  # noqa: E402
from common85 import sform  # noqa: E402
from inkscript.gold.text import folded as _folded  # noqa: E402

READERS = ["azure", "final", "v3", "v6r", "v7"]
OURS = ["final", "v3", "v6r"]
ERAS = ["pre-1950", "1950-1979", "1980-1999", "2000+"]
TYPES = ["title", "dark", "latin", "digits", "rotated"]


def fform(s):
    return re.sub(r"\s+", " ", _folded(to_visual(clean_label(s or "")))).strip()


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if Path(p).exists() else []


def run(measure: str):
    est81.form = sform if measure == "strict" else fform
    est81.READERS = READERS
    form = est81.form
    rows = {d["key"]: d for d in jl(OUT / "readings90.jsonl")}
    # v7 (experiment 89's runner-up), read after the sample was drawn: a REFERENCE only, scored against the judged
    # truths; never shown to the judge, so a judged line where it reads something no candidate had counts against it
    v7 = {d["key"]: d["v7"] for d in jl(OUT / "read/image_v7.jsonl")}
    for k, r in rows.items():
        if k in v7:
            r["readings"]["v7"] = v7[k]
    S = {d["key"]: d for d in jl(OUT / "judge/sample.jsonl")}
    ans = {d["key"]: d for d in jl(OUT / "judge/answers.jsonl")}
    frame = json.loads((OUT / "judge/frame.json").read_text())
    frame_n = {h: v["frame"] for h, v in frame.items()}
    cells, info, judged = defaultdict(list), Counter(), {}
    for k, s in S.items():
        if k not in ans:
            continue
        T, why = est81.truth_of(s, ans[k])
        info[f"{s['stratum']}|{why}"] += 1
        if T is None:
            continue
        r = rows[k]
        ev, n = est81.line_eval(r, T)
        h = f"{s['stratum']}|{s['era']}|{s['group']}"
        cells[h].append((f"{r['stem']}_{r['page']}", ev, n, r))
        judged[k] = (T, ans[k], s, r)
    rng = random.Random(90)

    def view(pred_h=lambda h: True):
        return {h: v for h, v in cells.items() if pred_h(h)}

    def fr(pred_h=lambda h: True):
        return {h: v for h, v in frame_n.items() if pred_h(h)}

    main_in = lambda h: not h.endswith("|title_x")  # noqa: E731
    main_out = lambda h: not h.endswith("|title_x") and not h.endswith("|masthead")  # noqa: E731
    out = dict(measure=measure, judged=dict(info), answered_by_stratum={h: len(v) for h, v in sorted(cells.items())})
    for name, p in (("masthead_in", main_in), ("masthead_out", main_out)):
        V, F = view(p), fr(p)
        o = dict(all=est81.estimate(V, F, rng=rng), by_era={}, by_set={}, paired_vs_azure={})
        for e in ERAS:
            sub = {h: v for h, v in V.items() if f"|{e}|" in h}
            if sub:
                o["by_era"][e] = est81.estimate(sub, F, rng=rng)
        for st_, eras in (("journals", ("1980-1999", "2000+")), ("old", ("pre-1950", "1950-1979"))):
            sub = {h: v for h, v in V.items() if any(f"|{e}|" in h for e in eras)}
            if sub:
                o["by_set"][st_] = est81.estimate(sub, F, rng=rng)
        for k in OURS:
            o["paired_vs_azure"][k] = {"all": est81.paired(V, F, k, "azure", rng)}
            for e in ERAS:
                sub = {h: v for h, v in V.items() if f"|{e}|" in h}
                if sub:
                    o["paired_vs_azure"][k][e] = est81.paired(sub, F, k, "azure", rng)
        o["final_minus_v3"] = est81.paired(V, F, "final", "v3", rng)
        o["final_minus_v6r"] = est81.paired(V, F, "final", "v6r", rng)
        out[name] = o
    # titles (the title strata alone) and mastheads alone
    # titles: every title line of page 1 of every locked document (on a test page: "title"; else "title_x"), as one
    # population; mastheads alone
    for name, gs in (("titles", ("|title", "|title_x")), ("mastheads", ("|masthead",))):
        V = view(lambda h, gs=gs: h.endswith(gs))
        if V:
            out[name] = dict(all=est81.estimate(V, frame_n, rng=rng),
                             paired_vs_azure={k: est81.paired(V, frame_n, k, "azure", rng) for k in OURS},
                             by_set={st_: est81.estimate({h: v for h, v in V.items() if any(f"|{e}|" in h for e in es)},
                                                         frame_n, rng=rng)
                                     for st_, es in (("journals", ("1980-1999", "2000+")), ("old", ("pre-1950", "1950-1979")))
                                     if any(f"|{e}|" in h for h in V for e in es)},
                             frame_lines=sum(v for h, v in frame_n.items() if h.endswith(gs)),
                             judged=sum(len(v) for v in V.values()))
    # line types, masthead OUT (domain estimates)
    A = [r for r in rows.values() if r["kind"] == "arabic" and r["group"] in ("title", "other")]
    out["line_types"] = {}
    if "titles" in out:                       # display titles: the title population above
        out["line_types"]["title"] = dict(out["titles"]["all"], _lines=out["titles"]["frame_lines"],
                                          _judged=out["titles"]["judged"], _borrowed_cells=0,
                                          _paired_final=out["titles"]["paired_vs_azure"]["final"])
    for t in [x for x in TYPES if x != "title"] + ["plain"]:
        inside = (lambda r, t=t: r["ltype"] == "plain") if t == "plain" else (lambda r, t=t: r["flags"][t])
        fn = Counter(f"{'agree' if r['agree_all'] else 'dispute'}|{r['era']}|{r['group']}" for r in A if inside(r))
        sub, borrowed, nj = {}, 0, 0
        for h in fn:
            L = [x for x in cells.get(h, []) if inside(x[3])]
            nj += len(L)
            if not L and cells.get(h):
                L, borrowed = cells[h], borrowed + 1
            sub[h] = L
        if not fn:
            continue
        est = est81.estimate(sub, dict(fn), rng=rng)
        est["_lines"], est["_judged"], est["_borrowed_cells"] = sum(fn.values()), nj, borrowed
        est["_paired_final"] = est81.paired(sub, dict(fn), "final", "azure", rng)
        out["line_types"][t] = est
    # the judge's own consistency
    cons = Counter()
    for k, (T, a, s, r) in judged.items():
        st_ = s["stratum"]
        b = form(a["blind"])
        cons[f"{st_}|n"] += 1
        cons[f"{st_}|blind_eq_final_answer"] += b == form(a["reading"])
        cons[f"{st_}|blind_eq_T"] += b == T
        cons[f"{st_}|blind_in_shown"] += b in {form(x) for x in s["shown"]}
        cons[f"{st_}|verdict_none"] += a["verdict"] == "none"
        for kk in READERS:
            cons[f"{st_}|T_eq_{kk}"] += form(r["readings"][kk]) == T
    out["judge_consistency"] = dict(sorted(cons.items()))
    cov = Counter()
    for k, (T, a, s, r) in judged.items():
        if "v7" in r["readings"]:
            cov["n"] += 1
            cov["v7_reading_shown_or_T"] += form(r["readings"]["v7"]) in ({form(x) for x in s["shown"]} | {T})
    out["v7_coverage"] = dict(cov)
    agr = [x for x in judged.values() if x[2]["stratum"] == "agree"]
    out["agree_but_wrong"] = {e: dict(n=sum(x[3]["era"] == e for x in agr),
                                      wrong=sum(x[3]["era"] == e and form(x[3]["readings"]["azure"]) != x[0] for x in agr))
                              for e in ERAS}
    return out


def verdict(R: dict) -> dict:
    st = R["strict"]["masthead_out"]
    v = {}
    a, f = st["all"]["azure"], st["all"]["final"]
    p = st["paired_vs_azure"]["final"]
    c1_all = f["letters"] <= a["letters"] and f["line"] <= a["line"]
    eras = {}
    for e, pe in p.items():
        if e == "all":
            continue
        eras[e] = dict(letters_diff=pe["letters_diff"], letters_ci=pe["letters_ci"], line_diff=pe["line_diff"],
                       line_ci=pe["line_ci"], not_clearly_worse=pe["letters_ci"][0] <= 0 and pe["line_ci"][0] <= 0,
                       ours_le_azure_point=pe["letters_diff"] <= 0 and pe["line_diff"] <= 0)
    v["C1"] = dict(overall=dict(final_letters=f["letters"], azure_letters=a["letters"], final_line=f["line"],
                                azure_line=a["line"], paired=p["all"], pass_=c1_all,
                                clearly_better=p["all"]["letters_ci"][1] < 0),
                   by_era=eras, pass_=c1_all and all(x["not_clearly_worse"] for x in eras.values()))
    types = {}
    for t, est in R["strict"]["line_types"].items():
        if t == "plain" or "final" not in est:
            continue
        ra = est["final"]["letters"] / max(1e-9, est["azure"]["letters"])
        types[t] = dict(final=est["final"]["letters"], final_ci=est["final"]["letters_ci"], azure=est["azure"]["letters"],
                        azure_ci=est["azure"]["letters_ci"], ratio=round(ra, 2), lines=est["_lines"], judged=est["_judged"],
                        pass_=ra <= 2.0)
    v["C2"] = dict(types=types, pass_=all(x["pass_"] for x in types.values()))
    v["PASS"] = v["C1"]["pass_"] and v["C2"]["pass_"]
    return v


def main():
    R = {m: run(m) for m in ("strict", "folded")}
    R["verdict"] = verdict(R)
    (OUT / "est90.json").write_text(json.dumps(R, ensure_ascii=False, indent=1))
    for m in ("strict", "folded"):
        for vname in ("masthead_in", "masthead_out"):
            o = R[m][vname]
            print(f"== {m} {vname}: all", {k: (v["letters"], v["letters_ci"], v["line"]) for k, v in o["all"].items()})
            for e, X in o["by_era"].items():
                print(f"   {e}", {k: (v["letters"], v["line"]) for k, v in X.items()})
        if "titles" in R[m]:
            print(f"== {m} titles", {k: (v["letters"], v["letters_ci"]) for k, v in R[m]["titles"]["all"].items()})
    print(json.dumps(R["verdict"], indent=1))


if __name__ == "__main__":
    main()

"""Experiment 90, step 3: every reader's reading of every locked line, the agreement map, the line types, and the
judge's sample (agree81.py's method).

    ../81_heldout_scale/out/venv/bin/python agree90.py map       -> out/readings90.jsonl, out/agree90.json
    ../81_heldout_scale/out/venv/bin/python agree90.py sample    -> out/judge/sample.jsonl, out/judge/frame.json
    ../81_heldout_scale/out/venv/bin/python agree90.py pilot     -> out/judge/pilot.jsonl (50 lines, not in the sample)

Readers: azure (its JSON from S3); final (experiment 89's pick, FINAL_READER.json); v3 (experiment 83); v6r
(experiment 85).  Argon: none exists for locked material (no locked document is among experiment 41's Argon pages).
Comparison form: STRICT = experiment 85's sform, i.e. experiment 81's `no_punct` with the scorer fix (punctuation
only removed; vowel marks stay marks).  Two readings AGREE when their strict forms are equal.
Frame: lines with an Arabic letter and arabic_share >= 0.5 (as experiment 81).
AGREE stratum = every reader shown to the judge agrees; DISPUTE = any differs.
Line types (fixed before any reader's reading of a locked line was looked at; from Azure's text, the polygon and the
48-px crop only):
  masthead   masthead90.py: a repeated band line (running header / journal logo) -- excluded from the reader's criteria
  title      experiment 89's title method (title89.py, imported unchanged; see TITLE below)
  dark       light text on a dark ground: the 48-px crop's median grey < 110 (diag81's threshold)
  latin      some Latin letters (arabic_share < 1)
  digits     any digit
  rotated    tilt over 3 degrees
  plain      none of the above
Sample (seed 90): strata = stratum (dispute / agree) x era x group, where group is masthead / title / other, so that
titles and mastheads (few lines) are judged in numbers; within a stratum, lines at random.  Every frame line of a
stratum carries the weight N_h / n_h, as experiment 81.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E / "85_disputes"))
sys.path.insert(0, str(E / "88_truth_and_lock"))
from common77 import clean_label  # noqa: E402
from common85 import sform as form  # noqa: E402

import os  # noqa: E402
# AGREE90_PRE=1: a map with v3 and v6r only (before experiment 89's pick), used ONLY to draw the 50-line pilot
OURS = ["v3", "v6r"] if os.environ.get("AGREE90_PRE") == "1" else ["final", "v3", "v6r"]
READERS = ["azure"] + OURS
SHOWN = ["azure"] + OURS
ERAS = ["pre-1950", "1950-1979", "1980-1999", "2000+"]
N_DIS, N_AGR, N_PILOT = 2500, 400, 50
GROUP_DIS = {"masthead": 150, "title": 60, "title_x": 300}   # disputes per group (all if fewer); the rest: other
GROUP_AGR = {"masthead": 40, "title": 15, "title_x": 60}
GROUPS = ["masthead", "title", "title_x", "other"]
# title   = a title line on a test page (part of the main frame);
# title_x = a title line on a page 1 that is not a test page (cut for the title test only; never in the main frame)


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if Path(p).exists() else []


def readings_of(name):
    f = OUT / f"read/image_{name}.jsonl"
    return {d["key"]: d[name] for d in jl(f)}


def crop_median():
    """key -> median grey of its 48-px crop."""
    import cv2
    import tarfile
    med = {}
    for t in sorted((OUT / "crops48").glob("test90-*.tar")):
        with tarfile.open(t) as tf:
            for m in tf:
                if m.name.endswith(".jpg"):
                    a = cv2.imdecode(np.frombuffer(tf.extractfile(m).read(), np.uint8), cv2.IMREAD_GRAYSCALE)
                    med[m.name[:-4]] = float(np.median(a))
    return med


def titles():
    """key -> True for title lines, by experiment 89's method (out/title90.json, written by title90.py)."""
    f = OUT / "title90.json"
    return set(json.loads(f.read_text())) if f.exists() else set()


def ltype(r, med, mast, tit):
    if r["key"] in mast:
        return "masthead"
    if r["key"] in tit:
        return "title"
    if med.get(r["key"], 255) < 110:
        return "dark"
    if (r["arabic_share"] or 0) < 1:
        return "latin"
    if any(c.isdigit() for c in r["azure"]):
        return "digits"
    if abs(r.get("ang") or 0) > 3:
        return "rotated"
    return "plain"


def flags(r, med, mast, tit):
    """Every type a line belongs to (types overlap; ltype gives the first in the order above)."""
    return dict(masthead=r["key"] in mast, title=r["key"] in tit, dark=med.get(r["key"], 255) < 110,
                latin=(r["arabic_share"] or 0) < 1, digits=any(c.isdigit() for c in r["azure"]),
                rotated=abs(r.get("ang") or 0) > 3)


def build_map():
    from locked_old import is_locked_any
    L = jl(OUT / "lines90.jsonl")
    R = {n: readings_of(n) for n in OURS}
    mast = json.loads((OUT / "masthead90.json").read_text())
    tit = titles()
    med = crop_median()
    rows, c = [], Counter()
    for r in L:
        assert is_locked_any(r["key"])
        c["lines"] += 1
        if not r["cut"] or any(r["key"] not in R[n] for n in OURS):
            c["not_cut_or_unread"] += 1
            continue
        s = r["arabic_share"]
        kind = "no_letters" if s is None else "mostly_latin" if s < 0.5 else "arabic"
        if r["set"] == "titles" and r["key"] not in tit:
            kind = "not_title"                 # cut as a title candidate, found not to be one when looked at
        rd = dict(azure=r["azure"], **{n: R[n][r["key"]] for n in OURS})
        F = {k: form(v) for k, v in rd.items()}
        agree_all = len({F[k] for k in SHOWN}) == 1
        fl = flags(r, med, mast, tit)
        rows.append(dict(key=r["key"], stem=r["stem"], page=r["page"], i=r["i"], jcode=r["jcode"], year=r["year"],
                         era=r["era"], set=r["set"], kind=kind, readings=rd, agree_all=agree_all,
                         ours_vs_azure={k: F[k] == F["azure"] for k in OURS}, ltype=ltype(r, med, mast, tit),
                         flags=fl, group="title_x" if r["set"] == "titles" else "masthead" if fl["masthead"]
                         else "title" if fl["title"] else "other",
                         median_grey=med.get(r["key"]), ang=r.get("ang"), W=r.get("W"), azure_len=len(F["azure"])))
    with open(OUT / "readings90.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    A = [r for r in rows if r["kind"] == "arabic" and r["set"] != "titles"]
    AT = [r for r in rows if r["kind"] == "arabic"]

    def pattern(r):
        o = r["ours_vs_azure"]
        n = sum(o.values())
        if n == len(OURS):
            return "ours = Azure"
        if n == 0:
            return "ours agree, Azure differs" if len({form(r["readings"][k]) for k in OURS}) == 1 else "ours split, none = Azure"
        return f"{n} of {len(OURS)} ours = Azure"

    def summ(X):
        n = len(X)
        if not n:
            return dict(lines=0)
        return dict(lines=n, patterns_pct={k: round(100 * v / n, 2) for k, v in Counter(map(pattern, X)).most_common()},
                    agree_with_azure_pct={k: round(100 * sum(r["ours_vs_azure"][k] for r in X) / n, 2) for k in OURS},
                    all_shown_agree_pct=round(100 * sum(r["agree_all"] for r in X) / n, 2))
    res = dict(counts=dict(c), kinds=dict(Counter(r["kind"] for r in rows)),
               all=summ(A), by_set={s: summ([r for r in A if r["set"] == s]) for s in ("journals", "old")},
               by_era={e: summ([r for r in A if r["era"] == e]) for e in ERAS},
               by_ltype={t: summ([r for r in A if r["ltype"] == t]) for t in sorted({r["ltype"] for r in A})},
               by_group={t: summ([r for r in AT if r["group"] == t]) for t in GROUPS},
               by_journal={j: summ([r for r in A if r["jcode"] == j]) for j in sorted({r["jcode"] for r in A if r["set"] == "journals"})},
               mostly_latin=summ([r for r in rows if r["kind"] == "mostly_latin"]),
               no_letters=summ([r for r in rows if r["kind"] == "no_letters"]))
    (OUT / "agree90.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: res[k] for k in ("counts", "kinds", "all", "by_era", "by_group")}, ensure_ascii=False, indent=1))


def shown_of(r: dict, rng: random.Random):
    """Distinct readings (strict form) of the shown readers, in random order; display text = the first reader with
    that form, in SHOWN order (Azure's punctuation first)."""
    seen = {}
    for k in SHOWN:
        seen.setdefault(form(r["readings"][k]), clean_label(r["readings"][k]))
    sh = list(seen.values())
    rng.shuffle(sh)
    return sh


def _alloc(pools: dict, n: int) -> dict:
    """Equal shares per era; an era with too few lines gives its quota to the others."""
    alloc = {e: min(len(pools[e]), n // len(pools)) for e in pools}
    left = n - sum(alloc.values())
    while left > 0:
        room = [e for e in pools if len(pools[e]) > alloc[e]]
        if not room:
            break
        for e in sorted(room, key=lambda e: len(pools[e]) - alloc[e]):
            add = min(left // len(room) or 1, len(pools[e]) - alloc[e], left)
            alloc[e] += add
            left -= add
            if left <= 0:
                break
    return alloc


def sample():
    rows = jl(OUT / "readings90.jsonl")
    pilot_keys = {s["key"] for s in jl(OUT / "judge/pilot.jsonl")}
    A = [r for r in rows if r["kind"] == "arabic" and r["key"] not in pilot_keys]     # the pilot lines are never sampled
    eras = [e for e in ERAS if any(r["era"] == e for r in A)]
    rng = random.Random(90)
    out, frame = [], {}
    pilot = set()
    for stratum, n, G in (("dispute", N_DIS, GROUP_DIS), ("agree", N_AGR, GROUP_AGR)):
        P = {(e, g): [r for r in A if r["era"] == e and r["group"] == g and (not r["agree_all"]) == (stratum == "dispute")]
             for e in eras for g in GROUPS}
        # group quotas first (masthead, title: all if fewer), split over eras; the rest goes to "other"
        k_g = {}
        for g, q in G.items():
            k_g.update({(e, g): v for e, v in _alloc({e: P[(e, g)] for e in eras}, q).items()})
        rest = n - sum(k_g.values())
        k_g.update({(e, "other"): v for e, v in _alloc({e: P[(e, "other")] for e in eras}, rest).items()})
        for (e, g), pool in P.items():
            k = k_g.get((e, g), 0)
            pick = rng.sample(pool, k)
            frame[f"{stratum}|{e}|{g}"] = dict(frame=len(pool), sampled=k)
            for r in pick:
                out.append(dict(key=r["key"], stem=r["stem"], page=r["page"], i=r["i"], era=e, group=g,
                                stratum=stratum, set=r["set"], shown=shown_of(r, rng)))
    rng.shuffle(out)
    (OUT / "judge").mkdir(parents=True, exist_ok=True)
    with open(OUT / "judge/sample.jsonl", "w", encoding="utf-8") as f:
        for s in out:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    (OUT / "judge/frame.json").write_text(json.dumps(frame, indent=1))
    print(json.dumps(frame, indent=1), len(out))


def make_pilot():
    """50 dispute lines NOT in the sample (seed 9090), for the cost and format check; standard calls."""
    rows = jl(OUT / "readings90.jsonl")
    assert not (OUT / "judge/sample.jsonl").exists(), "the pilot is drawn before the sample"
    pool = [r for r in rows if r["kind"] == "arabic" and not r["agree_all"] and r["set"] != "titles"]
    rng = random.Random(9090)
    P = rng.sample(pool, min(N_PILOT, len(pool)))
    with open(OUT / "judge/pilot.jsonl", "w", encoding="utf-8") as f:
        for r in P:
            f.write(json.dumps(dict(key=r["key"], stem=r["stem"], page=r["page"], i=r["i"], era=r["era"], group=r["group"],
                                    stratum="pilot", set=r["set"], shown=shown_of(r, rng)), ensure_ascii=False) + "\n")
    print("pilot", len(P))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "map":
        build_map()
    elif c == "sample":
        sample()
    elif c == "pilot":
        make_pilot()

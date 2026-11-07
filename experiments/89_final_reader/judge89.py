"""Experiment 89: the blind-first Gemini judge on the TITLE test lines (paid; exp 89's Gemini cap $5, stop at $4.8).

    ../../.venv/bin/python judge89.py sample ROUND NAMES      write out/judge/ROUND/sample.jsonl: the title lines that
                                                              need a verdict, candidates = the distinct readings of NAMES
    ../../.venv/bin/python judge89.py submit ROUND RND N      one Batch job (judge85.submit): RND 1 blind, 2 verdict
    ../../.venv/bin/python judge89.py collect ROUND [wait]
    ../../.venv/bin/python judge89.py std ROUND               the same two turns as standard calls (judge85.pilot), for a
                                                              small round
    ../../.venv/bin/python judge89.py spent

Experiment 85's judge85.py imported and pointed at this folder: judge81's prompts and schemas verbatim,
gemini-3.8-flash, thinking low, temperature 0, two turns of one conversation (blind reading first; then the distinct
candidates, shuffled by key, lettered, unnamed).  Changes, all here, none in judge85.py:
  - its folder (out/judge/ROUND/, crops = out/titles/crops, the 96-px 300-dpi cuts as judge81);
  - its candidates: the line's "cands" list (distinct by judge85's comparison form sform);
  - its guard: these lines are HELD-OUT by design (the test), so the held-out check is replaced by the locked-test
    guard alone (experiment 84's journals + experiment 88's documents);
  - its stop line: $4.8 minus every other round's spend (one cap for the whole experiment).
Rounds: "a" = every title line exp 81 never judged, or judged without a reading of v5 / v6r among its candidates
(candidates Azure, Argon, v3, v5, v6r); "b" = after v7 and v7-28M, the lines where one of their readings was never
shown to the judge (every reader's reading shown).  Truth per line: the latest round that answered it, else exp 81's
answer (score89.py).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "85_disputes"))
sys.path.insert(0, str(E / "88_truth_and_lock"))
sys.path.insert(0, str(E / "84_display_fonts"))
import judge85 as J85  # noqa: E402
from common85 import sform  # noqa: E402

CAP, STOP = 5.0, 4.8
JD = HERE / "out/judge"


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if Path(p).exists() else []


def spent_all() -> float:
    return sum(d["usd"] for f in JD.glob("*/spend.jsonl") for d in jl(f))


def point(rnd: str):
    d = JD / rnd
    d.mkdir(parents=True, exist_ok=True)
    if not (d / "crops").exists():
        (d / "crops").symlink_to(HERE / "out/titles/crops")
    J85.J, J85.SPEND, J85.STATE = d, d / "spend.jsonl", d / "batch_state.json"
    J85.R1, J85.R2 = d / "blind.jsonl", d / "answers.jsonl"
    other = spent_all() - sum(x["usd"] for x in jl(d / "spend.jsonl"))
    J85.STOP_AT = STOP - other

    def guard(keys, what=""):
        try:
            from locked_old import assert_not_locked
        except Exception:  # noqa: BLE001
            from locked import assert_not_locked
        try:
            assert_not_locked(keys)
        except FileNotFoundError:                       # exp 88's list not written yet: the journal guard alone
            from locked import assert_not_locked as a84
            a84(keys)
    J85.guard = guard

    def shown_of(s):
        seen, out = set(), []
        for c in s["cands"]:
            f = sform(c)
            if f and f not in seen:
                seen.add(f)
                out.append(c)
        random.Random(s["key"]).shuffle(out)
        return out
    J85.shown_of = shown_of
    return d


def readings(names):
    T = {d["key"]: d for d in jl(HERE / "out/titles/titles89.jsonl")}
    bad = {d["key"] for d in json.loads((HERE / "out/titles/not_titles.json").read_text())["lines"]}
    R = {}
    for k, d in T.items():
        if k in bad:
            continue
        R[k] = dict(azure=d["azure"])
        if d.get("argon"):
            R[k]["argon"] = d["argon"]
    for n in names:
        if n in ("azure", "argon"):
            continue
        for x in jl(HERE / f"out/pred/titles_{n}.jsonl"):
            if x["key"] in R:
                R[x["key"]][n] = x["pred"]
    return R


def sample(rnd, names):
    d = point(rnd)
    R = readings(names)
    prev = {}                                     # earlier truths: exp 81's answers, then earlier rounds
    S81 = {x["key"]: x for x in jl(E / "81_heldout_scale/out/judge/sample.jsonl")}
    for a in jl(E / "81_heldout_scale/out/judge/answers.jsonl"):
        if a["key"] in R and a["key"] in S81:
            prev[a["key"]] = [sform(x) for x in S81[a["key"]]["shown"]]
    for r in sorted(p.name for p in JD.iterdir() if p.is_dir() and p.name < rnd):
        for a in jl(JD / r / "answers.jsonl"):
            prev[a["key"]] = [sform(x) for x in a["shown"]]
    rows = []
    for k, rd in sorted(R.items()):
        cands = [rd[n] for n in ["azure", "argon"] + list(names) if n in rd]
        if k in prev and all(sform(rd[n]) in prev[k] for n in names if n in rd):
            continue                              # every named reader's reading already judged
        rows.append(dict(key=k, cands=cands))
    with open(d / "sample.jsonl", "w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"round {rnd}: {len(rows)} of {len(R)} title lines to judge; {len(prev)} with an earlier truth")


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "sample":
        sample(sys.argv[2], sys.argv[3].split(","))
    elif c == "submit":
        point(sys.argv[2])
        J85.submit(int(sys.argv[3]), int(sys.argv[4]))
    elif c == "collect":
        point(sys.argv[2])
        J85.collect(len(sys.argv) > 3 and sys.argv[3] == "wait")
    elif c == "std":
        d = point(sys.argv[2])
        (d / "pilot.jsonl").write_text((d / "sample.jsonl").read_text())
        J85.pilot()
    elif c == "status":
        point(sys.argv[2])
        J85.status()
    elif c == "spent":
        print(f"exp 89 Gemini ${spent_all():.4f} of ${CAP}")

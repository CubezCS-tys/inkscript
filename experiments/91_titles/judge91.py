"""Experiment 91: the blind-first Gemini judge on TEST title lines whose new reading the judge never saw (paid;
exp 91's Gemini cap $3, no request past $2.8).

    ../../.venv/bin/python judge91.py sample      -> out/judge/sample.jsonl (both test sets), out/judge/crops/ (links)
    ../../.venv/bin/python judge91.py std         standard calls (the round is small), judge90's two turns
    ../../.venv/bin/python judge91.py spent

The judge is experiment 90's judge90.py, imported with its paths pointed here (judge81's BLIND and VERDICT prompts and
schemas verbatim, gemini-3.8-flash, thinking low, temperature 0, two turns of one conversation: the crop alone ->
its own transcription, then the distinct candidate readings, lettered in a shuffled order, unnamed).
Lines (fixed before any score of the new reader was looked at):
  held-out titles (experiment 89's 250 judged lines, `h|`): a line is judged again when t91's reading (judge85's
      sform) is neither a candidate the judge saw nor the truth; candidates = every reader's reading there (Azure,
      Argon, v3, v5, v6r, v7, l28, t91);
  locked titles (experiment 90's 674, `l|`, a second read): a judged line where t91's or l28's reading (this folder's
      CPU read) is neither shown nor the truth; and an UNJUDGED line (agree stratum, not sampled) where t91 or l28
      differs from the agreed reading; candidates = Azure, final, v3, v6r, l28, t91.
Truth of a re-judged line = this round's answer (latest answer wins, as experiments 81/89/90).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "90_locked_final"))
sys.path.insert(0, str(E / "85_disputes"))
sys.path.insert(0, str(E / "89_final_reader"))
import judge90 as J  # noqa: E402
from common85 import sform  # noqa: E402

JD = HERE / "out/judge"
J.J, J.SPEND, J.STATE, J.R1, J.R2 = JD, JD / "spend.jsonl", JD / "batch_state.json", JD / "blind.jsonl", JD / "answers.jsonl"
J.CAP, J.STOP_AT = 3.0, 2.8


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if Path(p).exists() else []


def shown_of(key, cands):
    seen, out = set(), []
    for c in cands:
        f = sform(c)
        if f and f not in seen:
            seen.add(f)
            out.append(c)
    random.Random(key).shuffle(out)
    return out


def heldout_rows():
    import score89
    strict, _ = score89.title_forms()
    T = score89.title_truths(strict)                       # experiment 89's truths (with exp 81's answers)
    O89 = E / "89_final_reader/out"
    rows = {d["key"]: d for d in jl(O89 / "titles/titles89.jsonl")}
    bad = {d["key"] for d in json.loads((O89 / "titles/not_titles.json").read_text())["lines"]}
    rd = {k: {"azure": d["azure"], **({"argon": d["argon"]} if d.get("argon") else {})} for k, d in rows.items()
          if k not in bad}
    for n in ("v3", "v5", "v6r", "v7", "l28"):
        for x in jl(O89 / f"pred/titles_{n}.jsonl"):
            if x["key"] in rd:
                rd[x["key"]][n] = x["pred"]
    for x in jl(HERE / "out/host/pred/titles_t91.jsonl"):
        if x["key"] in rd:
            rd[x["key"]]["t91"] = x["pred"]
    return rows, rd, T


def locked_rows():
    O90 = E / "90_locked_final/out"
    keys = set(json.loads((O90 / "title90.json").read_text()))
    R = {d["key"]: d for d in jl(O90 / "readings90.jsonl") if d["key"] in keys}
    for n in ("l28", "t91"):
        for x in jl(HERE / f"out/locked/image_{n}.jsonl"):
            if x["key"] in R:
                R[x["key"]]["readings"][n] = x[n]
    S = {d["key"]: d for d in jl(O90 / "judge/sample.jsonl")}
    A = {d["key"]: d for d in jl(O90 / "judge/answers.jsonl")}
    return R, S, A


def sample():
    from locked_old import is_locked_any
    sys.path.insert(0, str(E / "81_heldout_scale"))
    import est81
    from common85 import sform as sf
    JD.mkdir(parents=True, exist_ok=True)
    (JD / "crops").mkdir(exist_ok=True)
    out = []
    rows, rd, T = heldout_rows()
    for k, r in sorted(rd.items()):
        if k not in T or "t91" not in r:
            continue
        t, shown, _ = T[k]
        if sf(r["t91"]) in {sf(x) for x in shown} | {sf(t)}:
            continue
        cands = [r[n] for n in ("azure", "argon", "v3", "v5", "v6r", "v7", "l28", "t91") if n in r]
        out.append(dict(key=k, set="heldout", stratum="h", shown=shown_of(k, cands),
                        crop=str(E / "89_final_reader/out/titles/crops" / f"{k}.png")))
    R, S, A = locked_rows()
    est81.form = sf
    for k, r in sorted(R.items()):
        rr = r["readings"]
        if "t91" not in rr:
            continue
        mine = [rr[n] for n in ("t91", "l28") if n in rr]
        if k in S and k in A:
            Tf, _ = est81.truth_of(S[k], A[k])
            if Tf is None:
                continue
            if all(sf(x) in {sf(y) for y in S[k]["shown"]} | {Tf} for x in mine):
                continue
        elif k in S:
            continue                                       # sampled but never answered (refused): left out, as exp 90
        else:
            if all(sf(x) == sf(rr["azure"]) for x in mine) and r.get("agree_all"):
                continue
        assert is_locked_any(k)
        cands = [rr[n] for n in ("azure", "final", "v3", "v6r", "l28", "t91") if n in rr]
        out.append(dict(key=k, set="locked", stratum="l", shown=shown_of(k, cands),
                        crop=str(E / "90_locked_final/out/judge/crops" / f"{k}.png")))
    with open(JD / "sample.jsonl", "w", encoding="utf-8") as f:
        for s in out:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
            dst = JD / "crops" / f"{s['key']}.png"
            if not dst.exists():
                dst.symlink_to(s["crop"])
    from collections import Counter
    print(len(out), "lines to judge", Counter(s["set"] for s in out),
          "missing crops:", sum(not Path(s["crop"]).exists() for s in out))


def std():
    import shutil
    shutil.copyfile(JD / "sample.jsonl", JD / "pilot.jsonl")   # judge90.pilot() reads pilot.jsonl
    J.pilot()
    print(f"spent ${J.spent():.4f} of ${J.CAP}")


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "sample":
        sample()
    elif c == "std":
        std()
    elif c == "spent":
        print(f"exp 91 Gemini: ${J.spent():.4f} of ${J.CAP}")

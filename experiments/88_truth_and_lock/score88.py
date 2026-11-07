"""Experiment 88, task 1: score Azure, v3 and v5 on the owner's 20 pages, original truth (rev1) and rev2 («» restored).

    nice -n 19 ionice -c3 ../../.venv/bin/python score88.py [--truth rev1|rev2|both] [--pred NAME=FILE ...]
        -> out/score88.json

Readings are the existing reads of the test tar by each checkpoint (nothing is re-read):
  v3 = experiment 83's out/pred/test_v3.jsonl  (out/weights/v3/best.pt)
  v5 = experiment 84's out/pred/test_v5.jsonl  (out/weights/v5/last.pt)
Azure is the line text in pages.json.

Measures, punctuation INCLUDED:
  «» and (( )) precision / recall, counted as quotes84.py does (per line, matched = min(count in reading, count in
      truth); each « or » counts one, each (( or )) counts one);
  letters wrong with punctuation (`faithful` CER, page level, eval83's own score()), and without (the headline's
      `no_punct`, for reference: rev2 cannot move it, since it only changes punctuation).

How to select rev2 elsewhere: `from score88 import yardstick_pages; pages = yardstick_pages("rev2")` returns
experiment 77's pages.json records with each yardstick page's truth taken from yardstick_truth_rev2_quotes.jsonl
(same line count and order, so gold_pos is unchanged).  eval83/eval78 keep reading rev1 (their default is untouched).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
HERE = Path(__file__).resolve().parent
E = HERE.parent
TEST = E / "77_scratch_reader/out/test"
REV2 = TEST / "yardstick_truth_rev2_quotes.jsonl"
PREDS = {"v3": E / "83_reader_scale/out/pred/test_v3.jsonl", "v5": E / "84_display_fonts/out/pred/test_v5.jsonl"}
KINDS = {"«»": re.compile("[«»]"), "(( ))": re.compile(r"\(\(|\)\)")}


def yardstick_pages(rev: str = "rev1") -> list[dict]:
    """pages.json; with rev='rev2' the 20 yardstick truths are replaced by rev2 («» restored)."""
    pages = json.loads((TEST / "pages.json").read_text(encoding="utf-8"))
    if rev == "rev1":
        return pages
    assert rev == "rev2", rev
    R = {d["page_id"]: d for d in map(json.loads, open(REV2, encoding="utf-8"))}
    for p in pages:
        if p["set"] == "yardstick":
            t = R[p["page_id"]]["truth"]
            assert len(t) == len(p["truth"])
            p["truth"] = t
            p["truth_source"] += "; rev2 (lead, 2026-11-05, owner OK): printed «» restored"
    return pages


def quote_counts(pages, readings):
    """readings: name -> {line key: text}.  Returns name -> kind -> counts."""
    res = {}
    for name, R in readings.items():
        c = {k: [0, 0, 0] for k in KINDS}
        for p in (p for p in pages if p["set"] == "yardstick"):
            gp = {int(k): v for k, v in p["gold_pos"].items()}
            for ln in p["lines"]:
                if ln["i"] not in gp or ln["key"] not in R:
                    continue
                r, t = R[ln["key"]], p["truth"][gp[ln["i"]]]
                for k, rx in KINDS.items():
                    a, b = len(rx.findall(r)), len(rx.findall(t))
                    c[k][0] += min(a, b)
                    c[k][1] += a
                    c[k][2] += b
        res[name] = {k: dict(matched=v[0], written=v[1], in_truth=v[2],
                             precision=round(v[0] / v[1], 3) if v[1] else None,
                             recall=round(v[0] / v[2], 3) if v[2] else None) for k, v in c.items()}
    return res


def cer(pages, preds):
    sys.path.insert(0, str(E / "83_reader_scale"))
    import eval83                                    # read only: its order_lines / reader_lines / score / agg
    rows = {}
    for p in (p for p in pages if p["set"] == "yardstick"):
        RL = eval83.reader_lines(p, preds)
        order = eval83.order_lines(p)
        ref = "\n".join(p["truth"])
        for name in ["azure"] + list(preds):
            rows.setdefault(name, []).append(eval83.score("\n".join(RL[name][i] for i in order), ref))
    out = {}
    for n, v in rows.items():
        a = eval83.agg(v)
        out[n] = dict(letters_punct=a["letters_punct"], words_punct=a["words_punct"], letters=a["letters"],
                      words=a["words"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", default="both", choices=["rev1", "rev2", "both"])
    ap.add_argument("--pred", action="append", default=[])
    a = ap.parse_args()
    files = dict(PREDS)
    for s in a.pred:
        n, f = s.split("=", 1)
        files[n] = Path(f)
    preds = {n: {d["key"]: d for d in map(json.loads, open(f, encoding="utf-8"))} for n, f in files.items()}
    base = yardstick_pages("rev1")
    readings = {"azure": {l["key"]: l["azure"] for p in base for l in p["lines"]}}
    readings.update({n: {k: d["pred"] for k, d in P.items()} for n, P in preds.items()})
    out = {}
    for rev in (["rev1", "rev2"] if a.truth == "both" else [a.truth]):
        pages = yardstick_pages(rev)
        out[rev] = dict(quotes=quote_counts(pages, readings), cer=cer(pages, preds))
        print(f"\n== truth {rev}")
        print(f"{'reader':8s} {'«» P':>12s} {'«» R':>12s} {'(( )) P':>12s} {'(( )) R':>12s} {'let+p%':>7s} {'let%':>6s}")
        for n in readings:
            q, c = out[rev]["quotes"][n], out[rev]["cer"][n]
            f = lambda d, w: f"{d['matched']}/{d[w]}"
            print(f"{n:8s} {f(q['«»'], 'written'):>12s} {f(q['«»'], 'in_truth'):>12s} {f(q['(( ))'], 'written'):>12s} "
                  f"{f(q['(( ))'], 'in_truth'):>12s} {c['letters_punct']:7.2f} {c['letters']:6.2f}")
    (HERE / "out").mkdir(exist_ok=True)
    (HERE / "out/score88.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

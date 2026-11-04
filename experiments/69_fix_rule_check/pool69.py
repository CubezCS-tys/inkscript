"""Experiment 69, step 3e: the two runs pooled (run 1: v36 / nofix on 44 pages; run 2: v36r / nofixr on 30 of them).
    pool69.py   -> out/pooled.json + table.  Net = words right with the bullet minus without, by kind, with and without
    experiment 66's guard; 95% interval by resampling pages (a page's units from both runs move together)."""
import json
import random
from collections import defaultdict

import common69 as C

RUNS = [("score_rows_units.json", "v36", "nofix"), ("score_rows_units_r.json", "v36r", "nofixr")]


def rows():
    out = []
    for f, a, b in RUNS:
        for r in json.load(open(C.OUT / f, encoding="utf-8")):
            out.append(dict(page=r["page_key"], kind=r["kind"], poor=r["poor"],
                            A=r["right"][a], B=r["right"][b], Ag=r["right"][a + "+g"], Bg=r["right"][b + "+g"]))
    return out


def net(s, x, y):
    return sum(r[x] for r in s) - sum(r[y] for r in s)


def ci(s, x, y, n=4000, seed=69):
    by = defaultdict(list)
    for r in s:
        by[r["page"]].append(r)
    keys = sorted(by)
    rnd = random.Random(seed)
    v = sorted(net([r for k in (rnd.choice(keys) for _ in keys) for r in by[k]], x, y) for _ in range(n))
    return v[int(.025 * n)], v[int(.975 * n)]


def main():
    R = rows()
    res = {}
    subsets = {"all": R, "letters": [r for r in R if r["kind"] == "letters"],
               "letters, poor print": [r for r in R if r["kind"] == "letters" and r["poor"]],
               "letters, clean print": [r for r in R if r["kind"] == "letters" and not r["poor"]],
               "ortho": [r for r in R if r["kind"] == "ortho"], "punct": [r for r in R if r["kind"] == "punct"],
               "marks": [r for r in R if r["kind"] == "marks"]}
    for name, s in subsets.items():
        res[name] = dict(units=len(s), pages=len({r["page"] for r in s}),
                         bullet=dict(net=net(s, "A", "B"), ci=ci(s, "A", "B")),
                         bullet_with_guard=dict(net=net(s, "Ag", "Bg"), ci=ci(s, "Ag", "Bg")),
                         guard_with_bullet=dict(net=net(s, "Ag", "A"), ci=ci(s, "Ag", "A")),
                         guard_without_bullet=dict(net=net(s, "Bg", "B"), ci=ci(s, "Bg", "B")))
        v = res[name]
        print(f"{name:22s} units {v['units']:3d} pages {v['pages']:2d} | bullet {v['bullet']['net']:+3d} {v['bullet']['ci']}"
              f" | bullet+guard {v['bullet_with_guard']['net']:+3d} {v['bullet_with_guard']['ci']}"
              f" | guard (with bullet) {v['guard_with_bullet']['net']:+3d} {v['guard_with_bullet']['ci']}"
              f" | guard (without) {v['guard_without_bullet']['net']:+3d} {v['guard_without_bullet']['ci']}")
    C.jdump(C.OUT / "pooled.json", res)


if __name__ == "__main__":
    main()

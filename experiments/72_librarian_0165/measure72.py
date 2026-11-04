"""Experiment 72: before / after numbers for journal 0165 (read-only on two release DBs).

Uses experiment 70's measures unchanged (measure70.base / cross / shared; measure52.measure inside a set):
- 0165's institutions (org level, current posts, twin lines not counted), with a country, in 2+ articles, countries;
- 0165's cited works (cards its references land on), shared by 2+ of its articles;
- shared between 0130 and 0165: cited works, institutions, authors, coupling edges;
- held: the share of 0165's references (Quran and hadith out) whose card has an accepted best link to a Mandumah
  publication.

    python measure72.py BEFORE.db AFTER.db  -> out/numbers72.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter

from common72 import E, OUT, add_paths, wjs

add_paths(E / "70_gate2_pilot", E / "52_journal_gate1")
import measure52  # noqa: E402
import measure70  # noqa: E402


def numbers(db: str) -> dict:
    B = measure70.base(db)
    cur = B["cur"]
    J = {v["pub_id"] for v in cur.values() if v["journal_id"] == "J0130"}
    K = {v["pub_id"] for v in cur.values() if v["journal_id"] == "J0165"}
    stem = {v["pub_id"]: s for s, v in cur.items()}
    runs = sorted({cur[stem[p]]["run"] for p in K})
    m = measure52.measure(db, runs, {stem[p] for p in K})
    m.pop("_coupling_graph", None)
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    ctry = {r[0]: r[1] for r in c.execute("SELECT inst_id, country_code FROM institutions")}
    ik = set().union(*[B["inst"][p] for p in K])
    per = Counter(i for p in K for i in B["inst"][p])
    held = measure70.cross(B, K, set(), "none", None)
    sh = measure70.shared(B, J, K)
    works = {}
    for mm in B["refs"]:
        if B["vpub"].get(mm["version_id"]) in K and mm["cited_work_pk"] is not None:
            works.setdefault(mm["cited_work_pk"], set()).add(B["vpub"][mm["version_id"]])
    return dict(
        db=db,
        institutions=len(ik), with_country=sum(1 for i in ik if ctry.get(i)),
        countries=len({ctry[i] for i in ik if ctry.get(i)}), in_2plus_articles=sum(1 for v in per.values() if v >= 2),
        measure52_institutions={k: v for k, v in (m.get("institutions") or {}).items() if not isinstance(v, list)},
        cited_works=len(works), cited_works_2plus=sum(1 for v in works.values() if len(v) >= 2),
        references=held.get("references"), held=held.get("held"),
        held_share=round((held.get("held") or 0) / max(1, held.get("references") or 1), 4),
        shared_0130_0165=sh,
        measure52_works={k: v for k, v in (m.get("works") or m.get("cited_works") or {}).items()
                         if not isinstance(v, (list, dict))})


def main():
    before, after = sys.argv[1], sys.argv[2]
    out = dict(before=numbers(before), after=numbers(after))
    wjs(OUT / "numbers72.json", out)
    keys = ["institutions", "with_country", "countries", "in_2plus_articles", "cited_works", "cited_works_2plus",
            "references", "held", "held_share"]
    for k in keys:
        print(f"{k:22s} {out['before'][k]!s:>10} -> {out['after'][k]!s:>10}")
    for k in ("cited_works", "institutions", "authors", "coupling_edges"):
        print(f"shared {k:15s} {out['before']['shared_0130_0165'][k]!s:>10} -> {out['after']['shared_0130_0165'][k]!s:>10}")


if __name__ == "__main__":
    main()

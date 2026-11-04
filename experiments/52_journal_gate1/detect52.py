"""Experiment 52: the correction load. The Desk's three detectors (experiment 49, desk/detectors.py, imported
unchanged) run on a platform v2 database read-only, and their tasks are COUNTED, never written: no PostgreSQL
connection is opened, so the live Desk schema is not touched. Each task is attributed to the articles whose stems
its candidates name.

    .venv/bin/python experiments/52_journal_gate1/detect52.py --db DB --runs RUN [RUN ...] --label NAME
        -> out/detect_<label>.json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "49_correction_desk"))
from desk import db as DDB  # noqa: E402
from desk.detectors import DETECTORS, load_cards  # noqa: E402
from desk.reading import Reading  # noqa: E402

STEM = re.compile(r"\b\d{4}-\d{3}-\d{3}-\d{3}\b")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--label", required=True)
    a = ap.parse_args()
    c = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    q = ",".join("?" * len(a.runs))
    stems = {r[0] for r in c.execute(f"SELECT stem FROM versions WHERE is_current = 1 AND run IN ({q})", a.runs)}
    R = Reading(DDB.open_reading(a.db))
    cards = load_cards(R)
    out = dict(db=a.db, runs=a.runs, articles=len(stems), kinds={}, examples={})
    per_art = Counter()
    for kind, fn in DETECTORS.items():
        found = fn(R, cards)
        mine = []
        for t in found:
            s = set(STEM.findall(json.dumps(t, ensure_ascii=False, default=str))) & stems
            if s:
                mine.append(t)
                for x in s:
                    per_art[x] += 1
        out["kinds"][kind] = dict(found_in_db=len(found), touching_set=len(mine),
                                  per_article=round(len(mine) / max(1, len(stems)), 3))
        out["examples"][kind] = [dict(question=t["question"], guess=t.get("guess"), keys=t["keys"]) for t in mine[:5]]
    tot = sum(v["touching_set"] for v in out["kinds"].values())
    out["tasks_touching_set"] = tot
    out["per_article"] = round(tot / max(1, len(stems)), 3)
    out["articles_with_a_task"] = len(per_art)
    (HERE / "out" / f"detect_{a.label}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                                                        encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "examples"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

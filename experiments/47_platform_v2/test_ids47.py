"""Experiment 47, fix round 1: two clean builds give the same ids and the same rows, whatever the step order and the
Python hash seed.

    .venv/bin/python experiments/47_platform_v2/test_ids47.py              # 8 documents, ~2 min
    .venv/bin/python experiments/47_platform_v2/test_ids47.py --full       # all four runs, ~5 min
    .venv/bin/pytest -q experiments/47_platform_v2/test_ids47.py           # the same small check under pytest

Build A: load v33_300, load v33_300_final, link            (PYTHONHASHSEED=1)
Build B: load v33_300_final, load v33_300, link, load v33_300 again (load after link), link again (relink with
         nothing changed)                                  (PYTHONHASHSEED=2)

Every table is then compared row by row (all columns but the clock and load-event ones), so a renumbered key, an id
minted from load order or a layer that depends on which step ran last all show up as a difference."""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PY = str(REPO / ".venv" / "bin" / "python")
STEMS = ["0419-000-044-007", "2280-006-001-014", "0328-000-032-006", "0069-000-026-005", "0955-000-025-001",
         "0955-000-023-001", "0523-011-003-011", "2319-000-022,023-022"]
# event and clock columns: they say when and in which load a row was written, not what it is
VOLATILE = {"created", "load_id", "created_load", "built_load", "link_run_id", "first_load", "started", "finished",
            "merged", "checked_at"}
# history, not state: the registry keeps every id ever minted and merged_ids every id retired, so a build that
# passed through more intermediate states holds more of both. They are compared on the live ids only (below).
HISTORY = {"id_registry", "merged_ids"}
LIVE = """SELECT person_id FROM persons UNION SELECT inst_id FROM institutions UNION
          SELECT cited_work_id FROM cited_works WHERE status = 'active'"""
SKIP = {"load_events", "link_runs", "link_run_versions", "search_fts", "search_fts_data", "search_fts_idx",
        "search_fts_content", "search_fts_docsize", "search_fts_config", "sqlite_stat1", "sqlite_sequence"}


def run(args, seed, work):
    env = dict(os.environ, PYTHONHASHSEED=str(seed))
    r = subprocess.run([PY, *args], cwd=REPO, env=env, capture_output=True, text=True)
    (work / "log.txt").open("a").write(r.stdout + r.stderr)
    if r.returncode:
        raise RuntimeError(f"{args} failed:\n{r.stderr[-3000:]}")


def build(db: Path, work: Path, order: list, seed: int, stems: list | None):
    st = [x for s in stems for x in ("--stem", s)] if stems else []
    for step in order:
        if step == "link":
            run([str(HERE / "link47.py"), "--db", str(db), "--work", str(work)], seed, work)
        else:
            extra = st if stems or step != "v33_300_judged" else ["--stem", "0368-000-013-009"]
            if step == "v33_300_judged" and stems:
                continue
            run([str(HERE / "load47.py"), "--db", str(db), "--run", step, *extra], seed, work)


def table_rows(con, t):
    cols = [r[1] for r in con.execute(f"PRAGMA table_info([{t}])") if r[1] not in VOLATILE]
    w = f" WHERE public_id IN ({LIVE})" if t == "id_registry" else ""
    if t == "cited_works":
        w = " WHERE status = 'active'"
    return cols, sorted(tuple("" if v is None else str(v) for v in r)
                        for r in con.execute(f"SELECT {','.join(f'[{c}]' for c in cols)} FROM [{t}]{w}"))


def compare(a: Path, b: Path) -> dict:
    ca, cb = sqlite3.connect(a), sqlite3.connect(b)
    tabs = [r[0] for r in ca.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
            if r[0] not in SKIP and r[0] != "merged_ids" and not r[0].startswith("search_fts")]
    out = {}
    for name, c in (("a", ca), ("b", cb)):
        # every retired id points at a live one (or at another retired id that does)
        dead = c.execute(f"""SELECT count(*) FROM merged_ids WHERE kind IN ('person', 'institution', 'cited_work') AND
                             new_id NOT IN ({LIVE}) AND new_id NOT IN (SELECT old_id FROM merged_ids)""").fetchone()[0]
        out[f"merged_ids ({name}): pointing at no live id"] = dict(rows_a=dead, rows_b=0, only_a=dead, only_b=0,
                                                                 example_a=[], example_b=[], cols=[])
    for t in tabs:
        cols, ra = table_rows(ca, t)
        _, rb = table_rows(cb, t)
        sa, sb = set(ra), set(rb)
        out[t] = dict(rows_a=len(ra), rows_b=len(rb), only_a=len(sa - sb), only_b=len(sb - sa),
                      example_a=sorted(sa - sb)[:2], example_b=sorted(sb - sa)[:2], cols=cols)
    return out


def check(full: bool = False, keep: Path | None = None) -> dict:
    tmp = Path(keep or tempfile.mkdtemp(prefix="ids47_"))
    tmp.mkdir(parents=True, exist_ok=True)
    stems = None if full else STEMS
    runs = ["v33_300", "v2_55", "v33_300_judged", "v33_300_final"] if full else ["v33_300", "v33_300_final"]
    a, b = tmp / "a.db", tmp / "b.db"
    for p in (a, b):
        for x in (p, Path(f"{p}-wal"), Path(f"{p}-shm")):
            x.unlink(missing_ok=True)
    (tmp / "wa").mkdir(exist_ok=True)
    (tmp / "wb").mkdir(exist_ok=True)
    build(a, tmp / "wa", runs + ["link"], 1, stems)
    order_b = list(reversed(runs)) + ["link", runs[0], "link"]
    build(b, tmp / "wb", order_b, 2, stems)
    res = compare(a, b)
    bad = {t: r for t, r in res.items() if r["only_a"] or r["only_b"]}
    return dict(folder=str(tmp), tables=len(res), differing=bad,
                ids=dict(persons=res["persons"]["rows_a"], institutions=res["institutions"]["rows_a"],
                         cited_works=res["cited_works"]["rows_a"], citation_mentions=res["citation_mentions"]["rows_a"],
                         authorships=res["authorships"]["rows_a"]))


def test_two_clean_builds_same_ids(tmp_path):
    r = check(False, tmp_path)
    assert not r["differing"], r["differing"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--keep", help="folder for the two dbs (kept)")
    x = ap.parse_args()
    r = check(x.full, Path(x.keep) if x.keep else None)
    print(f"{r['tables']} tables compared in {r['folder']}; rows of A: {r['ids']}")
    if r["differing"]:
        for t, d in r["differing"].items():
            print(f"DIFF {t}: A {d['rows_a']} rows, B {d['rows_b']}; only in A {d['only_a']}, only in B {d['only_b']}")
            print("   cols", d["cols"])
            print("   A:", d["example_a"])
            print("   B:", d["example_b"])
        sys.exit(1)
    print("identical: every id and every row (clock and load-event columns aside)")

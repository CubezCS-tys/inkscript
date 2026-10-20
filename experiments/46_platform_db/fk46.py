"""Experiment 46: the declared foreign keys of platform.db and their orphans (child rows whose parent is missing).
The keys are declared in schema46.sql for Datasette and as documentation, not enforced (loads run with
PRAGMA foreign_keys=OFF), so this is the consistency check. Nothing is changed or deleted.

    .venv/bin/python experiments/46_platform_db/fk46.py                 # table of keys, rows with a value, orphans
    .venv/bin/python experiments/46_platform_db/fk46.py --json out.json
    .venv/bin/python experiments/46_platform_db/fk46.py --counts        # rows per table (to compare two dbs)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common46 import DB  # noqa: E402


def tables(con):
    return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE "
                                      "'blocks_fts%' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def foreign_keys(con):
    out = []
    for t in tables(con):
        fks = {}
        for r in con.execute(f"PRAGMA foreign_key_list([{t}])"):
            fks.setdefault(r[0], dict(table=t, parent=r[2], cols=[], pcols=[]))
            fks[r[0]]["cols"].append(r[3])
            fks[r[0]]["pcols"].append(r[4])
        out += fks.values()
    return out


def orphans(con, fk):
    c, p = fk["cols"], fk["pcols"]
    nn = " AND ".join(f"c.[{x}] IS NOT NULL" for x in c)
    on = " AND ".join(f"p.[{y}] = c.[{x}]" for x, y in zip(c, p))
    with_value = con.execute(f"SELECT count(*) FROM [{fk['table']}] c WHERE {nn}").fetchone()[0]
    n = con.execute(f"SELECT count(*) FROM [{fk['table']}] c WHERE {nn} AND NOT EXISTS "
                    f"(SELECT 1 FROM [{fk['parent']}] p WHERE {on})").fetchone()[0]
    ex = [list(r) for r in con.execute(
        f"SELECT DISTINCT {', '.join('c.[%s]' % x for x in c)} FROM [{fk['table']}] c WHERE {nn} AND NOT EXISTS "
        f"(SELECT 1 FROM [{fk['parent']}] p WHERE {on}) LIMIT 5")]
    return with_value, n, ex


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--json")
    ap.add_argument("--counts", action="store_true")
    a = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    if a.counts:
        print(json.dumps({t: con.execute(f"SELECT count(*) FROM [{t}]").fetchone()[0] for t in tables(con)}, indent=1))
        return
    rows = []
    for fk in foreign_keys(con):
        wv, n, ex = orphans(con, fk)
        rows.append(dict(child=f"{fk['table']}({', '.join(fk['cols'])})",
                         parent=f"{fk['parent']}({', '.join(fk['pcols'])})", datasette=len(fk["cols"]) == 1,
                         with_value=wv, orphans=n, examples=ex))
        print(f"{rows[-1]['child']:44} -> {rows[-1]['parent']:36} {'' if rows[-1]['datasette'] else '(compound) '}"
              f"{wv:7} rows, {n:5} orphans {ex[:2] if n else ''}")
    print(f"{len(rows)} keys, {sum(r['datasette'] for r in rows)} single-column (Datasette), "
          f"{sum(1 for r in rows if r['orphans'])} with orphans")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

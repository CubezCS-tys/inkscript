"""Tiny read-only SQL helper: q.py [p|m] "SQL" -> rows as tab-separated text (p = platform_v2, m = marc)."""
import sqlite3, sys
P = "file:/home/appuser/data/platform_v2/platform_v2.db?mode=ro"
M = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
def pcon():
    c = sqlite3.connect(P, uri=True); c.row_factory = sqlite3.Row; return c
def mcon():
    c = sqlite3.connect(M, uri=True); c.row_factory = sqlite3.Row; return c
if __name__ == "__main__":
    con = pcon() if sys.argv[1] == "p" else mcon()
    cur = con.execute(sys.argv[2])
    if cur.description:
        print("\t".join(d[0] for d in cur.description))
    for r in cur:
        print("\t".join("" if x is None else str(x) for x in r))

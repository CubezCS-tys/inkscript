"""Experiment 56: pull the catalogue's institution authority out of marc.db (read-only) into a small table.

Two sources, both cataloguers' decisions:
- 502 $c (granting university) + $g (country) + $f (faculty): 169,600 thesis records;
- 110 / is_org author headings «البلد. الهيئة. الوحدة» (country first, then the body, then its unit).
Output: out/marc_inst56.db with tables thesis_unis(univ, country, faculty, n) and corp(heading, authority_id, n).
"""
import sqlite3
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out" / "marc_inst56.db"
MARC = Path.home() / "data/marc/marc.db"


def main():
    src = sqlite3.connect(f"file:{MARC}?mode=ro", uri=True)
    if OUT.exists():
        OUT.unlink()
    dst = sqlite3.connect(OUT)
    dst.executescript("""CREATE TABLE thesis_unis (univ TEXT, country TEXT, faculty TEXT, n INTEGER);
                         CREATE TABLE corp (heading TEXT, authority_id TEXT, n INTEGER);""")
    rows = src.execute("""SELECT name, authority_id, count(*) FROM authors WHERE is_org = 1
                          GROUP BY name, authority_id""").fetchall()
    dst.executemany("INSERT INTO corp VALUES (?,?,?)", rows)
    print("corp headings", len(rows), flush=True)
    # 502: one pass over the fields of tag 502 (no index on tag: a full scan, a few minutes)
    cur = src.execute("SELECT rec, fseq, code, value FROM fields WHERE tag = '502' AND code IN ('c', 'f', 'g')")
    agg = {}
    last = None
    acc = {}
    for rec, fseq, code, value in cur:
        k = (rec, fseq)
        if k != last and last is not None:
            t = (acc.get("c"), acc.get("g"), acc.get("f"))
            agg[t] = agg.get(t, 0) + 1
            acc = {}
        last = k
        acc[code] = (value or "").strip()
    if acc:
        t = (acc.get("c"), acc.get("g"), acc.get("f"))
        agg[t] = agg.get(t, 0) + 1
    dst.executemany("INSERT INTO thesis_unis VALUES (?,?,?,?)", [(a, b, c, n) for (a, b, c), n in agg.items()])
    dst.commit()
    print("thesis (univ, country, faculty) triples", len(agg), flush=True)


if __name__ == "__main__":
    sys.exit(main())

"""Query the local MARC catalogue database (experiment 45).

    marcq.py stem 0355-000-002-006          one PDF's record: main fields, people, PDFs, subjects, abstracts
    marcq.py stem 0355-000-002-006 --raw    ... and every MARC field as stored
    marcq.py record 0525299                 by 001 (also: marcq.py c999 129547)
    marcq.py author "الشاروني"              records whose people match (folded; every word must match)
    marcq.py authority 130243               records of one authority number (100/700 $9)
    marcq.py search "القصة المصرية"         full text over title + people + keywords/subject terms (folded)
    marcq.py sql "SELECT ..."               any SQL, tab-separated
Options: --db FILE (default ~/data/marc/marc.db), --limit N (default 50).
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build45 import DB, fold  # noqa: E402

MAIN = ["record_id", "title", "subtitle", "title_en", "parallel_titles", "language", "year", "year_hijri", "month",
        "journal", "journal_en", "journal_code", "issn", "volume", "issue", "issue_printed", "pages", "publisher",
        "country", "type", "type_en", "databases", "added", "doi", "thesis", "c999", "fields_of_study"]


def fts_query(text: str, column: str | None = None) -> str:
    words = [w.replace('"', "") for w in fold(text).split() if w.replace('"', "")]
    q = " AND ".join(f'"{w}"' for w in words)
    return f"{column}: ({q})" if column else q


def show(db, rec: int, raw: bool):
    r = db.execute("SELECT * FROM records_v WHERE rec = ?", (rec,)).fetchone()
    print(f"── rec {rec}")
    for k in MAIN:
        if r[k] not in (None, ""):
            print(f"  {k:16} {r[k]}")
    for a in db.execute("SELECT * FROM authors WHERE rec = ? ORDER BY seq", (rec,)):
        print(f"  person {a['seq']} [{a['tag']}] {a['name']}" + (f" / {a['latin']}" if a["latin"] else "") +
              f"  ({a['role'] or '-'}; authority {a['authority_id'] or '-'})")
    for p in db.execute("SELECT stem, label FROM pdf_ids WHERE rec = ? ORDER BY seq", (rec,)):
        print(f"  pdf    {p['stem']}" + (f"  «{p['label']}»" if p["label"] else ""))
    sub = [s["term"] for s in db.execute("SELECT term FROM subjects WHERE rec = ? AND source = '653' ORDER BY seq", (rec,))]
    if sub:
        print("  terms  " + " ; ".join(sub))
    kw = [f"{k['ar']}" + (f" ({k['en']})" if k["en"] else "") for k in
          db.execute("SELECT ar, en FROM keywords WHERE rec = ? ORDER BY seq", (rec,))]
    if kw:
        print("  kwds   " + " ; ".join(kw))
    for a in db.execute("SELECT code, text FROM abstracts WHERE rec = ? ORDER BY seq", (rec,)):
        t = " ".join(a["text"].split())
        print(f"  520 ${a['code']}  {t[:300]}{'…' if len(t) > 300 else ''}")
    if raw:
        print(f"  LDR    {r['leader']}")
        for f in db.execute("SELECT * FROM fields WHERE rec = ? ORDER BY fseq, sseq", (rec,)):
            ind = (f["ind1"] or "_") + (f["ind2"] or "_")
            print(f"  {f['tag']} {ind if f['code'] else '  '} {('$' + f['code']) if f['code'] else '  '} {f['value']}")


def listing(db, sql, args, limit):
    rows = db.execute(sql + f" LIMIT {int(limit)}", args).fetchall()
    for r in rows:
        stems = ",".join(x[0] for x in db.execute("SELECT stem FROM pdf_ids WHERE rec = ? ORDER BY seq LIMIT 3",
                                                  (r["rec"],)))
        names = " ; ".join(x[0] for x in db.execute("SELECT name FROM authors WHERE rec = ? ORDER BY seq", (r["rec"],)))
        print(f"{r['record_id']}\t{stems}\t{r['year']}\t{names}\t{r['title']}\t{r['journal']}")
    print(f"({len(rows)} rows{', limit reached' if len(rows) >= limit else ''})", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["stem", "record", "c999", "author", "authority", "search", "sql"])
    ap.add_argument("arg")
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--raw", action="store_true")
    a = ap.parse_args(argv)
    db = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    if a.cmd == "sql":
        cur = db.execute(a.arg)
        print("\t".join(d[0] for d in cur.description or []))
        for i, row in enumerate(cur):
            print("\t".join("" if v is None else str(v) for v in row))
        return 0
    if a.cmd in ("stem", "record", "c999"):
        col = {"stem": "SELECT rec FROM pdf_ids WHERE stem = ?", "record": "SELECT rec FROM records WHERE record_id = ?",
               "c999": "SELECT rec FROM records WHERE c999 = ?"}[a.cmd]
        recs = [r[0] for r in db.execute(col, (a.arg.removesuffix(".pdf"),))]
        if not recs:
            print(f"no record for {a.cmd} {a.arg}")
            return 1
        for rec in recs:
            show(db, rec, a.raw)
        return 0
    if a.cmd == "author":
        listing(db, "SELECT r.* FROM fts JOIN records r ON r.rec = fts.rowid WHERE fts MATCH ? ORDER BY r.year_int",
                (fts_query(a.arg, "authors"),), a.limit)
    elif a.cmd == "authority":
        listing(db, "SELECT r.* FROM records r WHERE r.rec IN (SELECT rec FROM authors WHERE authority_id = ?) "
                    "ORDER BY r.year_int", (a.arg,), a.limit)
    elif a.cmd == "search":
        listing(db, "SELECT r.* FROM fts JOIN records r ON r.rec = fts.rowid WHERE fts MATCH ? ORDER BY fts.rank",
                (fts_query(a.arg),), a.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())

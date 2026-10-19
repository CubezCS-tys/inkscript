"""Check marc.db against the bucket map's numbers and the catalogue index the masters use (experiment 45).

    .venv/bin/python experiments/45_marc_db/check45.py [--db FILE] [--n 200]  -> ~/data/marc/check45.json

1. counts vs experiments/44_bucket_map/out/summary44.json (records, PDF ids);
2. every PDF id of ~/.cache/inkscript/catalogue/catalogue.sqlite (src/inkscript/enrich/catalogue.py, experiment 29)
   is in marc.db and points at the same record (001);
3. 200 random PDF ids: the masters' record (Catalogue.get) against marc.db's tables, field by field;
4. the two example ids.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))
from build45 import DB  # noqa: E402
from inkscript.enrich.catalogue import Catalogue, _clean, default_index  # noqa: E402

SUMMARY44 = HERE.parent / "44_bucket_map" / "out" / "summary44.json"


def new_record(db, rec: int) -> dict:
    """marc.db's tables -> the masters' compact record shape (only the keys compared)."""
    r = db.execute("SELECT * FROM records WHERE rec = ?", (rec,)).fetchone()
    names = [dict(name=a["name"], tag=a["tag"], **({"org": 1} if a["is_org"] else {}), **({"latin": a["latin"]} if a["latin"] else {}),
                  **({"role": a["role"]} if a["role"] else {}), **({"auth": a["authority_id"]} if a["authority_id"] else {}))
             for a in db.execute("SELECT * FROM authors WHERE rec = ? ORDER BY seq", (rec,))]
    sub = lambda s: [x[0] for x in db.execute("SELECT term FROM subjects WHERE rec = ? AND source = ? ORDER BY seq",  # noqa: E731
                                              (rec, s))]
    return dict(
        id=r["record_id"], doi=r["doi"], lang=r["language"].split(",") if r["language"] else [], country=r["country"],
        title=r["title"], subtitle=r["subtitle"], title_en=r["title_en"], subtitle_en=r["subtitle_en"], names=names,
        publisher=r["publisher"], place=r["place"], year=r["year"], year_hijri=r["year_hijri"], month=r["month"],
        pages=r["pages"], type=r["type"], type_en=r["type_en"],
        thesis=json.loads(r["thesis"]) if r["thesis"] else None,
        abstracts=[[a["code"], a["text"]] for a in db.execute("SELECT code, text FROM abstracts WHERE rec = ? ORDER BY seq", (rec,))],
        keywords=sub("653"), terms=[[k["ar"], k["en"]] for k in db.execute("SELECT ar, en FROM keywords WHERE rec = ? ORDER BY seq", (rec,))],
        journal=dict(title=r["journal"], romanised=r["journal_romanised"], code=r["journal_code"], issn=r["issn"],
                     volume=r["volume"], issue=r["issue"], printed=r["issue_printed"], seq=r["article_seq"],
                     fields=sub("773$4"), fields_en=sub("773$6")),
        notes=[_clean(f[0]) for f in db.execute("SELECT value FROM fields WHERE rec = ? AND tag = '500' AND code = 'a' "
                                                "ORDER BY fseq, sseq", (rec,)) if _clean(f[0])],
        db=r["databases"].split(",") if r["databases"] else [],
        stems=[x[0] for x in db.execute("SELECT stem FROM pdf_ids WHERE rec = ? ORDER BY seq", (rec,))])


def norm_abs(t):
    return " ".join(t.split())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", type=Path, default=DB.parent / "check45.json")
    a = ap.parse_args(argv)
    db = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    old_path = default_index()
    old = Catalogue(old_path)
    R: dict = {"db": str(a.db), "masters_index": str(old_path), "masters_info": old.info}
    meta = dict(db.execute("SELECT k, v FROM meta").fetchall())
    s44 = json.loads(SUMMARY44.read_text())["catalogue"]
    R["counts"] = dict(
        records=int(meta["records"]), records_44=s44["records"], records_masters=int(old.info["records"]),
        pdf_stems=int(meta["pdf_stems"]), pdf_stems_44=s44["pdf_stems"], pdf_stems_masters=int(old.info["pdfs"]),
        pdf_id_rows=int(meta["pdf_id_rows"]), masters_duplicate_pdfs=int(old.info["duplicate_pdfs"]),
        stems_in_two_records=db.execute("SELECT count(*) FROM (SELECT stem FROM pdf_ids GROUP BY stem HAVING count(*) > 1)").fetchone()[0],
        records_without_pdf=db.execute("SELECT count(*) FROM records WHERE n_pdfs = 0").fetchone()[0],
        distinct_001=db.execute("SELECT count(DISTINCT record_id) FROM records").fetchone()[0],
        distinct_c999=db.execute("SELECT count(DISTINCT c999) FROM records").fetchone()[0],
        authors=db.execute("SELECT count(*) FROM authors").fetchone()[0],
        subjects=db.execute("SELECT count(*) FROM subjects").fetchone()[0],
        keywords=db.execute("SELECT count(*) FROM keywords").fetchone()[0],
        fields=db.execute("SELECT count(*) FROM fields").fetchone()[0])
    print(json.dumps(R["counts"]), flush=True)
    # 2. every masters' stem present, same record (001)
    db2 = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    db2.execute(f"ATTACH 'file:{old_path}?mode=ro' AS m")
    R["masters_stems_missing_in_db"] = db2.execute(
        "SELECT count(*) FROM m.pdf WHERE stem NOT IN (SELECT stem FROM pdf_ids)").fetchone()[0]
    R["db_stems_missing_in_masters"] = db2.execute(
        "SELECT count(*) FROM (SELECT DISTINCT stem FROM pdf_ids) WHERE stem NOT IN (SELECT stem FROM m.pdf)").fetchone()[0]
    print("missing", R["masters_stems_missing_in_db"], R["db_stems_missing_in_masters"], flush=True)
    # 3. sample
    rnd = random.Random(45)
    total = int(old.info["pdfs"])
    picks = sorted(rnd.sample(range(total), a.n))
    allstems = [r[0] for r in old.db.execute("SELECT stem FROM pdf")]
    sample = [allstems[i] for i in picks]
    del allstems
    diffs, keys_diff, compared = [], Counter(), 0
    for s in sample:
        o = old.get(s)
        recs = [r[0] for r in db.execute("SELECT rec FROM pdf_ids WHERE stem = ? ORDER BY rec", (s,))]
        if not recs:
            diffs.append(dict(stem=s, problem="not in db"))
            keys_diff["missing"] += 1
            continue
        n = new_record(db, recs[0])            # the masters keep the first record for a stem in two records
        compared += 1
        for k in sorted(set(o) | {"title", "names", "year", "journal", "keywords", "abstracts", "stems"}):
            if k in ("files", "links"):
                continue
            ov, nv = o.get(k), n.get(k)
            if k == "journal":
                ov = {kk: vv for kk, vv in (ov or {}).items() if kk in n["journal"]}
                nv = {kk: vv for kk, vv in nv.items() if vv}
            if k == "abstracts":
                ov = [[c, norm_abs(t)] for c, t in ov or []]
                nv = [[c, norm_abs(t)] for c, t in nv or []]
            if k == "stems":
                ov = [x for x in n["stems"]] if s in n["stems"] else ["(stem not in the record)"]
            if (ov or None) != (nv or None):
                keys_diff[k] += 1
                diffs.append(dict(stem=s, key=k, masters=ov, db=nv))
    R["sample"] = dict(n=a.n, compared=compared, records_with_a_difference=len({d["stem"] for d in diffs}),
                       differing_keys=dict(keys_diff), diffs=diffs[:60])
    print(json.dumps(R["sample"]["differing_keys"]), flush=True)
    # 4. examples
    R["examples"] = {}
    for s in ("0355-000-002-006", "2382-005-003-001"):
        recs = [r[0] for r in db.execute("SELECT rec FROM pdf_ids WHERE stem = ?", (s,))]
        R["examples"][s] = [new_record(db, x) for x in recs]
        for e in R["examples"][s]:
            e["abstracts"] = [[c, t[:200]] for c, t in e["abstracts"]]
    a.out.write_text(json.dumps(R, ensure_ascii=False, indent=1))
    print("->", a.out)


if __name__ == "__main__":
    main()

"""Build a local SQLite database of Mandumah's MARC 21 catalogue (experiment 45).

    .venv/bin/python experiments/45_marc_db/build45.py [--xml FILE] [--db FILE] [--limit N]

Streams the XML once with lxml iterparse (each record cleared after use), writes to <db>.part, renames at the end.
Flattened fields come from src/inkscript/enrich/catalogue.parse_record (the reader the masters use, experiment 29),
so PDF ids, titles, names and journal fields are read the same way; every subfield is also kept verbatim in `fields`.
Progress: <db>.log (one line every 50,000 records).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from inkscript.enrich.catalogue import MARC, _clean, _isbd, page_range, parse_record  # noqa: E402

DATA = Path.home() / "data" / "marc"
XML = DATA / "metadata_final.xml"
DB = DATA / "marc.db"

# ------------------------------------------------------------------ Arabic folding (search form)
_HARAKAT = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ‌-‏‪-‮⁦-⁩﻿]")
_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ٲ": "ا", "ٳ": "ا", "ؤ": "و", "ئ": "ي", "ى": "ي",
                      "ی": "ي", "ة": "ه", "ک": "ك", "ۀ": "ه", "ہ": "ه",
                      "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9"})


def fold(s: str | None) -> str:
    """Search form: no diacritics or tatweel, alef/hamza forms unified, ى→ي, ة→ه, lower case, single spaces."""
    return " ".join(_HARAKAT.sub("", s or "").translate(_MAP).lower().split())


SCHEMA = """
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE records (
  rec INTEGER PRIMARY KEY,          -- order in the XML (1-based); 001 is not guaranteed unique
  record_id TEXT,                   -- 001
  leader TEXT,
  title TEXT, subtitle TEXT,        -- 245 $a $b (ISBD punctuation trimmed)
  title_en TEXT, subtitle_en TEXT,  -- 242, else a Latin 246 (as the masters read it)
  parallel_titles TEXT,             -- every 246 $a[ : $b], ' | ' between
  language TEXT,                    -- 041 $a (several joined by ',')
  country TEXT,                     -- 044 $b
  year TEXT, year_int INTEGER,      -- 260 $c
  year_hijri TEXT, month TEXT,      -- 260 $m, $g
  publisher TEXT, place TEXT,       -- 260 $b, $a
  pages TEXT, page_first INTEGER, page_last INTEGER,   -- 300 $a
  type TEXT, type_en TEXT,          -- 336 $a $b
  journal TEXT, journal_en TEXT, journal_romanised TEXT, journal_code TEXT,   -- 773 $s, $t|$e, $f, $o
  issn TEXT, volume TEXT, issue TEXT, issue_printed TEXT, article_seq TEXT,  -- 773 $x $v $l $m $c
  fields_of_study TEXT,             -- 773 $4 (' | ')
  databases TEXT,                   -- 995 $a (',')
  added TEXT,                       -- 995 $d (date the record entered the database)
  abstract_codes TEXT,              -- 520 subfield codes present, e.g. 'ab' (text: view `abstracts`, or records_v.abstract)
  doi TEXT,                         -- 024 $3
  thesis TEXT,                      -- 502 $b $c $f $g as JSON
  c999 TEXT, d999 TEXT,             -- 999 $c $d
  n_pdfs INTEGER, n_authors INTEGER
);
CREATE TABLE fields (rec INTEGER, fseq INTEGER, sseq INTEGER, tag TEXT, ind1 TEXT, ind2 TEXT, code TEXT, value TEXT,  -- ind NULL = blank; code '' = control field
  PRIMARY KEY (rec, fseq, sseq)) WITHOUT ROWID;
CREATE TABLE pdf_ids (stem TEXT, rec INTEGER, record_id TEXT, seq INTEGER, label TEXT,
  PRIMARY KEY (stem, rec)) WITHOUT ROWID;
CREATE TABLE authors (rec INTEGER, seq INTEGER, tag TEXT, name TEXT, name_folded TEXT, latin TEXT, role TEXT,
  authority_id TEXT, is_org INTEGER, PRIMARY KEY (rec, seq)) WITHOUT ROWID;
CREATE TABLE keywords (rec INTEGER, seq INTEGER, ar TEXT, en TEXT, PRIMARY KEY (rec, seq)) WITHOUT ROWID;   -- 692 $a/$b
CREATE TABLE subjects (rec INTEGER, seq INTEGER, source TEXT, term TEXT, PRIMARY KEY (rec, seq)) WITHOUT ROWID;
  -- source: '653' subject term, '773$4' field of study (ar), '773$6' (en)
-- abstracts are 1.7 GB of text: kept once, in `fields`, and read through views (by rec they are PK lookups)
CREATE VIEW abstracts AS SELECT rec, fseq * 100 + sseq AS seq, code, value AS text FROM fields
  WHERE tag = '520' AND code IN ('a', 'b', 'd', 'e', 'f') AND trim(value) != '';
  -- 520 code: a author's Arabic, b English, d French/other, e Mandumah's Arabic, f Mandumah's English
CREATE VIEW records_v AS SELECT r.*, (SELECT f.value FROM fields f WHERE f.rec = r.rec AND f.tag = '520'
  AND f.code IN ('a', 'b', 'd', 'e', 'f') AND trim(f.value) != '' ORDER BY f.fseq, f.sseq LIMIT 1) AS abstract
  FROM records r;
CREATE TABLE tag_stats (tag TEXT, code TEXT, records INTEGER, occurrences INTEGER, PRIMARY KEY (tag, code));
CREATE VIRTUAL TABLE fts USING fts5(title, authors, keywords, content='', tokenize='unicode61 remove_diacritics 2');
  -- contentless, rowid = records.rec; every column holds the folded form (raw text + fold() of it)
"""

INDEXES = """
CREATE INDEX records_id ON records(record_id);
CREATE INDEX records_c999 ON records(c999);
CREATE INDEX records_issn ON records(issn);
CREATE INDEX records_year ON records(year_int);
CREATE INDEX records_journal ON records(journal_code, volume, issue);
CREATE INDEX pdf_rec ON pdf_ids(rec);
CREATE INDEX authors_auth ON authors(authority_id);
CREATE INDEX authors_name ON authors(name_folded);
"""


def sha_head(path: Path, n=100 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(n))
    return h.hexdigest()


def records(source):
    """Yield (leader, [(tag, ind1, ind2, [(code, value)])]) for each record; elements cleared as we go."""
    from lxml import etree
    for _, el in etree.iterparse(source, events=("end",), tag=MARC + "record", huge_tree=True):
        leader, fields = "", []
        for f in el:
            t = f.tag
            if t == MARC + "leader":
                leader = f.text or ""
            elif t == MARC + "controlfield":
                fields.append((f.get("tag") or "", "", "", [("", f.text or "")]))
            elif t == MARC + "datafield":
                fields.append((f.get("tag") or "", f.get("ind1") or "", f.get("ind2") or "",
                               [(s.get("code") or "", s.text or "") for s in f]))
        yield leader, fields
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]


def parallel_titles(fields) -> list[str]:
    """Every 246 as 'a : b' (the ISBD ' :' at the end of $a trimmed)."""
    par = []
    for t, sf in fields:
        if t == "246":
            d = {}
            for c, v in sf:
                if c in "ab" and _isbd(_clean(v)):
                    d.setdefault(c, _isbd(_clean(v)))
            if d:
                par.append(" : ".join(x for x in (d.get("a"), d.get("b")) if x))
    return par


def year_int(s: str):
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", s or "")
    return int(m.group(1)) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", type=Path, default=XML)
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--disk", default="/mnt/c", help="the disk whose free space is watched (WSL's C: holds the vhdx)")
    ap.add_argument("--min-free", type=float, default=38.0, help="stop when the watched disk has fewer GiB free (df -h units)")
    ap.add_argument("--full-sha", action="store_true", help="also hash the whole file (about 30 s for 7.7 GB)")
    a = ap.parse_args(argv)
    tmp = a.db.with_suffix(".part")
    logf = open(a.db.with_suffix(".log"), "a")

    def log(msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    db.execute("PRAGMA journal_mode=OFF")
    db.execute("PRAGMA synchronous=OFF")
    db.execute("PRAGMA page_size=8192")
    db.executescript(SCHEMA)
    t0 = time.time()
    log(f"build {a.xml} -> {a.db} limit={a.limit}")
    B = {k: [] for k in ("records", "fields", "pdf_ids", "authors", "keywords", "subjects", "fts")}
    SQL = {"records": "INSERT INTO records VALUES (" + ",".join("?" * 40) + ")",
           "fields": "INSERT INTO fields VALUES (?,?,?,?,?,?,?,?)",
           "pdf_ids": "INSERT OR IGNORE INTO pdf_ids VALUES (?,?,?,?,?)",
           "authors": "INSERT INTO authors VALUES (?,?,?,?,?,?,?,?,?)",
           "keywords": "INSERT INTO keywords VALUES (?,?,?,?)",
           "subjects": "INSERT INTO subjects VALUES (?,?,?,?)",
           "fts": "INSERT INTO fts(rowid, title, authors, keywords) VALUES (?,?,?,?)"}

    def flush():
        for k, rows in B.items():
            if rows:
                db.executemany(SQL[k], rows)
                rows.clear()
    n = nstem = ndup_stem = 0
    tag_rec, tag_occ = Counter(), Counter()
    with open(a.xml, "rb") as src:
        for leader, fields in records(src):
            n += 1
            rec = n
            seen_tc = set()
            for i, (tag, i1, i2, sf) in enumerate(fields):
                tag_occ[(tag, "")] += 1
                seen_tc.add((tag, ""))
                for j, (c, v) in enumerate(sf):
                    B["fields"].append((rec, i, j, tag, i1.strip() or None, i2.strip() or None, c, v))
                    if c:
                        tag_occ[(tag, c)] += 1
                        seen_tc.add((tag, c))
            for k in seen_tc:
                tag_rec[k] += 1
            stems, r = parse_record([(t, sf) for t, _, _, sf in fields])

            def first(tag, code):
                for t, _, _, sf in fields:
                    if t == tag:
                        for c, v in sf:
                            if c == code and _clean(v):
                                return _clean(v)
                return ""

            def every(tag, code):
                return [_clean(v) for t, _, _, sf in fields if t == tag for c, v in sf if c == code and _clean(v)]
            rid = r.get("id", "")
            j = r.get("journal", {})
            pr = page_range(r.get("pages", "")) or (None, None)
            par = parallel_titles([(t, sf) for t, _, _, sf in fields])
            ab = r.get("abstracts", [])
            names = r.get("names", [])
            # PDFs, with their 856 $y labels (parse_record keeps labels only when there are several or any label)
            labels = {}
            for u, y in r.get("files", []):
                s = re.sub(r"\.pdf$", "", u.strip(), flags=re.I)
                labels.setdefault(s, y)
            for i, s in enumerate(stems):
                B["pdf_ids"].append((s, rec, rid, i, labels.get(s, "")))
            nstem += len(stems)
            for i, d in enumerate(names):
                B["authors"].append((rec, i, d["tag"], d["name"], fold(d["name"]), d.get("latin", ""),
                                     d.get("role", ""), d.get("auth", ""), d.get("org", 0)))
            for i, (x, y) in enumerate(r.get("terms", [])):
                B["keywords"].append((rec, i, x, y))
            subs = [("653", x) for x in r.get("keywords", [])] + [("773$4", x) for x in j.get("fields", [])] + \
                   [("773$6", x) for x in j.get("fields_en", [])]
            for i, (s_, x) in enumerate(subs):
                B["subjects"].append((rec, i, s_, x))
            title = " : ".join(x for x in (r.get("title", ""), r.get("subtitle", "")) if x)
            tfull = " ".join([title, r.get("title_en", ""), r.get("subtitle_en", "")] + par)
            afull = " ; ".join(d["name"] + (" " + d["latin"] if d.get("latin") else "") for d in names)
            kfull = " ; ".join(r.get("keywords", []) + [x for p in r.get("terms", []) for x in p if x])
            B["fts"].append((rec, fold(tfull), fold(afull), fold(kfull)))
            B["records"].append((
                rec, rid, leader, r.get("title", ""), r.get("subtitle", ""), r.get("title_en", ""),
                r.get("subtitle_en", ""), " | ".join(par), ",".join(r.get("lang", [])), r.get("country", ""),
                r.get("year", ""), year_int(r.get("year", "")), r.get("year_hijri", ""), r.get("month", ""),
                r.get("publisher", ""), r.get("place", ""), r.get("pages", ""), pr[0], pr[1],
                r.get("type", ""), r.get("type_en", ""),
                j.get("title", ""), j.get("title_en", "") or j.get("title_en2", ""), j.get("romanised", ""),
                j.get("code", ""), j.get("issn", ""), j.get("volume", ""), j.get("issue", ""), j.get("printed", ""),
                j.get("seq", ""), " | ".join(j.get("fields", [])), ",".join(r.get("db", [])),
                first("995", "d"), "".join(dict.fromkeys(c for c, _ in ab)), r.get("doi", ""),
                json.dumps(r["thesis"], ensure_ascii=False) if r.get("thesis") else "",
                first("999", "c"), first("999", "d"), len(stems), len(names)))
            if len(B["fields"]) > 200_000:
                flush()
            if n % 50_000 == 0:
                free = shutil.disk_usage(a.disk).free / 2**30
                log(f"{n:,} records, {nstem:,} pdf ids, {time.time() - t0:.0f} s, {a.disk} free {free:.1f} GiB")
                if free < a.min_free:
                    log(f"STOP: {a.disk} free {free:.1f} GiB < {a.min_free} GiB; {tmp} left as it is")
                    db.commit()
                    sys.exit(3)
            if a.limit and n >= a.limit:
                break
    flush()
    t_load = time.time() - t0
    db.executemany("INSERT INTO tag_stats VALUES (?,?,?,?)",
                   [(t, c, tag_rec[(t, c)], o) for (t, c), o in sorted(tag_occ.items())])
    log(f"loaded {n:,} records in {t_load:.0f} s; indexing")
    db.executescript(INDEXES)
    db.execute("INSERT INTO fts(fts) VALUES ('optimize')")
    npdf = db.execute("SELECT count(*) FROM pdf_ids").fetchone()[0]
    nstem_u = db.execute("SELECT count(DISTINCT stem) FROM pdf_ids").fetchone()[0]
    added_max = db.execute("SELECT max(added) FROM records WHERE added GLOB '[12][0-9][0-9][0-9]-*'").fetchone()[0]
    st = a.xml.stat()
    meta = dict(source=str(a.xml), source_bytes=st.st_size,
                source_mtime=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
                source_sha256_first100MB=sha_head(a.xml), records=n, pdf_id_rows=npdf, pdf_stems=nstem_u,
                built=time.strftime("%Y-%m-%d %H:%M:%S"), seconds_load=round(t_load), limit=a.limit,
                dump_date="not stated in the XML (no 005, no collection attribute)",
                latest_995d_added=added_max or "", fold="diacritics/tatweel removed; أإآٱ→ا ؤ→و ئ→ي ى→ي ة→ه; lower")
    if a.full_sha:
        h = hashlib.sha256()
        with open(a.xml, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 24), b""):
                h.update(chunk)
        meta["source_sha256"] = h.hexdigest()
    meta["seconds_total"] = round(time.time() - t0)
    db.executemany("INSERT INTO meta VALUES (?,?)", [(k, str(v)) for k, v in meta.items()])
    db.commit()
    db.execute("ANALYZE")
    db.commit()
    db.close()
    tmp.replace(a.db)
    log(f"done: {json.dumps(meta, ensure_ascii=False)}; db {a.db.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()

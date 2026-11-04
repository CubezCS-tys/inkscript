"""Experiment 70 (gate 2's pilot): journal 0165 «مجلة الطفولة والتنمية» (Egypt), research articles
(type 'بحوث ومقالات') 2010-2025, split into the scan route (stem in the main bucket) and the Word route (a Word
original on the server, no scan). sample52.py's code with the journal and years as constants. No model calls;
marc.db read-only.

    .venv/bin/python experiments/70_gate2_pilot/sample70.py ids        -> out/ids_scan.txt (then: inkscript fetch)
    .venv/bin/python experiments/70_gate2_pilot/sample70.py build      -> out/sample70.json (run43 --set f)
    .venv/bin/python experiments/70_gate2_pilot/sample70.py inventory  -> out/inventory.json (per year scan / Word / nowhere)

out/sample70.json has run43's article shape (as sample52.json). out/word70.json lists the Word-route articles with
their catalogue record and Word file(s).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
E43 = EXP / "43_rehearsal"
sys.path.insert(0, str(E43))
MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
IDS_MAIN = EXP / "44_bucket_map/out/ids_main.txt"
WORD_LIST = EXP / "53_word_route/out/word_files_all.txt"
WORD_ROOT = Path("/home/adminuser/ai_data")
FETCH = HERE / "out" / "fetch"
JC, JNAME, Y0, Y1 = "0165", "مجلة الطفولة والتنمية", 2010, 2025
SQL = """select r.rec, r.year_int, r.journal, r.page_first, r.page_last, r.pages, r.volume, r.issue, r.title,
                r.language
         from records r
         where r.journal_code = ? and r.type = 'بحوث ومقالات' and r.year_int between ? and ?
         order by r.rec"""


def word_files():
    w = {}
    for line in open(WORD_LIST):
        folder, name = line.split()
        w.setdefault(name.rsplit(".", 1)[0], []).append(str(WORD_ROOT / folder / "docs" / name))
    return w


def records():
    main = set(IDS_MAIN.read_text().split())
    word = word_files()
    c = sqlite3.connect(MARC, uri=True)
    q = c.cursor()
    out = []
    for rec, year, journal, pf, pl, pages, vol, iss, title, lang in c.execute(SQL, (JC, Y0, Y1)).fetchall():
        stems = [s for (s,) in q.execute("select stem from pdf_ids where rec = ? order by seq", (rec,))]
        scan = [s for s in stems if s in main]
        wd = [(s, f) for s in stems for f in word.get(s, ())]
        route = "scan" if scan else ("word" if wd else "nowhere")
        out.append(dict(rec=rec, year=year, journal=journal, page_first=pf, page_last=pl, pages=pages, volume=vol,
                        issue=iss, title=title, language=lang, stems=stems, scan=scan, word=wd, route=route))
    return out


def cmd_ids():
    ids = [r["scan"][0] for r in records() if r["route"] == "scan"]
    (HERE / "out" / "ids_scan.txt").write_text("\n".join(ids) + "\n")
    print(len(ids), "ids")


def cmd_inventory():
    rs = records()
    by = {}
    for r in rs:
        by.setdefault(str(r["year"]), Counter())[r["route"]] += 1
    word = [dict(stem=r["word"][0][0], files=[f for _, f in r["word"]], **{k: r[k] for k in (
        "rec", "year", "page_first", "page_last", "pages", "volume", "issue", "title", "language")}) for r in rs
        if r["route"] == "word"]
    inv = dict(journal_code=JC, journal=JNAME, years=[Y0, Y1], records=len(rs),
               routes=dict(Counter(r["route"] for r in rs)),
               by_year={y: dict(c) for y, c in sorted(by.items())},
               word_ext=dict(Counter(Path(f).suffix for w in word for f in w["files"][:1])),
               multi_stem=sum(len(r["stems"]) > 1 for r in rs))
    (HERE / "out" / "inventory.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "out" / "word70.json").write_text(json.dumps(dict(articles=word), ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    print(json.dumps(inv, ensure_ascii=False, indent=1))


def cmd_build():
    import fetched43 as F
    arts, left = [], []
    for r in records():
        if r["route"] != "scan":
            continue
        stem = r["scan"][0]
        d = FETCH / stem
        pdf, az = d / f"{stem}.pdf", d / f"{stem}.json"
        p, info = F.problems(az, pdf, str(r["year"]))
        p = [x for x in p if not x.endswith(" pages") or x.startswith("PDF")]   # whole journal: no 1-30 page limit
        if p:
            left.append(dict(stem=stem, year=r["year"], problems=p))
            continue
        n = info["azure_pages"]
        arts.append(dict(stem=stem, kind="whole", first=1, last=n, pages_total=n, n=n, pdf=str(pdf), azure=str(az),
                         decade=f"{r['year'] // 10 * 10}s", year=str(r["year"]), journal=r["journal"],
                         why=f"journal {JC} (gate 2 pilot)", flags=[], source="catalogue", pool="journal",
                         printed_pages=r["pages"], azure_pages=n, pdf_pages=info["pdf_pages"], rec=r["rec"],
                         volume=r["volume"], issue=r["issue"], title=r["title"], language=r["language"]))
    out = dict(made="experiment 70 sample70.py build", journal_code=JC, journal=JNAME, years=[Y0, Y1],
               counts=dict(articles=len(arts), pages=sum(a["n"] for a in arts), left_out=len(left)),
               left_out=left, articles=arts)
    (HERE / "out" / "sample70.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out["counts"], left)


if __name__ == "__main__":
    {"ids": cmd_ids, "build": cmd_build, "inventory": cmd_inventory}[sys.argv[1]]()

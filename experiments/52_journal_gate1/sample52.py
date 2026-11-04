"""Experiment 52 (gate 1): the set of one journal, مجلة الطفولة العربية (catalogue journal_code 0130, Kuwait), its
articles (type 'بحوث ومقالات') 2005-2025 that are in the main bucket. No model calls; marc.db read-only.

    .venv/bin/python experiments/52_journal_gate1/sample52.py ids            -> out/ids_all.txt (then: inkscript fetch)
    .venv/bin/python experiments/52_journal_gate1/sample52.py build [--from YEAR]   -> out/sample52.json (run43 --set d)

out/sample52.json has run43's article shape (stem, first/last, pdf, azure, year, decade, journal, printed_pages, ...) plus
the catalogue's record (rec, volume, issue, title). An article whose PDF does not open or whose PDF and Azure page
counts differ is left out and listed under "left_out" (fetched43.problems; the 1-30 page limit of the samples is not
applied: a journal is taken whole).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E43 = HERE.parent / "43_rehearsal"
sys.path.insert(0, str(E43))
MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
IDS_MAIN = HERE.parent / "44_bucket_map/out/ids_main.txt"
FETCH = HERE / "out" / "fetch"
SQL = """select p.stem, r.rec, r.year_int, r.journal, r.page_first, r.page_last, r.pages, r.volume, r.issue, r.title,
                r.language
         from records r join pdf_ids p on p.rec = r.rec
         where r.journal_code = '0130' and r.type = 'بحوث ومقالات' and r.year_int between ? and 2025
         order by p.stem"""


def rows(y0=2005):
    main = set(IDS_MAIN.read_text().split())
    c = sqlite3.connect(MARC, uri=True)
    return [r for r in c.execute(SQL, (y0,)).fetchall() if r[0] in main]


def cmd_ids():
    ids = [r[0] for r in rows()]
    (HERE / "out" / "ids_all.txt").write_text("\n".join(ids) + "\n")
    print(len(ids), "ids")


def cmd_build(y0: int):
    import fetched43 as F
    arts, left = [], []
    for stem, rec, year, journal, pf, pl, pages, vol, iss, title, lang in rows(y0):
        d = FETCH / stem
        pdf, az = d / f"{stem}.pdf", d / f"{stem}.json"
        p, info = F.problems(az, pdf, str(year))
        p = [x for x in p if not x.endswith(" pages") or x.startswith("PDF")]   # whole journal: no 1-30 page limit
        if p:
            left.append(dict(stem=stem, year=year, problems=p))
            continue
        n = info["azure_pages"]
        arts.append(dict(stem=stem, kind="whole", first=1, last=n, pages_total=n, n=n, pdf=str(pdf), azure=str(az),
                         decade=f"{year // 10 * 10}s", year=str(year), journal=journal, why="journal 0130 (gate 1)",
                         flags=[], source="catalogue", pool="journal", printed_pages=pages, azure_pages=n,
                         pdf_pages=info["pdf_pages"], rec=rec, volume=vol, issue=iss, title=title, language=lang))
    out = dict(made="experiment 52 sample52.py build" + (f" --from {y0}" if y0 != 2005 else ""),
               journal_code="0130", journal="مجلة الطفولة العربية", years=[y0, 2025],
               counts=dict(articles=len(arts), pages=sum(a["n"] for a in arts), left_out=len(left)),
               left_out=left, articles=arts)
    (HERE / "out" / "sample52.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out["counts"], left)


if __name__ == "__main__":
    if sys.argv[1] == "ids":
        cmd_ids()
    else:
        y0 = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 2005
        cmd_build(y0)

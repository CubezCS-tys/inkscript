"""Experiment 58: legacy/ PDFs (made from the publishers' Word files, exp 53): does Indra read their first page from
the text layer, and does its text agree with PyMuPDF's extraction of the same layer?  No calls.

    nice -n 19 out/venv/bin/python run58.py --units out/units_legacy160.json --variant legacy_auto --mode auto
    /home/appuser/inkscript/.venv/bin/python legacy58.py   -> out/legacy_scores.json
"""
import json
from collections import Counter
from pathlib import Path
import pymupdf
from inkscript.gold.text import folded
OUT = Path(__file__).resolve().parent / "out"
units = json.loads((OUT / "units_legacy160.json").read_text())
rows = []
for u in units:
    d = json.loads((OUT / "indra/legacy_auto" / f"{u['id']}.json").read_text())
    with pymupdf.open(u["pdf"]) as doc:
        ref = doc[0].get_text()
    a, b = Counter(folded(ref).split()), Counter(folded(" ".join(l["text"] for l in d["lines"])).split())
    m = sum((a & b).values())
    n = sum(a.values()) + sum(b.values())
    rows.append(dict(id=u["id"], source=d["source"], note=d["note"], words=sum(a.values()),
                     disagree=round((n - 2 * m) / n, 4) if n else None))
by = {}
for s in ("text", "hybrid", "ocr"):
    rs = [r for r in rows if r["source"] == s and r["disagree"] is not None]
    if rs:
        by[s] = dict(pages=len(rs), mean_disagree=round(sum(r["disagree"] for r in rs) / len(rs), 4),
                     over_5pct=sum(r["disagree"] > 0.05 for r in rs))
print(by)
(OUT / "legacy_scores.json").write_text(json.dumps(dict(by_source=by, rows=rows), ensure_ascii=False, indent=1))

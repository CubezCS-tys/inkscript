"""Catalogue facts (year, journal, language) for every document experiment 33 may use -> out/meta.json.

    PYTHONPATH=../../src /home/yassine/inkscript/.venv/bin/python meta.py
Documents: experiment 19's draw (born-digital and scans) and this experiment's candidates (out/docs).
"""
import json, re
from pathlib import Path
from inkscript.enrich.catalogue import open_catalogue
OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
ids = [l.strip() for l in open(E19 / "ids.txt") if l.strip()]
ids += [p.name for p in (OUT / "docs").iterdir() if p.is_dir()]
cat = open_catalogue(); meta = {}
for i in ids:
    r = cat.get(i) or {}
    y = re.search(r"\d{4}", r.get("year") or "")
    meta[i] = dict(year=int(y.group()) if y else None, journal=(r.get("journal") or {}).get("title"), journal_code=i[:4],
                   lang=r.get("lang"), country=r.get("country"))
json.dump(meta, open(OUT / "meta.json", "w"), ensure_ascii=False, indent=1)
print(len(meta), "documents")

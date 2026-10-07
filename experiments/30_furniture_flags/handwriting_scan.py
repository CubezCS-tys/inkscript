"""Where does Azure say a page is handwritten? Azure's `styles` (isHandwritten, a confidence, text spans): the share of
each page's words inside a handwritten span, for every page of experiment 28's 205 documents.

    .venv/bin/python experiments/30_furniture_flags/handwriting_scan.py   -> out/handwriting_pages.json
"""
import json
from pathlib import Path

from inkscript.enrich.document import load

HERE = Path(__file__).resolve().parent
DATA = Path("/home/yassine/inkscript/experiments/28_scale/out")
rows = []
for d in sorted((DATA / "azure").iterdir()):
    stem = d.name
    j = json.loads((d / f"{stem}.json").read_text(encoding="utf-8"))
    ar = j.get("analyzeResult", j)
    styles = [s for s in ar.get("styles", []) if s.get("isHandwritten")]
    if not styles:
        continue
    doc = load(d / f"{stem}.json")
    for minc in (0.0,):
        pass
    hw = {}
    for w in doc["words"]:
        a = w["aoff"]
        best = 0.0
        for s in styles:
            for sp in s["spans"]:
                if sp["offset"] <= a < sp["offset"] + sp["length"]:
                    best = max(best, s.get("confidence", 0))
        hw[w["idx"]] = best
    pages = {}
    for w in doc["words"]:
        pages.setdefault(w["page"], []).append(w)
    for pn, ws in pages.items():
        n = len(ws)
        rows.append(dict(doc=stem, page=pn, words=n, hw_any=sum(hw[w["idx"]] > 0 for w in ws) / n,
                         hw_05=sum(hw[w["idx"]] >= 0.5 for w in ws) / n, hw_09=sum(hw[w["idx"]] >= 0.9 for w in ws) / n,
                         conf=sorted(w["conf"] or 0 for w in ws)[n // 2]))
(HERE / "out" / "handwriting_pages.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
rows.sort(key=lambda r: -r["hw_05"])
for r in rows[:40]:
    print(r)

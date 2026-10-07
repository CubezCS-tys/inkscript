"""The catalogue names not found on the page: the closest run of words to each, and how close (to choose the
threshold NAME_LEAST by looking, not by guessing).

    PYTHONPATH=src .venv/bin/python experiments/29_catalogue/names_missed.py
"""
import json
from pathlib import Path

from inkscript.enrich.catalogue import _name_variants, open_catalogue
from inkscript.enrich.document import load
from inkscript.enrich.structure import _align, sim

OUT = Path(__file__).resolve().parent / "out"
SET28 = Path("/home/yassine/inkscript/experiments/28_scale/out")
rows = json.loads((OUT / "after.json").read_text())
cat = open_catalogue()
for r in rows:
    if not r.get("catalogue"):
        continue
    rec = cat.get(r["stem"])
    people = rec.get("names", [])
    for p, ids in zip(people, r["author_word_ids"]):
        if ids or p.get("org"):
            continue
        doc = load(SET28 / "azure" / r["stem"] / f"{r['stem']}.json")
        early = [w for w in doc["words"] if w["page"] <= 3][:400]
        best = (0.0, "")
        for v, _ in _name_variants(p["name"]):
            run = _align(early, v, 0.0)
            if run:
                t = " ".join(doc["words"][k]["out"] for k in run)
                best = max(best, (round(sim(t, v), 2), t))
        print(f"{r['stem']}  {p['name']} ({p.get('role', '')})  closest {best[0]}: {best[1]}")

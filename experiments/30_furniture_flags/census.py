"""Every block the structure step sets aside as page furniture on experiment 28's 205 documents, with what a reader
sees of it (place, size, repetition, the reason the rule gave), without the build: only the Azure reading.

    PYTHONPATH=src .venv/bin/python experiments/30_furniture_flags/census.py NAME   -> out/census_NAME.json

NAME tags the code being measured (before / after). Stroke widths are not needed for furniture, so the scan is not
opened (headings without the bold cue are not measured here; experiment 26's truth set measures them).
"""
import json
import sys
from pathlib import Path

from inkscript.enrich import structure
from inkscript.enrich.document import load

HERE = Path(__file__).resolve().parent
DATA = Path("/home/yassine/inkscript/experiments/28_scale/out")
name = sys.argv[1]
stems = sorted(p.name for p in (DATA / "azure").iterdir())
if len(sys.argv) > 2:
    stems = [s for s in stems if s in sys.argv[2].split(",")]


def one(stem):
    doc = load(DATA / "azure" / stem / f"{stem}.json")
    a = structure.analyse(doc, structure.read_meta(stem, [DATA / "gemini"]), None)
    W = doc["words"]
    blocks = []
    for i, p in enumerate(doc["paras"]):
        pg = W[p["words"][0]]["page"]
        ws = [W[k] for k in p["words"] if W[k]["page"] == pg]
        b = structure._box(ws)
        P = doc["pages"][pg]
        blocks.append(dict(i=i, page=pg, kind=a["kinds"][i], why=a["why"][i], azure=p.get("role"),
                           text=" ".join(w["out"] for w in ws)[:200], n=len(ws),
                           box=[round(v) for v in b], W=round(P["w"]), H=round(P["h"]),
                           h_rel=round(structure._h(ws) / a["body_h"], 2)))
    print(stem, flush=True)
    return stem, dict(body_h=a["body_h"], pages=len(doc["pages"]),
                      furniture=[x for x in blocks if x["i"] in a["furniture"]],
                      kinds={x["i"]: [x["kind"], x["why"]] for x in blocks if x["kind"]},
                      journal=a.get("journal"))


from multiprocessing import Pool  # noqa: E402
with Pool(3) as pool:                     # 3 workers (memory: the largest document ~2 GB)
    out = dict(pool.map(one, stems, chunksize=1))
(HERE / "out" / f"census_{name}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print("furniture blocks", sum(len(v["furniture"]) for v in out.values()))

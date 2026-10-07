"""The context of each of experiment 19's judged words that a page- or block-level mark would use: is its block
vowelled, is its page handwritten (Azure's styles), how sure is Azure of the rest of its block. Verdicts and the
product's signals are experiment 27's (out/flag_features.json there); nothing is judged or paid again.

    PYTHONPATH=src .venv/bin/python experiments/30_furniture_flags/judged_context.py   -> out/judged_context.json
"""
import json
from collections import defaultdict
from pathlib import Path

from inkscript.enrich import trust as T
from inkscript.enrich.document import load

HERE = Path(__file__).resolve().parent
E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
E22 = Path("/home/yassine/inkscript/experiments/22_trust/out")
E27 = Path("/home/yassine/inkscript/experiments/27_corrections/out")

rows = {r["id"]: r for r in json.load(open(E22 / "judged_signals.json"))["rows"]}
F = [f for f in json.load(open(E27 / "flag_features.json")) if f.get("found") and f["real"]]
by_doc = defaultdict(list)
for f in F:
    by_doc[f["doc"]].append(f)
out = []
for n, (stem, fs) in enumerate(sorted(by_doc.items()), 1):
    doc = load(E19 / "docs" / stem / f"{stem}.json")
    reg = T.regions(doc)
    for f in fs:
        r = rows[f["id"]]
        w = next(w for w in doc["words"] if w["page"] == r["page"]
                 and all(abs(a - b) <= 3 for a, b in zip(w["box"], r["box"])))
        ctx = T.context(doc, reg, w)
        out.append(dict(f, ctx=ctx, hw=w["hw"]))
    print(f"{n}/{len(by_doc)} {stem}", flush=True)
(HERE / "out" / "judged_context.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

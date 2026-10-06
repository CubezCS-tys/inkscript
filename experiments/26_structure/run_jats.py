"""Write the JATS file of each document of the set with the code on PYTHONPATH, without touching the set's own
outputs (experiment 24's shapes.json is read, never written).

    python run_jats.py OUT_DIR [STEM...]     (default: the 20 documents of 24_product)

Data (gitignored, main checkout): ../24_product/out/azure/<id>/<id>.json (+ .pdf), ../24_product/out/set/w*/
<id>.shapes.json, out/gemini/<id>.gemini.title.json (fetch_gemini.py). The trust marks are computed without the
scan (the speck test needs it; marks only feed the counts in custom-meta).
"""
import inspect
import json
import sys
import time
from pathlib import Path

from inkscript.enrich import jats
from inkscript.enrich.document import load
from inkscript.enrich.quran import check_document
from inkscript.enrich.trust import assess

HERE = Path(__file__).resolve().parent
DATA = Path("/home/yassine/inkscript/experiments/24_product/out")
GEM = HERE / "out" / "gemini"
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
stems = sys.argv[2:] or sorted(p.name for p in (DATA / "azure").iterdir())
new_api = "meta" in inspect.signature(jats.write).parameters
res = {}
for stem in stems:
    t = time.time()
    shapes = next(iter(DATA.glob(f"set/w*/{stem}.shapes.json")), None)
    doc = load(DATA / "azure" / stem / f"{stem}.json", shapes)
    quotes = check_document(doc)
    marks = assess(doc, quotes, None)
    kw = {}
    if new_api:
        from inkscript.enrich.structure import read_meta
        kw["meta"] = read_meta(stem, [GEM])
        kw["scan_pdf"] = DATA / "azure" / stem / f"{stem}.pdf"
    r = jats.write(doc, quotes, marks, stem, out / f"{stem}.jats.xml", f"{stem}.alto.xml", **kw)
    r.pop("_ids", None)
    res[stem] = r
    print(stem, f"{time.time() - t:.1f}s", {k: v for k, v in r.items() if not isinstance(v, (dict, list))}, flush=True)
(out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

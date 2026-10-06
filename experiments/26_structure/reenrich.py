"""Rebuild the set's JATS and ALTO files with the new structure, the way `inkscript native --xml` writes them, into
out/set/ (experiment 24's outputs are copied, never written), and validate both against the official schemas.

    python reenrich.py      (needs ../24_product/out/set from experiment 24 and out/gemini from fetch_gemini.py)
"""
import json
import shutil
import time
from pathlib import Path

from inkscript.enrich import enrich, verify

HERE = Path(__file__).resolve().parent
DATA = Path("/home/yassine/inkscript/experiments/24_product/out")
OUT = HERE / "out" / "set"
OUT.mkdir(parents=True, exist_ok=True)
rows = {}
for rp in sorted((DATA / "set").glob("w*/native_pdf_report.json")):
    for r in json.loads(rp.read_text(encoding="utf-8")):
        stem = r["doc"]
        shutil.copy(rp.parent / f"{stem}.shapes.json", OUT / f"{stem}.shapes.json")
        t = time.time()
        e = enrich(stem, DATA / "azure" / stem / f"{stem}.json", DATA / "azure" / stem / f"{stem}.pdf", OUT, r,
                   xml=True, trust=False, meta_dirs=[HERE / "out" / "gemini"])
        probs = verify(stem, OUT, e)
        rows[stem] = dict(jats=e["jats"], alto_valid=e["alto"].get("valid"), problems=probs, s=round(time.time() - t, 1))
        print(stem, e["jats"].get("valid"), e["alto"].get("valid"), probs or "ok", rows[stem]["s"], flush=True)
(OUT / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("JATS valid", sum(bool(v["jats"].get("valid")) for v in rows.values()), "/", len(rows),
      "ALTO valid", sum(bool(v["alto_valid"]) for v in rows.values()), "/", len(rows))

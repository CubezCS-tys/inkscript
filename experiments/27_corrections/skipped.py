"""The quotation differences `propose` does not turn into proposals, with their category, for the report.

    python skipped.py   -> out/skipped.json
"""
import json
from collections import Counter
from pathlib import Path

from inkscript.enrich.corrections import propose
from inkscript.enrich.document import load
from inkscript.enrich.quran import check_document

HERE = Path(__file__).resolve().parent
SET = HERE / "out" / "set"
AZ = Path("/home/yassine/inkscript/experiments/24_product/out/azure")

if __name__ == "__main__":
    out = []
    for sj in sorted(SET.glob("w*/*.shapes.json")):
        stem = sj.name[:-len(".shapes.json")]
        doc = load(AZ / stem / f"{stem}.json", sj)
        props, skipped = propose(doc, check_document(doc))
        out += [dict(s, stem=stem) for s in skipped]
    (HERE / "out" / "skipped.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(out), Counter(s["category"] for s in out), Counter((s["category"], s["kind"]) for s in out))

"""Rewrite the enrich outputs (XML, trust PDFs) of an already built set without rebuilding the PDFs, then check
them as `--verify` would.   python reenrich.py [SET_DIR]

Used once on 2026-10-06 after the front-matter rules were tightened (rubric/author: no basmala, no "Abstract",
"بقلم" bylines, the journal masthead is a running head). The faithful PDFs are untouched; each trust PDF is
re-made from its faithful PDF; each build report's "enrich" entry is replaced."""
import json
import sys
from pathlib import Path

from inkscript.enrich import enrich, verify

HERE = Path(__file__).resolve().parent
SET = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out" / "set"
AZ = HERE / "out" / "azure"
for rp in sorted(SET.glob("w*/native_pdf_report.json")):
    reps = json.loads(rp.read_text(encoding="utf-8"))
    for r in reps:
        stem = r["doc"]
        e = enrich(stem, AZ / stem / f"{stem}.json", AZ / stem / f"{stem}.pdf", rp.parent, r, xml=True, trust=True)
        probs = verify(stem, rp.parent, e)
        r["enrich"] = e
        print(stem, e["trust"]["flagged"], e["jats"].get("title"), e["jats"].get("authors"), probs or "ok", flush=True)
    rp.write_text(json.dumps(reps, ensure_ascii=False, indent=1), encoding="utf-8")

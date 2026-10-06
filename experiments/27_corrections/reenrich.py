"""Rewrite the set's XML and trust PDFs with the product as it now is (the trust rule of experiment 27 and the
applied corrections), then check them as `--verify` would. The faithful PDFs are not rebuilt: `enrich` writes the
applied corrections into them again, which must change nothing (counted).

    python reenrich.py   -> each build report's "enrich" entry replaced; out/reenrich.json
"""
import json
from pathlib import Path

from inkscript.enrich import enrich, verify

HERE = Path(__file__).resolve().parent
SET = HERE / "out" / "set"
AZ = Path("/home/yassine/inkscript/experiments/24_product/out/azure")

if __name__ == "__main__":
    out = {}
    for rp in sorted(SET.glob("w*/native_pdf_report.json")):
        reps = json.loads(rp.read_text(encoding="utf-8"))
        for r in reps:
            stem = r["doc"]
            before = {n: (rp.parent / n).read_bytes() for n in (f"{stem}.pdf", f"{stem}_vector.pdf")}
            e = enrich(stem, AZ / stem / f"{stem}.json", AZ / stem / f"{stem}.pdf", rp.parent, r, xml=True, trust=True)
            probs = verify(stem, rp.parent, e)
            same = all((rp.parent / n).read_bytes() == b for n, b in before.items())
            r["enrich"] = e
            out[stem] = dict(trust=e["trust"], corrections=e.get("corrections"), problems=probs, pdfs_unchanged=same)
            print(stem, e["trust"]["flagged"], e["trust"].get("corrected"), "pdfs unchanged" if same else "PDFS CHANGED",
                  probs or "ok", flush=True)
        rp.write_text(json.dumps(reps, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "out" / "reenrich.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

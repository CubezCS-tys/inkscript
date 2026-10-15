"""Approach C: does a whole-document answer degrade towards the end? Every page of every whole document run
(not windows) scored against Azure (out/src/<stem>/<stem>.json or out/docs), by its position in the document.
Writes out/C_whole_document/position.json."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score
from common import OUT
import C_whole_document as C

CD = OUT / "C_whole_document"
rows = []
T = C.doc_table()
for f in sorted((CD / "raw" / "pdf_low").glob("*.json")):
    rec = json.loads(f.read_text())
    if rec.get("first") is not None or rec.get("failed"):
        continue
    stem, n = rec["stem"], rec["pages"]
    az = OUT / "docs" / f"{stem}.json"
    score.DOCS = az.parent if az.exists() else OUT / "src" / stem
    if not (score.DOCS / f"{stem}.json").exists():
        continue
    for k in range(1, n + 1):
        try:
            _, W, H = score.azure_doc_lines(stem, k)
        except Exception:
            continue
        u = dict(page_id=f"{stem}_p{k:03d}", stem=stem, page=k, kind="doc_page", truth=None, ncols=None, width=W,
                 height=H, referee_labels=None, unit="doc", tags=[])
        r = score.page_eval(u, CD)
        bl, _, _ = score.read_unit(CD, u)
        chars = sum(len(b["text"]) for b in bl or [])
        azc = sum(len(l["text"]) for l in score.azure_doc_lines(stem, k)[0])
        rows.append(dict(stem=stem, page=k, pages=n, pos=k / n, chars=chars, az_chars=azc,
                         ratio=round(chars / azc, 3) if azc else None,
                         cer_az_folded=round(r["az.d_err"] / r["az.d_chars"], 4) if r.get("az.d_chars") else None,
                         dropped=r.get("az.dropped"), invented=r.get("az.invented"), words=r.get("az.ref_words")))
(CD / "position.json").write_text(json.dumps(rows, indent=1))
import statistics as S
for name, sel in (("first third", lambda r: r["pos"] <= 1 / 3), ("middle", lambda r: 1 / 3 < r["pos"] <= 2 / 3),
                  ("last third", lambda r: r["pos"] > 2 / 3), ("last page", lambda r: r["page"] == r["pages"])):
    rs = [r for r in rows if sel(r) and r["pages"] > 1 and r["az_chars"] > 200]
    print(f"{name:12} pages={len(rs)} median chars/azure={S.median(r['ratio'] for r in rs):.3f} "
          f"dropped/1000w={1000 * sum(r['dropped'] for r in rs) / sum(r['words'] for r in rs):.1f} "
          f"median foldedCER={S.median(r['cer_az_folded'] for r in rs if r['cer_az_folded'] is not None):.3f}")
low = [r for r in rows if r["ratio"] is not None and r["az_chars"] > 200 and r["ratio"] < 0.85]
print("pages with < 85% of Azure's characters:", [(r["stem"], r["page"], r["ratio"]) for r in low])

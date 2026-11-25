"""Which exam / dev PDFs carry a text layer (chars per exam page), via the repo's pinned pypdfium2 (read only)."""
import json, os, sys
import pypdfium2 as pdfium
X = "/home/appuser/inkscript/experiments"
def pdf_of(s):
    for c in (f"{X}/96_layout3/out/gpu/pdflinks/{s}.pdf", f"{X}/74_gate2_full/out/fetch/{s}/{s}.pdf", f"{X}/43_rehearsal/out/fetch/{s}/{s}.pdf"):
        if os.path.exists(c):
            return os.path.realpath(c)
lock = json.load(open(f"{X}/97_extraction_evals/LOCKED_EVAL.json"))["articles"]
dev = json.load(open(f"{X}/99_liteparse_baseline/DEV_STEMS.json"))["stems"]
rows = []
for s, pages, kind in [(a["stem"], sorted(set(a["pages"].values())), "exam") for a in lock] + [(s, None, "dev") for s in dev]:
    f = pdf_of(s)
    doc = pdfium.PdfDocument(f)
    n = len(doc)
    pg = pages or list(range(1, n + 1))
    chars = {}
    for p in pg:
        if p > n:
            chars[p] = None; continue
        tp = doc[p - 1].get_textpage()
        chars[p] = tp.count_chars()
    w, h = doc[0].get_size()
    rows.append(dict(stem=s, set=kind, pdf=f, n_pages=n, page_pt=[round(w, 1), round(h, 1)], chars=chars,
                     producer=(doc.get_metadata_dict() or {}).get("Producer"), creator=(doc.get_metadata_dict() or {}).get("Creator")))
json.dump(rows, open(f"{X}/99_liteparse_baseline/out/inventory.json", "w"), ensure_ascii=False, indent=1)
for r in rows:
    print(r["set"], r["stem"], r["n_pages"], r["page_pt"], r["chars"], (r["producer"] or "")[:30], (r["creator"] or "")[:30])

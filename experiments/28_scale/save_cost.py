"""How long pymupdf takes to save one of the set's PDFs with each garbage level (native.py saves with garbage=3,
deflate=True), and the size it gives.   .venv/bin/python experiments/28_scale/save_cost.py PDF OUTDIR [LEVELS]"""
import sys, time
from pathlib import Path
import pymupdf
pdf, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
levels = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "1,2,3").split(",")]
d = pymupdf.open(str(pdf)); print(pdf.name, d.xref_length(), "objects", flush=True); d.close()
for g in levels:
    d = pymupdf.open(str(pdf)); t = time.time()
    f = out / f"g{g}.pdf"; d.save(str(f), garbage=g, deflate=True); d.close()
    print(f"garbage={g}: {time.time() - t:.1f} s, {f.stat().st_size / 1e6:.1f} MB", flush=True)

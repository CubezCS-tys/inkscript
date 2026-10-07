"""Render a page of a built document (scan, faithful or trust copy) for looking, and list the words whose letters
were not each given a box in the vector PDF.
    .venv/bin/python experiments/28_scale/look.py STEM PAGE [scan|faithful|trust] [--crop y0,y1] -> out/look/STEM_pPAGE.png"""
import re, sys
from pathlib import Path
import pymupdf, pypdfium2 as pdfium
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"
stem, page = sys.argv[1], int(sys.argv[2]); kind = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else "scan"
wd = next(OUT.glob(f"set/w*/{stem}.pdf")).parent
pdf = {"scan": OUT / "azure" / stem / f"{stem}.pdf", "faithful": wd / f"{stem}.pdf", "trust": wd / f"{stem}_trust.pdf"}[kind]
d = pymupdf.open(str(pdf)); p = d[page - 1]; r = p.rect
clip = r
if "--crop" in sys.argv:
    y0, y1 = [float(x) for x in sys.argv[sys.argv.index("--crop") + 1].split(",")]
    clip = pymupdf.Rect(0, r.height * y0, r.width, r.height * y1)
z = 900 / r.width
p.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=clip).save(str(OUT / "look" / f"{stem}_p{page}{'_' + kind if kind != 'scan' else ''}.png"))
a = pdfium.PdfDocument(str(wd / f"{stem}_vector.pdf")); tp = a[page - 1].get_textpage(); t = tp.get_text_range(); k = 0; miss = []; n = 0
for w in re.split(r"(\s+)", t):
    if re.fullmatch(r"[ء-ي]{2,}", w):
        n += 1
        boxes = {tuple(round(v, 1) for v in tp.get_charbox(k + m)) for m in range(len(w))}
        if len(boxes) < len(w) - len(re.findall("لا|لأ|لإ|لآ", w)): miss.append(f"{w}:{len(boxes)}")
    k += len(w)
print(f"{len(miss)} of {n} words uncut:", " ".join(miss[:60]))

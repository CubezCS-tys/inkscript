"""Render pages of the set's scans to PNG for reading by eye (the truth) and for the report.

    python render.py AZURE_DIR STEM[:PAGES] ...    PAGES like 1 or 1-3 or 1,4 (default 1)  -> out/pages/<stem>_p<n>.png
"""
import sys
from pathlib import Path

import cv2
import pypdfium2 as pdfium

HERE = Path(__file__).resolve().parent
OUT = HERE / "out" / "pages"
OUT.mkdir(parents=True, exist_ok=True)
AZ = Path(sys.argv[1])
for arg in sys.argv[2:]:
    stem, _, spec = arg.partition(":")
    pdf = pdfium.PdfDocument(str(AZ / stem / f"{stem}.pdf"))
    pages = []
    for part in (spec or "1").split(","):
        if part == "all":
            pages += list(range(1, len(pdf) + 1))
        elif "-" in part:
            a, b = part.split("-")
            pages += list(range(int(a), int(b) + 1))
        else:
            pages.append(int(part))
    for n in pages:
        if n > len(pdf):
            continue
        pg = pdf[n - 1]
        scale = 1100 / pg.get_width()
        a = pg.render(scale=scale, grayscale=True).to_numpy()
        cv2.imwrite(str(OUT / f"{stem}_p{n}.png"), a if a.ndim == 2 else a[..., 0])
        print(OUT / f"{stem}_p{n}.png")

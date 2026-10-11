"""The scan's pages as small images for the reading edition's "view the original" clips (experiment 35).

    page_images(ed, out_dir, dpi=120) -> {page: path of <out_dir>/scan/p<n>.jpg}

Each page is rendered once from the faithful PDF (its page renders as the scan; viewer/outputs.py does the same),
as a grey JPEG when the scan is grey, into <out_dir>/scan/p<n>.jpg. The HTML clips a paragraph out of the page with
an SVG viewBox in ALTO pixels, so there is one file per page and none per paragraph. An existing image is kept.
"""
from __future__ import annotations

from pathlib import Path


def page_images(ed, out_dir, dpi: int = 120, quality: int = 68) -> dict:
    out_dir = Path(out_dir)
    sd = out_dir / "scan"
    found, todo = {}, []
    for n in ed.page_numbers:
        p = sd / f"p{n}.jpg"
        if p.exists():
            found[n] = p
        else:
            todo.append(n)
    if todo and ed.pdf_path:
        import numpy as np
        import pymupdf
        sd.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(str(ed.pdf_path)) as d:
            for n in todo:
                if n - 1 >= len(d):
                    continue
                page = d[n - 1]
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n >= 3 and int(np.abs(a[..., 0].astype(np.int16) - a[..., 1]).max()) < 12 \
                        and int(np.abs(a[..., 1].astype(np.int16) - a[..., 2]).max()) < 12:
                    pix = page.get_pixmap(dpi=dpi, alpha=False, colorspace=pymupdf.csGRAY)
                p = sd / f"p{n}.jpg"
                p.write_bytes(pix.tobytes("jpg", jpg_quality=quality))
                found[n] = p
    return dict(sorted(found.items()))

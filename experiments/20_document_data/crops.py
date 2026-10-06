"""Crops of the ink at 300 dpi, from the scan PDF, by Azure's word boxes.

PyMuPDF renders the clip directly (the venv has no Pillow); boxes round
words are painted into the pixmap. Azure's boxes are in inches, PDF pages
in points (72 per inch)."""
from __future__ import annotations
import base64

import pymupdf

DPI = 300


class Pages:
    def __init__(self, pdf_path):
        self.doc = pymupdf.open(str(pdf_path))

    def size_in(self, n):
        r = self.doc[n - 1].rect
        return r.width / 72, r.height / 72

    def close(self):
        self.doc.close()


def union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def crop(pages: Pages, page: int, box_in, margin_in=0.05, marks=(), max_w=None, dpi=DPI,
         polys=()):
    """Pixmap of box (inches) plus margin. marks: [(box_in, rgb)] drawn as frames;
    polys: [(box_in, rgb, alpha)] drawn as translucent fills."""
    pg = pages.doc[page - 1]
    W, H = pg.rect.width / 72, pg.rect.height / 72
    x0, y0, x1, y1 = box_in
    m = margin_in
    clip_in = (max(0, x0 - m), max(0, y0 - m), min(W, x1 + m), min(H, y1 + m))
    scale = dpi / 72
    if max_w:
        wpx = (clip_in[2] - clip_in[0]) * dpi
        if wpx > max_w:
            scale *= max_w / wpx
    clip = pymupdf.Rect(*(v * 72 for v in clip_in))
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip, colorspace=pymupdf.csRGB, alpha=False)
    k = scale * 72                       # pixels per inch in this pixmap

    def px(b):
        return (int((b[0] - clip_in[0]) * k), int((b[1] - clip_in[1]) * k),
                int((b[2] - clip_in[0]) * k), int((b[3] - clip_in[1]) * k))
    for b, rgb, alpha in polys:
        a0, b0, a1, b1 = px(b)
        for yy in range(max(0, b0), min(pix.height, b1)):
            for xx in range(max(0, a0), min(pix.width, a1)):
                c = pix.pixel(xx, yy)
                pix.set_pixel(xx, yy, tuple(int(c[i] * (1 - alpha) + rgb[i] * alpha) for i in range(3)))
    t = max(2, int(k / 75))
    for b, rgb in marks:
        a0, b0, a1, b1 = px(b)
        a0 -= t; b0 -= t; a1 += t; b1 += t
        for r in [(a0, b0, a1, b0 + t), (a0, b1 - t, a1, b1), (a0, b0, a0 + t, b1), (a1 - t, b0, a1, b1)]:
            ir = pymupdf.IRect(r[0] + pix.x, r[1] + pix.y, r[2] + pix.x, r[3] + pix.y) & pix.irect
            if not ir.is_empty:
                pix.set_rect(ir, rgb)
    return pix


def data_uri(pix, q: int = 62) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(pix.tobytes("jpeg", jpg_quality=q)).decode()

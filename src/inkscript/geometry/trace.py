"""Ink as geometry: render, binarise, find every connected patch of ink,
trace its boundary as a polygon (holes kept)."""
from __future__ import annotations
import numpy as np, cv2, fitz

DPI = 300


def render_gray(page, dpi: int = DPI) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)


def page_blobs(gray):
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    # Rules first: a straight run of ink 4% of the page wide (or tall) is a
    # ruled line, an underline or a table border, never a letter (a tatweel
    # that long is rare). Cut out of the ink before components are taken,
    # so a header's underline no longer fuses with the word it touches
    # (one glyph then spanned the page and pdfium sorted the line by it).
    # They come back as their own blobs, flagged, drawn as page furniture.
    k = max(40, int(0.04 * max(ink.shape)))
    rules = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, k), np.uint8)) | cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((k, 1), np.uint8))
    out = []
    for img, is_rule in ((ink & ~rules, False), (rules, True)):
        n, lab, stats, _ = cv2.connectedComponentsWithStats(img, connectivity=8)
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            if area < 6:
                continue
            mask = (lab[y:y+h, x:x+w] == i).astype(np.uint8)
            cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
            paths = [(cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2) + [x, y]) for c in cs]
            keep = [(p, int(hier[0][k2][3] >= 0)) for k2, p in enumerate(paths) if len(p) >= 3]
            if keep:
                out.append(dict(x=int(x), y=int(y), w=int(w), h=int(h), cx=x + w / 2, cy=y + h / 2,
                                paths=[p for p, _ in keep], holes=[hh for _, hh in keep], word=None, rule=is_rule))
    return out


def render_from_outlines(blobs, shape) -> np.ndarray:
    """The page drawn from polygons alone: black ink on white."""
    H, W = shape
    img = np.full((H, W), 255, np.uint8)
    for b in blobs:
        for p, hole in zip(b["paths"], b["holes"]):
            cv2.fillPoly(img, [p.astype(np.int32)], 255 if hole else 0)
    return img


def fidelity(gray: np.ndarray, rendered: np.ndarray) -> float:
    """Share of the scan's ink pixels reproduced exactly by the outline render."""
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    ink = ink > 0
    return 1 - np.logical_xor(ink, rendered < 128).sum() / max(1, ink.sum())

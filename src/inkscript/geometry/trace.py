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
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 6:
            continue
        mask = (lab[y:y+h, x:x+w] == i).astype(np.uint8)
        cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        paths = [(cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2) + [x, y]) for c in cs]
        keep = [(p, int(hier[0][k][3] >= 0)) for k, p in enumerate(paths) if len(p) >= 3]
        if keep:
            out.append(dict(x=int(x), y=int(y), w=int(w), h=int(h), cx=x + w / 2, cy=y + h / 2,
                            paths=[p for p, _ in keep], holes=[hh for _, hh in keep], word=None))
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

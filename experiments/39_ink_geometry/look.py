"""Show the "liquid round the letters" geometry: each page's scan beside the shapes traced from it
(geometry/trace.py), the page redrawn from those shapes alone, and what the redraw misses.
-> out/<page>/*.jpg, out/summary.json, out/report.html (built by report.py)."""
import json, sys
from pathlib import Path
import cv2, fitz, numpy as np
from inkscript.geometry.trace import render_gray, page_blobs, render_from_outlines, fidelity

HERE = Path(__file__).parent; OUT = HERE / "out"; P38 = HERE.parent / "38_parser/out/pages"
FIX = HERE.parents[1] / "tests/fixtures/0582-004-009-012/input/0582-004-009-012.pdf"
PAGES = [  # (label, pdf, page index, kind)
    ("0582-004-009-012_p002", FIX, 1, "the fixture: modern single column"),
    ("0747-001-003-001_p006", None, 0, "fully vowelled, before 1960"),
    ("0737-001-020-003_p009", None, 0, "magazine, before 1960"),
    ("0690-037-002-014_p001", None, 0, "Quran verses, 1960s"),
    ("0924-012-005-007_p002", None, 0, "table, before 1960"),
    ("0460-009-003-012_p010", None, 0, "equations, 1980s"),
    ("0005-055-003-004_p008", None, 0, "two columns, 2000s"),
]
rng = np.random.default_rng(7)


def small(img, h=1400):
    return cv2.resize(img, (round(img.shape[1] * h / img.shape[0]), h), interpolation=cv2.INTER_AREA)


def shapes_view(blobs, shape, lw=2):
    """Each shape filled with its own colour, outline drawn dark, holes left white."""
    H, W = shape; img = np.full((H, W, 3), 255, np.uint8)
    for b in blobs:
        col = (0, 0, 200) if b["rule"] else tuple(int(c) for c in rng.integers(90, 230, 3))
        for p, hole in zip(b["paths"], b["holes"]):
            cv2.fillPoly(img, [p.astype(np.int32)], (255, 255, 255) if hole else col)
        cv2.polylines(img, [p.astype(np.int32) for p in b["paths"]], True, (40, 40, 40), lw)
    return img


def densest(ink, w, h):
    """Top-left corner of the w x h window with the most ink."""
    s = cv2.integral((ink > 0).astype(np.uint8))
    best, at = -1, (0, 0)
    for y in range(0, ink.shape[0] - h, h // 4):
        for x in range(0, ink.shape[1] - w, w // 4):
            v = s[y + h, x + w] - s[y, x + w] - s[y + h, x] + s[y, x]
            if v > best: best, at = v, (x, y)
    return at


summary = []
for pid, pdf, idx, kind in PAGES:
    pdf = pdf or P38 / pid / "master" / f"{pid}.pdf"
    d = OUT / pid; d.mkdir(parents=True, exist_ok=True)
    gray = render_gray(fitz.open(pdf)[idx])
    blobs = page_blobs(gray)
    redrawn = render_from_outlines(blobs, gray.shape)
    fid = fidelity(gray, redrawn)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    diff = np.full((*gray.shape, 3), 255, np.uint8)
    diff[(ink > 0) & (redrawn < 128)] = (200, 200, 200)       # reproduced: grey
    diff[(ink > 0) & (redrawn >= 128)] = (0, 0, 220)           # on the scan, missed: red
    diff[(ink == 0) & (redrawn < 128)] = (220, 120, 0)         # drawn, not on the scan: blue
    cv2.imwrite(str(d / "scan.jpg"), small(gray), [cv2.IMWRITE_JPEG_QUALITY, 85])
    cv2.imwrite(str(d / "shapes.jpg"), small(shapes_view(blobs, gray.shape, 3)), [cv2.IMWRITE_JPEG_QUALITY, 85])
    cv2.imwrite(str(d / "redrawn.jpg"), small(redrawn), [cv2.IMWRITE_JPEG_QUALITY, 85])
    cv2.imwrite(str(d / "diff.jpg"), small(diff), [cv2.IMWRITE_JPEG_QUALITY, 85])
    # a close-up at full resolution: the scan, then its outlines with every corner point marked
    x, y = densest(ink, 700, 260); zs = gray[y:y + 260, x:x + 700]
    zb = [b for b in blobs if x <= b["cx"] < x + 700 and y <= b["cy"] < y + 260]
    Z = 3; zo = np.full((260 * Z, 700 * Z, 3), 255, np.uint8)
    for b in zb:
        col = tuple(int(c) for c in rng.integers(150, 240, 3))
        for p, hole in zip(b["paths"], b["holes"]):
            q = ((p - [x, y]) * Z).astype(np.int32)
            cv2.fillPoly(zo, [q], (255, 255, 255) if hole else col)
        for p in b["paths"]:
            q = ((p - [x, y]) * Z).astype(np.int32)
            cv2.polylines(zo, [q], True, (30, 30, 30), 2)
            for pt in q: cv2.circle(zo, tuple(int(v) for v in pt), 3, (0, 0, 210), -1)
    cv2.imwrite(str(d / "zoom_scan.jpg"), cv2.resize(zs, (700 * Z, 260 * Z), interpolation=cv2.INTER_NEAREST), [cv2.IMWRITE_JPEG_QUALITY, 88])
    cv2.imwrite(str(d / "zoom_shapes.jpg"), zo, [cv2.IMWRITE_JPEG_QUALITY, 88])
    pts = sum(len(p) for b in blobs for p in b["paths"])
    summary.append(dict(page=pid, kind=kind, shapes=len(blobs), holes=sum(sum(b["holes"]) for b in blobs),
                        rules=sum(b["rule"] for b in blobs), points=pts, fidelity=round(float(fid), 4),
                        missed=int(((ink > 0) & (redrawn >= 128)).sum()), extra=int(((ink == 0) & (redrawn < 128)).sum()),
                        ink=int((ink > 0).sum()), zoom_shapes=len(zb), zoom_points=sum(len(p) for b in zb for p in b["paths"])))
    print(summary[-1], flush=True)
json.dump(summary, open(OUT / "summary.json", "w"), indent=1)

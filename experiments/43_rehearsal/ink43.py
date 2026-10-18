"""Experiment 43: ink without text — dark regions of a page that no Azure line (and no picture, table or equation
the answer already has) accounts for. No model calls. Used by rules43.pictures through masters43.azure_words.

    blobs(a, p, mask)  -> [{"box": [x0, y0, x1, y1] (0-1000), "fill": dark share of the box, "dark": dark px}]

How (on the 300 dpi render, out/pages of experiment 41, read at 1/3 = 100 dpi):
  dark      grey < DARK, or a saturated colour (show-through and paper tone stay out; print, photos, drawings in)
  mask      every box in `mask` (0-1000; the caller passes the text lines it believes, grown a little, and the
            pictures / tables / equations the answer already has) is blanked
  join      a closing of CLOSE px (about 2.5 mm) joins the strokes of one drawing; connected components
  keep      at least MIN_W x MIN_H (0-1000) and MIN_AREA; fill >= MIN_FILL (a frame or a page border is a thin outline:
            its box is almost empty); not a strip along the page edge (scanner shadow, binding: within EDGE of an
            edge and thinner than EDGE_STRIP)
Every number is set on experiment 41's 55 articles (README, "A picture is never lost").
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

DARK = 110            # grey level (0-255) below which a pixel is ink
TINTED = 0.25         # ... unless that much of the page is coloured: tinted paper
SAT = 90              # ... or a saturated colour (HSV saturation above this; yellowed paper stays below ~60)
SCALE = 3             # read the 300 dpi render at 100 dpi
CLOSE = 10            # px at 100 dpi (~2.5 mm): strokes of one drawing join
MIN_W, MIN_H = 25, 15         # 0-1000 of the page
MIN_AREA = 1500               # w * h in 0-1000 units (a 75 x 20 strip, a 39 x 39 stamp)
MIN_FILL = 0.06               # dark share of the box
EDGE, EDGE_STRIP = 20, 45     # 0-1000: a blob within EDGE of an edge and thinner than EDGE_STRIP is a shadow
SOLID = 0.85                  # a blob at the edge this full is a printed tab (thumb index), not a picture
MIN_DARK = 300                # dark px at 100 dpi (~0.2 cm2 of ink)
THIN = 6                      # px at 100 dpi: a rule is thinner than this (~1.5 mm)
RULE = 0.08                   # a straight run of ink this share of the page long is a rule or a bar
ROW_MAX_H = 50                # ... only for strips (pictures side by side stay apart: 0493 p4's two photos)
ROW_GAP = 2.5                 # pieces in one row (vertical overlap >= half) closer than this many heights: one blob


@lru_cache(maxsize=8)
def _dark(path: str):
    import cv2
    c = cv2.imread(path, cv2.IMREAD_COLOR)
    if c is None:
        return None
    h, w = c.shape[:2]
    c = cv2.resize(c, (w // SCALE, h // SCALE), interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV)
    colour = (hsv[..., 1] > SAT) & (hsv[..., 2] < 235)        # printed colour (0493 p4's green booklet cover)
    if colour.mean() > TINTED:                                 # tinted paper (0513 p2): colour says nothing
        colour[:] = False
    return ((g < DARK) | colour).astype(np.uint8)


def blobs(page_path, mask) -> list[dict]:
    import cv2
    d0 = _dark(str(page_path))
    if d0 is None:
        return []
    d = d0.copy()
    H, W = d.shape
    for b in mask:
        x0, y0 = max(0, int(b[0] * W / 1000)), max(0, int(b[1] * H / 1000))
        x1, y1 = min(W, int(np.ceil(b[2] * W / 1000))), min(H, int(np.ceil(b[3] * H / 1000)))
        if x1 > x0 and y1 > y0:
            d[y0:y1, x0:x1] = 0
    # rules and bars (a run of ink longer than RULE of the page's width or height) are page furniture: out first,
    # so a rule does not join a small mark to the far side of the page
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(RULE * W)), 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(3, int(RULE * H))))
    hl, vl = cv2.morphologyEx(d, cv2.MORPH_OPEN, hk), cv2.morphologyEx(d, cv2.MORPH_OPEN, vk)
    hl &= 1 - cv2.morphologyEx(hl, cv2.MORPH_OPEN, np.ones((THIN, 1), np.uint8))     # thin runs only: rows of a
    vl &= 1 - cv2.morphologyEx(vl, cv2.MORPH_OPEN, np.ones((1, THIN), np.uint8))     # photo are not rules
    d[(hl | vl) > 0] = 0
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (CLOSE, CLOSE))
    j = cv2.morphologyEx(d, cv2.MORPH_CLOSE, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(j, connectivity=8)
    pieces = []
    for i in range(1, n):
        x, y, w, h, _ = st[i]
        if w < 3 or h < 3:
            continue
        dark = int(d[y:y + h, x:x + w][lab[y:y + h, x:x + w] == i].sum())
        if dark < 20:
            continue
        bx = [x * 1000 / W, y * 1000 / H, (x + w) * 1000 / W, (y + h) * 1000 / H]
        pieces.append(dict(box=[round(float(v), 1) for v in bx], fill=round(dark / float(w * h), 3), dark=dark))
    out = []
    for b in rows(pieces):                    # pieces of one strip side by side first, then the size tests
        bx = b["box"]
        bw, bh = bx[2] - bx[0], bx[3] - bx[1]
        if bw < MIN_W or bh < MIN_H or bw * bh < MIN_AREA or b["dark"] < MIN_DARK or b["fill"] < MIN_FILL:
            continue
        near = bx[0] < EDGE or bx[1] < EDGE or bx[2] > 1000 - EDGE or bx[3] > 1000 - EDGE
        if near and (min(bw, bh) < EDGE_STRIP or b["fill"] >= SOLID):
            continue                          # a shadow along the edge, or a solid tab bleeding off it (2571 p1)
        out.append(b)
    return out


def dark_share(page_path, box) -> float:
    """Share of ink pixels in a box (0-1000): above ~0.5 the box is white print on a dark ground."""
    d = _dark(str(page_path))
    if d is None:
        return 0.0
    H, W = d.shape
    x0, y0 = max(0, int(box[0] * W / 1000)), max(0, int(box[1] * H / 1000))
    x1, y1 = min(W, int(np.ceil(box[2] * W / 1000))), min(H, int(np.ceil(box[3] * H / 1000)))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float(d[y0:y1, x0:x1].mean())


def rows(bs: list[dict]) -> list[dict]:
    """Pieces of one strip (a line of hieroglyphs, a row of symbols) side by side: one blob."""
    bs = sorted(bs, key=lambda b: b["box"][0])
    changed = True
    while changed:
        changed = False
        for i in range(len(bs)):
            for j in range(i + 1, len(bs)):
                a, b = bs[i]["box"], bs[j]["box"]
                ha, hb = a[3] - a[1], b[3] - b[1]
                vo = min(a[3], b[3]) - max(a[1], b[1])
                gap = max(a[0], b[0]) - min(a[2], b[2])
                if vo >= 0.5 * min(ha, hb) and gap <= ROW_GAP * max(ha, hb) and max(ha, hb) <= ROW_MAX_H:
                    u = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    area = lambda x: (x[2] - x[0]) * (x[3] - x[1])  # noqa: E731
                    fill = (bs[i]["fill"] * area(a) + bs[j]["fill"] * area(b)) / max(1e-9, area(u))
                    bs[i] = dict(bs[i], box=u, fill=round(fill, 3), dark=bs[i]["dark"] + bs[j]["dark"],
                                 pieces=bs[i].get("pieces", 1) + bs[j].get("pieces", 1),
                                 hit=bs[i].get("hit", []) + bs[j].get("hit", []))
                    del bs[j]
                    changed = True
                    break
            if changed:
                break
    return bs

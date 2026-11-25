"""Experiment 94, goal 3: line crops from OUR line finder for the frozen reader (experiment 92's cut, unchanged).

    python cut94.py test [VARIANT]  -> out/crops48/ln94{V}-<page>.tar, out/own94{V}.jsonl   (experiment 92's 457 pages)
    python cut94.py devaz           -> out/crops48dev/az-<page>.tar only
    python cut94.py dev  [VARIANT]  -> out/crops48dev/{az,ln94{V}}-<page>.tar, out/own94dev{V}.jsonl  (DEV pages:
                                       validation documents of the training pool, never the test set)

Own lines: the line finder's boxes with conf >= 0.25 (experiment 92's threshold), class-agnostic de-duplication
(IoU > 0.5, higher confidence kept).  Each box becomes a 4-point polygon in its reading frame from its direction class
(0 upright, 1 turned clockwise, 2 upside down, 3 turned anticlockwise), so common77.cut_line turns it upright.
Variant "" = upright boxes as given.  Variant "d" (deskew): the page's tilt is measured from the ink of its wide
upright boxes (median of per-box angles from the ink centroid of 16 vertical slices) and, when over 0.25 deg, every
upright box becomes the tilted rectangle whose upright bounds are the box.
Render, cut and keys as experiment 92: 250 dpi pypdfium2 5.12.1, cut_line(test=True) at 48 px.
"""
from __future__ import annotations

import io
import json
import math
import sys
import tarfile

import numpy as np

from common94 import E, E92, OUT, assert_not_locked, azure_lines, iou
from common92 import render_gray

sys.path.insert(0, str(E / "77_scratch_reader"))
from common77 import cut_line, encode  # noqa: E402

CONF = 0.25


def own_boxes(pred, W, H, conf=CONF):
    B = sorted((([b[0] * W, b[1] * H, b[2] * W, b[3] * H]), c, s)
               for b, c, s in zip(pred["boxes"], pred["cls"], pred["conf"]) if s >= conf)
    B.sort(key=lambda x: -x[2])
    keep = []
    for b in B:
        if all(iou(b[0], k[0]) <= 0.5 for k in keep):
            keep.append(b)
    return keep


def poly_of(b, cls):
    x0, y0, x1, y1 = b
    if cls == 1:
        return [x1, y0, x1, y1, x0, y1, x0, y0]
    if cls == 3:
        return [x0, y1, x0, y0, x1, y0, x1, y1]
    if cls == 2:
        return [x1, y1, x0, y1, x0, y0, x1, y0]
    return [x0, y0, x1, y0, x1, y1, x0, y1]


def box_angle(img, b, sx, sy):
    """Tilt (radians, y down) of the ink inside an upright box, from the ink centroid of 16 vertical slices."""
    import cv2
    x0, y0, x1, y1 = int(b[0] * sx), int(b[1] * sy), int(b[2] * sx), int(b[3] * sy)
    a = img[max(0, y0):y1, max(0, x0):x1]
    if a.size == 0 or a.shape[1] < 8 * a.shape[0] // 2:
        return None
    _, t = cv2.threshold(a, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    xs, ys = [], []
    for k, sl in enumerate(np.array_split(t, 16, axis=1)):
        m = sl.sum()
        if m < 5:
            continue
        yy = (sl.sum(axis=1) * np.arange(sl.shape[0])).sum() / m
        xs.append((k + 0.5) * a.shape[1] / 16)
        ys.append(yy)
    if len(xs) < 8:
        return None
    return math.atan(np.polyfit(xs, ys, 1)[0])


def tilted(b, ang):
    """The rectangle tilted by ang whose upright bounds are b, as a TL, TR, BR, BL polygon."""
    bw, bh = b[2] - b[0], b[3] - b[1]
    c, s = math.cos(abs(ang)), math.sin(abs(ang))
    den = c * c - s * s
    w = (bw * c - bh * s) / den
    h = max(0.5 * bh, (bh * c - bw * s) / den)
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    for u, v in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts += [cx + u * ca - v * sa, cy + u * sa + v * ca]
    return pts


def add(tar, key, crop):
    for name, data in ((key + ".jpg", encode(crop)), (key + ".txt", b"")):
        ti = tarfile.TarInfo(name)
        ti.size = len(data)
        tar.addfile(ti, io.BytesIO(data))


def dev_pages(n=150):
    """DEV pages: 150 validation-document pages of the training pool (seed 94), with their Azure JSON and PDF."""
    import random
    rows = [json.loads(l) for l in open(OUT / "train94.jsonl", encoding="utf-8")]
    rows = [r for r in rows if r["split"] == "val"]
    random.Random(941).shuffle(rows)
    az = {}
    for l in open(E / "76_finetune_pilot/out/inventory76.jsonl", encoding="utf-8"):
        a = json.loads(l)
        az.setdefault(a["stem"], a["azure"].replace("/home/yassine/", "/home/appuser/"))
    return [dict(key=r["key"], stem=r["stem"], page=r["page"], pdf=r["pdf"], azure=az[r["stem"]]) for r in rows[:n]]


def main(which="test", var=""):
    import cv2
    cv2.setNumThreads(1)
    if which == "test":
        pages = [json.loads(l) for l in open(E92 / "pages92.jsonl", encoding="utf-8")]
        pred = json.load(open(OUT / "pred94_line.json"))
        D, meta, do_az = OUT / "crops48", OUT / f"own94{var}.jsonl", False
    elif which == "devaz":                      # only Azure's cuts of the dev pages (no prediction needed)
        pages = dev_pages()
        pred = {p["key"]: dict(boxes=[], cls=[], conf=[]) for p in pages}
        D, meta, do_az = OUT / "crops48dev", OUT / "own94devaz_unused.jsonl", True
    else:
        pages = dev_pages()
        pred = json.load(open(OUT / "pred94_line_val.json"))
        D, meta, do_az = OUT / "crops48dev", OUT / f"own94dev{var}.jsonl", True
    assert_not_locked([p["key"] for p in pages])
    D.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["page"] for l in open(meta, encoding="utf-8")} if meta.exists() else set()
    with open(meta, "a", encoding="utf-8") as fm:
        for n, p in enumerate(pages, 1):
            k = p["key"]
            if k in done or k not in pred:
                continue
            img = render_gray(p["pdf"], p["page"])
            lines, W, H = azure_lines(p["azure"], p["page"])
            sx, sy = img.shape[1] / W, img.shape[0] / H
            if do_az and not (D / f"az-{k}.tar").exists():
                with tarfile.open(D / f"az-{k}.tar", "w") as t:
                    for ln in lines:
                        if ln["poly"]:
                            crop, _ = cut_line(img, ln["poly"], sx, sy, test=True)
                            if crop is not None:
                                add(t, f"{k}_l{ln['i']:03d}", crop)
            own = own_boxes(pred[k], W, H)
            pa = None
            if var == "d":
                angs = [a for b, c, _ in own if c == 0 and (a := box_angle(img, b, sx, sy)) is not None]
                pa = float(np.median(angs)) if len(angs) >= 3 else None
                pa = max(-0.09, min(0.09, pa)) if pa is not None and abs(pa) > math.radians(0.25) else None
            rows = []
            if which == "devaz":
                continue
            with tarfile.open(D / f"ln94{var}-{k}.tar", "w") as t:
                for j, (b, c, s) in enumerate(own):
                    poly = tilted(b, pa) if (pa is not None and c == 0) else poly_of(b, c)
                    crop, _ = cut_line(img, poly, sx, sy, test=True)
                    key = f"{k}_ln{j:03d}"
                    if crop is not None:
                        add(t, key, crop)
                    rows.append(dict(key=key, page=k, src=f"ln94{var}", j=j, box=[round(v, 5) for v in b],
                                     cls=c, conf=s, cut=crop is not None, page_angle=pa))
            for r in rows:
                fm.write(json.dumps(r, ensure_ascii=False) + "\n")
            fm.flush()
            if n % 20 == 0:
                print(n, "pages", flush=True)
    print("CUT94_DONE", which, var, flush=True)


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["test"]))

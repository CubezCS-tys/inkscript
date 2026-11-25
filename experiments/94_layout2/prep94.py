"""Experiment 94 on the GPU host: render the pages and write the two YOLO datasets.

    python prep94.py train  TRAIN_JSONL PDF_DIR D WORKERS   -> D/{lay,line}/images/{train,val}/<key>.jpg (grey, 1536 px long side; hard links)
                                                               D/lay/labels/{train,val}/<key>.txt   (16 fine classes)
                                                               D/line/labels/{train,val}/<key>.txt  (4 orientation classes)
                                                               + synthetic line pages D/line/images/syn/<key>_s{rot,band,gray,dots}.jpg (line dataset only)
                                                               D/lay.yaml, D/line.yaml
    python prep94.py test   PAGES_JSONL PDF_DIR D WORKERS   -> D/test/<key>.jpg  (experiment 92's 457 pages)

Boxes are the upright bounds of Azure's line polygons (page units -> pixels).  Layout class = the line's fine type
(common94.FINE; a line Argon left out is "other").  Line class = Azure's text direction (0 upright, 1 turned clockwise,
2 upside down, 3 turned anticlockwise).
Synthetic line pages (train split only, seed 94, each a copy of a real page, labels kept / transformed):
- rot  (8% of pages): the page turned 90 deg clockwise or anticlockwise; every line's direction class turns with it;
- band (5%): 1-4 consecutive upright lines on a dark band, light ink (white text on a dark strip);
- gray (3%): the same lines darker ink on a mid-grey band;
- dots (5%): dotted leaders drawn in the empty space beside short lines (not part of any box), as fill-in-the-blank
  pages print them.
Only the line dataset uses the synthetic pages; the layout dataset uses the real pages.
"""
from __future__ import annotations

import json
import os
import random
import sys
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

SIDE = 1536
FINE = ["title", "author", "affiliation", "abstract", "heading", "body", "list", "footnote", "reference", "table",
        "caption", "page_number", "header", "equation", "verse", "other"]
G = {}


def render(pdf, page):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    try:
        pg = doc[page - 1]
        w, h = pg.get_size()
        s = SIDE / max(w, h)
        a = pg.render(scale=s, grayscale=True).to_numpy()
        if a.ndim == 3:
            a = a[..., 0]
        return np.ascontiguousarray(a)
    finally:
        doc.close()


def boxes_of(r, img):
    h, w = img.shape
    sx, sy = w / r["W"], h / r["H"]
    out = []
    for x in r["lines"]:
        p = x["poly"]
        xs, ys = [v * sx for v in p[0::2]], [v * sy for v in p[1::2]]
        b = [max(0, min(xs)), max(0, min(ys)), min(w, max(xs)), min(h, max(ys))]
        if b[2] - b[0] >= 2 and b[3] - b[1] >= 2:
            out.append((b, x))
    return out


def yolo_rows(items, w, h):
    return "\n".join(f"{c} {(b[0] + b[2]) / 2 / w:.5f} {(b[1] + b[3]) / 2 / h:.5f} {(b[2] - b[0]) / w:.5f} "
                     f"{(b[3] - b[1]) / h:.5f}" for b, c in items)


def save(img, path):
    cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 90])


def synth(kind, img, B, rnd):
    """(new image, [(box, orient)]) or None."""
    h, w = img.shape
    if kind == "rot":
        cw = rnd.random() < 0.5
        out = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE if cw else cv2.ROTATE_90_COUNTERCLOCKWISE)
        nb = []
        for b, o in B:
            if cw:   # (x, y) -> (h - y, x)
                nb.append(([h - b[3], b[0], h - b[1], b[2]], (o + 1) % 4))
            else:    # (x, y) -> (y, w - x)
                nb.append(([b[1], w - b[2], b[3], w - b[0]], (o + 3) % 4))
        return out, nb
    up = sorted([(b, o) for b, o in B if o == 0], key=lambda t: t[0][1])
    if kind in ("band", "gray"):
        if len(up) < 2:
            return None
        k = rnd.randint(1, min(4, len(up)))
        s = rnd.randrange(0, len(up) - k + 1)
        sel = up[s:s + k]
        lh = float(np.median([b[3] - b[1] for b, _ in sel]))
        x0 = max(0, int(min(b[0] for b, _ in sel) - lh * rnd.uniform(0.3, 1.5)))
        x1 = min(w, int(max(b[2] for b, _ in sel) + lh * rnd.uniform(0.3, 1.5)))
        y0 = max(0, int(min(b[1] for b, _ in sel) - lh * rnd.uniform(0.2, 0.7)))
        y1 = min(h, int(max(b[3] for b, _ in sel) + lh * rnd.uniform(0.2, 0.7)))
        out = img.copy()
        p = out[y0:y1, x0:x1].astype(np.float32) / 255.0
        if kind == "band":
            d, L = rnd.uniform(10, 90), rnd.uniform(190, 255)
            out[y0:y1, x0:x1] = np.clip(d + (L - d) * (1.0 - p), 0, 255).astype(np.uint8)
        else:
            g = rnd.uniform(110, 185)
            out[y0:y1, x0:x1] = np.clip(g * p, 0, 255).astype(np.uint8)
        return out, B
    if kind == "dots":
        if len(up) < 3:
            return None
        L = min(b[0] for b, _ in up)
        R = max(b[2] for b, _ in up)
        out = img.copy()
        n = 0
        occ = [b for b, _ in B]
        for b, _ in up:
            lh = b[3] - b[1]
            if b[0] - L < 3 * lh or rnd.random() < 0.4:
                continue
            gap0, gap1 = L + rnd.uniform(0, 2) * lh, b[0] - 0.4 * lh
            if any(q[0] < gap1 and q[2] > gap0 and q[1] < b[3] and q[3] > b[1] and q is not b for q in occ):
                continue
            yb = int(b[3] - lh * rnd.uniform(0.15, 0.3))
            step = max(3.0, lh * rnd.uniform(0.25, 0.45))
            rr = max(1, int(round(lh * rnd.uniform(0.04, 0.08))))
            x = gap1
            while x > gap0:
                cv2.circle(out, (int(x), yb), rr, int(rnd.uniform(0, 70)), -1)
                x -= step
            n += 1
        _ = R
        return (out, B) if n else None
    return None


def work_train(r):
    D = G["D"]
    try:
        img = render(os.path.join(G["pdf"], os.path.basename(r["pdf"])), r["page"])
    except Exception as e:  # noqa: BLE001
        return r["key"], f"render {e}"
    h, w = img.shape
    sp = r["split"]
    B = boxes_of(r, img)
    save(img, D / "lay/images" / sp / f"{r['key']}.jpg")
    os.link(D / "lay/images" / sp / f"{r['key']}.jpg", D / "line/images" / sp / f"{r['key']}.jpg")   # hard link:
    # ultralytics resolves the yaml paths, so a symlinked folder would lose the /images/ -> /labels/ mapping
    (D / "lay/labels" / sp / f"{r['key']}.txt").write_text(
        yolo_rows([(b, FINE.index(x["fine"] or "other")) for b, x in B], w, h))
    (D / "line/labels" / sp / f"{r['key']}.txt").write_text(yolo_rows([(b, x["orient"]) for b, x in B], w, h))
    made = []
    if sp == "train":
        rnd = random.Random(f"94{r['key']}")
        u = rnd.random()
        kind = "rot" if u < 0.08 else "band" if u < 0.13 else "gray" if u < 0.16 else "dots" if u < 0.21 else None
        if kind:
            s = synth(kind, img, [(b, x["orient"]) for b, x in B], rnd)
            if s:
                im2, nb = s
                k2 = f"{r['key']}_s{kind}"
                save(im2, D / "line/images/syn" / f"{k2}.jpg")
                (D / "line/labels/syn" / f"{k2}.txt").write_text(yolo_rows(nb, im2.shape[1], im2.shape[0]))
                made.append(kind)
    return r["key"], made


def work_test(r):
    img = render(os.path.join(G["pdf"], os.path.basename(r["pdf"])), r["page"])
    save(img, G["D"] / "test" / f"{r['key']}.jpg")
    return r["key"], img.shape


def init(d, pdf):
    G["D"], G["pdf"] = Path(d), pdf
    cv2.setNumThreads(1)


def main():
    mode, jl, pdf, d, nw = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4]).resolve(), int(sys.argv[5])
    rows = [json.loads(l) for l in open(jl, encoding="utf-8")]
    if mode == "train":
        for sp in ("train", "val"):
            for sub in ("lay/images", "lay/labels", "line/images", "line/labels"):
                (d / sub / sp).mkdir(parents=True, exist_ok=True)
        (d / "line/images/syn").mkdir(parents=True, exist_ok=True)
        (d / "line/labels/syn").mkdir(parents=True, exist_ok=True)
        fn = work_train
    else:
        (d / "test").mkdir(parents=True, exist_ok=True)
        fn = work_test
    from collections import Counter
    made, bad = Counter(), []
    with Pool(nw, initializer=init, initargs=(str(d), pdf)) as P:
        for n, (k, m) in enumerate(P.imap_unordered(fn, rows, chunksize=8), 1):
            if isinstance(m, str):
                bad.append((k, m))
            elif isinstance(m, list):
                made.update(m)
            if n % 1000 == 0:
                print(n, len(rows), dict(made), len(bad), flush=True)
    if mode == "train":
        for name, names in (("lay", FINE), ("line", ["up", "cw", "flip", "ccw"])):
            tr = "[images/train, images/syn]" if name == "line" else "images/train"
            (d / f"{name}.yaml").write_text(f"path: {d / name}\ntrain: {tr}\nval: images/val\nnames:\n" +
                                            "".join(f"  {i}: {c}\n" for i, c in enumerate(names)))
    json.dump(dict(rows=len(rows), synthetic=made, bad=bad), open(os.environ.get("OUT94", "/work/out") + f"/prep94_{mode}.json", "w"))
    print("PREP94_DONE", mode, len(rows), dict(made), len(bad), flush=True)


if __name__ == "__main__":
    main()

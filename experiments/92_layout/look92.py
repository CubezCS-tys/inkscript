"""Experiment 92, step 8: pictures for the eye.  For a page: the reference (Argon's types on Azure's lines, with
Argon's reading order as numbers), our layout model's own lines (class colours, our XY-cut order), the rivers' blocks.

    python3 look92.py KEY [KEY ...]   -> out/look/<key>.jpg  (three panels side by side)
    python3 look92.py auto            -> pictures for the pages listed in out/look/pick.json and out/look/index.html
"""
from __future__ import annotations

import json
import sys

import cv2

from common92 import LABELS, OUT, xycut_order
from score92 import own_lines

COL = {"furniture": (160, 160, 160), "heading": (0, 0, 220), "body": (40, 160, 40), "list": (200, 120, 0),
       "verse": (180, 0, 180), "footnote": (0, 140, 255), "references": (140, 70, 20), "caption": (0, 200, 200),
       "table": (220, 0, 120), "equation": (0, 90, 160), "other": (90, 90, 90), None: (0, 0, 0)}


def panel(img, boxes, labels, nums, W, H, title):
    im = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    h, w = im.shape[:2]
    over = im.copy()
    for b, lab, n in zip(boxes, labels, nums):
        x0, y0, x1, y1 = int(b[0] / W * w), int(b[1] / H * h), int(b[2] / W * w), int(b[3] / H * h)
        cv2.rectangle(over, (x0, y0), (x1, y1), COL.get(lab, (0, 0, 0)), -1)
    im = cv2.addWeighted(over, 0.35, im, 0.65, 0)
    for b, lab, n in zip(boxes, labels, nums):
        x0, y0, x1, y1 = int(b[0] / W * w), int(b[1] / H * h), int(b[2] / W * w), int(b[3] / H * h)
        cv2.rectangle(im, (x0, y0), (x1, y1), COL.get(lab, (0, 0, 0)), 1)
        if n is not None:
            cv2.putText(im, str(n), (x1 + 2, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)
    cv2.rectangle(im, (0, 0), (w, 22), (255, 255, 255), -1)
    cv2.putText(im, title, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    return im


def draw(key, ref, Y, R):
    img = cv2.imread(str(OUT / "pages" / f"{key}.jpg"), cv2.IMREAD_GRAYSCALE)
    W, H = ref["W"], ref["H"]
    L = [x for x in ref["lines"] if x["box"]]
    a = panel(img, [x["box"] for x in L], [x["coarse"] for x in L], [x["rank"] for x in L], W, H,
              "reference: Argon types + order")
    own = own_lines(Y[key], W, H)
    o = xycut_order([b for b, _, _ in own])
    rk = {j: n for n, j in enumerate(o)}
    b = panel(img, [x[0] for x in own], [x[1] for x in own], [rk[j] for j in range(len(own))], W, H,
              "ours: layout model lines + XY-cut order")
    rv = R[key]
    sx, sy = W / rv["W"], H / rv["H"]
    rb = [(x * sx, y * sy, (x + w) * sx, (y + h) * sy) for x, y, w, h in rv["blocks"]]
    ro = {j: n for n, j in enumerate(xycut_order(rb))}
    c = panel(img, rb, ["other"] * len(rb), [ro[j] for j in range(len(rb))], W, H, "rivers: blocks")
    leg = img.shape[1]
    import numpy as np
    key_img = np.full((40, 3 * leg, 3), 255, np.uint8)
    x = 4
    for lab in LABELS:
        cv2.rectangle(key_img, (x, 10), (x + 14, 24), COL[lab], -1)
        cv2.putText(key_img, lab, (x + 18, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        x += 30 + 9 * len(lab)
    out = np.vstack([np.hstack([a, b, c]), key_img])
    (OUT / "look").mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / "look" / f"{key}.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return OUT / "look" / f"{key}.jpg"


def main(keys):
    refs = {json.loads(l)["key"]: json.loads(l) for l in open(OUT / "ref92.jsonl", encoding="utf-8")}
    import os
    Y = json.load(open(OUT / f"yolo92_{os.environ.get('MODEL', 'r1')}.json"))
    R = json.load(open(OUT / "rivers92.json"))
    notes = {}
    if keys == ["auto"]:
        notes = json.load(open(OUT / "look/pick.json"))
        keys = list(notes)
    for k in keys:
        print(draw(k, refs[k], Y, R))
    if notes:
        body = "".join(f"<h3>{k}</h3><p>{v}</p><img src='{k}.jpg' width='100%'>" for k, v in notes.items())
        (OUT / "look/index.html").write_text(f"<meta charset=utf-8><body style='font-family:sans-serif'>{body}",
                                              encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])

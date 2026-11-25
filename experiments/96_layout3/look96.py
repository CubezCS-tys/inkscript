"""Experiment 96: draw a page's lines in an order (DEV pages, for developing the rules; never the test set here).

    python look96.py KEY METHOD [METHOD2]  -> out/look/dev_<KEY>_<METHOD>.jpg  (Argon's order | the method's order:
                                              boxes numbered, successor steps drawn as lines, steps Argon does not take red)
"""
from __future__ import annotations

import json
import pickle
import sys

import cv2
import numpy as np

from common96 import E, O94, OUT
from orderdev96 import methods

sys.path.insert(0, str(E / "92_layout"))
from common92 import render_gray  # noqa: E402


def panel(img, sx, sy, L, order, ref_next):
    im = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    pts = {}
    for q, k in enumerate(order):
        b = L[k]["box"]
        p0, p1 = (int(b[0] * sx), int(b[1] * sy)), (int(b[2] * sx), int(b[3] * sy))
        cv2.rectangle(im, p0, p1, (200, 120, 0), 1)
        pts[k] = ((p0[0] + p1[0]) // 2, (p0[1] + p1[1]) // 2)
        cv2.putText(im, str(q), (p1[0] + 2, p1[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 200), 1)
    for a, b in zip(order, order[1:]):
        ok = ref_next.get(a) == b
        cv2.line(im, pts[a], pts[b], (0, 160, 0) if ok else (0, 0, 255), 1 if ok else 2)
    return im


def main(key, *ms):
    P = {p["key"]: p for p in pickle.load(open(OUT / "dev96_pages.pkl", "rb"))}
    p = P[key]
    pdf = next(json.loads(l)["pdf"] for l in open(O94 / "train94.jsonl", encoding="utf-8") if l.startswith('{"key": "' + key))
    img = render_gray(pdf, int(key.split("_p")[1]), dpi=110)
    sx, sy = img.shape[1] / p["W"], img.shape[0] / p["H"]
    L = p["lines"]
    ref = sorted(range(len(L)), key=lambda k: L[k]["rank"])
    rn = {a: b for a, b in zip(ref, ref[1:])}
    M = methods()
    pan = [panel(img, sx, sy, L, ref, rn)]
    for m in ms:
        pan.append(panel(img, sx, sy, L, M[m]([x["box"] for x in L], [x["fine"] for x in L], p["rtl"], p["H"], p["W"]), rn))
    (OUT / "look").mkdir(exist_ok=True)
    f = OUT / "look" / f"dev_{key}_{'_'.join(ms)}.jpg"
    cv2.imwrite(str(f), np.hstack(pan), [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(f)


if __name__ == "__main__":
    main(*sys.argv[1:])

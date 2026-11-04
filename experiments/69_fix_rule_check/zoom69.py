"""Experiment 69: one unit's word at high zoom (grey, contrast-stretched) -> out/zoom.jpg.   zoom69.py K [K ...]
(K = the row number on the sheets, i.e. the k-th unit of sheets69.todo)"""
import sys
import cv2
import numpy as np
import common69 as C
import sheets69
from sample66 import page_image, crop_box

import json
_order = json.load(open(C.ORDER))
_by = {u["uid"]: u for u in C.jlines(C.UNITS)}
U = [_by[x] for x in _order]
rows = []
for k in map(int, sys.argv[1:]):
    r = U[k - 1]
    img = cv2.imread(str(page_image(r)), cv2.IMREAD_GRAYSCALE)
    x0, y0, x1, y1 = crop_box(r, img)
    h = max(20, y1 - y0)
    c = img[max(0, y0 - h // 3):y1 + h // 3, max(0, x0 - h // 2):x1 + h // 2]
    lo, hi = np.percentile(c, 1), np.percentile(c, 99)
    c = np.clip((c.astype(float) - lo) * 255 / max(1, hi - lo), 0, 255).astype(np.uint8)
    sc = min(10.0, 1400 / c.shape[1], 420 / c.shape[0])
    c = cv2.resize(c, (int(c.shape[1] * sc), int(c.shape[0] * sc)), interpolation=cv2.INTER_CUBIC)
    row = np.full((c.shape[0] + 10, 1500), 255, np.uint8)
    row[5:5 + c.shape[0], 80:80 + c.shape[1]] = c
    cv2.putText(row, str(k), (4, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 0, 2)
    rows.append(row)
cv2.imwrite(str(C.OUT / "zoom.jpg"), np.vstack(rows))

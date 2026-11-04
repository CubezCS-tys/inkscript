"""Experiment 66: zoom on a few sampled fixes (the word at 4x) -> out/zoom.jpg.   zoom66.py SID [SID ...]"""
import sys
import cv2
import numpy as np
import common66 as C
from sample66 import page_image, crop_box

S = {r["sid"]: r for r in C.jlines(C.OUT / "sample.jsonl")}
rows = []
for sid in map(int, sys.argv[1:]):
    r = S[sid]
    img = cv2.imread(str(page_image(r)), cv2.IMREAD_COLOR)
    x0, y0, x1, y1 = crop_box(r, img)
    h = max(20, y1 - y0)
    c = img[max(0, y0 - h // 2):y1 + h // 2, max(0, x0 - 2 * h):x1 + 2 * h]
    sc = min(4.0, 1400 / c.shape[1], 260 / c.shape[0])
    c = cv2.resize(c, (int(c.shape[1] * sc), int(c.shape[0] * sc)), interpolation=cv2.INTER_CUBIC)
    row = np.full((c.shape[0] + 10, 1500, 3), 255, np.uint8)
    row[5:5 + c.shape[0], 80:80 + c.shape[1]] = c
    cv2.putText(row, str(sid), (4, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 0, 0), 2)
    rows.append(row)
cv2.imwrite(str(C.OUT / "zoom.jpg"), np.vstack(rows))

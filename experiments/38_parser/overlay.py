"""The new layout drawn on the scan -> out/pages/<pid>/shots/layout_overlay.jpg: each block's box coloured by kind,
its place in the reading order, and arrows from block to block.

    /home/yassine/inkscript/.venv/bin/python overlay.py [PID ...]
"""
from __future__ import annotations

import json
import sys

import cv2

from common import OUT, page_image, pages

COL = {"p": (60, 140, 60), "heading": (30, 30, 200), "title": (0, 0, 160), "li": (160, 110, 0), "fn": (150, 0, 150),
       "caption": (0, 140, 200), "figure": (200, 80, 0), "table": (0, 90, 230), "formula": (200, 0, 100),
       "header": (130, 130, 130), "footer": (130, 130, 130), "pagenum": (130, 130, 130)}


def draw(pid):
    L = json.loads((OUT / "pages" / pid / "layout.json").read_text(encoding="utf-8"))
    img = cv2.cvtColor(page_image(pid), cv2.COLOR_GRAY2BGR)
    prev = None
    k = 0
    for b in L["blocks"]:
        x0, y0, x1, y1 = (int(v) for v in b["box"])
        c = COL.get(b["role"], (0, 0, 0))
        cv2.rectangle(img, (x0, y0), (x1, y1), c, 4)
        if b["role"] in ("header", "footer", "pagenum"):
            continue
        k += 1
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        if prev:
            cv2.arrowedLine(img, prev, (cx, cy), (0, 0, 255), 3, tipLength=0.03)
        prev = (cx, cy)
        cv2.circle(img, (x1 - 30, y0 + 30), 28, c, -1)
        cv2.putText(img, str(k), (x1 - 48, y0 + 42), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3)
    sd = OUT / "pages" / pid / "shots"
    sd.mkdir(exist_ok=True)
    h = 1400
    s = h / img.shape[0]
    cv2.imwrite(str(sd / "layout_overlay.jpg"), cv2.resize(img, (int(img.shape[1] * s), h)),
                [cv2.IMWRITE_JPEG_QUALITY, 80])


if __name__ == "__main__":
    want = sys.argv[1:]
    for m in pages():
        if (not want or m["page_id"] in want) and (OUT / "pages" / m["page_id"] / "layout.json").exists():
            draw(m["page_id"])

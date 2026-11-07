"""Experiment 92, step 2: experiment 39's layout model (rounds 1 and 2) and the rivers of paper on every test page
(local CPU, niced, THREADS threads, default 2).

    nice -n 19 ionice -c3 out/venv/bin/python yolo92.py
        -> out/pages/<key>.jpg (grey, 1280 px long side: the model's input and the pictures' background)
           out/yolo92_r1.json, out/yolo92_r2.json  {key: {size, boxes (0-1, xyxy), cls, conf}}  (conf >= 0.05)
           out/rivers92.json  {key: {W, H (100-dpi pixels), blocks [[x, y, w, h], ...], u, g}}

The model is run as experiment 39's predict_local.py runs it (unfused, imgsz 1280, conf 0.05, iou 0.5, max_det 600)
on the page rendered at 250 dpi with pypdfium2 5.12.1 and shrunk to 1280 px (experiment 39 trained on 1280-px grey
pages).  Rivers: experiment 39's rivers.rivers() unchanged, on a 100-dpi render (its own resolution).
"""
from __future__ import annotations

import json
import os
import re
import time

import cv2
import torch

from common92 import E, OUT, WEIGHTS, assert_not_locked, render_gray

torch.set_num_threads(int(os.environ.get("THREADS", 2)))
SIDE = 1280


def load_rivers():
    src = (E / "39_ink_geometry/rivers.py").read_text()
    a = src.index("def rivers(gray):")
    b = src.index("\n", src.index("return ink, bars", a))
    ns = {"cv2": cv2, "np": __import__("numpy")}
    exec(src[a:b], ns)
    return ns["rivers"]


def main():
    import doclayout_yolo.nn.tasks as T
    T.BaseModel.fuse = lambda self, verbose=True: self
    from doclayout_yolo import YOLOv10
    pages = [json.loads(l) for l in open(OUT / "pages92.jsonl", encoding="utf-8")]
    assert_not_locked([p["key"] for p in pages])
    (OUT / "pages").mkdir(parents=True, exist_ok=True)
    models = {k: YOLOv10(str(w)) for k, w in WEIGHTS.items()}
    files = {k: OUT / f"yolo92_{k}.json" for k in models}
    pred = {k: (json.load(open(f)) if f.exists() else {}) for k, f in files.items()}
    rf = OUT / "rivers92.json"
    riv = json.load(open(rf)) if rf.exists() else {}
    rivers = load_rivers()
    t0 = time.time()
    for n, p in enumerate(pages, 1):
        k = p["key"]
        jp = OUT / "pages" / f"{k}.jpg"
        if not jp.exists():
            g = render_gray(p["pdf"], p["page"])
            h, w = g.shape
            s = SIDE / max(h, w)
            cv2.imwrite(str(jp), cv2.resize(g, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA),
                        [cv2.IMWRITE_JPEG_QUALITY, 90])
        for m, model in models.items():
            if k in pred[m]:
                continue
            r = model.predict(str(jp), imgsz=1280, conf=0.05, iou=0.5, verbose=False, max_det=600, device="cpu")[0]
            pred[m][k] = dict(size=list(r.orig_shape)[::-1], boxes=[[round(v, 5) for v in b] for b in r.boxes.xyxyn.tolist()],
                              cls=[int(c) for c in r.boxes.cls.tolist()], conf=[round(c, 4) for c in r.boxes.conf.tolist()])
        if k not in riv:
            g = render_gray(p["pdf"], p["page"], dpi=100)
            _, _, _, _, _, blocks, u, gg = rivers(g)
            riv[k] = dict(W=g.shape[1], H=g.shape[0], blocks=blocks, u=int(u), g=float(gg))
        if n % 10 == 0 or n == len(pages):
            for m, f in files.items():
                json.dump(pred[m], open(f, "w"))
            json.dump(riv, open(rf, "w"))
            print(f"{n}/{len(pages)} {time.time() - t0:.0f}s", flush=True)
    print("YOLO92_DONE", flush=True)


if __name__ == "__main__":
    main()

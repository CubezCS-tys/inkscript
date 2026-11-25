"""Experiment 94 on the GPU host: fine-tune DocLayout-YOLO (from experiment 39's round-1 weights) and predict.

    python yolo94.py train NAME DATA_YAML IMGSZ HOURS BATCH WORKERS   -> /work/run_NAME/r/weights/best.pt
    python yolo94.py predict NAME WEIGHTS TEST_DIR IMGSZ OUT_JSON      -> {key: {size, boxes (0-1 xyxy), cls, conf}}

Settings as experiment 39 (mosaic off, no flips, no rotation, translate 0.02, scale 0.1, unfused layers, AMP check
skipped), with a time budget (ultralytics' `time`: the epochs are fitted to HOURS after the first one).
"""
from __future__ import annotations

import glob
import json
import os
import sys

os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")


def patch():
    import numpy as np
    if not hasattr(np, "trapz"):          # numpy 2: the library's mAP still calls np.trapz
        np.trapz = np.trapezoid
    import doclayout_yolo.engine.trainer as TR
    import doclayout_yolo.nn.tasks as NT
    NT.BaseModel.fuse = lambda self, verbose=True: self
    TR.check_amp = lambda model: True


def train(name, data, imgsz, hours, batch, workers):
    patch()
    from doclayout_yolo import YOLOv10
    m = YOLOv10(os.environ.get("INIT94", "/work/init/r1.pt"))
    m.train(data=data, save_period=-1, epochs=100, time=float(hours), imgsz=int(imgsz), batch=int(batch),
            patience=100, project=os.environ.get("RUN94", "/work") + f"/run_{name}", name="r", exist_ok=True, workers=int(workers), plots=False,
            close_mosaic=0, mosaic=0.0, fliplr=0.0, degrees=0, translate=0.02, scale=0.1, hsv_h=0, hsv_s=0,
            hsv_v=0.2, val=True, cache=False)
    print("TRAIN94_DONE", name, flush=True)


def predict(name, weights, test_dir, imgsz, out_json):
    patch()
    from doclayout_yolo import YOLOv10
    m = YOLOv10(weights)
    pred = {}
    for f in sorted(glob.glob(f"{test_dir}/*.jpg")):
        r = m.predict(f, imgsz=int(imgsz), conf=0.05, iou=0.5, verbose=False, max_det=1000)[0]
        pred[os.path.basename(f)[:-4]] = dict(size=list(r.orig_shape)[::-1],
                                              boxes=[[round(v, 5) for v in b] for b in r.boxes.xyxyn.tolist()],
                                              cls=[int(c) for c in r.boxes.cls.tolist()],
                                              conf=[round(c, 4) for c in r.boxes.conf.tolist()])
    json.dump(pred, open(out_json, "w"))
    print("PREDICT94_DONE", name, len(pred), flush=True)


if __name__ == "__main__":
    {"train": train, "predict": predict}[sys.argv[1]](*sys.argv[2:])

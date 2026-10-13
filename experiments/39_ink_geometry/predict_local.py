"""Exp 39: the fine-tuned layout model's predictions on the val and test pages, on this machine's CPU.

The GPU run's own prediction step crashed: doclayout_yolo fuses Conv+BN before predicting, and its dilated block
then looks for the BN it just removed. Predicting unfused gives the same boxes. Writes out/gpu/predictions.json.
"""
import glob, json, os, sys
import doclayout_yolo.nn.tasks as T
T.BaseModel.fuse = lambda self, verbose=True: self
from doclayout_yolo import YOLOv10
import torch
torch.set_num_threads(int(os.environ.get("THREADS", 8)))

HERE = os.path.dirname(os.path.abspath(__file__))
best = YOLOv10(f"{HERE}/out/gpu/out/run/weights/best.pt")
OUT = f"{HERE}/out/gpu/predictions.json"
pred = json.load(open(OUT)) if os.path.exists(OUT) else {}
for split in ("test", "val"):
    for f in sorted(glob.glob(f"{HERE}/out/train/yolo/images/{split}/*.jpg")):
        k = os.path.basename(f)[:-4]
        if k in pred:
            continue
        r = best.predict(f, imgsz=1280, conf=0.05, iou=0.5, verbose=False, max_det=600, device="cpu")[0]
        pred[k] = dict(split=split, size=list(r.orig_shape)[::-1], boxes=r.boxes.xyxyn.tolist(),
                       cls=[int(c) for c in r.boxes.cls.tolist()], conf=r.boxes.conf.tolist())
        if len(pred) % 20 == 0:
            json.dump(pred, open(OUT, "w")); print(len(pred), flush=True)
json.dump(pred, open(OUT, "w"))
print("predicted", len(pred))

"""Exp 39: the fine-tuned layout model's predictions on the val and test pages, on this machine's CPU.

The GPU run's own prediction step crashed: doclayout_yolo fuses Conv+BN before predicting, and its dilated block
then looks for the BN it just removed. Predicting unfused gives the same boxes. Writes out/gpu/predictions.json.
Round 2: `predict_local.py round2` = the round-1 model on round 2's candidates (out/round2/pred.json);
WEIGHTS=out/gpu2/out/run/weights/best.pt YOLO=yolo2 OUT=out/gpu2/predictions.json = the round-2 model on its val+test.
"""
import glob, json, os, sys
import doclayout_yolo.nn.tasks as T
T.BaseModel.fuse = lambda self, verbose=True: self
from doclayout_yolo import YOLOv10
import torch
torch.set_num_threads(int(os.environ.get("THREADS", 8)))

HERE = os.path.dirname(os.path.abspath(__file__))
E = lambda k, d: os.path.join(HERE, os.environ.get(k, d))
best = YOLOv10(E("WEIGHTS", "out/gpu/out/run/weights/best.pt"))
ROUND2 = sys.argv[1:] == ["round2"]                                # the round-1 model on round 2's candidate pages
OUT = f"{HERE}/out/round2/pred.json" if ROUND2 else E("OUT", "out/gpu/predictions.json")
SPLITS = [("cand", f"{HERE}/out/round2/pages/*.jpg")] if ROUND2 else [(s, f"{HERE}/out/train/{os.environ.get('YOLO', 'yolo')}/images/{s}/*.jpg") for s in ("test", "val")]
pred = json.load(open(OUT)) if os.path.exists(OUT) else {}
for split, pat in SPLITS:
    for f in sorted(glob.glob(pat)):
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

#!/bin/bash
# On the rented GPU, after setup.sh and the dataset upload: fine-tune, then predict the val and test pages.
# Writes /work/out/ (weights, results.csv, predictions json) and /work/train.done (or train.failed).
cd /work
until [ -f setup.done ] && [ -f yolo.uploaded ]; do sleep 10; done
tar xf yolo.tar && sed -i "s#^path: .*#path: /work/yolo#" yolo/data.yaml
TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1 python - <<'PY' > train.log 2>&1 || { touch train.failed; exit 1; }
import json, glob, os
from doclayout_yolo import YOLOv10
import doclayout_yolo.engine.trainer as TR
TR.check_amp = lambda model: True          # its AMP self-test loads yolov8n.pt, which torch 2.9 refuses; a 5090 runs AMP
m = YOLOv10('/work/doclayout_yolo_docstructbench_imgsz1024.pt')
m.train(data='/work/yolo/data.yaml', epochs=int(os.environ.get('EPOCHS', 80)), imgsz=1280, batch=int(os.environ.get('BATCH', 8)), patience=20,
        project='/work/out', name='run', exist_ok=True, workers=8, plots=True, close_mosaic=10, mosaic=0.0,
        fliplr=0.0, degrees=0, translate=0.02, scale=0.1)
best = YOLOv10('/work/out/run/weights/best.pt')
pred = {}
for split in ('val', 'test'):
    for f in sorted(glob.glob(f'/work/yolo/images/{split}/*.jpg')):
        r = best.predict(f, imgsz=1280, conf=0.05, iou=0.5, verbose=False, max_det=600)[0]
        pred[os.path.basename(f)[:-4]] = dict(split=split, size=list(r.orig_shape)[::-1],
            boxes=r.boxes.xyxyn.tolist(), cls=[int(c) for c in r.boxes.cls.tolist()], conf=r.boxes.conf.tolist())
json.dump(pred, open('/work/out/predictions.json', 'w'))
print('predicted', len(pred))
PY
touch train.done

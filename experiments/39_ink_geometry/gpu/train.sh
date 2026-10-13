#!/bin/bash
# On the rented GPU, after setup.sh and the dataset upload: fine-tune, then predict the val and test pages.
# Writes /work/out/ (weights, results.csv, predictions json) and /work/train.done (or train.failed).
# DATA: the dataset folder (yolo = round 1, yolo2 = round 2). (No time= limit: it would rescale the epochs and the
# learning-rate schedule; the cost cap is gpu_wait.sh's MAXMIN, which fetches the best.pt saved so far.)
# Round 2 fixes: no checkpoint every 10 epochs (save_period=-1); layer fusing switched off (the final validation and
# predict crashed in round 1 with "'Conv' object has no attribute 'bn'"; unfused gives the same boxes).
cd /work; DATA=${DATA:-yolo}; export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
until [ -f setup.done ] && [ -f yolo.uploaded ]; do sleep 10; done
tar xf $DATA.tar && sed -i "s#^path: .*#path: /work/$DATA#" $DATA/data.yaml
DATA=$DATA TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1 python - <<'PY' > train.log 2>&1 || { touch train.failed; exit 1; }
import json, glob, os
from doclayout_yolo import YOLOv10
import doclayout_yolo.engine.trainer as TR
import doclayout_yolo.nn.tasks as NT
NT.BaseModel.fuse = lambda self, verbose=True: self
D = '/work/' + os.environ['DATA']
TR.check_amp = lambda model: True          # its AMP self-test loads yolov8n.pt, which torch 2.9 refuses; a 5090 runs AMP
m = YOLOv10('/work/doclayout_yolo_docstructbench_imgsz1024.pt')
m.train(data=f'{D}/data.yaml', save_period=-1, epochs=int(os.environ.get('EPOCHS', 80)), imgsz=1280, batch=int(os.environ.get('BATCH', 8)), patience=20,
        project='/work/out', name='run', exist_ok=True, workers=8, plots=True, close_mosaic=10, mosaic=0.0,
        fliplr=0.0, degrees=0, translate=0.02, scale=0.1)
best = YOLOv10('/work/out/run/weights/best.pt')
pred = {}
for split in ('val', 'test'):
    for f in sorted(glob.glob(f'{D}/images/{split}/*.jpg')):
        r = best.predict(f, imgsz=1280, conf=0.05, iou=0.5, verbose=False, max_det=600)[0]
        pred[os.path.basename(f)[:-4]] = dict(split=split, size=list(r.orig_shape)[::-1],
            boxes=r.boxes.xyxyn.tolist(), cls=[int(c) for c in r.boxes.cls.tolist()], conf=r.boxes.conf.tolist())
json.dump(pred, open('/work/out/predictions.json', 'w'))
print('predicted', len(pred))
PY
touch train.done

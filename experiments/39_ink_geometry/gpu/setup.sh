#!/bin/bash
# On the rented GPU: install DocLayout-YOLO and fetch its DocStructBench weights. Writes /work/setup.done.
set -x
cd /work
(apt-get update -qq && apt-get install -y -qq libxcb1 libgl1 libglib2.0-0) > /dev/null 2>&1   # cv2 needs these on the pytorch image
pip install -q doclayout-yolo huggingface_hub 2>&1 | tail -2
pip uninstall -y -q opencv-python 2>/dev/null; pip install -q opencv-python-headless 2>&1 | tail -1
python -c "
from huggingface_hub import hf_hub_download
p = hf_hub_download('juliozhao/DocLayout-YOLO-DocStructBench', 'doclayout_yolo_docstructbench_imgsz1024.pt', local_dir='/work')
print(p)"
touch /work/setup.done

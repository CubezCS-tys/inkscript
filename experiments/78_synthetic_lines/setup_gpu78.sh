#!/bin/bash
# Experiment 78 host set-up: the pytorch 2.9.0 / CUDA 12.8 image has torch; add OpenCV (headless), numpy, Pillow
# (its wheels carry raqm: HarfBuzz + FriBiDi, checked below) and fontTools.  No model downloads: weights start random.
set -e
cd /work
(apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libfribidi0 libraqm0 >/dev/null) 2>&1 | tail -1   # raqm in Pillow needs FriBiDi at run time
python -m pip install -q -U opencv-python-headless numpy "pillow==13.0.0" fonttools 2>&1 | tail -2
python -c "import torch, cv2; from PIL import features; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0), 'cv2', cv2.__version__, 'raqm', features.check('raqm'), features.version('raqm'))"
nproc; free -g | head -2
echo SETUP_DONE

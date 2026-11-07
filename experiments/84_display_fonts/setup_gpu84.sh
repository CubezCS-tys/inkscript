#!/bin/bash
# Experiment 84 host set-up (the pytorch 2.9.0 / CUDA 12.8 image has torch): OpenCV (headless), numpy, pypdfium2 5.12.1
# (the repo's pin: the line cutting renders pages exactly as experiments 77 / 83 did), Pillow 13.0.0 with raqm
# (FriBiDi + raqm from apt, as experiment 78) and fontTools for the synthetic display lines.  No model downloads.
set -e
cd /work
(apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libfribidi0 libraqm0 >/dev/null) 2>&1 | tail -1
python -m pip install -q opencv-python-headless numpy "pypdfium2==5.12.1" "pillow==13.0.0" fonttools rapidfuzz 2>&1 | tail -2
python -c "import torch, cv2, pypdfium2; from PIL import features; from pypdfium2.version import PYPDFIUM_INFO, PDFIUM_INFO; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0), 'cv2', cv2.__version__, 'pdfium', PYPDFIUM_INFO, PDFIUM_INFO, 'raqm', features.check('raqm'))"
nproc; cat /sys/fs/cgroup/cpu.max 2>/dev/null; free -g | head -2; df -h /work | tail -1
echo SETUP_DONE

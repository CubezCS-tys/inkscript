#!/bin/bash
# Experiment 85 host set-up (experiment 83's, unchanged): the pytorch 2.9.0 / CUDA 12.8 image already has torch; add OpenCV (headless), numpy and
# pypdfium2 5.12.1 (the repo's pin: the line cutting renders pages exactly as experiment 77 did).  No model downloads.
set -e
cd /work
python -m pip install -q opencv-python-headless numpy "pypdfium2==5.12.1" 2>&1 | tail -2
python -c "import torch, cv2, pypdfium2; from pypdfium2.version import PYPDFIUM_INFO, PDFIUM_INFO; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0), 'cv2', cv2.__version__, 'pdfium', PYPDFIUM_INFO, PDFIUM_INFO)"
nproc; cat /sys/fs/cgroup/cpu.max 2>/dev/null; free -g | head -2; df -h /work | tail -1
echo SETUP_DONE

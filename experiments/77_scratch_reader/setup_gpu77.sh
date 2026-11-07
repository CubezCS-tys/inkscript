#!/bin/bash
# Experiment 77 host set-up: the pytorch 2.9.0 / CUDA 12.8 image already has torch; add OpenCV (headless) and numpy.
# No Hugging Face, no model downloads: every weight is trained here from random initialisation.
set -e
cd /work
python -m pip install -q opencv-python-headless numpy 2>&1 | tail -2
python -c "import torch, cv2; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0), 'cv2', cv2.__version__)"
nproc; free -g | head -2
echo SETUP_DONE

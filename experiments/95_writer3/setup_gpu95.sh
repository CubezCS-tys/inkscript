#!/bin/bash
# Experiment 95 host set-up (copied from setup_gpu87.sh) (the pytorch 2.9.0 / CUDA 12.8 image has torch): OpenCV (headless), numba (the DTW),
# uharfbuzz (shaping the font libraries), scikit-image (thinning in line_metrics, medial axis).  No model downloads.
set -e
cd /work
python -m pip install -q opencv-python-headless numpy numba uharfbuzz scikit-image 2>&1 | tail -2
python -c "import torch, cv2, numba, uharfbuzz, skimage; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0), 'cv2', cv2.__version__, 'numba', numba.__version__)"
nproc; cat /sys/fs/cgroup/cpu.max 2>/dev/null; free -g | head -2; df -h /work | tail -1
echo SETUP_DONE

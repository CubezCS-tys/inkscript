#!/bin/bash
# Experiment 82 host set-up (a copy of exp 79's): the pytorch image has torch; add OpenCV (headless), numpy, networkx,
# fontTools, uharfbuzz and rapidfuzz.  No model downloads: weights start random.
set -e
cd /work
python -m pip install -q opencv-python-headless numpy networkx fonttools "uharfbuzz==0.57.0" rapidfuzz 2>&1 | tail -2
python -c "import torch, cv2, uharfbuzz, networkx, fontTools; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0), 'cv2', cv2.__version__, 'hb', uharfbuzz.__version__)"
nproc; cat /sys/fs/cgroup/cpu.max 2>/dev/null; free -g | head -2
echo SETUP_DONE

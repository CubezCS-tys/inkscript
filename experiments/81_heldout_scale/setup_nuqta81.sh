#!/bin/bash
# Experiment 81 on the rented GPU host (/work): Nuqta's env and PINNED weights only (the Nuqta part of experiment
# 75's workers/setup_gpu.sh: transformers 5.8.1 + accelerate on the image's torch; revision 6a8cdd62...).
cd /work; mkdir -p setup out models; export HF_HOME=/work/hf HF_HUB_ENABLE_HF_TRANSFER=1
PY=$(command -v python3 || command -v python)
( $PY -m venv /opt/hf && /opt/hf/bin/pip install -q -U "huggingface_hub>=1.0" hf_transfer > setup/hf_pip.log 2>&1
  for try in 1 2 3; do
    /opt/hf/bin/hf download SalahALHaismawi/Nuqta-Arabic-OCR-4B --revision 6a8cdd625f7360203bfce10ef48a41c4a5c1ad3c \
      --local-dir models/Nuqta-Arabic-OCR-4B > setup/dl.log 2>&1 && break; sleep 15
  done && touch setup/dl.ok || touch setup/dl.fail ) &
( $PY -m venv --system-site-packages /opt/nuqta && /opt/nuqta/bin/pip install -q "transformers==5.8.1" accelerate pillow > setup/nuqta_pip.log 2>&1 \
  && /opt/nuqta/bin/python -c "import torch, transformers; print(torch.__version__, transformers.__version__, torch.cuda.get_device_name(0))" > setup/nuqta.ok 2>&1 \
  || touch setup/nuqta.fail ) &
wait
touch setup/ALL_DONE

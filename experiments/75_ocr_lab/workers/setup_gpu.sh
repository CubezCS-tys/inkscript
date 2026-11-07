#!/bin/bash
# Runs on the rented GPU host in /work (started by gpu_session.py start). Builds each engine's own environment and
# downloads the PINNED weights from Hugging Face, in parallel. Markers: /work/setup/*.ok | *.fail, ALL_DONE.
#   base image: pytorch/pytorch:2.9.0-cuda12.8-cudnn9-runtime (torch 2.9.0 + CUDA 12.8; exp 36's proven image)
#   /opt/paddle  paddlepaddle-gpu 3.2.1 (cu126 wheels, the model card's command) + paddleocr[doc-parser] 3.7.0
#   /opt/nuqta   transformers 5.8.1 (the version in the Nuqta card's config.json) + accelerate, on the image's torch
#   /work/models/<name>  hf download --revision <pinned sha>
cd /work; mkdir -p setup logs models; export HF_HOME=/work/hf HF_HUB_ENABLE_HF_TRANSFER=1
PY=$(command -v python3 || command -v python)
# Blackwell cards (compute capability 12.x, e.g. RTX 5090) need Paddle's cu129 wheel (experiment 36); older cards
# take the model card's cu126 wheel
CC=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | cut -d. -f1)
PADDLE_CU=cu126; [ "${CC:-0}" -ge 12 ] && PADDLE_CU=cu129
echo "compute capability major $CC -> paddle wheel $PADDLE_CU" > setup/paddle_wheel.txt
(apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libgomp1 libgl1 libglib2.0-0 gcc > setup/apt.log 2>&1 \
  && touch setup/apt.ok || touch setup/apt.fail) &
(
  $PY -m venv /opt/hf && /opt/hf/bin/pip install -q -U "huggingface_hub>=1.0" hf_transfer > setup/hf_pip.log 2>&1
  for spec in PaddlePaddle/PaddleOCR-VL-1.6@c5630abae1d940eafe0697512a0325494b02ab42 \
              PaddlePaddle/PP-DocLayoutV3@241f8bdfc77a7c7bee915a5057aaee58c235a8d3 \
              SalahALHaismawi/Nuqta-Arabic-OCR-4B@6a8cdd625f7360203bfce10ef48a41c4a5c1ad3c; do
    repo=${spec%@*}; rev=${spec#*@}; tag=$(basename $repo); S=$(date +%s)
    for try in 1 2 3; do
      /opt/hf/bin/hf download $repo --revision $rev --local-dir models/$tag > setup/dl_$tag.log 2>&1 && break; sleep 15
    done && echo "$(( $(date +%s)-S )) s" > setup/dl_$tag.ok || touch setup/dl_$tag.fail
  done
  (cd models && sha256sum PaddleOCR-VL-1.6/model.safetensors PP-DocLayoutV3/inference.pdiparams \
     Nuqta-Arabic-OCR-4B/model.safetensors > ../setup/weights.sha256)
) &
(
  $PY -m venv /opt/paddle && /opt/paddle/bin/pip install -q -U pip > setup/paddle_pip.log 2>&1 \
  && /opt/paddle/bin/pip install paddlepaddle-gpu==3.2.1 -i https://www.paddlepaddle.org.cn/packages/stable/$PADDLE_CU/ >> setup/paddle_pip.log 2>&1 \
  && /opt/paddle/bin/pip install "paddleocr[doc-parser]==3.7.0" >> setup/paddle_pip.log 2>&1 \
  && /opt/paddle/bin/python -c "import paddle, paddleocr, paddlex; print(paddle.__version__, paddleocr.__version__, paddlex.__version__, paddle.device.cuda.get_device_capability())" > setup/paddle.ok 2>&1 \
  || touch setup/paddle.fail
) &
(
  $PY -m venv --system-site-packages /opt/nuqta && /opt/nuqta/bin/pip install -q "transformers==5.8.1" accelerate pillow > setup/nuqta_pip.log 2>&1 \
  && /opt/nuqta/bin/python -c "import torch, transformers, torchvision; print(torch.__version__, torch.version.cuda, transformers.__version__, torch.cuda.get_device_name(0))" > setup/nuqta.ok 2>&1 \
  || touch setup/nuqta.fail
) &
wait
/opt/paddle/bin/pip freeze > setup/paddle_freeze.txt 2>/dev/null; /opt/nuqta/bin/pip freeze > setup/nuqta_freeze.txt 2>/dev/null
nvidia-smi > setup/nvidia_smi.txt 2>&1
touch setup/ALL_DONE

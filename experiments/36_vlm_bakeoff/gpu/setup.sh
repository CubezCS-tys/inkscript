#!/bin/bash
# Runs on the GPU host in /work (started with nohup by gpu_run.sh). Builds the two stacks of models.md in their own
# venvs and downloads the pinned weights from Hugging Face, all in parallel. Marker files: *.ok / *.fail in /work/setup/.
cd /work; mkdir -p setup logs out/raw; export HF_HOME=/work/hf
PY=$(command -v python3 || command -v python)
# the runtime image lacks a C compiler (triton builds a helper at vLLM start-up) and the libraries paddle and cv2 load
(apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq gcc libgomp1 libgl1 libglib2.0-0 > setup/apt.log 2>&1) &
# 1. weights (a tiny venv of its own so downloads start at once)
(
  $PY -m venv /opt/hf && /opt/hf/bin/pip install -q -U "huggingface_hub>=1.0" > setup/hf_pip.log 2>&1
  for spec in rednote-hilab/dots.mocr@e539fbb52280393adc081b289ec597430a0f9031 \
              PaddlePaddle/PaddleOCR-VL-1.5@2a4195faa5e7914c12f2fc601d72c81caf8d2da5 \
              rednote-hilab/dots.ocr@c0111ce6bc07803dbc267932ffef0ae3a51dc951 \
              QuantTrio/Qwen3-VL-32B-Instruct-AWQ@c2d44b1376c73fa120fdb4e216c2ef61c1945498 \
              Qwen/Qwen3-VL-8B-Instruct@0c351dd01ed87e9c1b53cbc748cba10e6187ff3b \
              amad-iq/amad-vlm6@7daf90cd5e5706173e159c88ca4e6dc2475a485e; do
    repo=${spec%@*}; rev=${spec#*@}; tag=$(basename $repo)
    S=$(date +%s)
    for try in 1 2 3; do /opt/hf/bin/hf download $repo --revision $rev > setup/dl_$tag.log 2>&1 && break; sleep 20; done \
      && echo $(( $(date +%s)-S )) > setup/dl_$tag.ok || touch setup/dl_$tag.fail
  done
) &
# 2. vLLM 0.13.0 stack (brings torch 2.9.0+cu129)
(
  $PY -m venv /opt/vllm && /opt/vllm/bin/pip install -q -U pip \
  && /opt/vllm/bin/pip install "vllm==0.13.0" --extra-index-url https://download.pytorch.org/whl/cu129 > setup/vllm_pip.log 2>&1 \
  && /opt/vllm/bin/pip install "huggingface_hub[hf_transfer]" openai pillow qwen-vl-utils >> setup/vllm_pip.log 2>&1 \
  && /opt/vllm/bin/python -c "import torch, vllm, transformers; print(torch.__version__, torch.version.cuda, vllm.__version__, transformers.__version__, torch.cuda.get_device_capability())" > setup/vllm.ok 2>&1 \
  || touch setup/vllm.fail
) &
# 3. Paddle stack (layout pipeline client)
(
  $PY -m venv /opt/paddle && /opt/paddle/bin/pip install -q -U pip \
  && /opt/paddle/bin/pip install paddlepaddle-gpu==3.2.1 -i https://www.paddlepaddle.org.cn/packages/stable/cu129/ > setup/paddle_pip.log 2>&1 \
  && /opt/paddle/bin/pip install "paddleocr[doc-parser]==3.7.0" >> setup/paddle_pip.log 2>&1 \
  && /opt/paddle/bin/python -c "import paddle, paddleocr, paddlex; print(paddle.__version__, paddleocr.__version__, paddlex.__version__, paddle.device.cuda.get_device_capability())" > setup/paddle.ok 2>&1 \
  || touch setup/paddle.fail
) &
# 4. pages
(until [ -f pages.uploaded ]; do sleep 5; done;tar xf pages.tar && ls pages | wc -l > setup/pages.ok) &
wait
touch setup/ALL_DONE

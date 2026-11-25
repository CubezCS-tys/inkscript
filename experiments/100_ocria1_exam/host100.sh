#!/bin/bash
# Experiment 100 on the rented GPU host.  Follow with a bracket pattern only:  gs100.py follow '[h]ost100.sh'
#   info     GPU, driver, CPUs, disk -> out/host100.log (run by start() as workers/setup_gpu.sh)
#   setup    fresh venv /work/venv (uv): vllm==0.34.0 (torch 2.14 / CUDA 13.0) + nvcc 13.0 from the cuda-toolkit wheel
#   model    llamaindex/OCRia-1 from HuggingFace into /work/hf (this host only; destroyed with it), sha256 checked
#   serve    vllm serve on 127.0.0.1:8000 (loopback only), waits until /v1/models answers; log out/vllm.log
#   all      info + setup + model + serve (each skipped when its STAGE marker is already in out/stages.log)
#   dev | exam   run infer100.py on in/dev or in/exam (settings from the environment, see infer100.py)
# No telemetry: VLLM_NO_USAGE_STATS, DO_NOT_TRACK, HF_HUB_DISABLE_TELEMETRY.  Scans never leave this host except
# back to our server over the same ssh.
set -e -o pipefail
cd /work
mkdir -p out hf
export VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 HF_HUB_DISABLE_TELEMETRY=1 VLLM_DO_NOT_TRACK=1
export HF_HOME=/work/hf HF_HUB_ENABLE_HF_TRANSFER=0
export OMP_NUM_THREADS=4
MODEL=llamaindex/OCRia-1
REV=${REV:-dae83aa51ecd0a8574d415d929a4d9e79348fd2a}     # the repo's commit on 2026-11-24 (card, prompt.txt, LICENSE read at it)
SHA=426d9aa2df62e72e1e79068698962b407208d45df06b612641a87fc50f904a87   # model.safetensors, from the card
MAXLEN=${MAXLEN:-40960}     # card: 32768; 40960 so a full-size page (~8,000 image tokens) still has room for 24,576 out
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }
done_() { grep -q "$1" out/stages.log 2>/dev/null; }

info() {
  { date -u +%FT%TZ; nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    nvidia-smi | grep -o "CUDA Version: [0-9.]*"; nproc; free -g | head -2; df -h /work | tail -1; python3 --version; } >> out/host100.log 2>&1 || true
  stage INFO_DONE
}

setup() {
  python3 -m pip install -q uv
  python3 -m uv venv -q --python 3.12 /work/venv || python3 -m uv venv -q /work/venv
  python3 -m uv pip install --python /work/venv/bin/python "vllm==0.34.0" "cuda-toolkit[nvcc,cudart]==13.0.3" > out/uv.log 2>&1
  # flashinfer's JIT links -lcudart, which the pip CUDA wheels do not provide as libcudart.so (seen 2026-11-25):
  # use NVIDIA's apt packages for CUDA 13.0 (compiler + cudart dev), the wheel's nvcc only as a last resort
  NVCC=$(ls /usr/local/cuda-13.0/bin/nvcc 2>/dev/null || true)
  if [ -z "$NVCC" ]; then
    (apt-get update -qq && apt-get install -y -qq wget >/dev/null && \
     wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb && \
     dpkg -i cuda-keyring_1.1-1_all.deb >/dev/null && apt-get update -qq && \
     DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cuda-nvcc-13-0 cuda-cudart-dev-13-0 libcurand-dev-13-0 >/dev/null) 2>&1 | tail -2
    NVCC=$(ls /usr/local/cuda-13.0/bin/nvcc 2>/dev/null || find /work/venv -type f -name nvcc -perm -u+x | head -1)
  fi
  echo "NVCC=$NVCC" >> out/host100.log
  echo "export CUDA_HOME=$(dirname $(dirname $NVCC)) PATH=$(dirname $NVCC):\$PATH" > /work/cuda_env.sh
  . /work/cuda_env.sh
  /work/venv/bin/python -c "import torch, vllm, transformers; print('torch', torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0), 'vllm', vllm.__version__, 'transformers', transformers.__version__)" >> out/host100.log 2>&1
  nvcc --version | tail -1 >> out/host100.log 2>&1
  stage SETUP_DONE
}

model() {
  /work/venv/bin/python - <<EOF >> out/host100.log 2>&1
import hashlib, os
from huggingface_hub import snapshot_download
p = snapshot_download("$MODEL", revision="$REV", allow_patterns=["*.json", "*.jinja", "*.txt", "model.safetensors", "LICENSE"])
print("model dir", p)
h = hashlib.sha256()
with open(os.path.join(p, "model.safetensors"), "rb") as f:
    for b in iter(lambda: f.read(1 << 24), b""):
        h.update(b)
print("sha256", h.hexdigest(), "OK" if h.hexdigest() == "$SHA" else "MISMATCH")
open("/work/model_dir", "w").write(p)
EOF
  grep -q "sha256 $SHA OK" out/host100.log || { echo "weights sha256 mismatch" >> out/host100.log; exit 3; }
  cmp -s "$(cat /work/model_dir)/prompt.txt" /work/prompt.txt && echo "prompt.txt identical to ours" >> out/host100.log \
    || echo "WARNING prompt.txt differs from ours" >> out/host100.log
  stage MODEL_DONE
}

serve() {
  . /work/cuda_env.sh
  export VLLM_USE_FLASHINFER_SAMPLER=0      # greedy decoding needs no sampler kernel; its JIT build wanted curand.h
  if ! curl -sf http://127.0.0.1:8000/v1/models >/dev/null; then
    HF_HUB_OFFLINE=1 setsid nohup /work/venv/bin/vllm serve "$(cat /work/model_dir)" --served-model-name ocria-1 \
      --host 127.0.0.1 --port 8000 --max-model-len $MAXLEN --limit-mm-per-prompt '{"image": 1}' \
      --gpu-memory-utilization 0.90 --max-num-seqs 32 > out/vllm.log 2>&1 < /dev/null &
    echo $! > /work/vllm.pid
  fi
  for i in $(seq 1 180); do                     # up to 30 minutes for start-up and kernel compilation
    if curl -sf http://127.0.0.1:8000/v1/models >/dev/null; then
      stage SERVE_UP; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader >> out/host100.log; return 0
    fi
    if ! kill -0 "$(cat /work/vllm.pid)" 2>/dev/null; then echo "vllm died" >> out/host100.log; tail -40 out/vllm.log >> out/host100.log; exit 4; fi
    sleep 10
  done
  echo "vllm not up in 30 min" >> out/host100.log; exit 5
}

gpumon() {   # GPU memory and use every 15 s while an inference set runs
  while sleep 15; do nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader >> out/gpumon_$1.csv; done
}

infer() {   # $1 = dev | exam ; settings: PIXELS, CONC, TAG (see infer100.py)
  gpumon "$1_${TAG:-run}" & GM=$!
  /work/venv/bin/python infer100.py --set "$1" --in /work/in/$1 --out /work/out/$1${TAG:+_$TAG} \
    --prompt /work/prompt.txt --max-pixels "${PIXELS:-4100000}" --concurrency "${CONC:-16}" >> out/infer_$1${TAG:+_$TAG}.log 2>&1
  kill $GM 2>/dev/null || true
  stage "INFER_$1${TAG:+_$TAG}_DONE"
}

case "$1" in
  all) done_ INFO_DONE || info; done_ SETUP_DONE || setup; done_ MODEL_DONE || model; serve; stage ALL_UP ;;
  dev|exam) infer "$1" ;;
  *) "$1" ;;
esac

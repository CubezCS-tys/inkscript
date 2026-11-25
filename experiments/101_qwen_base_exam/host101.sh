#!/bin/bash
# Experiment 101 on the rented GPU host (experiment 100's host100.sh, copied 2026-11-24, with its three set-up fixes
# kept exactly: uv pip install --python, CUDA_HOME from NVIDIA's apt packages for 13.0, VLLM_USE_FLASHINFER_SAMPLER=0).
# Follow with a bracket pattern only:  gs101.py follow '[h]ost101.sh'
#   info     GPU, driver, CPUs, disk -> out/host101.log (run by start() as workers/setup_gpu.sh)
#   setup    fresh venv /work/venv (uv): vllm==0.34.0 (torch 2.14 / CUDA 13.0) + nvcc 13.0
#   model    Qwen/Qwen3.5-$ARM from HuggingFace into /work/hf (this host only; destroyed with it), every shard's sha256
#            checked against the HuggingFace listing read on 2026-11-24 (card/api_*.json)
#   serve    vllm serve on 127.0.0.1:8000 (loopback only), waits until /v1/models answers; log out/vllm_$ARM.log
#   stopserve  stop the running vLLM server (to swap 4B -> 9B on the same host)
#   all      info + setup + model + serve (each skipped when its STAGE marker is already in out/stages.log)
#   dev | exam   run infer101.py on in/dev or in/exam; settings from the environment: ARM (4B | 9B), PROMPT (P1 | P2),
#                PIXELS, TAG, CONC.  Output: out/$ARM/dev_$TAG or out/$ARM/exam
# ARM defaults to 4B.  No telemetry: VLLM_NO_USAGE_STATS, DO_NOT_TRACK, HF_HUB_DISABLE_TELEMETRY.  Scans never leave
# this host except back to our server over the same ssh.
set -e -o pipefail
cd /work
mkdir -p out hf
export VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 HF_HUB_DISABLE_TELEMETRY=1 VLLM_DO_NOT_TRACK=1
export HF_HOME=/work/hf HF_HUB_ENABLE_HF_TRANSFER=0
export OMP_NUM_THREADS=4
ARM=${ARM:-4B}
MODEL=Qwen/Qwen3.5-$ARM
case "$ARM" in        # repo commits on 2026-11-24 (card, licence, chat template read at them); shard sha256 from the listing
  4B) REV=851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a
      SHAS="model.safetensors-00001-of-00002.safetensors=26a93f066e1916adb13453dae5a0c707c0fbc71299ed98779571a907b8e74c61
model.safetensors-00002-of-00002.safetensors=cb544bd9bfae93dc59b0f22b292f5933573854a7f9b97835c67060d7d910e188" ;;
  9B) REV=c202236235762e1c871ad0ccb60c8ee5ba337b9a
      SHAS="model.safetensors-00001-of-00004.safetensors=db6f444b43d318c92f360a13a25561a6a65b10c0631b8ed305a426dbaa6c380e
model.safetensors-00002-of-00004.safetensors=31c7d7e2dd5d207840b31cc59083c8f4c4718959149e0358c0364052bb9a0330
model.safetensors-00003-of-00004.safetensors=7ec36ba3a4176a44c3c0876ad80c56a2f70c84bf008d82e9501df642f17dadec
model.safetensors-00004-of-00004.safetensors=b62b0c4cd7e44edee103ee8f4fe225f246d5e768e07bfd5f25b63a8aa1fdd0c6" ;;
  *) echo "ARM must be 4B or 9B"; exit 2 ;;
esac
MAXLEN=${MAXLEN:-40960}     # as experiment 100: a full-size page's image tokens still leave room for 24,576 out
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }
done_() { grep -q "$1" out/stages.log 2>/dev/null; }

info() {
  { date -u +%FT%TZ; nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    nvidia-smi | grep -o "CUDA Version: [0-9.]*"; nproc; free -g | head -2; df -h /work | tail -1; python3 --version; } >> out/host101.log 2>&1 || true
  stage INFO_DONE
}

setup() {
  python3 -m pip install -q uv
  python3 -m uv venv -q --python 3.12 /work/venv || python3 -m uv venv -q /work/venv
  python3 -m uv pip install --python /work/venv/bin/python "vllm==0.34.0" "cuda-toolkit[nvcc,cudart]==13.0.3" > out/uv.log 2>&1
  # flashinfer's JIT links -lcudart, which the pip CUDA wheels do not provide as libcudart.so (exp 100, 2026-11-25):
  # use NVIDIA's apt packages for CUDA 13.0 (compiler + cudart dev + curand dev), the wheel's nvcc only as a last resort
  NVCC=$(ls /usr/local/cuda-13.0/bin/nvcc 2>/dev/null || true)
  if [ -z "$NVCC" ]; then
    (apt-get update -qq && apt-get install -y -qq wget >/dev/null && \
     wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb && \
     dpkg -i cuda-keyring_1.1-1_all.deb >/dev/null && apt-get update -qq && \
     DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cuda-nvcc-13-0 cuda-cudart-dev-13-0 libcurand-dev-13-0 >/dev/null) 2>&1 | tail -2
    NVCC=$(ls /usr/local/cuda-13.0/bin/nvcc 2>/dev/null || find /work/venv -type f -name nvcc -perm -u+x | head -1)
  fi
  echo "NVCC=$NVCC" >> out/host101.log
  echo "export CUDA_HOME=$(dirname $(dirname $NVCC)) PATH=$(dirname $NVCC):\$PATH" > /work/cuda_env.sh
  . /work/cuda_env.sh
  /work/venv/bin/python -c "import torch, vllm, transformers; print('torch', torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0), 'vllm', vllm.__version__, 'transformers', transformers.__version__)" >> out/host101.log 2>&1
  nvcc --version | tail -1 >> out/host101.log 2>&1
  stage SETUP_DONE
}

model() {
  SHAS="$SHAS" /work/venv/bin/python - <<EOF >> out/host101.log 2>&1
import hashlib, os, json
from huggingface_hub import snapshot_download
p = snapshot_download("$MODEL", revision="$REV", allow_patterns=["*.json", "*.jinja", "*.txt", "*.safetensors", "LICENSE"])
print("model dir $ARM", p)
bad = 0
for line in os.environ["SHAS"].split():
    fn, want = line.split("=")
    h = hashlib.sha256()
    with open(os.path.join(p, fn), "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    ok = h.hexdigest() == want
    bad += not ok
    print("sha256", fn, h.hexdigest(), "OK" if ok else "MISMATCH")
lic = open(os.path.join(p, "LICENSE")).read(200)
print("licence head:", " ".join(lic.split())[:60])
print("ALL_SHA_OK" if not bad else "SHA_MISMATCH")
open("/work/model_dir_$ARM", "w").write(p)
EOF
  tail -1 out/host101.log | grep -q ALL_SHA_OK || { echo "weights sha256 mismatch ($ARM)" >> out/host101.log; exit 3; }
  stage MODEL_${ARM}_DONE
}

serve() {
  . /work/cuda_env.sh
  export VLLM_USE_FLASHINFER_SAMPLER=0      # greedy decoding needs no sampler kernel; its JIT build wanted curand.h
  if ! curl -sf http://127.0.0.1:8000/v1/models >/dev/null; then
    HF_HUB_OFFLINE=1 setsid nohup /work/venv/bin/vllm serve "$(cat /work/model_dir_$ARM)" --served-model-name qwen \
      --host 127.0.0.1 --port 8000 --max-model-len $MAXLEN --limit-mm-per-prompt '{"image": 1}' \
      --gpu-memory-utilization 0.90 --max-num-seqs ${MAXSEQS:-32} > out/vllm_$ARM.log 2>&1 < /dev/null &
    echo $! > /work/vllm.pid
  fi
  for i in $(seq 1 180); do                     # up to 30 minutes for start-up and kernel compilation
    if curl -sf http://127.0.0.1:8000/v1/models >/dev/null; then
      { echo "serving $ARM:"; curl -sf http://127.0.0.1:8000/v1/models | head -c 400; echo; } >> out/host101.log
      stage SERVE_UP_$ARM; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader >> out/host101.log; return 0
    fi
    if ! kill -0 "$(cat /work/vllm.pid)" 2>/dev/null; then echo "vllm died ($ARM)" >> out/host101.log; tail -40 out/vllm_$ARM.log >> out/host101.log; exit 4; fi
    sleep 10
  done
  echo "vllm not up in 30 min" >> out/host101.log; exit 5
}

stopserve() {   # the server started by serve(), by its pid (never pkill -f)
  if [ -f /work/vllm.pid ]; then
    P=$(cat /work/vllm.pid)
    kill -TERM -- -"$P" 2>/dev/null || kill -TERM "$P" 2>/dev/null || true
    for i in $(seq 1 30); do kill -0 "$P" 2>/dev/null || break; sleep 2; done
    kill -0 "$P" 2>/dev/null && { kill -KILL -- -"$P" 2>/dev/null || kill -KILL "$P"; }
    rm -f /work/vllm.pid
  fi
  sleep 5; nvidia-smi --query-gpu=memory.used --format=csv,noheader >> out/host101.log
  stage SERVER_STOPPED
}

gpumon() {   # GPU memory and use every 15 s while an inference set runs
  while sleep 15; do nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader >> out/$ARM/gpumon_$1.csv; done
}

infer() {   # $1 = dev | exam ; settings: ARM, PROMPT, PIXELS, TAG, CONC (see infer101.py)
  mkdir -p out/$ARM
  D=$1; [ "$1" = dev ] && D=dev_${TAG:?TAG needed for dev}
  gpumon "$D" & GM=$!
  /work/venv/bin/python infer101.py --set "$1" --in /work/in/$1 --out /work/out/$ARM/$D \
    --prompt /work/prompts/${PROMPT:?PROMPT needed}.txt --max-pixels "${PIXELS:?PIXELS needed}" --concurrency "${CONC:-16}" \
    --tag "$ARM ${TAG:-exam} $PROMPT" >> out/$ARM/infer_$D.log 2>&1 || { kill $GM 2>/dev/null; exit 6; }
  kill $GM 2>/dev/null || true
  stage "INFER_${ARM}_${D}_DONE"
}

devall() {   # the four 4B dev candidates in turn (prompt x image size); each resumable
  for c in "P1 2000000 p1_px20" "P1 4100000 p1_px41" "P2 2000000 p2_px20" "P2 4100000 p2_px41"; do
    set -- $c; PROMPT=$1 PIXELS=$2 TAG=$3 infer dev
  done
}

case "$1" in
  all) done_ INFO_DONE || info; done_ SETUP_DONE || setup; done_ "MODEL_${ARM}_DONE" || model; serve; stage "ALL_UP_$ARM" ;;
  swap) stopserve; done_ "MODEL_${ARM}_DONE" || model; serve; stage "SWAPPED_TO_$ARM" ;;
  dev|exam) infer "$1" ;;
  devall) devall ;;
  *) "$1" ;;
esac

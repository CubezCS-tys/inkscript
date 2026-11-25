#!/bin/bash
# Experiment 102 on the rented GPU host.  Experiment 101's host101.sh (2026-11-24) for info / setup / model, with its
# set-up fixes kept exactly (uv pip install --python; CUDA_HOME from NVIDIA's apt packages for 13.0;
# VLLM_USE_FLASHINFER_SAMPLER=0), plus the training packages.  Follow with a bracket pattern only:
#   gs102.py follow '[h]ost102.sh'
#   info      GPU, driver, CPUs, RAM, disk -> out/host102.log (run by start() as workers/setup_gpu.sh)
#   setup     fresh venv /work/venv (uv): vllm==0.34.0 (torch 2.14.0 / CUDA 13.0), transformers==5.22.2, peft==0.21.2,
#             accelerate==1.15.0, flash-linear-attention==0.6.0, then causal-conv1d==1.7.0 built with nvcc 13.0
#             (if that build fails, training still runs on Transformers' slower PyTorch path: logged, not fatal)
#   model     Qwen/Qwen3.5-4B at the commit read on 2026-11-24, every shard's sha256 checked (experiment 101's listing)
#   all       info + setup + model (each skipped when its STAGE marker is already in out/stages.log)
#   zeroshot  the untrained model on DEV at H=96 and H=64 (the height rule, README), -> out/eval/dev_base_H96|H64.jsonl
#   train TAG SET EPOCHS SAVE_EVERY [extra train102 args]      -> /work/run_TAG (checkpoints), out/train_TAG.log
#             CROPS="crops/S" to train S from its own 0.34 GB of shards while M is still uploading
#   devckpts TAG     every /work/run_TAG/ckpt-* on DEV in one engine (LoRA), -> out/eval/dev_TAG.jsonl
#   final TAG CKPT   the chosen checkpoint on the exam lines (and the locked lines if /work/crops/locked exists)
#   base_final       the untrained model on the exam lines (and locked lines if present): the zero-shot arm
#   speed TAG CKPT   lines per second on 5,000 DEV-like lines (M crops) for the cost per million lines
# H (default 96) is read from /work/H once the zero-shot rule has picked it (README).  No telemetry.  Line images never
# leave this host except back to our server over the same ssh.
set -e -o pipefail
cd /work
mkdir -p out out/eval hf
export VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 HF_HUB_DISABLE_TELEMETRY=1 VLLM_DO_NOT_TRACK=1 WANDB_DISABLED=true
export HF_HOME=/work/hf HF_HUB_ENABLE_HF_TRANSFER=0 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=2 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
MODEL=Qwen/Qwen3.5-4B
REV=851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a
SHAS="model.safetensors-00001-of-00002.safetensors=26a93f066e1916adb13453dae5a0c707c0fbc71299ed98779571a907b8e74c61
model.safetensors-00002-of-00002.safetensors=cb544bd9bfae93dc59b0f22b292f5933573854a7f9b97835c67060d7d910e188"
H=$(cat /work/H 2>/dev/null || echo 96)
PY=/work/venv/bin/python
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }
done_() { grep -q "$1" out/stages.log 2>/dev/null; }
C=$(OMP_NUM_THREADS= nproc --all); W=$(( C - 4 > 10 ? 10 : C - 4 )); [ "$W" -lt 2 ] && W=2

info() {
  { date -u +%FT%TZ; nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    nvidia-smi | grep -o "CUDA Version: [0-9.]*"; nproc; cat /sys/fs/cgroup/cpu.max 2>/dev/null; free -g | head -2
    df -h /work | tail -1; python3 --version; } >> out/host102.log 2>&1 || true
  stage INFO_DONE
}

setup() {
  python3 -m pip install -q uv
  python3 -m uv venv -q --python 3.12 /work/venv || python3 -m uv venv -q /work/venv
  python3 -m uv pip install --python $PY "vllm==0.34.0" "cuda-toolkit[nvcc,cudart]==13.0.3" "transformers==5.22.2" \
      "peft==0.21.2" "accelerate==1.15.0" "flash-linear-attention==0.6.0" pillow ninja packaging > out/uv.log 2>&1
  NVCC=$(ls /usr/local/cuda-13.0/bin/nvcc 2>/dev/null || true)
  if [ -z "$NVCC" ]; then
    (apt-get update -qq && apt-get install -y -qq wget >/dev/null && \
     wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb && \
     dpkg -i cuda-keyring_1.1-1_all.deb >/dev/null && apt-get update -qq && \
     DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cuda-nvcc-13-0 cuda-cudart-dev-13-0 libcurand-dev-13-0 >/dev/null) 2>&1 | tail -2
    NVCC=$(ls /usr/local/cuda-13.0/bin/nvcc 2>/dev/null || find /work/venv -type f -name nvcc -perm -u+x | head -1)
  fi
  echo "NVCC=$NVCC" >> out/host102.log
  echo "export CUDA_HOME=$(dirname $(dirname $NVCC)) PATH=$(dirname $NVCC):\$PATH" > /work/cuda_env.sh
  . /work/cuda_env.sh
  # the Gated DeltaNet fast path for training (Transformers falls back to slow PyTorch ops without it)
  MAX_JOBS=8 CAUSAL_CONV1D_FORCE_BUILD=TRUE python3 -m uv pip install --python $PY --no-build-isolation "causal-conv1d==1.7.0" \
      > out/conv1d.log 2>&1 || echo "causal-conv1d build FAILED (training uses the PyTorch path)" >> out/host102.log
  $PY - >> out/host102.log 2>&1 <<'EOF'
import torch, vllm, transformers, peft, accelerate
print("torch", torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0), "vllm", vllm.__version__,
      "transformers", transformers.__version__, "peft", peft.__version__, "accelerate", accelerate.__version__)
for m in ("fla", "causal_conv1d"):
    try:
        __import__(m); print(m, "OK")
    except Exception as e:  # noqa: BLE001
        print(m, "MISSING", repr(e)[:120])
EOF
  nvcc --version | tail -1 >> out/host102.log 2>&1
  stage SETUP_DONE
}

model() {
  SHAS="$SHAS" $PY - <<EOF >> out/host102.log 2>&1
import hashlib, os
from huggingface_hub import snapshot_download
p = snapshot_download("$MODEL", revision="$REV", allow_patterns=["*.json", "*.jinja", "*.txt", "*.safetensors", "LICENSE"])
print("model dir", p)
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
print("ALL_SHA_OK" if not bad else "SHA_MISMATCH")
open("/work/model_dir", "w").write(p)
EOF
  tail -1 out/host102.log | grep -q ALL_SHA_OK || { echo "weights sha256 mismatch" >> out/host102.log; exit 3; }
  stage MODEL_DONE
}

gpumon() { while sleep 30; do nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader >> out/gpumon_$1.csv; done; }

ev() {   # SET CROPS OUT [adapters...]
  local set=$1 crops=$2 o=$3; shift 3
  . /work/cuda_env.sh; export VLLM_USE_FLASHINFER_SAMPLER=0
  if [ $# -gt 0 ]; then
    $PY eval102.py --model "$(cat /work/model_dir)" --set $set --crops $crops --out $o --H $H --adapters "$@" \
      || { echo "LoRA serving failed: falling back to merged checkpoints" >> out/host102.log;
           $PY eval102.py --model "$(cat /work/model_dir)" --set $set --crops $crops --out $o --H $H --adapters "$@" --merged; }
  else
    $PY eval102.py --model "$(cat /work/model_dir)" --set $set --crops $crops --out $o --H $H
  fi
}

zeroshot() {
  . /work/cuda_env.sh; export VLLM_USE_FLASHINFER_SAMPLER=0
  for h in 96 64; do
    $PY eval102.py --model "$(cat /work/model_dir)" --set sets/dev.jsonl --crops crops/dev --out out/eval/dev_base_H$h.jsonl --H $h \
      >> out/eval_zeroshot.log 2>&1
  done
  stage ZEROSHOT_DONE
}

train() {   # TAG SET EPOCHS SAVE_EVERY [extra]
  local tag=$1 set=$2 ep=$3 se=$4; shift 4
  . /work/cuda_env.sh
  gpumon train_$tag & GM=$!
  $PY train102.py --model "$(cat /work/model_dir)" --set $set --crops ${CROPS:-crops/M crops/L} --dev sets/dev.jsonl \
    --dev_crops crops/dev --out /work/run_$tag --epochs $ep --save_every $se --H $H --workers $W "$@" \
    >> out/train_$tag.log 2>&1 || { kill $GM 2>/dev/null; exit 6; }
  kill $GM 2>/dev/null || true
  cp /work/run_$tag/train_log.jsonl out/train_log_$tag.jsonl
  stage "TRAIN_DONE $tag"
}

devckpts() {
  local tag=$1
  ev sets/dev.jsonl crops/dev out/eval/dev_$tag.jsonl $(ls -d /work/run_$tag/ckpt-* | sort -t- -k2 -n) >> out/eval_$tag.log 2>&1
  stage "DEV_DONE $tag"
}

final() {   # TAG CKPT
  local tag=$1 ck=$2
  ev sets/exam.jsonl crops/exam out/eval/exam_$tag.jsonl $ck >> out/eval_final_$tag.log 2>&1
  [ -f sets/locked.jsonl ] && ev sets/locked.jsonl crops/locked out/eval/locked_$tag.jsonl $ck >> out/eval_final_$tag.log 2>&1
  mkdir -p out/weights/$tag && cp -r $ck out/weights/$tag/      # the adapter comes home with the monitor's copy
  stage "FINAL_DONE $tag $ck"
}

base_final() {
  ev sets/exam.jsonl crops/exam out/eval/exam_base.jsonl >> out/eval_final_base.log 2>&1
  [ -f sets/locked.jsonl ] && ev sets/locked.jsonl crops/locked out/eval/locked_base.jsonl >> out/eval_final_base.log 2>&1
  stage "FINAL_DONE base"
}

speed() {   # TAG CKPT: 5,000 training-pool lines (M crops), for lines per second at serving
  head -5000 sets/M.jsonl > sets/speed.jsonl
  ev sets/speed.jsonl crops/M out/eval/speed_$1.jsonl $2 >> out/eval_speed.log 2>&1
  stage "SPEED_DONE $1"
}

mkdir -p crops/L
case "$1" in
  all) done_ INFO_DONE || info; done_ SETUP_DONE || setup; done_ MODEL_DONE || model; stage ALL_UP ;;
  train) shift; train "$@" ;;
  devckpts|final|speed) f=$1; shift; $f "$@" ;;
  *) "$1" ;;
esac

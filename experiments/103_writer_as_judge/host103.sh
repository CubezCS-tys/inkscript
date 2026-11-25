#!/bin/bash
# Experiment 103 on the rented GPU host (one RTX 5090).  Experiment 102's host102.sh is reused for info / setup / model
# (uploaded beside this file, unchanged: vllm 0.34.0, transformers 5.22.2, peft 0.21.2, Qwen3.5-4B at the pinned
# commit with every shard's sha256 checked).  Follow with a bracket pattern:  gs103.py follow '[h]ost103.sh'
#   all        host102.sh all (info + setup + model) and wsetup, each skipped when done (out/stages.log)
#   wsetup     the writer's own venv /work/wvenv (torch 2.14.0 for CUDA 13.0 + the packages experiments 87/95 used,
#              pinned to the versions of 87's local venv); kept apart so vLLM's venv is never disturbed
#   repair     continue experiment 102's M adapter on sets/R.jsonl: 2 epochs, lr 2e-5 (M used 1e-4), warm-up 3%,
#              cosine, checkpoints every 50 steps -> /work/run_R (train102.py unchanged, --resume_adapter)
#   repairdev  M and every R checkpoint on dev103 + devmix, one engine, with log-probabilities
#   heldout    M and every R checkpoint on the held-out pool (9,731 lines), with log-probabilities
#   force CKPT the reader's log-likelihood of the B candidates (out/b/force_cands.jsonl), adapter CKPT
#   wsmoke     the writer: imports, programs, fonts, 32 lines x 20 steps on the GPU
#   judge      the writer: page styles, then the absolute check, then the contrastive check (judge103.py)
#   exam CKPT  (B3 only, if B1 or B2 passed) the chosen reader on the exam's 584 lines, once
# No telemetry.  Line images never leave this host except back to our server over the same ssh.
set -e -o pipefail
cd /work
mkdir -p out out/eval out/judge hf
export VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 HF_HUB_DISABLE_TELEMETRY=1 VLLM_DO_NOT_TRACK=1 WANDB_DISABLED=true
export HF_HOME=/work/hf TOKENIZERS_PARALLELISM=false PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=/work/venv/bin/python
WPY=/work/wvenv/bin/python
M=/work/weights/M/ckpt-3125
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }
done_() { grep -q "$1" out/stages.log 2>/dev/null; }
C=$(OMP_NUM_THREADS= nproc --all); W=$(( C - 4 > 10 ? 10 : C - 4 )); [ "$W" -lt 2 ] && W=2
export OMP_NUM_THREADS=2

wsetup() {
  python3 -m pip install -q uv
  python3 -m uv venv -q --python 3.12 /work/wvenv || python3 -m uv venv -q /work/wvenv
  python3 -m uv pip install --python $WPY --index-url https://download.pytorch.org/whl/cu130 \
      --extra-index-url https://pypi.org/simple "torch==2.14.0" > out/wuv.log 2>&1
  python3 -m uv pip install --python $WPY "numpy==2.5.4" "numba==0.68.1" "uharfbuzz==0.57.0" "scikit-image==0.26.0" \
      "scipy==1.18.1" "opencv-python-headless==5.0.0.93" >> out/wuv.log 2>&1
  $WPY -c "import torch, cv2, numba, uharfbuzz, skimage; print('writer venv: torch', torch.__version__, torch.version.cuda, torch.cuda.is_available(), 'cv2', cv2.__version__, 'numba', numba.__version__)" >> out/host103.log 2>&1
  stage WSETUP_DONE
}

ev() {   # SET CROPS OUT [adapters...]
  local set=$1 crops=$2 o=$3; shift 3
  . /work/cuda_env.sh; export VLLM_USE_FLASHINFER_SAMPLER=0
  $PY eval103.py read --model "$(cat /work/model_dir)" --set $set --crops $crops --out $o --H 96 --adapters "$@"
}

repair() {
  . /work/cuda_env.sh
  $PY train102.py --model "$(cat /work/model_dir)" --set sets/R.jsonl --crops crops/R --dev sets/dev103.jsonl \
    --dev_crops crops/dev --out /work/run_R --epochs 2 --lr 2e-5 --warmup 0.03 --save_every 50 --H 96 --workers $W \
    --resume_adapter $M >> out/train_R.log 2>&1
  cp /work/run_R/train_log.jsonl out/train_log_R.jsonl
  mkdir -p out/weights/R && cp -r /work/run_R/ckpt-* out/weights/R/     # every checkpoint comes home (~250 MB each)
  stage REPAIR_DONE
}

repairdev() {
  local ck=$(ls -d /work/run_R/ckpt-* | sort -t- -k2 -n)
  ev sets/dev103.jsonl crops/dev out/eval/dev103_R.jsonl $M $ck >> out/eval_repair.log 2>&1
  ev sets/devmix.jsonl crops/devmix out/eval/devmix_R.jsonl $M $ck >> out/eval_repair.log 2>&1
  stage REPAIRDEV_DONE
}

heldout() {
  local ck=$(ls -d /work/run_R/ckpt-* | sort -t- -k2 -n)
  ev sets/heldout.jsonl crops/heldout out/eval/heldout_R.jsonl $M $ck >> out/eval_heldout.log 2>&1
  stage HELDOUT_DONE
}

force() {   # CKPT
  . /work/cuda_env.sh; export VLLM_USE_FLASHINFER_SAMPLER=0
  $PY eval103.py force --model "$(cat /work/model_dir)" --cands out/b/force_cands.jsonl --crops crops/heldout \
    --out out/eval/force_b.jsonl --adapters $1 >> out/eval_force.log 2>&1
  stage FORCE_DONE
}

judgeenv() {
  export WORK103=/work B103=/work/out/b J103=/work/out/judge CROPS103=/work/crops/heldout_png
  export FONTS87=/work/fonts PROG95=/work/programs DATA87=/work/data87 E87=/work/e87 WARP87=0.6 THREADS=8
  cp -n /work/judge_guards.json /work/out/judge/guards.json 2>/dev/null || true
}

wsmoke() { judgeenv; $WPY judge103.py smoke >> out/judge.log 2>&1; stage WSMOKE_DONE; }

judge() {
  judgeenv
  done_ STYLES_DONE || { $WPY judge103.py styles >> out/judge.log 2>&1; stage STYLES_DONE; }
  done_ CHECK_DONE || { $WPY judge103.py check >> out/judge.log 2>&1; stage CHECK_DONE; }
  done_ CONTRAST_DONE || { $WPY judge103.py contrast >> out/judge.log 2>&1; stage CONTRAST_DONE; }
  stage JUDGE_DONE
}

exam() {   # CKPT (B3 only)
  ev sets/exam.jsonl crops/exam out/eval/exam_R.jsonl $1 >> out/eval_exam.log 2>&1
  stage "EXAM_DONE $1"
}

case "$1" in
  all) bash host102.sh all; done_ WSETUP_DONE || wsetup; stage ALL103_UP ;;
  force|exam) f=$1; shift; $f "$@" ;;
  *) "$1" ;;
esac

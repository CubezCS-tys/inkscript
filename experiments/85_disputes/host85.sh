#!/bin/bash
# Experiment 85 on the GPU host, stage by stage (each started with gs85.py run, fetched before the next):
#   bash host85.sh cut                         re-cut experiment 83's data from presigned URLs (/work/urls_*.jsonl),
#                                              exactly as experiment 83 (cut83.py, unchanged)
#   bash host85.sh train TAG LABELS EPOCHS LR [EXTRA]
#                                              fine-tune from /work/init/best.pt on d/ with LABELS (held lines dropped
#                                              or relabelled), checkpoint each epoch in run_TAG, then its test/dev reads
#   bash host85.sh read TAG                    run_TAG reads experiment 77's test crops and the dev split again
# Layout: /work/d (shards, manifests: never mirrored), /work/out (small results, mirrored), /work/run_* (checkpoints,
# mirrored), /work/test (experiment 77's test crops), /work/init (the starting reader), /work/labels (label files).
set -e
cd /work
mkdir -p d out
# real CPUs: the cgroup quota (v2 cpu.max "QUOTA PERIOD"; v1 cpu.cfs_quota_us / cpu.cfs_period_us), else nproc
C=$(awk '$1 != "max" {print int($1 / $2)}' /sys/fs/cgroup/cpu.max 2>/dev/null || true)
if [ -z "$C" ] && [ -f /sys/fs/cgroup/cpu/cpu.cfs_quota_us ]; then
  q=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us); p=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)
  [ "$q" -gt 0 ] && C=$(( q / p ))
fi
[ -z "$C" ] && C=$(nproc)
[ "$C" -gt "$(nproc)" ] && C=$(nproc)
W=$(( C - 2 > 16 ? 16 : C - 2 ))          # data-loader workers
CW=$(( C - 4 > 40 ? 40 : C - 4 ))         # cutting workers (CPU only)
T=$(( C > 8 ? 8 : C ))                    # torch threads in the main process: within the cgroup quota
export OMP_NUM_THREADS=1
echo "$(date -u +%FT%TZ) cpus(quota)=$C loader=$W cut=$CW torch_threads=$T" >> out/host85.log
case "$1" in
cut)
  for s in r77dev:dev-r77 r77train:train-r77 o80:train-o80 new:train-n83; do
    u=${s%%:*}; p=${s##*:}
    echo "$(date -u +%FT%TZ) cut $u -> $p ($CW workers)" >> out/cut.log
    python cut83.py urls_$u.jsonl d $CW $p >> out/cut.log 2>&1
  done
  cat d/docs-*.jsonl > out/docs85.jsonl
  python - <<'EOF' >> out/cut.log
import glob, json
from collections import Counter
c = Counter()
for f in glob.glob("d/manifest-*.jsonl"):
    p = f.split("manifest-")[1].rsplit("-", 1)[0]
    c[p] += sum(1 for _ in open(f))
err = sum(1 for l in open("out/docs85.jsonl") if "error" in json.loads(l))
print("LINES", dict(c), "doc errors", err)
EOF
  echo CUT_STAGE_DONE >> out/cut.log ;;
train)
  tag=$2; labels=$3; ep=$4; lr=$5; extra=$6      # extra: e.g. --drop_paren for a start from v5
  [ -f "$labels" ] || gunzip -k "$labels.gz"
  python train85.py train --data d --out run_$tag --labels $labels --epochs $ep --workers $W --lr $lr --pct 0.1 \
      --init init/best.pt --threads $T $extra > out/train_$tag.log 2>&1
  mkdir -p out/pred
  python train85.py infer --ckpt run_$tag/best.pt --data test --split test --pred out/pred/test_$tag.jsonl --workers 4 --threads $T >> out/train_$tag.log 2>&1
  python train85.py infer --ckpt run_$tag/last.pt --data test --split test --pred out/pred/test_${tag}_last.jsonl --workers 4 --threads $T >> out/train_$tag.log 2>&1
  python train85.py infer --ckpt run_$tag/best.pt --data d --split dev --pred out/pred/dev_$tag.jsonl --workers 8 --threads $T >> out/train_$tag.log 2>&1
  echo TRAIN_STAGE_DONE >> out/train_$tag.log ;;
read)
  tag=$2
  mkdir -p out/pred
  python train85.py infer --ckpt run_$tag/best.pt --data test --split test --pred out/pred/test_$tag.jsonl --workers 4 --threads $T > out/read_$tag.log 2>&1
  echo READ_STAGE_DONE >> out/read_$tag.log ;;
*) echo "usage: host85.sh cut | train TAG LABELS EPOCHS LR | read TAG"; exit 1 ;;
esac

#!/bin/bash
# Experiment 83 on the GPU host, stage by stage (each stage is started with gs83.py run and fetched before the next):
#   bash host83.sh cut                      fetch + cut every document from its presigned URLs (/work/urls_*.jsonl)
#   bash host83.sh consensus                v1 reads the new lines; consensus labels v3 (/work/out/agree_v3.json)
#   bash host83.sh train TAG LABELS EPOCHS "SIZE ARGS"   train TAG (run_TAG, checkpoint each epoch), then its test/dev reads
#   bash host83.sh relabel                  v3 reads the new lines; the held-aside ones v3 now reads as Azure -> labels v4
# Layout: /work/d (shards, manifests, labels, held lines: never mirrored), /work/out (small results, mirrored by
# ops/lab_monitor.py), /work/run_* (checkpoints, mirrored), /work/test (experiment 77's test crops), /work/v1 (weights).
set -e
cd /work
mkdir -p d out
# real CPUs: the cgroup quota (cpu.max "QUOTA PERIOD"), else nproc; workers = CPUs - 2, at most 16
C=$(awk '$1 != "max" {print int($1 / $2)}' /sys/fs/cgroup/cpu.max 2>/dev/null || true)
if [ -z "$C" ] && [ -f /sys/fs/cgroup/cpu/cpu.cfs_quota_us ]; then          # cgroup v1
  q=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us); p=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)
  [ "$q" -gt 0 ] && C=$(( q / p ))
fi
[ -z "$C" ] && C=$(nproc)
[ "$C" -gt "$(nproc)" ] && C=$(nproc)
W=$(( C - 2 > 16 ? 16 : C - 2 ))          # data-loader workers
CW=$(( C - 4 > 40 ? 40 : C - 4 ))         # cutting workers (CPU only)
case "$1" in
cut)
  for s in r77dev:dev-r77 r77train:train-r77 o80:train-o80 new:train-n83; do
    u=${s%%:*}; p=${s##*:}
    echo "$(date -u +%FT%TZ) cut $u -> $p ($CW workers)" >> out/cut.log
    python cut83.py urls_$u.jsonl d $CW $p >> out/cut.log 2>&1
  done
  cat d/docs-*.jsonl > out/docs83.jsonl
  python - <<'EOF' >> out/cut.log
import glob, json
from collections import Counter
c = Counter()
for f in glob.glob("d/manifest-*.jsonl"):
    p = f.split("manifest-")[1].rsplit("-", 1)[0]
    c[p] += sum(1 for _ in open(f))
err = sum(1 for l in open("out/docs83.jsonl") if "error" in json.loads(l))
print("LINES", dict(c), "doc errors", err)
EOF
  echo CUT_STAGE_DONE >> out/cut.log ;;
consensus)
  mkdir -p d/pred
  python train77.py infer --ckpt v1/best.pt --data d --split train-n83 --pred d/pred/n83_v1.jsonl --workers 12 > out/consensus.log 2>&1
  python train77.py infer --ckpt v1/best.pt --data d --split train-o80 --pred d/pred/o80_v1.jsonl --workers 12 >> out/consensus.log 2>&1
  python consensus83.py d --manifest 'd/manifest-train-n83-*.jsonl' --manifest 'd/manifest-train-o80-*.jsonl' \
      --pred d/pred/n83_v1.jsonl --pred d/pred/o80_v1.jsonl --tag v3 >> out/consensus.log 2>&1
  cp d/agree_v3.json out/
  gzip -kf d/held_v3.jsonl
  echo CONSENSUS_STAGE_DONE >> out/consensus.log ;;
train)
  tag=$2; labels=$3; ep=$4; size=$5
  python train77.py train --data d --out run_$tag --labels $labels --epochs $ep --workers $W --lr 1e-3 $size > out/train_$tag.log 2>&1
  mkdir -p out/pred
  python train77.py infer --ckpt run_$tag/best.pt --data test --split test --pred out/pred/test_$tag.jsonl --workers 4 >> out/train_$tag.log 2>&1
  python train77.py infer --ckpt run_$tag/best.pt --data d --split dev --pred out/pred/dev_$tag.jsonl --workers 8 >> out/train_$tag.log 2>&1
  python train77.py infer --ckpt v1/best.pt --data test --split test --pred out/pred/test_v1_host.jsonl --workers 4 >> out/train_$tag.log 2>&1
  echo TRAIN_STAGE_DONE >> out/train_$tag.log ;;
relabel)
  python train77.py infer --ckpt run_v3/best.pt --data d --split train-n83 --pred d/pred/n83_v3.jsonl --workers 12 > out/relabel.log 2>&1
  python train77.py infer --ckpt run_v3/best.pt --data d --split train-o80 --pred d/pred/o80_v3.jsonl --workers 12 >> out/relabel.log 2>&1
  python consensus83.py d --manifest 'd/manifest-train-n83-*.jsonl' --manifest 'd/manifest-train-o80-*.jsonl' \
      --pred d/pred/n83_v3.jsonl --pred d/pred/o80_v3.jsonl --only d/held_v3.jsonl --tag v4held >> out/relabel.log 2>&1
  # v4 labels: drop only the lines still held after v3's reading (labels_v4held lists exactly those, within held_v3)
  cp d/labels_v4held.jsonl d/labels_v4.jsonl
  cp d/agree_v4held.json out/
  gzip -kf d/held_v4held.jsonl
  echo RELABEL_STAGE_DONE >> out/relabel.log ;;
*) echo "usage: host83.sh cut|consensus|train TAG LABELS EPOCHS SIZE|relabel"; exit 1 ;;
esac

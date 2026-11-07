#!/bin/bash
# Experiment 84 on the GPU host, stage by stage (each started with gs84.py run, fetched before the next):
#   bash host84.sh cut          re-cut experiment 83's training lines from S3 (presigned URLs; experiment 83's cut83.py)
#   bash host84.sh render       synthetic lines: 300k training (train-syn84-*; 60% display faces, 40% «» / (( )) body
#                               lines) + 4k dev (vsyn84-*)
#   bash host84.sh train TAG SYN EPOCHS DROP   fine-tune v3 -> run_TAG; SYN=1 keeps the synthetic lines, 0 moves them
#                               out; DROP=1 drops real lines whose Azure label has (( or )) (never rewritten);
#                               then reads experiment 77's test crops, the real dev and the synthetic dev
# Layout: /work/d (shards, never mirrored), /work/out (small results, mirrored by ops/lab_monitor.py), /work/run_*
# (checkpoints, mirrored), /work/test (exp 77's test crops), /work/v3 (exp 83's v3 weights), /work/fonts, /work/r78.
# Follow with bracket patterns only, e.g.  gs84.py follow '[c]ut83.py'  /  '[r]ender84.py'  /  '[t]rain84.py'.
set -e
cd /work
mkdir -p d out
C=$(awk '$1 != "max" {print int($1 / $2)}' /sys/fs/cgroup/cpu.max 2>/dev/null || true)
for g in /sys/fs/cgroup/cpu /sys/fs/cgroup/cpu,cpuacct; do                  # cgroup v1 (either mount name)
  if [ -z "$C" ] && [ -f $g/cpu.cfs_quota_us ]; then
    q=$(cat $g/cpu.cfs_quota_us); p=$(cat $g/cpu.cfs_period_us)
    [ "$q" -gt 0 ] && C=$(( q / p ))
  fi
done
[ -z "$C" ] && C=$(nproc)
[ "$C" -gt "$(nproc)" ] && C=$(nproc)
W=$(( C - 2 > 16 ? 16 : C - 2 ))          # data-loader workers
CW=$(( C - 1 > 40 ? 40 : C - 1 ))         # cutting / rendering workers (CPU only)
export OMP_NUM_THREADS=1
echo "$(date -u +%FT%TZ) cpus $C loader $W cpu-workers $CW" >> out/host84.log
case "$1" in
cut)
  for s in r77dev:dev-r77 r77train:train-r77 o80:train-o80 new:train-n83; do
    u=${s%%:*}; p=${s##*:}
    echo "$(date -u +%FT%TZ) cut $u -> $p ($CW workers)" >> out/cut.log
    python cut83.py urls_$u.jsonl d $CW $p >> out/cut.log 2>&1
  done
  cat d/docs-*.jsonl > out/docs84.jsonl
  python - <<'EOF' >> out/cut.log
import glob, json
from collections import Counter
c = Counter()
for f in glob.glob("d/manifest-*.jsonl"):
    p = f.split("manifest-")[1].rsplit("-", 1)[0]
    c[p] += sum(1 for _ in open(f))
err = sum(1 for l in open("out/docs84.jsonl") if "error" in json.loads(l))
print("LINES", dict(c), "doc errors", err)
EOF
  rm -f urls_*.jsonl                       # the presigned URLs are not needed any more
  echo CUT_STAGE_DONE >> out/cut.log ;;
render)
  python render84.py shards --n 300000 --workers $CW --out d --split train-syn84 --root /work --root78 /work/r78 > out/render.log 2>&1
  python render84.py shards --n 4000 --workers 8 --out d --split vsyn84 --root /work --root78 /work/r78 --seed 8484 >> out/render.log 2>&1
  python render84.py sheet --n 60 --out out/syn84_sheet.png --root /work --root78 /work/r78 >> out/render.log 2>&1
  echo RENDER_STAGE_DONE >> out/render.log ;;
train)
  tag=$2; syn=$3; ep=$4; drop=${5:-0}
  DR=""; [ "$drop" = "1" ] && DR='\(\(|\)\)'
  mkdir -p d/off
  if [ "$syn" = "0" ]; then mv d/train-syn84-*.tar d/off/ 2>/dev/null || true; else mv d/off/train-syn84-*.tar d/ 2>/dev/null || true; fi
  python train84.py train --data d --out run_$tag --labels labels_v3.jsonl --init v3/best.pt --epochs $ep --workers $W \
      --lr 3e-4 --warm 0.1 --invert 0.06 --band 0.04 --dev2 vsyn84 ${DR:+--drop_re "$DR"} > out/train_$tag.log 2>&1
  mv d/off/train-syn84-*.tar d/ 2>/dev/null || true
  mkdir -p out/pred
  for ck in last; do
    python train84.py infer --ckpt run_$tag/$ck.pt --data test --split test --pred out/pred/test_${tag}.jsonl --workers 4 >> out/train_$tag.log 2>&1
    python train84.py infer --ckpt run_$tag/$ck.pt --data d --split dev --pred out/pred/dev_${tag}.jsonl --workers 8 >> out/train_$tag.log 2>&1
    python train84.py infer --ckpt run_$tag/$ck.pt --data d --split vsyn84 --pred out/pred/vsyn_${tag}.jsonl --workers 8 >> out/train_$tag.log 2>&1
  done
  if [ ! -f out/pred/vsyn_v3.jsonl ]; then
    python train84.py infer --ckpt v3/best.pt --data d --split vsyn84 --pred out/pred/vsyn_v3.jsonl --workers 8 >> out/train_$tag.log 2>&1
    python train84.py infer --ckpt v3/best.pt --data test --split test --pred out/pred/test_v3_host.jsonl --workers 4 >> out/train_$tag.log 2>&1
  fi
  cp d/manifest-vsyn84-*.jsonl out/ 2>/dev/null || true
  echo TRAIN_STAGE_DONE >> out/train_$tag.log ;;
*) echo "usage: host84.sh cut|render|train TAG SYN EPOCHS [DROP]"; exit 1 ;;
esac

#!/bin/bash
# Experiment 89 on the GPU host.  Stages (each can be started alone with gs89.py run; `all` chains them with no idle gap):
#   bash host89.sh cut        re-cut experiment 83's training lines from presigned URLs (cut83.py unchanged), as 84/85
#   bash host89.sh render     experiment 84's synthetic lines, unchanged: 300k training (180k display faces, 0097 and
#                             «العربية للتربية» excluded by text84; 120k «» / (( )) body lines labelled as rendered) + 4k dev
#   bash host89.sh v7         fine-tune v6r (init/best.pt) on v3's consensus lines + v6r's labels + the 300k synthetic
#                             lines, polarity 6% inverted / 4% band, real lines whose Azure label has (( or )) dropped;
#                             3 epochs, one-cycle 3e-4, warm-up 10%; then the reads (below)
#   bash host89.sh l28        the same data and augmentation at 28M parameters (exp 77's sweep: cw 1.5, feat 640, hid
#                             768), FROM SCRATCH with v6r's charset: 8 epochs, one-cycle 1e-3, warm-up 5% (v3's own
#                             from-scratch recipe); then the reads
#   bash host89.sh reads TAG CKPT    test (exp 77's test crops), dev, vsyn84, t81 (exp 81's 22,783 crops), titles (exp 89)
#   bash host89.sh all        cut, render, v7, l28 back to back (STAGE markers in out/stages.log)
# Every training run passes --forbid forbidden89.json: train89.py refuses to start if a held-out or locked key is in it.
# Layout: /work/d (shards; never mirrored), /work/out (results, mirrored by ops/lab_monitor.py), /work/run_* (checkpoints,
# mirrored), /work/test, /work/t81, /work/titles (crops to read), /work/init (v6r), /work/fonts, /work/text, /work/r78.
# Follow with bracket patterns only:  gs89.py follow '[h]ost89.sh'
set -e
cd /work
mkdir -p d out out/pred
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
T=$(( C > 8 ? 8 : C ))                    # torch threads in the main process, within the quota
export OMP_NUM_THREADS=1
echo "$(date -u +%FT%TZ) cpus(quota) $C loader $W cpu-workers $CW torch $T" >> out/host89.log
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }
DR='\(\(|\)\)'

reads() {   # TAG CKPT
  local tag=$1 ck=$2
  python train89.py infer --ckpt $ck --data test --split test --pred out/pred/test_$tag.jsonl --workers 4 --threads $T >> out/reads_$tag.log 2>&1
  python train89.py infer --ckpt $ck --data d --split dev --pred out/pred/dev_$tag.jsonl --workers 8 --threads $T >> out/reads_$tag.log 2>&1
  python train89.py infer --ckpt $ck --data d --split vsyn84 --pred out/pred/vsyn_$tag.jsonl --workers 8 --threads $T >> out/reads_$tag.log 2>&1
  python train89.py infer --ckpt $ck --data t81 --split test81 --pred out/pred/t81_$tag.jsonl --workers 8 --threads $T >> out/reads_$tag.log 2>&1
  if ls titles/titles89-*.tar >/dev/null 2>&1; then
    python train89.py infer --ckpt $ck --data titles --split titles89 --pred out/pred/titles_$tag.jsonl --workers 2 --threads $T >> out/reads_$tag.log 2>&1
  fi
  stage "READS_DONE $tag"
}

do_cut() {
  for s in r77dev:dev-r77 r77train:train-r77 o80:train-o80 new:train-n83; do
    u=${s%%:*}; p=${s##*:}
    echo "$(date -u +%FT%TZ) cut $u -> $p ($CW workers)" >> out/cut.log
    python cut83.py urls_$u.jsonl d $CW $p >> out/cut.log 2>&1
  done
  cat d/docs-*.jsonl > out/docs89.jsonl
  python - <<'EOF' >> out/cut.log
import glob, json
from collections import Counter
c = Counter()
for f in glob.glob("d/manifest-*.jsonl"):
    p = f.split("manifest-")[1].rsplit("-", 1)[0]
    c[p] += sum(1 for _ in open(f))
err = sum(1 for l in open("out/docs89.jsonl") if "error" in json.loads(l))
print("LINES", dict(c), "doc errors", err)
EOF
  rm -f urls_*.jsonl                       # the presigned URLs are not needed any more
  stage CUT_DONE
}

do_render() {
  python render84.py shards --n 300000 --workers $CW --out d --split train-syn84 --root /work --root78 /work/r78 > out/render.log 2>&1
  python render84.py shards --n 4000 --workers 8 --out d --split vsyn84 --root /work --root78 /work/r78 --seed 8484 >> out/render.log 2>&1
  cp d/manifest-vsyn84-*.jsonl out/ 2>/dev/null || true
  stage RENDER_DONE
}

do_v7() {
  [ -f labels/labels_v6r.jsonl ] || gunzip -k labels/labels_v6r.jsonl.gz
  python train89.py train --data d --out run_v7 --labels labels/labels_v6r.jsonl --init init/best.pt --epochs 3 \
      --workers $W --threads $T --lr 3e-4 --warm 0.1 --invert 0.06 --band 0.04 --dev2 vsyn84 --drop_re "$DR" \
      --forbid forbidden89.json > out/train_v7.log 2>&1
  stage TRAIN_DONE v7
  reads v7 run_v7/last.pt
}

do_l28() {
  [ -f labels/labels_v6r.jsonl ] || gunzip -k labels/labels_v6r.jsonl.gz
  python train89.py train --data d --out run_l28 --labels labels/labels_v6r.jsonl --charset_from init/best.pt \
      --arch lstm --cw 1.5 --feat 640 --hid 768 --epochs ${L28_EPOCHS:-8} --minutes ${L28_MINUTES:-0} \
      --workers $W --threads $T --lr 1e-3 --warm 0.05 --invert 0.06 --band 0.04 --dev2 vsyn84 --drop_re "$DR" \
      --forbid forbidden89.json > out/train_l28.log 2>&1
  stage TRAIN_DONE l28
  reads l28 run_l28/last.pt
}

case "$1" in
cut) do_cut ;;
render) do_render ;;
v7) do_v7 ;;
l28) do_l28 ;;
reads) reads $2 $3 ;;
all)
  stage START all
  [ -f d/manifest-train-n83-0.jsonl ] || ls d/manifest-train-n83-*.jsonl >/dev/null 2>&1 || do_cut
  ls d/train-syn84-*.tar >/dev/null 2>&1 || do_render
  n=0; while [ ! -f forbidden89.json ] && [ $n -lt 240 ]; do   # the guard's list (forbid89.py) may arrive after the cut
    [ $n -eq 0 ] && stage "WAITING for forbidden89.json"; sleep 30; n=$((n + 1)); done
  [ -f run_v7/last.pt ] && [ -f out/pred/t81_v7.jsonl ] || do_v7
  do_l28
  stage ALL_DONE ;;
*) echo "usage: host89.sh cut|render|v7|l28|reads TAG CKPT|all"; exit 1 ;;
esac

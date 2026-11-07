#!/bin/bash
# Experiment 82 on the rented host, one stage at a time (python3 gs82.py run 'bash experiments/82_path_accuracy/host82.sh STAGE');
# fetch out/ after every stage.  W = data workers (real CPUs - 2, from cgroup cpu.max).
set -e
cd /work/experiments/82_path_accuracy
Q=$(awk '{print $1}' /sys/fs/cgroup/cpu.max 2>/dev/null || echo max); P=$(awk '{print $2}' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 100000)
if [ "$Q" = "max" ] || [ -z "$Q" ]; then
  Q1=$(cat /sys/fs/cgroup/cpu,cpuacct/cpu.cfs_quota_us 2>/dev/null || echo -1); P1=$(cat /sys/fs/cgroup/cpu,cpuacct/cpu.cfs_period_us 2>/dev/null || echo 100000)
  if [ "$Q1" -gt 0 ] 2>/dev/null; then C=$((Q1 / P1)); else C=$(nproc); fi                   # cgroup v1 quota
else C=$((Q / P)); fi
W=$((C > 4 ? C - 2 : 2)); W=$((W > 40 ? 40 : W)); W=${W82:-$W}
echo "cpus $C workers $W"
D=/work/d82; R=/work/r82; O=/work/out; mkdir -p $D $R $O
case "$1" in
  gen)      # training pairs for the network, reader lines, reader test lines
    python gen82.py --set unet   --n ${N_UNET:-80000}  --workers $W --out $D
    python gen82.py --set reader --n ${N_READ:-60000}  --workers $W --out $D
    python gen82.py --set test   --n ${N_TEST:-3000}   --workers $W --out $D ;;
  genreader) # only the reader lines and the reader test lines (the network already exists)
    python gen82.py --set reader --n ${N_READ:-60000}  --workers $W --out $D
    python gen82.py --set test   --n ${N_TEST:-3000}   --workers $W --out $D ;;
  train)    # the learned rebuilder
    python learn82.py train --data $D --out $O --name ${NAME:-u1} --steps ${STEPS:-20000} --workers $W ;;
  shape)    # its centre lines on the shape-test lines, then the shape metric of the learned paths (CPU)
    for F in modern traced; do
      python learn82.py shape --model $O/${NAME:-u1}/model.pt --lines out/shape_$F/lines.json --out $O/${NAME:-u1}/shape_$F
      python shape82.py --faces $F --lines out/shape_$F/lines.json --methods learned --cl $O/${NAME:-u1}/shape_$F/cl \
        --levels clean,mild,heavy,spread,fill --workers $W --tag _learned --outdir $O/${NAME:-u1}
    done ;;
  feats)    # reader signals: rule (skeleton) and learned paths of the same lines
    python learn82.py feats --model $O/${NAME:-u1}/model.pt --data $D --split reader --workers $W --out $R
    python learn82.py feats --model $O/${NAME:-u1}/model.pt --data $D --split test --workers $W --out $R ;;
  readers)  # the downstream check: one reader on rule paths, one on learned paths, side by side on the one GPU
    H=$((W / 2))
    OUT82=$O python reader82.py --data $R --train-split reader --kind recon   --name rd_rule    --epochs ${EP:-8} --workers $H --skip-real --budget 50000 > $O/rd_rule.log 2>&1 &
    OUT82=$O python reader82.py --data $R --train-split reader --kind learned --name rd_learned --epochs ${EP:-8} --workers $H --skip-real --budget 50000 > $O/rd_learned.log 2>&1
    wait ;;
  *) echo "stage: gen | genreader | train | shape | feats | readers"; exit 1 ;;
esac
echo "STAGE $1 DONE"

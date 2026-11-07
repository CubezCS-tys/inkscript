#!/bin/bash
# Experiment 87: the full held-out judged test for both rounds' frozen rules (after the HarfBuzz empty-reading fix).
#   round 1: RUN87=out/run  (no warp floor);  round 2: RUN87=out/run2, WARP87=0.6, round 1's page styles
set -e
cd /work
[ -f up87.tgz ] && [ ! -d out/data ] && tar xzf up87.tgz
mkdir -p out/run out/run2
cp -n style_held.jsonl out/run/ 2>/dev/null || true
C=$(awk '$1 != "max" {print int($1 / $2)}' /sys/fs/cgroup/cpu.max 2>/dev/null || true); [ -z "$C" ] && C=$(nproc)
T=$(( C > 8 ? 8 : C ))
export OMP_NUM_THREADS=$T THREADS=$T FONTS87=/work/fonts
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }
stage j1 start
RUN87=out/run python run87.py check judged --iters 100 --batch 32; stage j1 done
RUN87=out/run2 STYLE87=out/run WARP87=0.6 python run87.py check judged --iters 100 --batch 32; stage J_DONE

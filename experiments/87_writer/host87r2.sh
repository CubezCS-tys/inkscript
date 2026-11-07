#!/bin/bash
# Experiment 87, round 2 on the GPU host: the checker again with round 1's page styles (STYLE87=out/run), the warp
# floor (WARP87=0.6: no letter squeezed below 60% of the line's width) and the per-word / per-letter features.
# Pool planted variants (the design) and exp 81's judged lines only (budget): the held planted set stays round 1's.
set -e
cd /work
C=$(awk '$1 != "max" {print int($1 / $2)}' /sys/fs/cgroup/cpu.max 2>/dev/null || true); [ -z "$C" ] && C=$(nproc)
T=$(( C > 8 ? 8 : C ))
export OMP_NUM_THREADS=$T THREADS=$T FONTS87=/work/fonts RUN87=out/run2 STYLE87=out/run WARP87=0.6
mkdir -p out/run2
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }
stage r2 start
python run87.py check pool --iters 100 --batch 32; stage r2 pool done
python run87.py check judged --iters 100 --batch 32; stage R2_DONE

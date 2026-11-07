#!/bin/bash
# Experiment 78: typefaces traced from our own old scans (experiment 11's make_font.py), training-pool journals only.
# One article at a time, niced, one thread; peak memory logged by /usr/bin/time -v.
cd /home/appuser/inkscript
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
O=experiments/78_synthetic_lines/out/fonts/traced; mkdir -p $O
while read stem fam az pdf; do
  [ -f "$O/$fam.ttf" ] && continue
  echo "== $stem $fam $(date)"
  taskset -c 6,7 nice -n 19 ionice -c3 /usr/bin/time -v .venv/bin/python experiments/11_typeface/make_font.py "$az" "$pdf" "$fam" "$O/$fam.ttf" > "$O/$fam.log" 2>&1
  grep -E "Maximum resident|Elapsed|Exit" "$O/$fam.log"
done < experiments/78_synthetic_lines/${LIST:-trace_list.txt}

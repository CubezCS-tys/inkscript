#!/bin/bash
# Build the product set: every document with --vector --verify --xml --trust, resumably, on W polite workers.
#   run_set.sh <azure_dir> <out_dir> <workers> [first_stem_for_w0]
# Same shape as experiments/09_pen_path/run_set.sh (one output folder per worker, --resume skips finished
# documents); no frontpage dir: page 1 stays Azure's reading.
cd "$(dirname "$(readlink -f "$0")")/../.."; INK=.venv/bin/inkscript; A=$1; J=$2; W=${3:-3}; FIRST=$4
mkdir -p $J; ls $A | sort > $J/stems.txt; rm -f $J/stems_w*
i=0; for w in $(seq 0 $((W-1))); do : > $J/stems_w$w; done
[ -n "$FIRST" ] && echo "$FIRST" >> $J/stems_w0
while read s; do [ "$s" = "$FIRST" ] && continue; echo "$s" >> $J/stems_w$((i % W)); i=$((i+1)); done < $J/stems.txt
for w in $(seq 0 $((W-1))); do
  ( while read d; do [ -z "$d" ] && continue
      /usr/bin/time -f "$d peak_kb=%M wall=%e" nice -n 10 $INK native --azure-dir $A --out $J/w$w --vector --verify --xml --trust --resume --only "$d" 2>&1 | grep -v -i "warning\|MuPDF error"
    done < $J/stems_w$w ) >> $J/w$w.log 2>&1 &
done
wait
echo "SET DONE $(date)" >> $J/w0.log

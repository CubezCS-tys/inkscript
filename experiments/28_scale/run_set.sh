#!/bin/bash
# Experiment 28: build the set with everything on, resumably, on W polite workers.
#   run_set.sh <azure_dir> <frontpage_dir> <out_dir> <workers>
# Same shape as experiments/24_product/run_set.sh (one output folder per worker, --resume), plus:
#  * --frontpage-dir (Gemini title files for the structure step; no page-1 readings, so page 1 stays Azure's);
#  * a per-document time limit (TLIM seconds, default 5400) so a hang shows up as a timeout, not a stuck worker;
#  * each document's exit status in <out>/status/<stem> (0 ok, 124 timeout, other = crash) and its full stderr in
#    <out>/logs/<stem>.err (tracebacks are kept; the per-worker log drops only pymupdf/MuPDF warnings);
#  * a document that already has a status (other than killed: 137/143) is not tried again on a rerun.
# Long documents are dealt first (longest-processing-time order) so no worker is left with a long tail.
cd "$(dirname "$(readlink -f "$0")")/../.."; INK=.venv/bin/inkscript; A=$1; FP=$2; J=$3; W=${4:-3}; TLIM=${TLIM:-5400}
mkdir -p $J/status $J/logs
if [ ! -f $J/order.txt ]; then      # documents by page count, longest first (fixed once, so reruns deal the same way)
  .venv/bin/python - "$A" > $J/order.txt <<'EOF'
import sys, os, pymupdf
a = sys.argv[1]; rows = []
for s in sorted(os.listdir(a)):
    try: n = pymupdf.open(f"{a}/{s}/{s}.pdf").page_count
    except Exception: n = 0
    rows.append((n, s))
for n, s in sorted(rows, reverse=True): print(s)
EOF
fi
for w in $(seq 0 $((W-1))); do : > $J/stems_w$w; done
i=0; while read s; do echo "$s" >> $J/stems_w$((i % W)); i=$((i+1)); done < $J/order.txt
for w in $(seq 0 $((W-1))); do
  ( while read d; do [ -z "$d" ] && continue
      if [ -f $J/status/$d ]; then c=$(cat $J/status/$d); [ "$c" != 137 ] && [ "$c" != 143 ] && continue; fi
      /usr/bin/time -f "$d peak_kb=%M wall=%e exit=%x" -o $J/logs/$d.time timeout $TLIM nice -n 10 \
          $INK native --azure-dir $A --frontpage-dir $FP --out $J/w$w --vector --verify --xml --trust --resume --only "$d" \
          2> $J/logs/$d.err | grep -v -i "fitz\|MuPDF error"
      c=${PIPESTATUS[0]}; echo $c > $J/status/$d; cat $J/logs/$d.time; echo "$d exit=$c $(date +%H:%M:%S)"
    done < $J/stems_w$w ) >> $J/w$w.log 2>&1 &
done
wait
echo "SET DONE $(date)" >> $J/w0.log

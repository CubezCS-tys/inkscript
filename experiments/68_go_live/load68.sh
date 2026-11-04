#!/bin/bash
# Experiment 68: load the four *_fix61_d30 runs into a platform DB (default: the working copy), then link47 with its
# cache in out/linkwork (the live cache untouched). Usage: load68.sh [DB]
set -e
cd /home/appuser/inkscript
DB=${1:-/home/appuser/data/platform_v2/golive68_work.db}
P=experiments/47_platform_v2
L=experiments/68_go_live/out/logs
PY="nice -n 10 .venv/bin/python"
for rk in "j0130_final_fix61_d30 final" "v2_55_fix61_d30 sample" "v33_300b_fix3_lettersfix_fix61_d30 final" "v33_300_final_lettersfix_fix61_d30 final"; do
  set -- $rk
  echo "== load $1 $(date +%H:%M)"
  /usr/bin/time -v $PY $P/load47.py --run $1 --kind $2 --db $DB --note "experiment 68: go live (exp 65 leak fixes + exp 66 D30 guard)" > $L/load_$1.log 2> $L/load_$1.time
  tail -n 3 $L/load_$1.log; grep "Maximum resident" $L/load_$1.time
done
echo "== link47 $(date +%H:%M)"
/usr/bin/time -v $PY $P/link47.py --db $DB --work ${WORK:-experiments/68_go_live/out/linkwork} > $L/link47.log 2> $L/link47.time
tail -n 5 $L/link47.log; grep "Maximum resident" $L/link47.time
echo "== done $(date +%H:%M)"

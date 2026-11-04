#!/bin/bash
# Experiment 74: after a journal's Batch read: rechunk its MAX_TOKENS chunks (rechunk43) and ask them again on
# Standard, then build74.sh, then judge74.sh (judge, retries, final). Usage: finish_read74.sh J
J=$1
cd /home/appuser/inkscript/experiments/43_rehearsal
export META43_CATALOGUE_FIRST=1
echo "== rechunk $J $(date +%H:%M)"
nice ../../.venv/bin/python rechunk43.py --run j$J 2>&1 | grep -E "^$J|->" | cut -c1-200
S=$(ls out/j$J/raw/*.failed.json 2>/dev/null | xargs -r -n1 basename | sed 's/_c[0-9-]*\.failed\.json//' | sort -u)
if [ -n "$S" ]; then
  nice -n 5 ../../.venv/bin/python run43.py --set g --run j$J --prompt v3.6 --thinking low --cap 450 --mode standard --threads 3 --stems $S > ../74_gate2_full/out/logs/run_j${J}_rechunk.log 2>&1
  tail -n 1 ../74_gate2_full/out/logs/run_j${J}_rechunk.log
fi
cd ../74_gate2_full
bash build74.sh $J
bash judge74.sh $J 450 > out/logs/judge_$J.log 2>&1; grep -E "^== |findings|invalid" out/logs/judge_$J.log
echo "== finished $J $(date +%H:%M)"

#!/bin/bash
# Experiment 74: the second half of build74.sh (flags, views, summary) for journal J, then judge74.sh (when the plain
# build is done but a later step stopped). Usage: after_build74.sh J
J=$1
cd /home/appuser/inkscript/experiments/43_rehearsal
PY="nice -n 10 ../../.venv/bin/python"
F=out/j$J
/usr/bin/time -v $PY flags43.py --run j$J > $F/flags_run.log 2> $F/flags_run.time; head -4 $F/flags.txt; grep "Maximum res" $F/flags_run.time
stems=$(ls $F/masters/*.jats.xml | xargs -n1 basename | sed 's/.jats.xml//')
$PY views43.py --masters $F/masters --out $F/views --stems $stems --report $F/views_report.json > $F/views.log 2>&1
$PY summary43.py --run j$J > $F/summary.log 2>&1; tail -n 1 $F/summary.log
cd ../74_gate2_full
bash judge74.sh $J 470 > out/logs/judge_$J.log 2>&1; grep -E "^== |findings|invalid" out/logs/judge_$J.log

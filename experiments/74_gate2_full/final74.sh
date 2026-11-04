#!/bin/bash
# Experiment 74 (from final70.sh), step 6 for journal J: patched masters (judge two-key edits + page retries) for
# out/J/jJ_final, validation, flags, views, summary. No calls. Usage: final74.sh J
set -e
J=$1
cd /home/appuser/inkscript/experiments/43_rehearsal
PY="nice -n 10 ../../.venv/bin/python"
export PYTHONPATH=/home/appuser/inkscript/experiments/43_rehearsal/out/lettersfix/pylib
export META43_CATALOGUE_FIRST=1
F=out/j${J}_final
mkdir -p $F/masters $F/rules
cp -a out/j$J/masters/. $F/masters/
cp -a out/j$J/rules/. $F/rules/
ln -sfn ../j$J/raw $F/raw
echo "== patches $J $(date +%H:%M)"
$PY patches43.py build --run j${J}_final --src out/j$J/rules --out $F > $F/patch_build.log 2>&1; tail -n 3 $F/patch_build.log
$PY lettersfix43.py validate $F/masters > $F/validate.log; tail -n 1 $F/validate.log | cut -c1-400
echo "== flags $(date +%H:%M)"
$PY flags43.py --run j${J}_final --patches $F/patches > $F/flags_run.log 2>&1
head -4 $F/flags.txt
echo "== views $(date +%H:%M)"
stems=$(ls $F/masters/*.jats.xml | xargs -n1 basename | sed 's/.jats.xml//')
$PY views43.py --masters $F/masters --out $F/views --stems $stems --report $F/views_report.json > $F/views.log 2>&1
echo "== summary $(date +%H:%M)"
$PY summary43.py --run j${J}_final > $F/summary.log 2>&1; tail -n 1 $F/summary.log
echo "== done $(date +%H:%M)"

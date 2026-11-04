#!/bin/bash
# Experiment 52 step 6: patched masters (judge two-key edits + page retries) for out/j0130_final, validation, flags,
# views, summary (as out/v33_300b_fix3/build3.sh). No calls.
set -e
cd /home/appuser/inkscript/experiments/43_rehearsal
PY=../../.venv/bin/python
export PYTHONPATH=/home/appuser/inkscript/experiments/43_rehearsal/out/lettersfix/pylib
F=out/j0130_final
mkdir -p $F/masters $F/rules
cp -a out/j0130/masters/. $F/masters/
cp -a out/j0130/rules/. $F/rules/
echo "== patches $(date +%H:%M)"
$PY patches43.py build --run j0130_final --src out/j0130/rules --out $F > $F/patch_build.log 2>&1; tail -n 3 $F/patch_build.log
$PY lettersfix43.py validate $F/masters | tee $F/validate.log
echo "== flags $(date +%H:%M)"
$PY flags43.py --run j0130_final --patches $F/patches > $F/flags_run.log 2>&1
head -4 $F/flags.txt
echo "== views $(date +%H:%M)"
stems=$(ls $F/masters/*.jats.xml | xargs -n1 basename | sed 's/.jats.xml//')
$PY views43.py --masters $F/masters --out $F/views --stems $stems --report $F/views_report.json > $F/views.log 2>&1
echo "== summary $(date +%H:%M)"
$PY summary43.py --run j0130_final > $F/summary.log 2>&1; tail -n 1 $F/summary.log
echo "== done $(date +%H:%M)"

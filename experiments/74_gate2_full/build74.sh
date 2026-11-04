#!/bin/bash
# Experiment 74 (from build70.sh), step 3 for journal J: the run's answers through today's rules + the letter fix
# (lettersfix43 plain) + the D30 guard / leak fixes, into out/J/jJ (rules + masters), JATS DTD + ALTO XSD checked.
# The catalogue's page range wins (META43_CATALOGUE_FIRST=1, exp 70's issue 4). No calls. Usage: build74.sh J [stems]
set -e
J=$1; shift
cd /home/appuser/inkscript/experiments/43_rehearsal
PY="nice -n 10 ../../.venv/bin/python"
export PYTHONPATH=/home/appuser/inkscript/experiments/43_rehearsal/out/lettersfix/pylib   # latex2mathml (lettersfix's own)
export META43_CATALOGUE_FIRST=1
F=out/j$J
echo "== plain $J $(date +%H:%M)"
/usr/bin/time -v $PY lettersfix43.py plain --run j$J --set g --dst $F ${1:+--stems "$@"} > $F/build.log 2> $F/build.time
tail -n 1 $F/build.log | cut -c1-600; grep "Maximum resident" $F/build.time
$PY lettersfix43.py validate $F/masters > $F/validate.log; tail -n 1 $F/validate.log | cut -c1-400
echo "== flags + views + summary $(date +%H:%M)"
$PY flags43.py --run j$J > $F/flags_run.log 2>&1; head -4 $F/flags.txt
stems=$(ls $F/masters/*.jats.xml | xargs -n1 basename | sed 's/.jats.xml//')
$PY views43.py --masters $F/masters --out $F/views --stems $stems --report $F/views_report.json > $F/views.log 2>&1
$PY summary43.py --run j$J > $F/summary.log 2>&1; tail -n 1 $F/summary.log
echo "== done $(date +%H:%M)"

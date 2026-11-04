#!/bin/bash
# Experiment 52 step 3: the run's answers through today's rules + the letter fix (letters43 via lettersfix43), into
# out/j0130 (rules + masters), JATS DTD + ALTO XSD checked; then views, flags, summary. No calls. Args: stems (optional).
set -e
cd /home/appuser/inkscript/experiments/43_rehearsal
PY=../../.venv/bin/python
export PYTHONPATH=/home/appuser/inkscript/experiments/43_rehearsal/out/lettersfix/pylib   # latex2mathml (lettersfix's own)
F=out/j0130
echo "== plain $(date +%H:%M)"
/usr/bin/time -v $PY lettersfix43.py plain --run j0130 --set d --dst $F ${1:+--stems "$@"} > $F/build.log 2> $F/build.time
tail -n 2 $F/build.log; grep "Maximum resident" $F/build.time
$PY lettersfix43.py validate $F/masters | tee $F/validate.log

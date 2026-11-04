#!/bin/bash
# Experiment 65: every current run rebuilt from its SAVED answers with today's code (+ the letter fix, + the run's
# patches), into NEW folders <run>_fix61 beside the old ones (never overwritten). No calls. One build at a time, nice.
#   build65.sh            the four runs
#   build65.sh control    v2_55 with EXP65_OFF=1 (today's code without experiment 65) -> out/v2_55_fix61_control,
#                         the control that proves this experiment changes no printed text
set -e
cd /home/appuser/inkscript/experiments/43_rehearsal
PY="nice -n 10 ../../.venv/bin/python"
L=/home/appuser/inkscript/experiments/65_fix_leaks/out/logs
mkdir -p $L
one() {   # one RUN SET PATCHES_DIR(or -) FOLDER
  local RUN=$1 SET=$2 PATCHES=$3 F=$4 tag=$(basename $4)
  echo "== $tag plain $(date +%H:%M)"
  mkdir -p $F
  /usr/bin/time -v $PY lettersfix43.py plain --run $RUN --set $SET --dst $F/plain > $L/$tag.plain.log 2> $L/$tag.plain.time
  tail -n 2 $L/$tag.plain.log; grep "Maximum resident" $L/$tag.plain.time
  mkdir -p $F/masters
  cp -a $F/plain/masters/. $F/masters/
  if [ "$PATCHES" != "-" ]; then
    mkdir -p $F/patches
    cp -n $PATCHES/*.json $F/patches/
    echo "== $tag patches $(date +%H:%M)"
    /usr/bin/time -v $PY patches43.py build --run $RUN --src $F/plain/rules --out $F > $L/$tag.patches.log 2> $L/$tag.patches.time
    grep -c applied $L/$tag.patches.log; grep "Maximum resident" $L/$tag.patches.time
  fi
  echo "== $tag validate $(date +%H:%M)"
  $PY lettersfix43.py validate $F/masters | tee $L/$tag.validate.log
}
if [ "$1" == "control" ]; then
  export EXP65_OFF=1
  one v2_55 a - out/v2_55_fix61_control
  exit 0
fi
W=${1:-all}     # all | j0130 | v2 | exam | first
[[ $W == all || $W == j0130 ]] && one j0130 d out/j0130_final/patches out/j0130_final_fix61
[[ $W == all || $W == v2 ]] && one v2_55 a - out/v2_55_fix61
[[ $W == all || $W == exam ]] && one v33_300b_fix3 c out/v33_300b_fix3/patches out/v33_300b_fix3_lettersfix_fix61
[[ $W == all || $W == first ]] && one v33_300 b out/v33_300_final/patches out/v33_300_final_lettersfix_fix61
echo "== done $(date +%H:%M)"

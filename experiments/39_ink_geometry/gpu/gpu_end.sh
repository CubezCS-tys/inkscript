#!/bin/bash
# Destroy the instance and log the end with its cost:  DPH=<$/h> gpu_end.sh "jobs done"
E=/home/yassine/inkscript/experiments/39_ink_geometry; V=~/.local/venvs/vast/bin/vastai; OUT=$E/${GOUT:-out/gpu}; LOG=$E/out/gpu/gpu_spend.jsonl
read ID HOST PORT < $OUT/gpu_instance.txt
START=$(grep "\"instance\": $ID" $LOG | grep '"start"' | tail -1 | python3 -c "import json,sys,datetime; print(datetime.datetime.fromisoformat(json.loads(sys.stdin.read())['time']).timestamp())")
$V destroy instance $ID -y
H=$(python3 -c "import time; print(round((time.time()-$START)/3600, 3))")
echo "{\"event\": \"end\", \"time\": \"$(date -Is)\", \"instance\": $ID, \"hours\": $H, \"dph\": ${DPH:-0}, \"cost\": $(python3 -c "print(round($H*${DPH:-0},3))"), \"jobs\": \"$1\"}" >> $LOG
tail -1 $LOG; $V show instances

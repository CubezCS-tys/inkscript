#!/bin/bash
# Status of the run and pull of results so far:  gpu_status.sh [pull]   (reads out/gpu_instance.txt: ID HOST PORT)
OUT=/home/yassine/inkscript/experiments/36_vlm_bakeoff/out; read ID HOST PORT < $OUT/gpu_instance.txt
SSH="ssh -i $HOME/.ssh/id_ed25519_vast -p $PORT -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 root@$HOST"
timeout 60 $SSH '
cd /work; echo "setup: $(ls setup 2>/dev/null | grep -E "\.(ok|fail)$|ALL" | tr "\n" " ")"
echo "state: $(ls state 2>/dev/null | tr "\n" " ")"; tail -4 logs/orch.log 2>/dev/null
for d in out/raw/* out/smoke/*; do [ -d $d ] && echo "$d: $(ls $d | grep -c "^[^.]*\.json$") ok, $(ls $d | grep -c "\..*\.json$") fail"; done
f=$(ls -t logs/client_*.log 2>/dev/null | head -1); [ -n "$f" ] && echo "$f:" && tail -2 $f | cut -c1-200
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; df -h /work | tail -1
' 2>&1 | grep -v -i "welcome to vast\|have fun\|authentication fails"
if [ "$1" = pull ]; then
  mkdir -p $OUT/remote_logs
  timeout 300 $SSH "cd /work && tar cz out logs setup/*.ok setup/*.fail state 2>/dev/null" 2>/dev/null | tar xz -C $OUT/remote_logs 2>/dev/null
  mkdir -p $OUT/raw $OUT/smoke; cp -r $OUT/remote_logs/out/raw/. $OUT/raw/ 2>/dev/null; cp -r $OUT/remote_logs/out/smoke/. $OUT/smoke/ 2>/dev/null
  echo "pulled: $(find $OUT/raw -name '*.json' | wc -l) files in out/raw"
fi

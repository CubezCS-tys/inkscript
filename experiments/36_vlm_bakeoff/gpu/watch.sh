#!/bin/bash
# Emit new orchestrator log lines and setup markers every 60 s (for a monitor); pull results every 10 min.
OUT=/home/yassine/inkscript/experiments/36_vlm_bakeoff/out; read ID HOST PORT < $OUT/gpu_instance.txt
SSH="ssh -i $HOME/.ssh/id_ed25519_vast -p $PORT -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 root@$HOST"
prev=""; n=0
while true; do
  cur=$(timeout 40 $SSH 'cd /work; ls setup | grep -E "\.(ok|fail)$|ALL" | sed "s/^/setup /"; cat logs/orch.log 2>/dev/null | cut -c1-220' 2>/dev/null | grep -v -i "welcome\|have fun")
  [ -n "$cur" ] && { comm -13 <(echo "$prev" | sort) <(echo "$cur" | sort); prev=$cur; }
  n=$((n+1)); [ $((n % 10)) = 0 ] && bash $(dirname $0)/gpu_status.sh pull > /dev/null 2>&1
  echo "$cur" | grep -q "ALL DONE" && { echo "ALL DONE seen"; exit 0; }
  sleep 60
done

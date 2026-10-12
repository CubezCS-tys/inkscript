#!/bin/bash
# Run a short command on the GPU host:  rsh.sh 'cmd'   (reads out/gpu_instance.txt)
read ID HOST PORT < /home/yassine/inkscript/experiments/36_vlm_bakeoff/out/gpu_instance.txt
for t in 1 2 3; do
  out=$(timeout 60 ssh -i ~/.ssh/id_ed25519_vast -p "$PORT" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "root@$HOST" "cd /work; $1" 2>&1) && break; sleep 5
done
echo "$out" | grep -v -i "welcome to vast\|have fun"

#!/bin/bash
# Status of the GPU job:  gpu_status.sh HOST PORT   (checkpoints so far, last log lines, GPU use)
timeout 40 ssh -i ~/.ssh/id_ed25519_vast -p "$2" -o StrictHostKeyChecking=accept-new "root@$1" '
cd /work
for r in ftA ppA; do [ -f $r.start ] || [ -d $r ] && echo "$r: $(ls $r 2>/dev/null | tr "\n" " ")"; done
for f in ftA.exit ppA.exit DONE; do [ -f $f ] && echo "$f=$(cat $f)"; done
tr "\r" "\n" < $(ls -t ftA.log ppA.log 2>/dev/null | head -1) | grep -a -v "^\s*$" | grep -a -i "error\|traceback\|stage\|accuracy" | tail -2 | cut -c1-160
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
' 2>&1 | grep -v -i "welcome to vast\|have fun\|authentication fails"

#!/bin/bash
# Wait for train.done / train.failed on the rented GPU (or a hard stop at MAXMIN minutes since renting), fetch
# /work/out (weights best/last, results.csv, plots, predictions; no epoch checkpoints) and the logs into $GOUT (default out/gpu/), then destroy the instance and log its cost (gpu_end.sh).
EXP=$(cd "$(dirname "$0")/.." && pwd); OUT=$EXP/${GOUT:-out/gpu}; G=$(cd "$(dirname "$0")" && pwd)
read ID HOST PORT < $OUT/gpu_instance.txt
[ -f $OUT/gpu_job.env ] && . $OUT/gpu_job.env                       # DPH and JOB as gpu_run.sh was given them
SSH="ssh -i $HOME/.ssh/id_ed25519_vast -p $PORT -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new root@$HOST"
T0=$(date +%s); MAXMIN=${MAXMIN:-150}
until $SSH "ls /work/train.done /work/train.failed 2>/dev/null | grep -q ." 2>/dev/null || [ $(( ($(date +%s) - T0) / 60 )) -ge $MAXMIN ]; do sleep 60; done
$SSH "cd /work && tar czf result.tgz --exclude='epoch*.pt' out train.log train.out 2>/dev/null; ls -la result.tgz; ls train.done train.failed 2>/dev/null"
scp -q -i ~/.ssh/id_ed25519_vast -P $PORT root@$HOST:/work/result.tgz $OUT/ && tar xzf $OUT/result.tgz -C $OUT && echo fetched
[ -f $OUT/out/predictions.json ] && cp $OUT/out/predictions.json $OUT/predictions.json
DPH=${DPH:-0.852} bash $G/gpu_end.sh "${JOB:-layout fine-tune}"

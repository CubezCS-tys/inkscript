#!/bin/bash
# Rent one GPU, test the link, start setup at once, upload the page pack and scripts, start the orchestrator.
#   DPH=<$/h> [GOUT=out/gpu2 DATA=yolo2 JOB="layout fine-tune round 2"] gpu_run.sh OFFER_ID   (adapted from experiments/36_vlm_bakeoff/gpu/gpu_run.sh: the dataset, then train.sh)
# Link test: 20 MB in 8 parallel scp streams right after renting; under MINRATE (0.5 MB/s) the instance is destroyed
# (-y) and the script exits 2. Every start and end goes to out/gpu_spend.jsonl. Prints "INSTANCE <id> <host> <port>".
# GOUT: where this run's instance file and results go (default out/gpu, round 1); DATA: the dataset folder, uploaded as
# out/train/$DATA.tar; the spend log is always out/gpu/gpu_spend.jsonl.
E=/home/yassine/inkscript/experiments/39_ink_geometry; V=~/.local/venvs/vast/bin/vastai; OUT=$E/${GOUT:-out/gpu}; mkdir -p $OUT $E/out/gpu; LOG=$E/out/gpu/gpu_spend.jsonl
DATA=${DATA:-yolo}; JOB=${JOB:-layout fine-tune}
G=$(cd "$(dirname "$0")" && pwd); OID=$1; DPH=${DPH:-0}
ID=$($V create instance $OID --image pytorch/pytorch:2.9.0-cuda12.8-cudnn9-runtime --disk 60 --ssh --direct --raw | python3 -c "import json,sys; print(json.load(sys.stdin)['new_contract'])")
[ -z "$ID" ] && { echo "create failed"; exit 1; }
T0=$(date +%s); echo $ID > $OUT/gpu_instance.txt
echo "{\"event\": \"start\", \"time\": \"$(date -Is)\", \"instance\": $ID, \"offer\": $OID, \"dph\": $DPH, \"job\": \"$JOB\"}" >> $LOG
for i in $(seq 90); do $V show instance $ID --raw 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d and d.get('actual_status')=='running' else 1)" 2>/dev/null && break; sleep 10; done
URL=$($V ssh-url $ID); HP=${URL#ssh://root@}; HOST=${HP%:*}; PORT=${HP#*:}
echo "$ID $HOST $PORT" > $OUT/gpu_instance.txt
SSH="ssh -i $HOME/.ssh/id_ed25519_vast -p $PORT -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 root@$HOST"
for i in $(seq 12); do $SSH "mkdir -p /work" 2>/dev/null && break; sleep 10; done
pup() {   # upload one file in 8 parallel pieces, joined on the far side
  local f=$1 b=$(basename $1) d=/tmp/pup.$$; rm -rf $d; mkdir -p $d; split -n 8 -d "$f" $d/$b.part
  for p in $d/$b.part*; do (for t in 1 2 3; do scp -q -i ~/.ssh/id_ed25519_vast -P $PORT -o StrictHostKeyChecking=accept-new "$p" root@$HOST:/work/ 2>/dev/null && break; sleep 5; done) & done; wait
  $SSH "cd /work && cat $b.part* > $b && rm -f $b.part*" 2>/dev/null; rm -rf $d
}
head -c 20000000 /dev/urandom > /tmp/linktest.bin
S=$(date +%s.%N); pup /tmp/linktest.bin; E=$(date +%s.%N)
RATE=$(python3 -c "print(round(20/($E-$S),2))")
echo "link test: $RATE MB/s to $HOST"
if python3 -c "import sys; sys.exit(0 if $RATE >= ${MINRATE:-0.5} else 1)"; then :; else
  $V destroy instance $ID -y > /dev/null
  H=$(python3 -c "print(round(($(date +%s)-$T0)/3600, 3))")
  echo "{\"event\": \"end\", \"time\": \"$(date -Is)\", \"instance\": $ID, \"hours\": $H, \"dph\": $DPH, \"cost\": $(python3 -c "print(round($H*$DPH,3))"), \"jobs\": \"none: link test $RATE MB/s\"}" >> $LOG
  echo "DESTROYED $ID (slow link)"; exit 2
fi
tar czf /tmp/gpu39.tgz -C "$G/.." gpu
pup /tmp/gpu39.tgz
$SSH "rm -f /work/linktest.bin; cd /work && tar xzf gpu39.tgz && chmod +x gpu/*.sh && (setsid nohup gpu/setup.sh > logs_setup.out 2>&1 < /dev/null &)" 2>/dev/null

$SSH "cd /work && (setsid nohup env EPOCHS=${EPOCHS:-80} DATA=$DATA gpu/train.sh > train.out 2>&1 < /dev/null &)" 2>/dev/null; S=$(date +%s); pup $E/out/train/$DATA.tar; echo "$DATA.tar up in $(( $(date +%s)-S )) s"
$SSH "cd /work && ls -l $DATA.tar && touch yolo.uploaded" 2>/dev/null
echo "INSTANCE $ID $HOST $PORT"

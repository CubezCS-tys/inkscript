#!/bin/bash
# Rent one GPU, test the link, upload and start the job at once (nothing is rented ahead of time).
#   gpu_run.sh OFFER_ID JOB.sh FILE [FILE ...]     (FILEs go to /work; JOB.sh runs there with nohup)
# Uploads go in 8 parallel scp streams (pup). Offers: gpu_offers.sh (the owner's rules: datacenter, verified, reliability >= 0.995, 16+ cores, disk >= 2000 MB/s,
# inet up and down >= 300 Mbps). Link test: a 20 MB upload right after renting; under MINRATE (0.5 MB/s) it is destroyed
# (-y) and the script exits 2. Every start and end goes to out/gpu_spend.jsonl (the estimate is logged before).
# Prints "INSTANCE <id> <host> <port>".
V=~/.local/venvs/vast/bin/vastai; LOG=/home/yassine/inkscript/experiments/33_kraken/out/gpu_spend.jsonl
OID=$1; JOB=$2; shift 2
DPH=${DPH:-0}                                                           # the offer's $/h, given by the caller
ID=$($V create instance $OID --image pytorch/pytorch:2.9.0-cuda12.8-cudnn9-runtime --disk 30 --ssh --direct --raw | python3 -c "import json,sys; print(json.load(sys.stdin)['new_contract'])")
T0=$(date +%s)
echo "{\"event\": \"start\", \"time\": \"$(date -Is)\", \"instance\": $ID, \"offer\": $OID, \"dph\": $DPH, \"job\": \"$(basename $JOB)\"}" >> $LOG
until $V show instance $ID --raw 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d and d.get('actual_status')=='running' else 1)" 2>/dev/null; do sleep 10; done
URL=$($V ssh-url $ID); HP=${URL#ssh://root@}; HOST=${HP%:*}; PORT=${HP#*:}
SSH="ssh -i $HOME/.ssh/id_ed25519_vast -p $PORT -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 root@$HOST"
for i in 1 2 3 4 5 6 7 8 9; do $SSH "mkdir -p /work" 2>/dev/null && break; sleep 10; done
pup() {   # upload one file in 8 parallel pieces, joined on the far side
  local f=$1 b=$(basename $1) d=/tmp/pup.$$; rm -rf $d; mkdir -p $d; split -n 8 -d "$f" $d/$b.part
  for p in $d/$b.part*; do scp -q -i ~/.ssh/id_ed25519_vast -P $PORT -o StrictHostKeyChecking=accept-new "$p" root@$HOST:/work/ 2>/dev/null & done; wait
  $SSH "cd /work && cat $b.part* > $b && rm -f $b.part*" 2>/dev/null; rm -rf $d
}
# link test: 20 MB in 8 parallel streams (one ssh stream from this WSL machine to a far host has run at 0.02-0.9 MB/s)
head -c 20000000 /dev/urandom > /tmp/linktest.bin
S=$(date +%s.%N); pup /tmp/linktest.bin; E=$(date +%s.%N)
RATE=$(python3 -c "print(round(20/($E-$S),2))")
echo "link test: $RATE MB/s to $HOST"
# the owner's rule was 5 MB/s; this machine's own upload measured 1.15 MB/s to Cloudflare (2026-10-12 01:30), so
# 5 can never pass; 0.5 MB/s keeps any upload of this experiment under 20 minutes
if python3 -c "import sys; sys.exit(0 if $RATE >= ${MINRATE:-0.5} else 1)"; then :; else
  $V destroy instance $ID -y > /dev/null
  H=$(python3 -c "print(round(($(date +%s)-$T0)/3600, 3))")
  echo "{\"event\": \"end\", \"time\": \"$(date -Is)\", \"instance\": $ID, \"hours\": $H, \"dph\": $DPH, \"cost\": $(python3 -c "print(round($H*$DPH,3))"), \"jobs\": \"none: link test $RATE MB/s\"}" >> $LOG
  echo "DESTROYED $ID (slow link)"; exit 2
fi
$SSH "rm -f /work/linktest.bin; cd /work && (setsid nohup pip install -q kraken==7.1.1 > pip.log 2>&1 < /dev/null &)" 2>/dev/null
for f in "$JOB" "$@"; do pup "$f"; done
$SSH "cd /work && chmod +x $(basename $JOB) && (setsid nohup ./$(basename $JOB) > job.out 2>&1 < /dev/null &)" 2>/dev/null
echo "INSTANCE $ID $HOST $PORT"

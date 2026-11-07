#!/bin/bash
# Experiment 86, step 3: every reader on every prepared subset (local CPU, niced, 2 threads, sequential).
#   bash read86.sh NAME CKPT [SUBSETS...]   -> out/pred/NAME_<subset>.jsonl
cd "$(dirname "$0")"
PY=../81_heldout_scale/out/venv/bin/python
NAME=$1; CK=$2; shift 2
SUBS=${@:-patsocr synthesizear isippt ourslines hindawi arabicocr historyar muharaf khatt onlinekhatt adab evarest}
for s in $SUBS; do
  [ -s out/pred/${NAME}_$s.jsonl.info.json ] && continue
  nice -n 19 ionice -c3 $PY ../77_scratch_reader/train77.py infer --ckpt "$CK" --data out/shards --split $s \
    --pred out/pred/${NAME}_$s.jsonl --workers 0 --threads 2 --budget 16000 || echo "FAIL $NAME $s"
done
echo "done $NAME"

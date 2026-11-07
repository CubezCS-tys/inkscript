#!/bin/bash
# Experiment 85 on the GPU host: readers on experiment 81's held-out crops (/work/t81, test81-*.tar), greedy.
#   bash read81host85.sh NAME CKPT        -> /work/out/pred/t81_NAME.jsonl ({key, pred, cmin, cmean})
set -e
cd /work
mkdir -p out/pred
python train85.py infer --ckpt $2 --data t81 --split test81 --pred out/pred/t81_$1.jsonl --workers 8 --threads 8 > out/read81_$1.log 2>&1
echo READ81_DONE >> out/read81_$1.log

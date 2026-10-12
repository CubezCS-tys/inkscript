#!/bin/bash
# The line finder's fine-tune on this machine's CPU, because tonight no upload to a rented GPU ran faster than
# 0.15 MB/s (gpu_spend.jsonl). 400 training pages and 40 dev pages drawn from seg_data.py's (seed 33), from kraken's
# default blla model, 3 epochs, dev after each.
#   script -qfc experiments/33_kraken/segtrain_cpu.sh out/train/segcpu.log
cd /home/yassine/inkscript/experiments/33_kraken/out
mkdir -p train/segcpu
exec /usr/bin/time -v nice env/bin/ketos --workers 2 --threads 6 -d cpu segtrain -f page \
  -i env/lib/python3.12/site-packages/kraken/blla.mlmodel --resize both --augment -N 3 -q fixed -F 1 \
  -o train/segcpu -t lists/seg_train_cpu.txt -e lists/seg_dev_cpu.txt

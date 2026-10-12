#!/bin/bash
# Round C on this machine's CPU (uploads to rented GPUs ran at 0.15 MB/s tonight, too slow for the 280 MB pack):
# the VGSL model from round A's best (ftA, never saw a journal held out by experiment 34), on pack_C.py's lines
# (pre-1970 and small-print silver lines, synthetic vowelled lines, born-digital replay), one epoch, dev twice.
#   script -qfc experiments/33_kraken/trainC_cpu.sh out/train/ftC.log
cd /home/yassine/inkscript/experiments/33_kraken/out
mkdir -p train/ftC
exec /usr/bin/time -v nice env/bin/ketos --workers 2 --threads 6 -d cpu train -f binary -i models/ftA.safetensors \
  --resize union -u NFD --augment -B 16 -r 0.0002 --warmup 100 -N 1 -q fixed -F 0.5 \
  -o train/ftC -e train/C_dev.lst -t train/C_train.lst

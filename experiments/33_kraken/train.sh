#!/bin/bash
# Fine-tune the OpenITI Arabic print model on the born-digital training lines (CPU).
#   script -qfc "bash experiments/33_kraken/train.sh ft1" out/train/ft1.log      (script gives the progress bar a terminal)
# out/train/train.arrow and dev.arrow come from:
#   ketos compile -f path --force-type baseline -o out/train/train.arrow -F out/lists/train.txt   (and dev)
# Measured on this machine: 0.17 batches of 16 a second (about 2.7 lines a second) whatever the thread count above 6,
# peak memory below 5 GB.
TAG=${1:-ft1}
cd /home/yassine/inkscript/experiments/33_kraken/out
mkdir -p train/$TAG
exec /usr/bin/time -v nice env/bin/ketos --workers 2 --threads 6 -d cpu train -f binary \
  -i models/arabic_best.mlmodel --resize union -u NFD \
  -B 16 -r 0.0003 --warmup 100 -N 2 -q fixed -F 0.25 \
  -o train/$TAG -e train/dev.lst -t train/train.lst

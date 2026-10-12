#!/bin/bash
# Round C on the GPU: old prints, footnotes, vowelled lines (pack_C.py). Both engines continue from round A's best
# (models that never saw a journal held out by experiment 34), side by side, 50 minutes each at most.
#   ftC  VGSL from ftA (dev-best)          ppC  PP-OCRv6 small from ppA (dev-best)
cd /work
while pgrep -f "pip install" > /dev/null; do sleep 5; done
python -c "import kraken" 2>/dev/null || pip install -q kraken==7.1.1 >> pip.log 2>&1 || { echo PIPFAIL > DONE5; exit 1; }
tar xf C.tar
ketos --workers 14 --threads 1 compile -f path --force-type baseline -o trainC.arrow -F C/train.txt > compile.log 2>&1
ketos --workers 14 --threads 1 compile -f path --force-type baseline -o devC.arrow -F C/dev.txt >> compile.log 2>&1
echo /work/trainC.arrow > trainC.lst; echo /work/devC.arrow > devC.lst
date +%s > C.start
timeout 50m ketos --workers 6 --threads 3 -d cuda:0 train -f binary -i ftA.safetensors --resize union -u NFD \
  --augment -B 16 -r 0.0002 --warmup 200 -N 30 -q early --min-epochs 4 --lag 4 -F 1 \
  -o ftC -e devC.lst -t trainC.lst > ftC.log 2>&1 &
TORCHDYNAMO_DISABLE=1 timeout 50m ketos --workers 6 --threads 3 -d cuda:0 train -f binary --arch ppocrv6 -i ppA.safetensors \
  --resize union -u NFD --augment -B 8 -r 0.0002 --warmup 200 -N 6 -q fixed -F 1 \
  -o ppC -e devC.lst -t trainC.lst > ppC.log 2>&1 &
wait
date +%s > C.end
for d in ftC ppC; do b=$(ls $d/checkpoint_*.ckpt 2>/dev/null | sort -t- -k2 -g | tail -1); [ -n "$b" ] && ketos convert -o ${d}_best.safetensors "$b" > /dev/null 2>&1 && echo "$b" > ${d}_best.txt; done
echo ok > DONE5

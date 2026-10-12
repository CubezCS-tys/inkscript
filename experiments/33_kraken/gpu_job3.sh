#!/bin/bash
# Third GPU job, same instance (the guard ends it at 210 minutes): the scan-domain round. Both fine-tunes continue
# from round A's best, now on the born-digital lines PLUS real scan lines read by Azure (silver_train.arrow), with dev =
# born-digital dev + silver dev. Run side by side on the one GPU, each capped at 45 minutes.
#   ftB  VGSL, from ftA's best        ppB  PP-OCRv6 small, from ppA's best
cd /work
printf "/work/train.arrow\n/work/silver_train.arrow\n" > trainB.lst; printf "/work/dev.arrow\n/work/silver_dev.arrow\n" > devB.lst
PPBEST=$(ls ppA/checkpoint_*.ckpt | sort -t- -k2 -g | tail -1)
ketos convert -o ppA_best.safetensors "$PPBEST" > convert.log 2>&1
echo "$PPBEST" > ppA_best.txt
date +%s > B.start
timeout 45m ketos --workers 6 --threads 3 -d cuda:0 train -f binary -i ftA/best_0.9806.safetensors --resize union -u NFD \
  --augment -B 16 -r 0.0002 --warmup 200 -N 30 -q early --min-epochs 4 --lag 3 -F 1 \
  -o ftB -e devB.lst -t trainB.lst > ftB.log 2>&1 &
TORCHDYNAMO_DISABLE=1 timeout 45m ketos --workers 6 --threads 3 -d cuda:0 train -f binary --arch ppocrv6 -i ppA_best.safetensors \
  --resize union -u NFD --augment -B 8 -r 0.0002 --warmup 200 -N 6 -q fixed -F 1 \
  -o ppB -e devB.lst -t trainB.lst > ppB.log 2>&1 &
wait
date +%s > B.end
echo ok > DONE3

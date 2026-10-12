#!/bin/bash
# Runs ON the rented GPU (Vast.ai, one RTX 5090), in /work, after train.arrow, dev.arrow, arabic_best.mlmodel and
# ppocrv6_small.safetensors were copied there. Two fine-tunes one after the other, each capped in wall time:
#   ftA  the OpenITI Arabic print model (VGSL, as the CPU run), with kraken's augmentation, early stopping on dev
#   ppA  the PP-OCRv6 small multilingual base model (kraken 7.1's new architecture), same data and stopping
# Progress: one checkpoint per epoch in ftA/ and ppA/ (file name = dev accuracy). Writes DONE at the end.
cd /work
pip install -q kraken==7.1.1 > pip.log 2>&1 || { echo PIPFAIL > DONE; exit 1; }
python -c "import torch; print(torch.__version__, torch.cuda.get_device_name(0))" > gpu.txt 2>&1
echo /work/train.arrow > train.lst; echo /work/dev.arrow > dev.lst
date +%s > ftA.start
timeout 65m ketos --workers 12 --threads 4 -d cuda:0 train -f binary -i arabic_best.mlmodel --resize union -u NFD \
  --augment -B 32 -r 0.0003 --warmup 200 -N 40 -q early --min-epochs 6 --lag 4 -F 1 \
  -o ftA -e dev.lst -t train.lst > ftA.log 2>&1
echo $? > ftA.exit; date +%s > ftA.end
timeout 65m ketos --workers 12 --threads 4 -d cuda:0 train -f binary --arch ppocrv6 -i ppocrv6_small.safetensors \
  --resize union -u NFD --augment -B 32 -r 0.0003 --warmup 200 -N 40 -q early --min-epochs 6 --lag 4 -F 1 \
  -o ppA -e dev.lst -t train.lst > ppA.log 2>&1
echo $? > ppA.exit; date +%s > ppA.end
echo ok > DONE

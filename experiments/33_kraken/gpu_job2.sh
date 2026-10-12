#!/bin/bash
# Second GPU job, same instance: the PP-OCRv6 fine-tune. Its cosine schedule needs a finite length, so a fixed number
# of epochs (gpu_job.sh's early-stopping run died at once: "cannot convert float infinity to integer"); torch.compile
# is off because the runtime image has no C compiler; batch 8 because 32 ran out of the 5090's 32 GB.
cd /work
date +%s > ppA.start
TORCHDYNAMO_DISABLE=1 timeout 60m ketos --workers 12 --threads 4 -d cuda:0 train -f binary --arch ppocrv6 -i ppocrv6_small.safetensors \
  --resize union -u NFD --augment -B 8 -r 0.0003 --warmup 200 -N 16 -q fixed -F 1 \
  -o ppA -e dev.lst -t train.lst > ppA.log 2>&1
echo $? > ppA.exit; date +%s > ppA.end
echo ok > DONE2

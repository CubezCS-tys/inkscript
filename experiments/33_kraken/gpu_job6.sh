#!/bin/bash
# VLM smoke test on the GPU: PaddleOCR-VL-0.9B on 60 scan lines and 10 pages (vlm_prep.py). Writes DONE6.
cd /work
while pgrep -f "pip install" > /dev/null; do sleep 5; done
tar xf vlm.tar
pip install -q "transformers==5.19.0" einops sentencepiece accelerate > pip6.log 2>&1     # 4.55 (the card's config) fails: the model code changed in 2026-03
timeout 30m python vlm_read.py > vlm.log 2>&1
echo $? > vlm.exit
echo ok > DONE6

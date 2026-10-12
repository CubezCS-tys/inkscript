#!/bin/bash
# One rental for two jobs, so the GPU is never idle while this machine's slow upload runs: the line finder (gpu_job4.sh)
# starts at once; round C's material (C.tar, ftA/ppA weights, gpu_job5.sh) uploads meanwhile and a file C.ready marks it
# complete; round C (gpu_job5.sh) starts as soon as both are true.
cd /work
bash gpu_job4.sh
until [ -f C.ready ]; do sleep 10; done
bash gpu_job5.sh

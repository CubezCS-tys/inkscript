#!/bin/bash
# Experiment 79r on the rented host: learned centre lines (experiment 82's U-Net) for the same real lines as p4r,
# a reader trained exactly like p4r on them (p4L), and the re-scoring. Stages back to back; each ends with a marker
# line "STAGE <name> DONE" in /work/out/r79/stages.log so the driver can fetch after every stage.
set -e
export OMP_NUM_THREADS=4 X82=/work/x82
mkdir -p /work/out/r79 /work/data7 /work/r/fuse_p3t
pip install -q pypdfium2==5.12.1 2>&1 | grep -v WARN | tail -1
cp /work/r/fuse_p3t_dev.jsonl /work/r/fuse_p3t/dev.jsonl && cp /work/r/fuse_p3t_test.jsonl /work/r/fuse_p3t/test.jsonl
S=/work/out/r79/stages.log
cd /work/c
python reallearn79.py --jobs /work/real/jobs_dev.jsonl --split dev --out /work/data7 --workers 26 && echo "STAGE dev DONE $(date -u +%T)" >> $S
python reallearn79.py --crops /work/r/testcrops.npz --split test --out /work/data7 --workers 26 && cp /work/data7/real.npz /work/out/r79/real_learned.npz && echo "STAGE test DONE $(date -u +%T)" >> $S
python score79.py --reuse /work/r/fuse_p3t --sig /work/r/p4r.pt --sigdata /work/data7 --out /work/out/r79/fuse_p4r_on_learned && echo "STAGE p4r_on_learned DONE $(date -u +%T)" >> $S
python reallearn79.py --jobs /work/real/jobs_train.jsonl --split train --out /work/data7 --workers 26 && echo "STAGE train_data DONE $(date -u +%T)" >> $S
python train79b.py --data /work/data7 --kind real --init /work/r/p3t.pt --charset /work/r/charset.json --epochs 10 --lr 5e-4 --budget 50000 --workers 8 --name r79/p4L && echo "STAGE p4L DONE $(date -u +%T)" >> $S
python score79.py --reuse /work/r/fuse_p3t --sig /work/out/r79/p4L/model.pt --sigdata /work/data7 --out /work/out/r79/fuse_p4L && echo "STAGE fuse_p4L DONE $(date -u +%T)" >> $S
echo "ALL DONE" >> $S

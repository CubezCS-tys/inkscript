#!/bin/bash
# Experiment 89: build the upload for the GPU host (local, light; run niced).  out/gpu/up/ then holds, flat:
#   up89.tgz  -> unpacks in /work to: fonts/ text/ r78/ (experiment 84's synthetic-line inputs, as bundled for 84),
#                init/best.pt (experiment 85's v6r), labels/labels_v6r.jsonl.gz (v6r's held-line labels),
#                test/ (experiment 77's test crops: the owner's 20 pages, lab docs), t81/ (experiment 81's 22,783
#                held-out crops at 48 px, READ only, never trained on)
#   forbidden89.json (forbid89.py: the guard's list), urls_*.jsonl (presign89host.py, mode 600; they expire)
# The title crops (titles89-*.tar, title89.py) go up separately, to /work/titles, when they are cut.
set -e
cd "$(dirname "$0")"
E=..
U=out/up89; B=out/gpu/up
mkdir -p $U/init $U/labels $U/test $U/t81 $B
cp $E/85_disputes/out/host/run_v6r/best.pt $U/init/best.pt
cp $E/85_disputes/out/gpu/up/labels/labels_v6r.jsonl.gz $U/labels/
cp $E/77_scratch_reader/out/test/* $U/test/
cp $E/81_heldout_scale/out/crops48/test81-*.tar $U/t81/
tar czf $B/up89.tgz -C $E/84_display_fonts/out/up84 fonts text r78 -C "$PWD/$U" init labels test t81
ls -la $B

#!/bin/bash
# Experiment 91: build the upload for the GPU host (local, light; run niced).  out/gpu/up/ then holds, flat:
#   up91.tgz  -> unpacks in /work to: fonts/ text/ r78/ (experiment 84's synthetic-line inputs), init/l28.pt (the final
#                reader v7-28M, experiment 89), labels/labels_v6r.jsonl.gz, test/ (experiment 77's test crops: the
#                owner's 20 pages, lab documents), t81/ (experiment 81's 22,783 held-out crops, READ only),
#                titles/titles89-0.tar (experiment 89's held-out title crops, READ only)
#   forbidden91.json (forbid91.py), urls_*.jsonl (presign91host.py, mode 600; they expire)
# The locked title lines (experiment 90) never go to the host: they are read on the local CPU.
set -e
cd "$(dirname "$0")"
E=..
U=out/up91; B=out/gpu/up
mkdir -p $U/init $U/labels $U/test $U/t81 $U/titles $B
cp $E/89_final_reader/out/weights/v7_28m/last.pt $U/init/l28.pt
cp $E/85_disputes/out/gpu/up/labels/labels_v6r.jsonl.gz $U/labels/
cp $E/77_scratch_reader/out/test/* $U/test/
cp $E/81_heldout_scale/out/crops48/test81-*.tar $U/t81/
cp $E/89_final_reader/out/titles/titles89-0.tar $U/titles/
tar czf $B/up91.tgz -C $E/84_display_fonts/out/up84 fonts text r78 -C "$PWD/$U" init labels test t81 titles
ls -la $B

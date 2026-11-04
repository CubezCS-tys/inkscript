#!/bin/bash
# Experiment 74: the Word files of every journal (prep: .docx copied / .doc converted; legacy PDFs from S3 read-only;
# the title / first-page check). No model calls. Usage: wordprep74.sh J [J ...]
cd /home/appuser/inkscript
L=experiments/74_gate2_full/out/logs
for J in "$@"; do
  echo "== $J prep $(date +%H:%M)"
  /usr/bin/time -v nice -n 10 .venv/bin/python experiments/74_gate2_full/word74.py $J prep > $L/word_prep_$J.log 2> $L/word_prep_$J.time
  tail -n 1 $L/word_prep_$J.log; grep "Maximum resident" $L/word_prep_$J.time
  echo "== $J legacy $(date +%H:%M)"
  nice -n 10 .venv/bin/python experiments/74_gate2_full/word74.py $J legacy > $L/word_legacy_$J.log 2>&1; tail -n 1 $L/word_legacy_$J.log
  echo "== $J check $(date +%H:%M)"
  nice -n 10 .venv/bin/python experiments/74_gate2_full/word74.py $J check > $L/word_check_$J.log 2>&1; head -n 1 $L/word_check_$J.log
done
echo "== done $(date +%H:%M)"

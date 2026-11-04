#!/bin/bash
# Memory guard for experiment 58 (the machine is shared with a live service): every 5 s, if less than
# 8 GB is available, kill every process of this experiment's venv and log it. Exits when nothing has run for 10 min.
cd "$(dirname "$(readlink -f "$0")")"; idle=0
while sleep 5; do
  pids=$(pgrep -f "58_indra_ocr/out/((venv|venv_surya)/bin/python|llamacpp/)")
  if [ -z "$pids" ]; then idle=$((idle+5)); [ $idle -ge 600 ] && exit 0; continue; fi; idle=0
  avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  if [ "$avail" -lt 8000 ]; then kill $pids; echo "$(date) killed $pids: only ${avail} MB available" >> out/guard.log; fi
done

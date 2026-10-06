#!/bin/bash
# Experiment 18 (copied from 16_feel/watchdog.sh): kills collect.py / run18.py processes when memory gets tight.
idle=0
while sleep 15; do
  pids=$(ps -eo pid,cmd | grep -E "[c]ollect.py|[r]un18.py" | awk '{print $1}')
  if [ -z "$pids" ]; then idle=$((idle + 15)); [ $idle -ge 600 ] && exit 0; continue; fi
  idle=0; avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  if [ "$avail" -lt 2500 ]; then
    for p in $pids; do kill $p; done
    echo "$(date) stopped collect.py or run18.py: only ${avail} MB of memory was available" >> "$(dirname "$(readlink -f "$0")")/out/watchdog.log"
  fi
done

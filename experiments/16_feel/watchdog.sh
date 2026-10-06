#!/bin/bash
# Experiment 16's runs (bench.py, possibly several agents at once) stop if memory gets tight: the machine must
# never be starved again (CLAUDE.md, "Memory"). Same rule as experiments/09_pen_path/watchdog.sh: under 2.5 GB
# available, every bench.py process is killed and the event logged. Exits after 10 idle minutes.
idle=0
while sleep 15; do
  pids=$(ps -eo pid,cmd | grep "[b]ench.py" | awk '{print $1}')
  if [ -z "$pids" ]; then idle=$((idle + 15)); [ $idle -ge 600 ] && exit 0; continue; fi
  idle=0; avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  if [ "$avail" -lt 2500 ]; then
    for p in $pids; do kill $p; done
    echo "$(date) stopped bench.py runs: only ${avail} MB of memory was available" >> "$(dirname "$(readlink -f "$0")")/out/watchdog.log"
  fi
done

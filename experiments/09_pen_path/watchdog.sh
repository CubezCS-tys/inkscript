#!/bin/bash
# Stops the set run if memory gets tight: the machine must never be starved again.
while sleep 20; do
  pids=$(ps -eo pid,cmd | grep "[b]in/inkscript native" | awk '{print $1}'); [ -z "$pids" ] && { sleep 60; pids=$(ps -eo pid,cmd | grep "[b]in/inkscript native" | awk '{print $1}'); [ -z "$pids" ] && exit 0; }
  avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  if [ "$avail" -lt 2500 ]; then
    for p in $(ps -eo pid,cmd | grep "[r]un_set.sh" | awk '{print $1}'); do kill $p; done; for p in $pids; do kill $p; done
    echo "$(date) stopped the run: only ${avail} MB of memory was available" >> "$(dirname "$(readlink -f "$0")")/out/watchdog.log"; exit 1
  fi
done

#!/bin/bash
# The experiment-9 watchdog's rule for this experiment's runs: stop them if under 2.5 GB of memory is free.
while sleep 20; do
  pids=$(pgrep -f "experiments/39_ink_geometry/[t]rain") ; [ -z "$pids" ] && exit 0
  avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  if [ "$avail" -lt 2500 ]; then kill $pids; echo "$(date) stopped: only ${avail} MB free" >> "$(dirname "$0")/out/watchdog.log"; exit 1; fi
done

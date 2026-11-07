#!/bin/bash
# Experiment 77's memory watchdog (experiments/09_pen_path/watchdog.sh's rule, for this experiment's own jobs):
# every 20 s, if MemAvailable < 2500 MB, stop the job whose PID is in $1 (a pid file) and its children, by exact PID.
PIDFILE="$1"; LOG="$(dirname "$(readlink -f "$0")")/out/watchdog77.log"
while sleep 20; do
  pid=$(cat "$PIDFILE" 2>/dev/null); [ -z "$pid" ] && continue
  kill -0 "$pid" 2>/dev/null || exit 0
  avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  if [ "$avail" -lt 2500 ]; then
    for c in $(pgrep -P "$pid"); do kill "$c"; done; kill "$pid"
    echo "$(date) stopped $pid: only ${avail} MB available" >> "$LOG"; exit 1
  fi
done

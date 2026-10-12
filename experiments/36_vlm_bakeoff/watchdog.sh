#!/bin/bash
# Experiment 36's memory guard (the pattern of 33's watchdog.sh; experiments/09_pen_path/watchdog.sh only watches
# `inkscript native`): every 10 s, sum the proportional resident memory of every process whose command line names
# 36_vlm_bakeoff; above 6 GB in all, or under 2 GB available on the machine, kill them and log it.
#   nohup experiments/36_vlm_bakeoff/watchdog.sh &      (runs until killed)
LOG=/home/yassine/inkscript/experiments/36_vlm_bakeoff/out/watchdog.log
while sleep 10; do
  pids=""
  for p in $(pgrep -f "36_vlm_bakeoff/.*\.py|kraken_check"); do
    [ "$p" = "$$" ] && continue
    case "$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null)" in *watchdog*) continue;; *36_vlm_bakeoff*|*kraken_check*) pids="$pids $p";; esac
  done
  [ -z "$pids" ] && continue
  rss=0; for p in $pids; do r=$(awk '/^Pss:/ {print $2}' /proc/$p/smaps_rollup 2>/dev/null); rss=$((rss + ${r:-0})); done
  rss=$((rss / 1024)); avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  if [ "$rss" -gt 6000 ] || [ "$avail" -lt 2000 ]; then
    kill $pids; echo "$(date) killed 36's processes: ${rss} MB in use by them, ${avail} MB available" >> $LOG
  fi
done

#!/bin/bash
# Experiment 52's memory guard (production box): stops any of this experiment's Python processes over 3 GB, and all of
# them if the machine's available memory falls under 10 GB. Matches command lines naming set d / j0130 / gate1 / exp 52.
LOG="$(dirname "$(readlink -f "$0")")/out/watchdog52.log"
PAT='python.*(--set d|j0130|gate1|52_journal_gate1)'
while sleep 15; do
  pids=$(pgrep -f "$PAT" | grep -v "^$$\$")
  [ -z "$pids" ] && continue
  avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  for p in $pids; do
    rss=$(awk '/VmRSS/ {print int($2/1024)}' /proc/$p/status 2>/dev/null); [ -z "$rss" ] && continue
    if [ "$rss" -gt 3072 ]; then kill $p; echo "$(date) killed $p ($(tr '\0' ' ' </proc/$p/cmdline 2>/dev/null | cut -c1-120)): ${rss} MB" >> "$LOG"; fi
  done
  if [ "$avail" -lt 10240 ]; then
    for p in $pids; do kill $p; done; echo "$(date) stopped all: only ${avail} MB available" >> "$LOG"
  fi
done

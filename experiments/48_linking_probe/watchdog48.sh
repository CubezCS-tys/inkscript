#!/bin/bash
# Experiment 48's memory guard (this box is production): stops any probe script over 3 GB,
# and every probe script if the machine's available memory falls under 10 GB.
LOG="$(dirname "$(readlink -f "$0")")/out/watchdog48.log"
while sleep 15; do
  pids=$(pgrep -f "experiments/48_linking_probe/.*\.py")
  [ -z "$pids" ] && continue
  avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  for p in $pids; do
    rss=$(awk '/VmRSS/ {print int($2/1024)}' /proc/$p/status 2>/dev/null); [ -z "$rss" ] && continue
    if [ "$rss" -gt 3072 ]; then kill $p; echo "$(date) killed $p ($(tr '\0' ' ' </proc/$p/cmdline 2>/dev/null | cut -c1-120)): ${rss} MB" >> "$LOG"; fi
  done
  if [ "$avail" -lt 10240 ]; then
    for p in $pids; do kill $p; done; echo "$(date) stopped all probe scripts: only ${avail} MB available" >> "$LOG"
  fi
done

#!/bin/bash
# Experiment 74's memory guard (production box; from watchdog70.sh): stops any of this experiment's Python processes
# over 5 GB (raised from 3 GB at 15:0x for flags43 on 0523's 346 articles), and all of them if the machine's available memory falls under 10 GB. Polls every 5 s (exp 70's 15 s
# missed a 3.31 GB peak). Matches command lines naming set g / the gate-2 runs / exp 74.
LOG="$(dirname "$(readlink -f "$0")")/out/watchdog74.log"
PAT='python.*(--set g|74_gate2_full|j(0011|0523|1001|0246|1182|0097|0840|0013)|w(0011|0523|1001|0246|1182|0097|0840|0013|0130)_|word74|wordmodel74|lib74)'
while sleep 5; do
  pids=$(pgrep -f "$PAT" | grep -v "^$$\$")
  [ -z "$pids" ] && continue
  avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  for p in $pids; do
    rss=$(awk '/VmRSS/ {print int($2/1024)}' /proc/$p/status 2>/dev/null); [ -z "$rss" ] && continue
    if [ "$rss" -gt 5120 ]; then kill $p; echo "$(date) killed $p ($(tr '\0' ' ' </proc/$p/cmdline 2>/dev/null | cut -c1-120)): ${rss} MB" >> "$LOG"; fi
  done
  if [ "$avail" -lt 10240 ]; then
    for p in $pids; do kill $p; done; echo "$(date) stopped all: only ${avail} MB available" >> "$LOG"
  fi
done

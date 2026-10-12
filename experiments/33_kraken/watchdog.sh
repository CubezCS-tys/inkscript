#!/bin/bash
# Experiment 33's memory guard (experiment 34 shares the 15 GB machine): every 10 s, sum the resident memory of every
# process running from 33's venv (proportional set size, so shared libraries count once); above 8 GB in all, or under 2 GB available on the machine, kill them and log it.
# Runs until killed.   nohup experiments/33_kraken/watchdog.sh &
LOG=/home/yassine/inkscript/experiments/33_kraken/out/watchdog.log
while sleep 10; do
  pids=""                                       # 33's venv, whether started by absolute path or from out/
  for p in $(pgrep -f "env/bin/(python|ketos)"); do
    case "$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null) $(readlink /proc/$p/cwd 2>/dev/null)" in *33_kraken*) pids="$pids $p";; esac
  done
  [ -z "$pids" ] && continue
  rss=0; for p in $pids; do r=$(awk '/^Pss:/ {print $2}' /proc/$p/smaps_rollup 2>/dev/null); rss=$((rss + ${r:-0})); done
  rss=$((rss / 1024)); avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  if [ "$rss" -gt 8000 ] || [ "$avail" -lt 2000 ]; then
    kill $pids; echo "$(date) killed 33's processes: ${rss} MB in use by them, ${avail} MB available" >> $LOG
  fi
done

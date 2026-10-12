#!/bin/bash
# Memory now used by experiment 33's processes (proportional set size, MB) and what the machine has available.
t=0
for p in $(pgrep -f "env/bin/(python|ketos)"); do
  case "$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null) $(readlink /proc/$p/cwd 2>/dev/null)" in *33_kraken*) ;; *) continue;; esac
  r=$(awk '/^Pss:/ {print $2}' /proc/$p/smaps_rollup 2>/dev/null)
  t=$((t + ${r:-0}))
done
echo "33 uses $((t / 1024)) MB; available $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo) MB"

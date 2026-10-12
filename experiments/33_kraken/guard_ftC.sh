#!/bin/bash
# While the line finder and round C train side by side on the CPU: if experiment 33 passes 7.5 GB, stop round C first
# (the line finder is further along), before watchdog.sh's 8 GB stops both.
while sleep 5; do
  m=$(/home/yassine/inkscript/.claude/worktrees/agent-a1fea0acd31fcb1dc/experiments/33_kraken/mem.sh | awk '{print $3}')
  if [ "${m:-0}" -gt 7500 ]; then
    for p in $(pgrep -f "train/ftC"); do kill $p; done
    echo "$(date) stopped round C at ${m} MB" >> /home/yassine/inkscript/experiments/33_kraken/out/watchdog.log; exit 0
  fi
  pgrep -f "train/ftC" > /dev/null || exit 0
done

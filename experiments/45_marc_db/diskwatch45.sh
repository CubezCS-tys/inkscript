#!/bin/bash
# Pause (SIGSTOP) the build when C: (which holds WSL's disk) falls below MIN GiB free, as df -h counts; log every 30 s.
MIN=${MIN:-38}; LOG=${LOG:-$HOME/data/marc/diskwatch.log}
while pgrep -f '[b]uild45\.py' >/dev/null; do
  free=$(df -B1G --output=avail /mnt/c | tail -1 | tr -d ' ')
  echo "$(date +%T) free ${free} GiB $(ls -l $HOME/data/marc/marc.part 2>/dev/null | awk '{print $5}')" >> "$LOG"
  if [ "$free" -lt "$MIN" ]; then pkill -STOP -f '[b]uild45\.py'; echo "$(date +%T) PAUSED build (free ${free} < ${MIN} GiB)" >> "$LOG"; exit 0; fi
  sleep 30
done

#!/bin/bash
# Safety net for rented Vast.ai GPUs, independent of any Claude session: every 5 minutes, destroy any
# instance older than MAX_MIN minutes (default 120) and log it. Jobs take minutes, so this only ever
# catches a machine an interrupted agent forgot.  Start: setsid nohup ops/vast_guard.sh >/dev/null 2>&1 &
V=~/.local/venvs/vast/bin/vastai; MAX_MIN=${MAX_MIN:-120}; LOG=~/.config/vastai/guard.log
while true; do
  $V show instances --raw 2>/dev/null | python3 -c "
import json,sys,time
try: d=json.load(sys.stdin)
except Exception: sys.exit()
for i in d:
    age=(time.time()-(i.get('start_date') or time.time()))/60
    print(i['id'], int(age))" | while read id age; do
      if [ "$age" -ge "$MAX_MIN" ]; then
        echo "$(date -Is) destroying $id (running ${age} min)" >> $LOG
        $V destroy instance "$id" >> $LOG 2>&1
      fi
  done
  sleep 300
done

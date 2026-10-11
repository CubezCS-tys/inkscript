#!/bin/bash
# Safety net for rented Vast.ai GPUs, independent of any Claude session. Every 5 minutes it destroys, and logs:
#  - any instance older than MAX_MIN minutes (default 360);
#  - any instance whose GPU has been under 5% busy for IDLE_MIN minutes in a row (default 30): a job that ended
#    or hung while nobody turned the machine off.
# Start: setsid nohup ops/vast_guard.sh >/dev/null 2>&1 &     Log: ~/.config/vastai/guard.log
V=~/.local/venvs/vast/bin/vastai; MAX_MIN=${MAX_MIN:-360}; IDLE_MIN=${IDLE_MIN:-30}
LOG=~/.config/vastai/guard.log; IDLE=~/.config/vastai/guard_idle.json
while true; do
  $V show instances --raw 2>/dev/null | MAX_MIN=$MAX_MIN IDLE_MIN=$IDLE_MIN IDLE=$IDLE python3 -c "
import json, os, sys, time
try: d = json.load(sys.stdin)
except Exception: sys.exit()
path = os.environ['IDLE']
try: idle = json.load(open(path))
except Exception: idle = {}
now = time.time(); keep = {}
for i in d:
    iid = str(i['id']); age = (now - (i.get('start_date') or now)) / 60
    util = i.get('gpu_util')
    if i.get('actual_status') == 'running' and util is not None and util < 5:
        keep[iid] = idle.get(iid, now)
    if age >= int(os.environ['MAX_MIN']):
        print(iid, f'running {age:.0f} min')
    elif iid in keep and (now - keep[iid]) / 60 >= int(os.environ['IDLE_MIN']):
        print(iid, f'GPU idle {(now - keep[iid]) / 60:.0f} min')
json.dump(keep, open(path, 'w'))" | while read id why; do
      echo "$(date -Is) destroying $id ($why)" >> $LOG
      $V destroy instance "$id" -y >> $LOG 2>&1
  done
  sleep 300
done

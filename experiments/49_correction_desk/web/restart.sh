#!/usr/bin/env bash
# Restart the Desk's web app on 127.0.0.1:8004 (after `npx next build`). Kills only the process listening on
# 127.0.0.1:8004 (never by name: AI-Search's own next-servers run on this box too).
set -euo pipefail
cd "$(dirname "$0")"
pid=$(ss -ltnpH 'sport = :8004' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2 || true)
if [ -n "${pid:-}" ]; then kill "$pid"; for _ in $(seq 20); do ss -ltnH 'sport = :8004' | grep -q . || break; sleep 0.5; done; fi
NEXT_TELEMETRY_DISABLED=1 setsid nohup npx next start -p 8004 -H 127.0.0.1 >> /home/appuser/data/desk/web.log 2>&1 < /dev/null &
for _ in $(seq 30); do curl -s -o /dev/null http://127.0.0.1:8004/signin && break; sleep 0.5; done
ss -ltnpH 'sport = :8004'

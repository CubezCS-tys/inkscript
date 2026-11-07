#!/usr/bin/env bash
# Telegram the owner when Vast credit runs low (2026-11-04). Checks every 10 min; warns once below $4 (top-up at $5 failed), once below $2.
V=/home/appuser/.local/venvs/vast/bin/vastai; warned8=0; warned3=0
while true; do
  c=$($V show user --raw 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('credit',''))" 2>/dev/null)
  n=$($V show instances --raw 2>/dev/null | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d), round(sum(i['dph_total'] for i in d),2))" 2>/dev/null)
  if [ -n "$c" ]; then
    if python3 -c "import sys;sys.exit(0 if float('$c')<2 else 1)" && [ $warned3 = 0 ]; then
      /home/appuser/bin/tg "URGENT, Vast credit is nearly out: \$$(printf %.2f $c) left. Machines running and \$/hour: $n. Experiments will pause soon. Please top up at cloud.vast.ai (Billing)."; warned3=1; warned8=1
    elif python3 -c "import sys;sys.exit(0 if float('$c')<4 else 1)" && [ $warned8 = 0 ]; then
      /home/appuser/bin/tg "Vast credit is low and the auto top-up (at \$5) has not fired: \$$(printf %.2f $c) left. Machines running and \$/hour: $n. Please top up about \$30-50 at cloud.vast.ai (Billing) to avoid pauses."; warned8=1
    fi
    python3 -c "import sys;sys.exit(0 if float('$c')>=8 else 1)" && { warned8=0; warned3=0; }
  fi
  sleep 600
done

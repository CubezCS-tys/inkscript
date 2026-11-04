#!/bin/bash
# Experiment 70: load gate 2's pilot (journal 0165) into a platform DB (default: the work copy), then link47 with its
# own cache in out/linkwork (started from a copy of the live cache; the live cache is untouched). Usage: load70.sh [DB]
set -e
cd /home/appuser/inkscript
DB=${1:-/home/appuser/data/platform_v2/exp70_work.db}
P=experiments/47_platform_v2
O=experiments/70_gate2_pilot/out
L=$O/logs
PY="nice -n 10 .venv/bin/python"
mkdir -p $L $O/linkwork
[ -e $O/linkwork/link_cache47.json ] || cp -a /home/appuser/data/platform_v2/link_cache47.json $O/linkwork/link_cache47.json
echo "== load j0165_final $(date +%H:%M)"
/usr/bin/time -v $PY $P/load47.py --run j0165_final --kind final --db $DB --note "experiment 70: gate 2 pilot, journal 0165, the scan route (prompt v3.6, judge, letter fix, D30 guard)" > $L/load_j0165_final.log 2> $L/load_j0165_final.time
tail -n 1 $L/load_j0165_final.log | cut -c1-300; grep "Maximum resident" $L/load_j0165_final.time
echo "== load w0165_final $(date +%H:%M)"
/usr/bin/time -v $PY $P/load47.py --run w0165_final --kind final --word $O/word --db $DB --note "experiment 70: gate 2 pilot, journal 0165, the Word route (code + gemini-3.8-flash text-only step)" > $L/load_w0165_final.log 2> $L/load_w0165_final.time
tail -n 1 $L/load_w0165_final.log | cut -c1-300; grep "Maximum resident" $L/load_w0165_final.time
echo "== link47 $(date +%H:%M)"
/usr/bin/time -v $PY $P/link47.py --db $DB --work $O/linkwork > $L/link47.log 2> $L/link47.time
tail -n 5 $L/link47.log; grep "Maximum resident" $L/link47.time
echo "== done $(date +%H:%M)"

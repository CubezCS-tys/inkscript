#!/bin/bash
# Experiment 74 (from load70.sh): load journal J into a WORK COPY of the platform DB (backup-API copy of the live one),
# scan route jJ_final (when read) + Word route wJ_final, then link47 with its own cache (out/J/linkwork, started from a
# copy of the live cache; the live cache is untouched), and the id-stability check against the live DB.
# Usage: load74.sh J        (the live DB is only read; the work copy is ~/data/platform_v2/exp74_work.db)
set -e
J=$1
cd /home/appuser/inkscript
D=/home/appuser/data/platform_v2
DB=$D/exp74_work.db
P=experiments/47_platform_v2
O=experiments/74_gate2_full/out/$J
L=$O/logs
PY="nice -n 10 .venv/bin/python"
mkdir -p $L $O/linkwork
echo "== ids before + work copy $J $(date +%H:%M)"
$PY experiments/68_go_live/ids68.py snap $D/platform_v2.db $O/ids_before.json > $L/ids_snap.log
rm -f $DB $DB-wal $DB-shm
.venv/bin/python - <<PYEOF
import sqlite3
s = sqlite3.connect("file:$D/platform_v2.db?mode=ro", uri=True); d = sqlite3.connect("$DB"); s.backup(d); d.close()
assert sqlite3.connect("file:$DB?mode=ro", uri=True).execute("pragma quick_check").fetchone()[0] == "ok"
print("work copy ok")
PYEOF
cp -a $D/link_cache47.json $O/linkwork/link_cache47.json
if [ "$J" != "0130" ] && [ -d experiments/43_rehearsal/out/j${J}_final/masters ] && ls experiments/43_rehearsal/out/j${J}_final/masters/*.jats.xml >/dev/null 2>&1; then
  echo "== load j${J}_final $(date +%H:%M)"
  /usr/bin/time -v $PY $P/load47.py --run j${J}_final --kind final --db $DB --note "experiment 74: gate 2, journal $J, the scan route (prompt v3.6, judge, letter fix, D30 guard, catalogue page range)" > $L/load_j${J}_final.log 2> $L/load_j${J}_final.time
  tail -n 1 $L/load_j${J}_final.log | cut -c1-300; grep "Maximum resident" $L/load_j${J}_final.time
fi
if ls experiments/43_rehearsal/out/w${J}_final/masters/*.jats.xml >/dev/null 2>&1; then
  echo "== load w${J}_final $(date +%H:%M)"
  /usr/bin/time -v $PY $P/load47.py --run w${J}_final --kind final --word $O/word --db $DB --note "experiment 74: gate 2, journal $J, the Word route (code + gemini-3.8-flash text-only step)" > $L/load_w${J}_final.log 2> $L/load_w${J}_final.time
  tail -n 1 $L/load_w${J}_final.log | cut -c1-300; grep "Maximum resident" $L/load_w${J}_final.time
fi
echo "== link47 $(date +%H:%M)"
/usr/bin/time -v $PY $P/link47.py --db $DB --work $O/linkwork > $L/link47.log 2> $L/link47.time
tail -n 5 $L/link47.log; grep "Maximum resident" $L/link47.time
echo "== ids compare $(date +%H:%M)"
nice -n 10 experiments/49_correction_desk/.venv/bin/python experiments/68_go_live/ids68.py compare $O/ids_before.json $DB > $O/ids_compare.txt 2>&1; tail -n 12 $O/ids_compare.txt
echo "== done $(date +%H:%M)"

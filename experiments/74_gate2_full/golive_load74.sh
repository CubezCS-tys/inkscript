#!/bin/bash
# Experiment 74 (from golive70.sh): make journal J's verified work copy live.
#   1. back up platform_v2.db, the link cache and the Desk schema (dated)
#   2. copy the verified work copy exp74_work.db over platform_v2.db (SQLite backup API: safe with readers open)
#      and its link cache over the live one
#   3. build the Desk release (--keep 14: no release copy is pruned)
#   4. the audit on the new release (Word-route articles skipped: no scan), the before/after against the current
#      /audit pointer, and the /audit pointer moved to out/audit_live (~/data/desk/audit_current)
# The API is NOT restarted here. Usage: golive_load74.sh J
set -e
J=$1
cd /home/appuser/inkscript
T=$(date +%Y%m%dT%H%M%S)
D=/home/appuser/data/platform_v2
W=$D/exp74_work.db
O=experiments/74_gate2_full/out/$J
BEFORE=$(cat /home/appuser/data/desk/audit_current)
.venv/bin/python - <<PYEOF
import sqlite3
s = sqlite3.connect("file:$D/platform_v2.db?mode=ro", uri=True); d = sqlite3.connect("$D/backups/platform_v2.before_exp74_${J}_$T.db"); s.backup(d); d.close()
assert sqlite3.connect("file:$D/backups/platform_v2.before_exp74_${J}_$T.db?mode=ro", uri=True).execute("pragma quick_check").fetchone()[0] == "ok"
w = sqlite3.connect("file:$W?mode=ro", uri=True); assert w.execute("pragma quick_check").fetchone()[0] == "ok"
d = sqlite3.connect("$D/platform_v2.db"); w.backup(d); d.close()
print("platform_v2.db <- $W; backup $D/backups/platform_v2.before_exp74_${J}_$T.db")
PYEOF
cp -a $D/link_cache47.json $D/backups/link_cache47.before_exp74_${J}_$T.json
cp -a $O/linkwork/link_cache47.json $D/link_cache47.json
pg_dump -Fc -n desk inkdesk -f /home/appuser/data/desk/backups/desk_schema_before_exp74_${J}_$T.dump
cd experiments/49_correction_desk
.venv/bin/python -m desk.release --keep 14 --note "experiment 74: gate 2, journal $J (scan route j${J}_final + Word route w${J}_final)" | tee ../74_gate2_full/out/$J/release_load.json
R=$(.venv/bin/python -c "import json; print(json.load(open('../74_gate2_full/out/$J/release_load.json'))['path'])")
cd ../..
A=experiments/74_gate2_full/out/audit_live
nice -n 10 .venv/bin/python experiments/61_nothing_lost/audit61.py --release $R --out $A run --workers 3 --force
nice -n 10 .venv/bin/python experiments/61_nothing_lost/audit61.py --release $R --out $A aggregate
.venv/bin/python experiments/65_fix_leaks/before_after65.py --before $BEFORE/audit.json --after $A/audit.json --outdir $A || true
echo "$(pwd)/$A" > /home/appuser/data/desk/audit_current
cp -a $A/audit.json $O/audit_after_load.json
echo "live release: $R; /audit -> $(cat /home/appuser/data/desk/audit_current)"

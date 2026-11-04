#!/bin/bash
# Experiment 70: make gate 2's pilot live (the steps experiment 68's golive68.sh takes, for the verified work copy).
#   1. back up platform_v2.db, the link cache and the Desk schema (dated)
#   2. copy the verified reading exp70_work.db over platform_v2.db (SQLite backup API: safe with readers open) and its
#      link cache over the live one
#   3. build the Desk release (--keep 8: no release copy is pruned; 7 exist)
#   4. the audit on the new release (Word-route articles skipped: no scan), and point the /audit page at it; the
#      previous audit stays where it is (68_go_live/out/audit_live) as "before"
# The API is NOT restarted here (the lead does that; see README "What the lead must run").
set -e
cd /home/appuser/inkscript
T=$(date +%Y%m%dT%H%M%S)
D=/home/appuser/data/platform_v2
W=$D/exp70_work.db
O=experiments/70_gate2_pilot/out
.venv/bin/python - <<EOF
import sqlite3
s = sqlite3.connect("file:$D/platform_v2.db?mode=ro", uri=True); d = sqlite3.connect("$D/backups/platform_v2.before_exp70_$T.db"); s.backup(d); d.close()
assert sqlite3.connect("file:$D/backups/platform_v2.before_exp70_$T.db?mode=ro", uri=True).execute("pragma quick_check").fetchone()[0] == "ok"
w = sqlite3.connect("file:$W?mode=ro", uri=True); assert w.execute("pragma quick_check").fetchone()[0] == "ok"
d = sqlite3.connect("$D/platform_v2.db"); w.backup(d); d.close()
print("platform_v2.db <- $W; backup $D/backups/platform_v2.before_exp70_$T.db")
EOF
cp -a $D/link_cache47.json $D/backups/link_cache47.before_exp70_$T.json
cp -a $O/linkwork/link_cache47.json $D/link_cache47.json
pg_dump -Fc -n desk inkdesk -f /home/appuser/data/desk/backups/desk_schema_before_exp70_$T.dump
pg_dump -n desk inkdesk -f /home/appuser/data/desk/backups/desk_schema_before_exp70_$T.sql
cd experiments/49_correction_desk
.venv/bin/python -m desk.release --keep 8 --note "experiment 70: gate 2 pilot - journal 0165 (145 scan articles j0165_final + 218 Word-route articles w0165_final)" | tee ../70_gate2_pilot/out/release70.json
R=$(.venv/bin/python -c "import json; print(json.load(open('../70_gate2_pilot/out/release70.json'))['path'])")
cd ../..
nice -n 10 .venv/bin/python experiments/61_nothing_lost/audit61.py --release $R --out $O/audit_live run --workers 3 --force
nice -n 10 .venv/bin/python experiments/61_nothing_lost/audit61.py --release $R --out $O/audit_live aggregate
.venv/bin/python experiments/65_fix_leaks/before_after65.py --before experiments/68_go_live/out/audit_live/audit.json --after $O/audit_live/audit.json --outdir $O/audit_live
echo "$(pwd)/$O/audit_live" > /home/appuser/data/desk/audit_current
echo "live release: $R; the /audit page reads $(cat /home/appuser/data/desk/audit_current) after the API restart"

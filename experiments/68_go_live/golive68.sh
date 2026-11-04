#!/bin/bash
# Experiment 68: make the verified candidate live. NOT run by the agent (it stopped on 3 orphaned decisions, as the
# lead asked); the lead runs it after deciding. Every step is reversible (see README "Reverting").
#   1. back up platform_v2.db, the link cache and the Desk schema (dated)
#   2. copy the verified reading golive68_work6.db over platform_v2.db (SQLite backup API: safe with readers open)
#      and its link cache over the live one
#   3. build the Desk release (keep 7: no release copy is pruned)
#   4. the audit on the new release, and point the /audit page at it
# Then restart the API (README): the twin-row counts, the model-suggestion layer on the page view and the audit
# pointer are in code the running API has not loaded.
set -e
cd /home/appuser/inkscript
T=$(date +%Y%m%dT%H%M%S)
D=/home/appuser/data/platform_v2
W=$D/golive68_work6.db
O=experiments/68_go_live/out
.venv/bin/python - <<EOF
import sqlite3
s = sqlite3.connect("file:$D/platform_v2.db?mode=ro", uri=True); d = sqlite3.connect("$D/backups/platform_v2.before_golive68_$T.db"); s.backup(d); d.close()
w = sqlite3.connect("file:$W?mode=ro", uri=True); assert w.execute("pragma quick_check").fetchone()[0] == "ok"
d = sqlite3.connect("$D/platform_v2.db"); w.backup(d); d.close()
print("platform_v2.db <- $W; backup $D/backups/platform_v2.before_golive68_$T.db")
EOF
cp -a $D/link_cache47.json $D/backups/link_cache47.before_golive68_$T.json
cp -a $O/linkwork6/link_cache47.json $D/link_cache47.json
pg_dump -Fc -n desk inkdesk -f /home/appuser/data/desk/backups/desk_schema_before_golive68_$T.dump
cd experiments/49_correction_desk
.venv/bin/python -m desk.release --keep 7 --note "experiment 68: go live - experiment 65's leak fixes + experiment 66's D30 guard (four *_fix61_d30 runs); twin rows" | tee ../68_go_live/out/release68.json
R=$(.venv/bin/python -c "import json,sys; print(json.load(open('../68_go_live/out/release68.json'))['path'])")
cd ../..
nice -n 10 .venv/bin/python experiments/61_nothing_lost/audit61.py --release $R --out $O/audit_live run --workers 3 --force
nice -n 10 .venv/bin/python experiments/61_nothing_lost/audit61.py --release $R --out $O/audit_live aggregate
.venv/bin/python experiments/65_fix_leaks/before_after65.py --after $O/audit_live/audit.json --outdir $O/audit_live
echo "$(pwd)/$O/audit_live" > /home/appuser/data/desk/audit_current
echo "live release: $R; the /audit page reads $(cat /home/appuser/data/desk/audit_current) after the API restart"

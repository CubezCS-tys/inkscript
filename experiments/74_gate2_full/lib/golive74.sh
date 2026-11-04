#!/bin/bash
# Experiment 74: apply one journal's librarian pass to the live Desk (from golive72.sh). Usage: golive74.sh J
#   1. back up the Desk schema (pg_dump, dated: .dump and .sql). The platform database is not written by this pass.
#   2. import OUT/plan74.jsonl as decisions of agent:librarian and the held items as tasks, through desk.ops
#      (import74.py; idempotent)
#   3. build the Desk release (--keep 14)
#   4. measure before / after (measure74.py)
# Needs LIB74_RELEASE (the release the pass was planned on). The API is NOT restarted here.
set -e
J=$1; [ -n "$J" ] || { echo "usage: golive74.sh J"; exit 1; }
[ -n "$LIB74_RELEASE" ] || { echo "set LIB74_RELEASE"; exit 1; }
export LIB74_J=$J
cd /home/appuser/inkscript
T=$(date +%Y%m%dT%H%M%S)
B=/home/appuser/data/desk/backups
O=experiments/74_gate2_full/out/$J/lib
pg_dump -Fc -n desk inkdesk -f $B/desk_schema_before_exp74_${J}_$T.dump
pg_dump -n desk inkdesk -f $B/desk_schema_before_exp74_${J}_$T.sql
echo "backup: $B/desk_schema_before_exp74_${J}_$T.{dump,sql}"
BEFORE=$(ls -1 /home/appuser/data/desk/releases/R*.db | sort | tail -1)
cd experiments/49_correction_desk
.venv/bin/python ../74_gate2_full/lib/import74.py --schema desk --tasks | tee ../74_gate2_full/out/$J/lib/import74_live.json
.venv/bin/python -m desk.release --keep 14 --note "experiment 74: the librarian pass on journal $J (institutions, affiliations, cited works)" | tee ../74_gate2_full/out/$J/lib/release74.json
R=$(.venv/bin/python -c "import json; print(json.load(open('../74_gate2_full/out/$J/lib/release74.json'))['path'])")
cd ../74_gate2_full/lib
nice ../../49_correction_desk/.venv/bin/python measure74.py $BEFORE $R
echo "live release: $R (before: $BEFORE)"

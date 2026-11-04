#!/bin/bash
# Experiment 72: apply the librarian pass to the live Desk.
#   1. back up the Desk schema (pg_dump, dated: .dump and .sql). The platform database is not written by this pass
#      (decisions live in the Desk; the release is a copy), so it needs no backup.
#   2. import the plan (out/plan72.jsonl) as decisions of agent:librarian and the held items as tasks, through
#      desk.ops (import72.py; idempotent: a second run skips what is in)
#   3. build the Desk release (--keep 9: no release copy is pruned; 8 exist)
#   4. measure before / after (measure72.py)
# The API is NOT restarted and the web NOT rebuilt here (no code the API serves changed; see README "For the lead").
set -e
cd /home/appuser/inkscript
T=$(date +%Y%m%dT%H%M%S)
B=/home/appuser/data/desk/backups
O=experiments/72_librarian_0165/out
pg_dump -Fc -n desk inkdesk -f $B/desk_schema_before_exp72_$T.dump
pg_dump -n desk inkdesk -f $B/desk_schema_before_exp72_$T.sql
echo "backup: $B/desk_schema_before_exp72_$T.{dump,sql}"
BEFORE=$(ls -1 /home/appuser/data/desk/releases/R*.db | sort | tail -1)
cd experiments/49_correction_desk
.venv/bin/python ../72_librarian_0165/import72.py --schema desk --tasks | tee ../72_librarian_0165/out/import72_live.json
.venv/bin/python -m desk.release --keep 9 --note "experiment 72: the first production librarian pass (journal 0165: institutions, affiliations, cited works, one person; exp 68's three orphans re-anchored)" | tee ../72_librarian_0165/out/release72.json
R=$(.venv/bin/python -c "import json; print(json.load(open('../72_librarian_0165/out/release72.json'))['path'])")
cd ../72_librarian_0165
nice ../49_correction_desk/.venv/bin/python measure72.py $BEFORE $R
echo "live release: $R (before: $BEFORE)"

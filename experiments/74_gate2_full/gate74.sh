#!/bin/bash
# Experiment 74: the checks on journal J's work copy BEFORE it goes live: the dry-run release (throwaway schema
# test_e74dry: every Desk decision replayed on the work copy; scratch release in the scratchpad), then the audit of
# J's scan articles on that scratch release (out/J/audit_dry) and the journal's leak rate (b + d lines / lines).
# Usage: gate74.sh J
set -e
J=$1
S=/tmp/claude-1001/-home-appuser-inkscript/ce324538-f0e5-4bcd-bb2c-24ff5624e7cb/scratchpad/dry_$J
O=/home/appuser/inkscript/experiments/74_gate2_full/out/$J
mkdir -p $S
cd /home/appuser/inkscript/experiments/49_correction_desk
echo "== dry run $J $(date +%H:%M)"
nice -n 10 .venv/bin/python ../74_gate2_full/dryrun_load74.py --reading /home/appuser/data/platform_v2/exp74_work.db --out $S --report $O/dryrun_load.json --schema test_e74dry > $O/logs/dryrun_load.log 2>&1
python3 -c "
import json; d=json.load(open('$O/dryrun_load.json')); print({k: d[k] for k in ('release_id','n_decisions','n_applied','n_superseded','n_orphaned','n_conflict')}); print('not applied:', [(x['op'], x['status']) for x in d['not_applied']][:12])"
R=$(python3 -c "import json; print(json.load(open('$O/dryrun_load.json'))['path'])")
cd /home/appuser/inkscript
STEMS=$(ls experiments/43_rehearsal/out/j${J}_final/masters/*.jats.xml 2>/dev/null | xargs -n1 basename | sed 's/.jats.xml//')
if [ -n "$STEMS" ]; then
  echo "== audit on the dry release $(date +%H:%M)"
  nice -n 10 .venv/bin/python experiments/61_nothing_lost/audit61.py --release $R --out $O/audit_dry run --workers 3 --force --stems $STEMS > $O/logs/audit_dry.log 2>&1
  nice -n 10 .venv/bin/python experiments/61_nothing_lost/audit61.py --release $R --out $O/audit_dry aggregate >> $O/logs/audit_dry.log 2>&1
  python3 -c "
import json; d=json.load(open('$O/audit_dry/audit.json'))['journals']['$J']; b=d['lines_by_bucket']
print('audit $J:', d['articles'], 'articles', d['lines'], 'lines; accounted', d['accounted_lines'], '%; generic-only', b.get('b',0), 'nowhere', b.get('d',0), '; leak rate', round(100*(b.get('b',0)+b.get('d',0))/d['lines'],3), '%')"
fi
echo "== done $(date +%H:%M)"

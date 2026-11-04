"""Experiment 72: a scratch release of the throwaway schema after fix72 (the lead's follow-up), to see it replay.

    cd experiments/49_correction_desk
    .venv/bin/python ../72_librarian_0165/dryfix72.py --out <scratch dir> [--schema test_e72dry]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "49_correction_desk"))
from desk import db, release  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--schema", default="test_e72dry")
ap.add_argument("--out", required=True)
a = ap.parse_args()
assert a.schema.startswith("test_")
with db.connect(a.schema) as pg:
    r = release.build_release(pg, "/home/appuser/data/platform_v2/platform_v2.db", a.out, keep=1,
                              note="exp 72 fix dry run", built_by="agent:exp72-dryrun")
    apps = pg.execute("SELECT a.status, d.op, d.subject_keys, a.detail, d.evidence->>'source_id' src FROM applications a "
                      "JOIN decisions d USING (decision_id) WHERE a.release_id = %s", (r["release_id"],)).fetchall()
out = {k: r[k] for k in ("release_id", "n_decisions", "n_applied", "n_superseded", "n_orphaned", "n_conflict",
                         "fingerprint", "path")}
out["checks"] = {k: v for k, v in r["checks"].items() if k in ("fk_ok", "failing", "decisions_hold")}
out["fix"] = [dict(status=x["status"], op=x["op"], keys=x["subject_keys"], src=x["src"]) for x in apps
              if (x["src"] or "").startswith("E72:fix")]
out["not_applied"] = [dict(status=x["status"], op=x["op"], keys=x["subject_keys"], detail=x["detail"], src=x["src"])
                      for x in apps if x["status"] not in ("applied", "superseded")]
(HERE / "out" / f"dryfix72_{a.schema}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))

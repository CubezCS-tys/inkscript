"""Experiment 70 (copied from experiment 68), the dry run: a throwaway schema holding a copy of the Desk's actors and decisions as they stand, and
a release built from it on a given reading into a scratch folder. The live `desk` schema and its releases are only
read.

    cd experiments/49_correction_desk
    .venv/bin/python ../68_go_live/dryrun68.py --reading DB --out <scratch dir> [--schema test_e70dry]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
E68 = HERE.parent / "68_go_live"
DESK = HERE.parent / "49_correction_desk"
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(HERE.parent / "67_apply_works"))
from desk import db, release  # noqa: E402
from dryrun67 import copy_desk  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default="test_e70dry")
    ap.add_argument("--reading", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not a.schema.startswith("test_"):
        raise SystemExit("the dry run writes a test_ schema only")
    n = copy_desk(a.schema)
    print(json.dumps(dict(copied_decisions=n)))
    with db.connect(a.schema) as pg:
        r = release.build_release(pg, a.reading, a.out, keep=1, note="exp 70 dry run", built_by="agent:exp70-dryrun")
        apps = pg.execute("SELECT a.status, d.op, d.subject_keys, a.detail FROM applications a JOIN decisions d "
                          "USING (decision_id) WHERE a.release_id = %s", (r["release_id"],)).fetchall()
    by = Counter((x["op"], x["status"]) for x in apps)
    keep = ("release_id", "n_decisions", "n_applied", "n_superseded", "n_orphaned", "n_conflict", "checks",
            "counts_before", "counts_after", "timings", "path", "fingerprint")
    out = {k: r[k] for k in keep}
    out["checks"] = {k: v for k, v in out["checks"].items() if k != "tables"}
    out["by_op_status"] = {f"{o} {s}": c for (o, s), c in sorted(by.items())}
    out["not_applied"] = [dict(op=x["op"], status=x["status"], keys=x["subject_keys"], detail=x["detail"])
                          for x in apps if x["status"] not in ("applied", "superseded")]
    out["moved_twins"] = sum(1 for x in apps if "moved to its twin" in json.dumps(x["detail"], ensure_ascii=False))
    (Path("/home/appuser/inkscript/experiments/70_gate2_pilot/out") / f"dryrun70_{a.schema}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1,
                                                                       default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("counts_before",)}, ensure_ascii=False, indent=1,
                     default=str)[:8000])


if __name__ == "__main__":
    main()

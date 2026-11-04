"""Experiment 74 (from dryrun72.py), the dry run of one journal's import: a throwaway schema test_e74<J> holding a
copy of the Desk's actors, decisions and open tasks as they stand, this pass imported into it (decisions and tasks),
and a release built from it on the live reading into a scratch folder. The live `desk` schema and its releases are
only read. Reports orphans / conflicts (all, and this pass's) -> OUT/dryrun74_<schema>.json.

    cd experiments/49_correction_desk
    LIB74_J=.. LIB74_RELEASE=.. .venv/bin/python ../74_gate2_full/lib/dryrun74.py --out <scratch dir> [--schema test_e74<J>]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common74 import DESK, E67, JOURNAL, OUT, RELEASE, SRC  # noqa: E402
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(E67))
from desk import db, release  # noqa: E402
from dryrun67 import copy_desk  # noqa: E402
import import74  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default=f"test_e74{JOURNAL}")
    ap.add_argument("--reading", default="/home/appuser/data/platform_v2/platform_v2.db")
    ap.add_argument("--state", default=str(RELEASE))
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not a.schema.startswith("test_"):
        raise SystemExit("the dry run writes a test_ schema only")
    n = copy_desk(a.schema)
    with db.connect(a.schema) as pg:           # the open tasks too, so a task the pass answers is closed as live
        cols = [r["column_name"] for r in pg.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'desk' AND table_name = 'tasks' "
            "ORDER BY ordinal_position")]
        cl = ", ".join(cols)
        pg.execute(f"INSERT INTO {a.schema}.tasks ({cl}) SELECT {cl} FROM desk.tasks ON CONFLICT DO NOTHING")
        pg.execute(f"SELECT setval(pg_get_serial_sequence('{a.schema}.tasks', 'task_id'), "
                   f"(SELECT max(task_id) FROM {a.schema}.tasks))")
        pg.commit()
    for f in OUT.glob(f"import74_{a.schema}*.jsonl"):
        f.write_text("", encoding="utf-8")
    print(json.dumps(dict(copied_decisions=n)))
    import74.main(["--schema", a.schema, "--state", a.state, "--tasks"])
    with db.connect(a.schema) as pg:
        r = release.build_release(pg, a.reading, a.out, keep=1, note=f"exp 74 dry run ({JOURNAL})", built_by="agent:exp74-dryrun")
        apps = pg.execute("SELECT a.status, d.op, d.subject_keys, a.detail, d.actor_id, d.evidence->>'source_id' src "
                          "FROM applications a JOIN decisions d USING (decision_id) WHERE a.release_id = %s",
                          (r["release_id"],)).fetchall()
        tasks = pg.execute("SELECT kind, state, count(*) n FROM tasks GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
    by = Counter((x["op"], x["status"]) for x in apps)
    keep = ("release_id", "n_decisions", "n_applied", "n_superseded", "n_orphaned", "n_conflict", "checks",
            "counts_before", "counts_after", "timings", "path", "fingerprint")
    out = {k: r[k] for k in keep}
    out["checks"] = {k: v for k, v in out["checks"].items() if k != "tables"}
    out["by_op_status"] = {f"{o} {s}": c for (o, s), c in sorted(by.items())}
    out["this_pass_by_status"] = dict(Counter(x["status"] for x in apps if (x["src"] or "").startswith(SRC)))
    out["this_pass_not_applied"] = [dict(op=x["op"], status=x["status"], keys=x["subject_keys"], detail=x["detail"],
                                         source=x["src"]) for x in apps if (x["src"] or "").startswith(SRC)
                                    and x["status"] not in ("applied", "superseded")]
    out["not_applied"] = [dict(op=x["op"], status=x["status"], keys=x["subject_keys"], detail=x["detail"],
                               source=x["src"]) for x in apps if x["status"] not in ("applied", "superseded")]
    out["tasks"] = [dict(t) for t in tasks]
    (OUT / f"dryrun74_{a.schema}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                                                         encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("counts_before",)}, ensure_ascii=False, indent=1,
                     default=str)[:8000])


if __name__ == "__main__":
    main()

"""Experiment 67, the dry run: a throwaway schema holding a copy of the Desk's actors and decisions as they stand,
the plan imported into it, and a release built from it into a scratch folder. The live `desk` schema and its
releases are only read.

    cd experiments/49_correction_desk
    .venv/bin/python ../67_apply_works/dryrun67.py --out <scratch dir> [--schema test_e67dry]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESK = HERE.parent / "49_correction_desk"
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(HERE))
from desk import db, release  # noqa: E402
import import67  # noqa: E402

COLS = ("decision_id, seq, domain, op, subject_keys, payload, reason_code, note, evidence, actor_id, role_at_time, "
        "created_at, confidence, status, supersedes, review_policy_at_time, is_demo")


def copy_desk(schema: str):
    db.init_schema(schema, drop=True)
    with db.connect(schema) as pg:
        pg.execute(f"INSERT INTO {schema}.actors SELECT * FROM desk.actors ON CONFLICT DO NOTHING")
        pg.execute(f"INSERT INTO {schema}.decisions ({COLS}) SELECT {COLS} FROM desk.decisions ORDER BY seq")
        pg.execute(f"UPDATE {schema}.decisions t SET superseded_by = s.superseded_by FROM desk.decisions s "
                   f"WHERE s.decision_id = t.decision_id AND s.superseded_by IS NOT NULL")
        pg.execute(f"SELECT setval(pg_get_serial_sequence('{schema}.decisions', 'seq'), "
                   f"(SELECT max(seq) FROM {schema}.decisions))")
        n = pg.execute("SELECT count(*) n FROM decisions").fetchone()["n"]
        pg.commit()
    return n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default="test_e67dry")
    ap.add_argument("--out", required=True)
    ap.add_argument("--state", default="/home/appuser/data/desk/releases/R20261102T155701.db")
    a = ap.parse_args(argv)
    if not a.schema.startswith("test_"):
        raise SystemExit("the dry run writes a test_ schema only")
    n = copy_desk(a.schema)
    for f in (HERE / "out").glob(f"import67_{a.schema}*.jsonl"):     # a fresh schema: fresh logs
        f.write_text("", encoding="utf-8")
    print(json.dumps(dict(copied_decisions=n)))
    import67.main(["--schema", a.schema, "--state", a.state])
    with db.connect(a.schema) as pg:
        r = release.build_release(pg, None, a.out, keep=1, note="exp 67 dry run", built_by="agent:exp67-dryrun")
    keep = ("release_id", "n_decisions", "n_applied", "n_superseded", "n_orphaned", "n_conflict", "checks",
            "counts_before", "counts_after", "timings", "path", "fingerprint")
    out = {k: r[k] for k in keep}
    out["checks"] = {k: v for k, v in out["checks"].items() if k != "tables"}
    (HERE / "out" / f"dryrun67_{a.schema}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                                                         encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()

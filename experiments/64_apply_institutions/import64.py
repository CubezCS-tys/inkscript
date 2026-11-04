"""Experiment 64, step 2: import the planned decisions (out/plan64.jsonl) into the Desk as decisions of
agent:librarian, through the Desk's own code path (desk.ops.decide: validation against the state the Desk reads,
ownership, the one-key rule, the append-only table and its triggers). No SQL of its own touches `decisions`.

Idempotent: a planned decision whose source_id already has a standing decision is skipped, so a stopped import is
resumed by running it again. Commits every 50 decisions; writes out/import64_<schema>.jsonl (one line per decision).

    cd experiments/49_correction_desk
    .venv/bin/python ../64_apply_institutions/import64.py [--schema desk] [--state RELEASE.db]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESK = HERE.parent / "49_correction_desk"
sys.path.insert(0, str(DESK))
from desk import db, ops  # noqa: E402
from desk.cli import add_actor  # noqa: E402
from desk.reading import Reading  # noqa: E402

ACTOR = "agent:librarian"
ACTOR_NAME = "The AI librarian (institutions: experiment 56's pass, verified by experiment 63, applied by experiment 64)"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default=db.pg_schema())
    ap.add_argument("--state", help="the state decisions are validated against (default: what the Desk reads)")
    ap.add_argument("--plan", default=str(HERE / "out" / "plan64.jsonl"))
    a = ap.parse_args(argv)
    plan = [json.loads(l) for l in open(a.plan, encoding="utf-8")]
    log = HERE / "out" / f"import64_{a.schema}.jsonl"
    t0 = time.time()
    with db.connect(a.schema) as pg:
        add_actor(pg, ACTOR, ACTOR_NAME, "corrector", ["ar", "en", "fr"], kind="agent")
        pg.commit()
        state = Path(a.state) if a.state else db.state_path(pg)
        R = Reading(sqlite3.connect(f"file:{state}?mode=ro", uri=True))
        have = {r["sid"] for r in pg.execute(
            "SELECT evidence->>'source_id' sid FROM decisions WHERE actor_id = %s AND status IN ('proposed', "
            "'accepted')", (ACTOR,))}
        done = Counter()
        with open(log, "a", encoding="utf-8") as f:
            for i, p in enumerate(plan):
                if p["source_id"] in have:
                    done["already"] += 1
                    continue
                try:
                    d = ops.decide(pg, ACTOR, p["op"], p["subject_keys"], p["payload"], reason_code=p["reason_code"],
                                   note=p["note"], confidence=p["confidence"], evidence=p["evidence"], state=R)
                except ops.OpError as e:
                    pg.rollback()
                    raise SystemExit(f"refused at {i} ({p['source_id']}): {e}")
                done[p["op"]] += 1
                f.write(json.dumps(dict(source_id=p["source_id"], decision_id=str(d["decision_id"]), op=p["op"],
                                        status=d["status"]), ensure_ascii=False) + "\n")
                if (i + 1) % 50 == 0:
                    pg.commit()
                    f.flush()
            pg.commit()
    print(json.dumps(dict(schema=a.schema, state=str(state), imported=dict(done), seconds=round(time.time() - t0, 1)),
                     indent=1))


if __name__ == "__main__":
    main()

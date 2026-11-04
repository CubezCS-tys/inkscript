"""Experiment 67, step 2: import the planned decisions (out/plan67.jsonl) into the Desk as decisions of
agent:librarian, through the Desk's own code path (desk.ops.decide: validation against the state the Desk reads,
ownership, the one-key rule, the append-only table and its triggers). No SQL of its own touches `decisions`.

A key 'work:@<source_id>#<g>' names group g of a split imported earlier: it becomes the card id the Desk minted for
that group (the split decision's payload). Idempotent: a planned decision whose source_id already has a standing
decision is skipped, so a stopped import is resumed by running it again. Commits every 50; writes
out/import67_<schema>.jsonl (one line per decision) and out/import67_<schema>_refused.jsonl (what the Desk refused,
with its message: nothing is forced).

    cd experiments/49_correction_desk
    .venv/bin/python ../67_apply_works/import67.py [--schema desk] [--state RELEASE.db]
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
ACTOR_NAME = "The AI librarian (institutions: experiments 56, 63, 64; cited works: experiments 62, 67)"


def resolve_keys(pg, keys: list[str]) -> list[str]:
    out = []
    for k in keys:
        if k.startswith("work:@"):
            src, _, g = k[len("work:@"):].rpartition("#")
            r = pg.execute("SELECT payload FROM decisions WHERE actor_id = %s AND evidence->>'source_id' = %s AND "
                           "status IN ('proposed', 'accepted') AND op = 'split_work'", (ACTOR, src)).fetchone()
            if not r:
                raise LookupError(f"{k}: the split {src} is not imported")
            k = f"work:{r['payload']['groups'][int(g)]['card_id']}"
        out.append(k)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default=db.pg_schema())
    ap.add_argument("--state", help="the state decisions are validated against (default: what the Desk reads)")
    ap.add_argument("--plan", default=str(HERE / "out" / "plan67.jsonl"))
    a = ap.parse_args(argv)
    plan = [json.loads(l) for l in open(a.plan, encoding="utf-8")]
    log = HERE / "out" / f"import67_{a.schema}.jsonl"
    bad = HERE / "out" / f"import67_{a.schema}_refused.jsonl"
    t0 = time.time()
    with db.connect(a.schema) as pg:
        if not pg.execute("SELECT 1 FROM actors WHERE actor_id = %s", (ACTOR,)).fetchone():
            add_actor(pg, ACTOR, ACTOR_NAME, "corrector", ["ar", "en", "fr"], kind="agent")
        pg.commit()
        state = Path(a.state) if a.state else db.state_path(pg)
        R = Reading(sqlite3.connect(f"file:{state}?mode=ro", uri=True))
        have = {r["sid"] for r in pg.execute(
            "SELECT evidence->>'source_id' sid FROM decisions WHERE actor_id = %s AND status IN ('proposed', "
            "'accepted')", (ACTOR,))}
        done, refused = Counter(), Counter()
        with open(log, "a", encoding="utf-8") as f, open(bad, "a", encoding="utf-8") as fb:
            for i, p in enumerate(plan):
                if p["source_id"] in have:
                    done["already"] += 1
                    continue
                pg.execute("SAVEPOINT one")
                try:
                    keys = resolve_keys(pg, p["subject_keys"])
                    d = ops.decide(pg, ACTOR, p["op"], keys, p["payload"], reason_code=p["reason_code"],
                                   note=p["note"], confidence=p["confidence"], evidence=p["evidence"], state=R)
                    pg.execute("RELEASE one")
                except (ops.OpError, LookupError) as e:
                    pg.execute("ROLLBACK TO one")
                    refused[p["op"]] += 1
                    fb.write(json.dumps(dict(source_id=p["source_id"], op=p["op"], keys=p["subject_keys"],
                                             why=str(e)), ensure_ascii=False) + "\n")
                    continue
                done[p["op"]] += 1
                f.write(json.dumps(dict(source_id=p["source_id"], decision_id=str(d["decision_id"]), op=p["op"],
                                        keys=keys, status=d["status"]), ensure_ascii=False) + "\n")
                if (i + 1) % 50 == 0:
                    pg.commit()
                    f.flush()
            pg.commit()
    print(json.dumps(dict(schema=a.schema, state=str(state), imported=dict(done), refused=dict(refused),
                          seconds=round(time.time() - t0, 1)), indent=1))


if __name__ == "__main__":
    main()

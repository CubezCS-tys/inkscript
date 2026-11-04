"""Experiment 74 (from import72.py): import one journal's planned decisions (OUT/plan74.jsonl) into the Desk as
decisions of agent:librarian, through the Desk's own code path (desk.ops.decide: validation against the state the
Desk reads, ownership, the one-key rule, the append-only table and its triggers), and the held items as Desk tasks
(desk.ops.add_task). No SQL of its own touches `decisions` or `tasks`.

Idempotent: a planned decision whose source_id already has a standing decision is skipped. A refused decision is
logged with the Desk's message (OUT/import74_<schema>_refused.jsonl): nothing is forced.

    cd experiments/49_correction_desk
    LIB74_J=.. LIB74_RELEASE=.. .venv/bin/python ../74_gate2_full/lib/import74.py [--schema desk] [--state RELEASE.db] [--tasks]
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
sys.path.insert(0, str(HERE))
from common74 import DESK, JOURNAL, OUT  # noqa: E402
sys.path.insert(0, str(DESK))
from desk import db, ops  # noqa: E402
from desk.cli import add_actor  # noqa: E402
from desk.reading import Reading  # noqa: E402

ACTOR = "agent:librarian"
ACTOR_NAME = "The AI librarian (institutions: experiments 56, 63, 64; cited works: 62, 67; production passes: 72, 74)"
TASK_SOURCE = dict(detector="librarian74", experiment=74, journal=JOURNAL)


def card_side(R, cid):
    info = R.card_info(cid) or {}
    ms = R.q("""SELECT m.mention_id, m.printed, v.stem, a.anchor_key FROM cited_work_members cm
                JOIN cited_works w ON w.cited_work_pk = cm.cited_work_pk
                JOIN citation_mentions m ON m.mention_pk = cm.full_mention_pk
                JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
                LEFT JOIN ink_anchors a ON a.anchor_pk = m.anchor_pk WHERE w.cited_work_id = ? LIMIT 3""", (cid,))
    return dict(work=f"work:{cid}", title=info.get("title"), authors=[], n_mentions=info.get("n_mentions"),
                n_articles=info.get("n_citing_pubs"),
                sample=[dict(mention=f"mention:{m['mention_id']}", stem=m["stem"], printed=m["printed"],
                             anchor=m["anchor_key"], authors=[]) for m in ms])


def import_tasks(pg, R, path):
    made, skipped = Counter(), 0
    for t in (json.loads(l) for l in open(path, encoding="utf-8") if l.strip()):
        q = t["q"]
        meta = q.get("meta") or {}
        answers = dict(flash=t["flash"], opus=t["opus"])
        if t["kind"] == "works:pair":
            a, b = meta["cards"]
            keys = sorted([f"work:{a}", f"work:{b}"])
            tid = ops.add_task(pg, "possible_same_work", keys, question=f"Are «{q['evidence']['A']['title']}» and "
                               f"«{q['evidence']['B']['title']}» the same work? (librarian: {t['why']})",
                               candidates=[card_side(R, a), card_side(R, b)],
                               machine_guess=dict(op=None, librarian=answers), impact=2, uncertainty=0.5,
                               source=dict(TASK_SOURCE, question=t["qid"], why=t["why"]), skills=["ar"])
            kind = "possible_same_work"
        else:
            if t["kind"] == "conflicting_answers":
                keys = list(meta["keys"][:1])
            elif t["kind"].startswith("inst:"):
                ev = q["evidence"]
                keys = [meta["key"]] if meta.get("key") else [f"inst:{r}" for r in meta.get("rows") or
                                                              [meta.get("row")] if r]
            else:
                keys = [f"work:{meta['card']}"]
            tid = ops.add_task(pg, "librarian_question", keys, question=f"{q['question']} (librarian: {t['why']})",
                               candidates=[dict(evidence=q["evidence"], options=q["options"])],
                               machine_guess=dict(librarian=answers), impact=1, uncertainty=0.5,
                               source=dict(TASK_SOURCE, question=t["qid"], kind=t["kind"], why=t["why"]),
                               skills=["ar"], check_standing=False)   # another question on a decided subject
            kind = "librarian_question"
        if tid is None:
            skipped += 1
        else:
            made[kind] += 1
    return dict(made=dict(made), skipped_decided=skipped)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default=db.pg_schema())
    ap.add_argument("--state", help="the state decisions are validated against (default: what the Desk reads)")
    ap.add_argument("--plan", default=str(OUT / "plan74.jsonl"))
    ap.add_argument("--tasks", action="store_true", help="also write the held items as tasks")
    a = ap.parse_args(argv)
    plan = [json.loads(l) for l in open(a.plan, encoding="utf-8")]
    log = OUT / f"import74_{a.schema}.jsonl"
    bad = OUT / f"import74_{a.schema}_refused.jsonl"
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
                    d = ops.decide(pg, ACTOR, p["op"], p["subject_keys"], p["payload"], reason_code=p["reason_code"],
                                   note=p["note"], confidence=p["confidence"], evidence=p["evidence"], state=R,
                                   supersedes=p.get("supersedes"))
                    pg.execute("RELEASE one")
                except (ops.OpError, LookupError) as e:
                    pg.execute("ROLLBACK TO one")
                    refused[p["op"]] += 1
                    fb.write(json.dumps(dict(source_id=p["source_id"], op=p["op"], keys=p["subject_keys"],
                                             why=str(e)), ensure_ascii=False) + "\n")
                    continue
                done[p["op"]] += 1
                f.write(json.dumps(dict(source_id=p["source_id"], decision_id=str(d["decision_id"]), op=p["op"],
                                        keys=p["subject_keys"], status=d["status"]), ensure_ascii=False) + "\n")
                if (i + 1) % 100 == 0:
                    pg.commit()
                    f.flush()
            pg.commit()
        # the orphan tasks a superseding decision answers (exp 72's code; none planned by exp 74): closed the way the
        # Desk's API closes a task
        # it answers (state answered, answered_by the superseding decision, a task event)
        closed = 0
        for line in open(log, encoding="utf-8"):
            x = json.loads(line)
            p = next((q for q in plan if q["source_id"] == x["source_id"]), None)
            if not p or not p.get("supersedes"):
                continue
            for t in pg.execute("SELECT task_id FROM tasks WHERE kind = 'orphaned_decision' AND state IN ('open', "
                                "'claimed') AND about_decision = %s", (p["supersedes"],)).fetchall():
                pg.execute("UPDATE tasks SET state = 'answered', answered_by = %s, claimed_by = NULL, lease_until = "
                           "NULL, updated_at = now() WHERE task_id = %s", (x["decision_id"], t["task_id"]))
                ops.task_event(pg, t["task_id"], ACTOR, "answered", x["decision_id"])
                closed += 1
        pg.commit()
        done["orphan_tasks_answered"] = closed
        tasks = None
        if a.tasks:
            tasks = import_tasks(pg, R, OUT / "tasks74.jsonl")
            pg.commit()
    print(json.dumps(dict(schema=a.schema, state=str(state), imported=dict(done), refused=dict(refused), tasks=tasks,
                          seconds=round(time.time() - t0, 1)), indent=1))


if __name__ == "__main__":
    main()

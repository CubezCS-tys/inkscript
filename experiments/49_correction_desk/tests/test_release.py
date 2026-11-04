"""P1 is done when (DESIGN §12):
(a) a rebuild from scratch reproduces every decision;
(b) a "not the same" decision (and a split) survives a linker run;
(c) orphaned decisions are detected.
The three tests run in this order and share one schema and one temporary copy of the reading."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import time

import pytest

from conftest import add_actor
from desk import db, examples as ex, ops, release
from desk.keys import key_value
from desk.reading import Reading

REPO = db.HERE.parents[2]
MAIN_PY = REPO / ".venv" / "bin" / "python"
LINK47 = REPO / "experiments" / "47_platform_v2" / "link47.py"
ACTOR = "person:tester-a"
STATE = {}


def ro(path) -> Reading:
    return Reading(sqlite3.connect(f"file:{path}?mode=ro", uri=True))


def check_decisions_hold(R: Reading, made: dict, machine_joined_not_same=False):
    """Every example decision is visible in the release db."""
    split = made["split"]
    cards = []
    for i, g in enumerate(split["payload"]["groups"]):
        on = {R.card_of_mention(m) for m in g["members"]}
        assert len(on) == 1, f"group {i} of the split is not on one card: {on}"
        cards.append(on.pop())
        assert cards[-1] == (key_value(ex.DIWAN) if i == 0 else g["card_id"])
    assert len(set(cards)) == len(cards) == 7, "the diwans are not seven cards"
    assert R.card_of_mention(key_value(ex.QAYSI_MEMBER)) == key_value(ex.QAYSI_CARD)
    keep, gone = (key_value(k) for k in ex.MUQADDIMA)
    assert R.q1("SELECT new_id, asserted_by FROM merged_ids WHERE old_id = ?", (gone,))[:] == (keep, "person")
    assert R.card(gone)["status"] == "merged"
    for m in made["same_work"]["evidence"]["members"][ex.MUQADDIMA[1]]:
        assert R.card_of_mention(m) == keep
    auth, prov = (key_value(k) for k in ex.ALOTAIBI)
    assert R.person(prov)["status"] == "merged"
    assert R.q1("SELECT new_id FROM merged_ids WHERE old_id = ?", (prov,))[0] == auth
    rows = R.q("SELECT * FROM authorships WHERE pub_id = 'W824016' AND person_id = ?", (auth,))
    assert len(rows) == 1, "the byline and its catalogue twin are not one authorship"
    printed = R.q("SELECT b.printed FROM authorship_mentions am JOIN byline_mentions b USING (mention_pk) "
                  "WHERE am.authorship_pk = ?", (rows[0]["authorship_pk"],))
    assert [p[0] for p in printed] == ["Dr Khalid Talal Alotaibi"]
    assert rows[0]["c999"] == "824016" and rows[0]["catalogue_seq"] == 2
    a, b = made["not_same"]["payload"]["a_members"], made["not_same"]["payload"]["b_members"]
    assert not ({R.card_of_mention(m) for m in a} & {R.card_of_mention(m) for m in b})
    assert {R.card_of_mention(m) for m in b} == {key_value(ex.NOT_SAME[1])}
    assert R.card(key_value(ex.NOT_SAME[1]))["status"] == "active"


def apps(pg, rid):
    return [(str(r["decision_id"]), r["status"], json.dumps(r["detail"], sort_keys=True, ensure_ascii=False))
            for r in pg.execute("SELECT * FROM applications WHERE release_id = %s ORDER BY ord", (rid,))]


def test_a_rebuild_reproduces_every_decision(pg, test_dir):
    add_actor(pg, ACTOR)
    made = ex.make_test_a(pg, ACTOR)
    pg.commit()
    STATE["made"] = made
    assert all(d["status"] == "accepted" and d["review_policy_at_time"] == "single" for d in made.values())
    t0 = time.time()
    r1 = release.build_release(pg, db.PLATFORM_V2)
    t1 = time.time() - t0
    assert (r1["n_decisions"], r1["n_applied"], r1["n_orphaned"], r1["n_conflict"]) == (5, 5, 0, 0)
    assert r1["checks"]["fk_ok"] and r1["checks"]["foreign_key_violations_after"] == 0
    assert r1["checks"]["decisions_hold"]
    check_decisions_hold(ro(r1["path"]), made)
    # counts moved as the decisions say: one card merged, 6 cards made by the split, one authorship fewer
    ch = r1["checks"]["count_changes"]
    assert ch["cited_works_active"] == 6 - 1 and ch["authorships"] == -1 and ch["merged_ids"] == 2
    # the reading itself is untouched
    assert ro(db.PLATFORM_V2).q1("SELECT count(*) FROM merged_ids WHERE asserted_by = 'person'")[0] == 0
    r2 = release.build_release(pg, db.PLATFORM_V2)
    assert r2["fingerprint"] == r1["fingerprint"], (r1["checks"]["tables"], r2["checks"]["tables"])
    assert [x[1:] for x in apps(pg, r1["release_id"])] == [x[1:] for x in apps(pg, r2["release_id"])]
    print(f"\n(a) release {r1['release_id']}: 5/5 applied in {t1:.0f} s ({r1['timings']}); rebuilt "
          f"{r2['release_id']}: identical fingerprint {r1['fingerprint'][:16]}")


def test_b_decisions_survive_a_linker_run(pg, test_dir):
    made = STATE["made"]
    reading = test_dir / "reading_b.db"
    release.copy_reading(db.PLATFORM_V2, reading)
    STATE["reading"] = reading
    R = ro(reading)
    ids_before = ({r[0] for r in R.q("SELECT cited_work_id FROM cited_works WHERE status = 'active'")},
                  {r[0] for r in R.q("SELECT person_id FROM persons WHERE status <> 'merged'")},
                  {r[0] for r in R.q("SELECT mention_id FROM citation_mentions m JOIN versions v USING (version_id) "
                                     "WHERE v.is_current = 1")})
    R.con.close()
    work = test_dir / "link_work"
    work.mkdir()
    shutil.copy(db.PLATFORM_V2.parent / "link_cache47.json", work / "link_cache47.json")
    t0 = time.time()
    p = subprocess.run([str(MAIN_PY), str(LINK47), "--db", str(reading), "--work", str(work)], cwd=str(REPO),
                       capture_output=True, text=True, timeout=5400)   # exp 74: the platform holds ~30k cards after gate 2; link47 on a copy takes ~60 min
    t_link = time.time() - t0
    assert p.returncode == 0, p.stderr[-3000:]
    R = ro(reading)
    ids_after = ({r[0] for r in R.q("SELECT cited_work_id FROM cited_works WHERE status = 'active'")},
                 {r[0] for r in R.q("SELECT person_id FROM persons WHERE status <> 'merged'")},
                 {r[0] for r in R.q("SELECT mention_id FROM citation_mentions m JOIN versions v USING (version_id) "
                                    "WHERE v.is_current = 1")})
    # the stable keys the Desk relies on survive a relink unchanged (experiment 47's claim, measured here)
    assert ids_after == ids_before
    # the machine has re-joined the diwans (its rule has not changed)
    assert len(R.card_members(key_value(ex.DIWAN))) == 8
    R.con.close()
    # ... and a future linker that also joins the "not the same" pair (simulated: what an under-merge rule would do)
    con = sqlite3.connect(reading)
    a, b = (key_value(k) for k in ex.NOT_SAME)
    pa, pb = (con.execute("SELECT cited_work_pk FROM cited_works WHERE cited_work_id = ?", (x,)).fetchone()[0]
              for x in (a, b))
    con.execute("UPDATE cited_work_members SET cited_work_pk = ? WHERE cited_work_pk = ?", (pa, pb))
    con.execute("UPDATE cited_works SET status = 'merged' WHERE cited_work_pk = ?", (pb,))
    con.execute("INSERT INTO merged_ids VALUES (?, ?, 'cited_work', 'merged-into', '2026-10-21', 'simulated linker "
                "join', 'link47', NULL)", (b, a))
    con.commit()
    con.close()
    r = release.build_release(pg, reading)
    assert (r["n_applied"], r["n_orphaned"], r["n_conflict"]) == (5, 0, 0)
    assert r["checks"]["fk_ok"] and r["checks"]["decisions_hold"]
    check_decisions_hold(ro(r["path"]), made)
    det = {x[0]: json.loads(x[2]) for x in apps(pg, r["release_id"])}
    assert "the machine joined them" in det[str(made["not_same"]["decision_id"])]["how"]
    Rr = ro(r["path"])
    assert Rr.q1("SELECT count(*) FROM merged_ids WHERE old_id = ?", (b,))[0] == 0, "the kept-apart card is retired"
    print(f"\n(b) link47 on a copy: {t_link:.0f} s, card/person/mention ids unchanged; release {r['release_id']} "
          f"from the relinked copy: 5/5 applied, split and «not the same» hold")


def test_c_orphaned_decision_is_detected(pg, test_dir):
    made = STATE["made"]
    d = ex.make_more(pg, ACTOR)["unresolvable"]
    pg.commit()
    reading = STATE["reading"]
    mid = key_value(ex.UNRESOLVABLE)
    new_mid = mid.replace("w203-207", "w203-208")       # a re-extraction read one more word into the note
    con = sqlite3.connect(reading)
    n = con.execute("UPDATE citation_mentions SET mention_id = ? WHERE mention_id = ?", (new_mid, mid)).rowcount
    con.commit()
    con.close()
    assert n >= 1
    r = release.build_release(pg, reading)
    assert (r["n_decisions"], r["n_applied"], r["n_orphaned"]) == (6, 5, 1)
    a = pg.execute("SELECT * FROM applications WHERE release_id = %s AND decision_id = %s",
                   (r["release_id"], d["decision_id"])).fetchone()
    assert a["status"] == "orphaned" and "not in the reading" in a["detail"]["why"]
    t = pg.execute("SELECT * FROM tasks WHERE kind = 'orphaned_decision' AND about_decision = %s",
                   (d["decision_id"],)).fetchone()
    assert t and t["state"] == "open" and t["reserved_for"] == ACTOR
    assert pg.execute("SELECT status FROM subjects WHERE subject_key = %s", (ex.UNRESOLVABLE,)).fetchone()[
        "status"] == "orphaned"
    check_decisions_hold(ro(r["path"]), made)
    # the owner re-anchors it on the new key: the orphan is superseded and the new decision applies
    nd = ops.decide(pg, ACTOR, "unresolvable", [f"mention:{new_mid}"], task=dict(t), supersedes=d["decision_id"],
                    state=ro(reading))
    pg.execute("UPDATE tasks SET state = 'answered', answered_by = %s WHERE task_id = %s", (nd["decision_id"],
                                                                                           t["task_id"]))
    pg.commit()
    r2 = release.build_release(pg, reading)
    got = {str(x["decision_id"]): x["status"] for x in pg.execute(
        "SELECT * FROM applications WHERE release_id = %s", (r2["release_id"],))}
    assert got[str(d["decision_id"])] == "superseded" and got[str(nd["decision_id"])] == "applied"
    assert r2["n_orphaned"] == 0
    assert pg.execute("SELECT status FROM subjects WHERE subject_key = %s", (f"mention:{new_mid}",)).fetchone()[
        "status"] == "live"
    # never more than 2 release copies on disk
    on_disk = sorted(p.name for p in (test_dir / "releases").glob("R*.db"))
    assert len(on_disk) == 2
    print(f"\n(c) release {r['release_id']}: the decision on a vanished mention is orphaned, a task for its owner "
          f"opened; re-anchored -> {r2['release_id']} applies it. Copies on disk: {on_disk}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

"""The two engine items left open after P1 (2026-10-21):
- a corrected back reference carries along the ibids that followed it by link47's "mention just before" rule;
- constraints are re-checked only where a decision changed something, giving the same release as checking all."""
from __future__ import annotations

import json
import os
import sqlite3

from conftest import add_actor
from desk import db, examples as ex, ops, release

ACTOR = "person:tester-engine"
# A real chain in 1635-082-003-006 (p2): footnote 26 «Ibid. P. 172» resolved to the mention just before it, then
# footnotes 27-33, all «Ibid.», resolved through it ("chain collapsed"); p1 holds another full citation.
HEAD, F1, F2 = ("1635-082-003-006|p2|w244-247|1", "1635-082-003-006|p2|w248-250|1", "1635-082-003-006|p2|w251-252|1")
NEW_TARGET = "1635-082-003-006|p1|w8-19|1"


def mention(path, mid):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c.execute("SELECT m.* FROM citation_mentions m JOIN versions v ON v.version_id = m.version_id "
                     "AND v.is_current = 1 WHERE m.mention_id = ?", (mid,)).fetchone()


def test_backref_chain_follows_a_person(pg, test_dir):
    add_actor(pg, ACTOR)
    before = [mention(db.PLATFORM_V2, m) for m in (HEAD, F1, F2)]
    target_pk = mention(db.PLATFORM_V2, NEW_TARGET)["mention_pk"]
    assert before[1]["resolve_method"] == before[2]["resolve_method"] == "previous-mention (chain collapsed)"
    assert len({b["full_mention_pk"] for b in before}) == 1 and before[0]["full_mention_pk"] != target_pk
    ops.resolve_backref(pg, ACTOR, f"mention:{HEAD}", f"mention:{NEW_TARGET}")
    pg.commit()
    r = release.build_release(pg, db.PLATFORM_V2, test_dir / "engine")
    assert r["n_applied"] == 1 and r["checks"]["decisions_hold"]
    after = [mention(r["path"], m) for m in (HEAD, F1, F2)]
    assert after[0]["full_mention_pk"] == target_pk and after[0]["resolved_by"] == "person"
    for a in after[1:]:
        assert a["full_mention_pk"] == target_pk, "an ibid after the corrected one did not follow"
        assert a["resolved_by"] == "desk-chain" and json.loads(a["resolve_evidence"])["follows"] == HEAD
    app = pg.execute("SELECT detail FROM applications WHERE release_id = %s", (r["release_id"],)).fetchone()
    chain = [f"1635-082-003-006|p2|w{a}-{a + 2}|1" for a in (248, 251, 253, 256, 259, 262, 265)]
    chain[1] = F2
    assert app["detail"]["followers"] == chain, "footnotes 27-33 should all follow footnote 26"
    for mid in chain:
        assert mention(r["path"], mid)["full_mention_pk"] == target_pk


def test_incremental_check_equals_full_check(pg, test_dir):
    # the P1 example decisions on top of the back reference above: splits, merges, not-same, person merges
    ex.make_test_a(pg, ACTOR)
    pg.commit()
    os.environ["DESK_FULL_CHECK"] = "1"
    try:
        full = release.build_release(pg, db.PLATFORM_V2, test_dir / "engine")
    finally:
        os.environ.pop("DESK_FULL_CHECK")
    fast = release.build_release(pg, db.PLATFORM_V2, test_dir / "engine")
    assert fast["fingerprint"] == full["fingerprint"]
    st = lambda rid: [(str(x["decision_id"]), x["status"]) for x in pg.execute(  # noqa: E731
        "SELECT decision_id, status FROM applications WHERE release_id = %s ORDER BY ord", (rid,))]
    assert st(fast["release_id"]) == st(full["release_id"])
    assert fast["checks"]["decisions_hold"] and full["checks"]["decisions_hold"]
    assert fast["timings"]["constraint_checks"] < full["timings"]["constraint_checks"]
    print(f"\nconstraint checks: full {full['timings']['constraint_checks']}, incremental "
          f"{fast['timings']['constraint_checks']} (decisions: {fast['n_decisions']})")

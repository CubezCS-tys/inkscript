"""The Desk's rules: decisions are append-only; ownership (owner, 2026-10-21: one key, only the owner or an admin
supersedes or reverts, notes instead of disagreement); detectors make no task for a decided subject; the queue."""
from __future__ import annotations

import hashlib

import psycopg
import pytest
from fastapi.testclient import TestClient

from conftest import add_actor
from desk import detectors, examples as ex, ops

ALICE, BOB, ADMIN = "person:alice", "person:bob", "person:admin"
CARD = "work:CF622F7PED"                   # «المقدّمة»
TOKENS = {}


@pytest.fixture(scope="module")
def client(pg):
    for a, role, skills in ((ALICE, "corrector", ["ar"]), (BOB, "corrector", ["ar", "fr"]),
                            (ADMIN, "admin", ["ar", "en", "fr"])):
        add_actor(pg, a, role, skills)
        tok = f"tok-{a}"
        pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                   (hashlib.sha256(tok.encode()).hexdigest(), a))
        TOKENS[a] = {"X-Desk-Token": tok}
    pg.commit()
    from desk.api import app
    return TestClient(app)


# ------------------------------------------------------------------ append-only
def test_decisions_are_append_only(pg, client):
    d = ops.set_work_type(pg, ALICE, "work:CK4KYP6BAX", "diwan", note="append-only test")
    pg.commit()
    with pytest.raises(psycopg.errors.RestrictViolation, match="append-only"):
        pg.execute("UPDATE decisions SET payload = '{\"type\": \"book\"}' WHERE decision_id = %s", (d["decision_id"],))
    pg.rollback()
    with pytest.raises(psycopg.errors.RestrictViolation, match="append-only"):
        pg.execute("UPDATE decisions SET note = 'changed' WHERE decision_id = %s", (d["decision_id"],))
    pg.rollback()
    with pytest.raises(psycopg.errors.RestrictViolation, match="DELETE"):
        pg.execute("DELETE FROM decisions WHERE decision_id = %s", (d["decision_id"],))
    pg.rollback()
    with pytest.raises(psycopg.errors.RestrictViolation, match="TRUNCATE"):
        pg.execute("TRUNCATE decisions CASCADE")
    pg.rollback()
    with pytest.raises(psycopg.errors.RestrictViolation, match="cannot go from"):
        pg.execute("UPDATE decisions SET status = 'proposed' WHERE decision_id = %s", (d["decision_id"],))
    pg.rollback()
    # what may change: the status, and superseded_by once (that is how a revert works)
    r = ops.revert(pg, ALICE, d["decision_id"], note="undo")
    pg.commit()
    row = pg.execute("SELECT status, superseded_by, payload FROM decisions WHERE decision_id = %s",
                     (d["decision_id"],)).fetchone()
    assert row["status"] == "superseded" and str(row["superseded_by"]) == str(r["decision_id"])
    assert row["payload"] == {"type": "diwan"}


# ------------------------------------------------------------------ ownership (replaces the two-keys test)
def test_corrector_cannot_revert_or_supersede_anothers_decision(client):
    r = client.post("/desk/api/decisions", headers=TOKENS[ALICE],
                    json=dict(op="set_work_type", subject_keys=[CARD], payload=dict(type="turath"),
                              note="Ibn Khaldun's Muqaddima is turath"))
    assert r.status_code == 200, r.text
    did = r.json()["decision_id"]
    assert r.json()["status"] == "accepted" and r.json()["review_policy_at_time"] == "single"
    r = client.post(f"/desk/api/decisions/{did}/revert", headers=TOKENS[BOB], json=dict(note="I think it's a book"))
    assert r.status_code == 403 and ALICE in r.json()["detail"]
    r = client.post("/desk/api/decisions", headers=TOKENS[BOB],
                    json=dict(op="set_work_type", subject_keys=[CARD], payload=dict(type="book"), supersedes=did))
    assert r.status_code == 403 and ALICE in r.json()["detail"]
    # nor by deciding the same question again over her decision
    r = client.post("/desk/api/decisions", headers=TOKENS[BOB],
                    json=dict(op="set_work_type", subject_keys=[CARD], payload=dict(type="book")))
    assert r.status_code == 403 and ALICE in r.json()["detail"]
    assert client.get(f"/desk/api/decisions/{did}", headers=TOKENS[BOB]).json()["status"] == "accepted"
    # the owner can supersede her own
    r = client.post("/desk/api/decisions", headers=TOKENS[ALICE],
                    json=dict(op="set_work_type", subject_keys=[CARD], payload=dict(type="book"), supersedes=did))
    assert r.status_code == 200, r.text
    assert client.get(f"/desk/api/decisions/{did}", headers=TOKENS[ALICE]).json()["status"] == "superseded"
    TOKENS["alice_decision"] = r.json()["decision_id"]


def test_admin_can_revert_anothers_decision(client):
    did = TOKENS["alice_decision"]
    r = client.post(f"/desk/api/decisions/{did}/revert", headers=TOKENS[ADMIN], json=dict(note="admin undo"))
    assert r.status_code == 200, r.text
    assert r.json()["op"] == "revert" and r.json()["supersedes"] == did and r.json()["actor_id"] == ADMIN
    d = client.get(f"/desk/api/decisions/{did}", headers=TOKENS[ALICE]).json()
    assert d["status"] == "superseded" and d["superseded_by"] == r.json()["decision_id"]
    hist = client.get(f"/desk/api/subjects/{CARD}/history", headers=TOKENS[BOB]).json()
    assert [x["op"] for x in hist["decisions"]] == ["set_work_type", "set_work_type", "revert"]


def test_note_on_someones_decision_reaches_their_me_notes(client):
    r = client.post("/desk/api/decisions", headers=TOKENS[ALICE],
                    json=dict(op="confirm_work", subject_keys=[CARD], note="one work"))
    assert r.status_code == 200, r.text
    did = r.json()["decision_id"]
    r = client.post(f"/desk/api/subjects/{CARD}/notes", headers=TOKENS[BOB],
                    json=dict(text="0596's member is an editor's preface, not the Muqaddima", decision_id=did))
    assert r.status_code == 200, r.text
    nid = r.json()["note_id"]
    mine = client.get("/desk/api/me/notes", headers=TOKENS[ALICE]).json()
    assert [n["note_id"] for n in mine] == [nid] and mine[0]["author"] == BOB and mine[0]["decision_id"] == did
    assert client.get("/desk/api/me/notes", headers=TOKENS[BOB]).json() == []
    assert client.get("/desk/api/me", headers=TOKENS[ALICE]).json()["open_notes_on_my_decisions"] == 1
    assert any(n["note_id"] == nid for n in client.get(f"/desk/api/subjects/{CARD}/notes", headers=TOKENS[ADMIN]).json())
    r = client.post(f"/desk/api/notes/{nid}/resolve", headers=TOKENS[ALICE])
    assert r.status_code == 200 and r.json()["resolved_by"] == ALICE
    assert client.get("/desk/api/me/notes", headers=TOKENS[ALICE]).json() == []


def test_gold_is_shown_to_admins_only(client):
    assert "gold" not in client.get("/desk/api/stats/overview", headers=TOKENS[ALICE]).json()
    assert "gold" in client.get("/desk/api/stats/overview", headers=TOKENS[ADMIN]).json()


# ------------------------------------------------------------------ detectors
def test_detector_makes_no_task_for_a_decided_subject(pg, client):
    pair = sorted(ex.MUQADDIMA)
    rep = detectors.run(pg)
    pg.commit()
    # 62 / 154 on the 600 alone; 67 / 291 since journal 0130 (j0130_final, 126 articles) was loaded on 2026-10-22
    # (the same on the db before the letter-fix reload and after the v3.5b-fields reload)
    # experiment 70 (2026-11-02): journal 0165 (363 articles, scan + Word route) loaded -> 93 / 609
    assert rep["work_joined_without_author"]["found"] == 93 and rep["possible_same_work"]["found"] == 609
    assert rep["byline_twin"]["found"] >= 11
    t = pg.execute("SELECT * FROM tasks WHERE kind = 'possible_same_work' AND subject_keys = %s", (pair,)).fetchone()
    assert t and t["state"] == "open" and t["machine_guess"]["op"] == "same_work"
    diwan = pg.execute("SELECT * FROM tasks WHERE kind = 'work_joined_without_author' AND subject_keys = %s",
                       ([ex.DIWAN],)).fetchone()
    assert diwan["machine_guess"]["op"] == "split_work" and diwan["priority"] > 1
    twin = pg.execute("SELECT * FROM tasks WHERE kind = 'byline_twin' AND subject_keys = %s",
                      ([ex.ALOTAIBI[1]],)).fetchone()
    assert twin["machine_guess"]["subject_keys"] == list(ex.ALOTAIBI) and twin["skills"] == ["ar", "en|fr"]
    # Bob decides the pair and the twin; the open tasks close, and a new detector run makes none for them
    ops.not_same_work(pg, BOB, *pair, note="detector test")
    ops.same_person(pg, BOB, *ex.ALOTAIBI, note="detector test")
    pg.commit()
    assert pg.execute("SELECT state FROM tasks WHERE task_id = %s", (t["task_id"],)).fetchone()["state"] == "closed"
    rep2 = detectors.run(pg)
    pg.commit()
    for kind, keys in (("possible_same_work", pair), ("byline_twin", [ex.ALOTAIBI[1]])):
        live = pg.execute("SELECT count(*) n FROM tasks WHERE kind = %s AND subject_keys = %s AND state IN "
                          "('open', 'claimed')", (kind, keys)).fetchone()["n"]
        assert live == 0, f"{kind} task came back for {keys}"
    assert rep2["possible_same_work"]["skipped_decided"] >= 1 and rep2["byline_twin"]["skipped_decided"] >= 1


# ------------------------------------------------------------------ the queue
def test_queue_claims_by_skill_and_lease(client):
    r = client.get("/desk/api/queue/next", headers=TOKENS[ALICE])        # Alice reads Arabic only
    assert r.status_code == 200
    t1 = r.json()
    assert all(s == "ar" for s in t1["skills"]) and t1["claimed_by"] == ALICE
    assert client.get("/desk/api/queue/next", headers=TOKENS[ALICE]).json()["task_id"] == t1["task_id"]  # held
    t_b = client.get("/desk/api/queue/next", headers=TOKENS[BOB]).json()
    assert t_b["task_id"] != t1["task_id"]                                  # never the same task to two people
    assert client.post(f"/desk/api/tasks/{t1['task_id']}/answer", headers=TOKENS[BOB],
                       json=dict(op="confirm_work")).status_code == 409
    assert client.post(f"/desk/api/tasks/{t1['task_id']}/skip", headers=TOKENS[ALICE]).status_code == 200
    t2 = client.get("/desk/api/queue/next", headers=TOKENS[ALICE]).json()
    assert t2["task_id"] != t1["task_id"]
    r = client.post(f"/desk/api/tasks/{t2['task_id']}/unsure", headers=TOKENS[ALICE], json=dict(note="can't tell"))
    assert r.status_code == 200
    t3 = client.get("/desk/api/queue/next", headers=TOKENS[ALICE]).json()
    assert t3["task_id"] not in (t1["task_id"], t2["task_id"])
    en = client.get("/desk/api/queue/next?lang=en", headers=TOKENS[ADMIN]).json()
    assert any("en" in s.split("|") for s in en["skills"])


# ------------------------------------------------------------------ two people disagree across subjects
def test_conflict_between_two_owners_is_never_silently_chosen(pg, client, test_dir):
    from desk import release
    split = ops.split_work(pg, ALICE, ex.DIWAN, [[f"mention:{m}" for m in ms] for _, ms in ex.DIWAN_GROUPS[:2]],
                           note="conflict test")
    g1 = f"work:{split['payload']['groups'][1]['card_id']}"     # a card the split makes (not in any release yet)
    joined = ops.same_work(pg, BOB, ex.DIWAN, g1, note="conflict test: Bob thinks they are one diwan")
    pg.commit()
    r = release.build_release(pg)
    got = {str(a["decision_id"]): a for a in pg.execute("SELECT * FROM applications WHERE release_id = %s",
                                                         (r["release_id"],))}
    assert got[str(split["decision_id"])]["status"] == "applied"           # the earlier one holds
    c = got[str(joined["decision_id"])]
    assert c["status"] == "conflict" and str(split["decision_id"]) in c["detail"]["with_decisions"]
    assert r["checks"]["decisions_hold"]
    # both owners hear about it, and Bob (the later owner) gets the task
    assert any(n["decision_id"] == str(joined["decision_id"])
               for n in client.get("/desk/api/me/notes", headers=TOKENS[BOB]).json())
    assert any(n["decision_id"] == str(split["decision_id"])
               for n in client.get("/desk/api/me/notes", headers=TOKENS[ALICE]).json())
    t = pg.execute("SELECT * FROM tasks WHERE kind = 'conflict' AND about_decision = %s",
                   (joined["decision_id"],)).fetchone()
    assert t["reserved_for"] == BOB
    # Alice cannot answer Bob's conflict task (it would supersede his decision); Bob retires his own
    assert client.post(f"/desk/api/tasks/{t['task_id']}/answer", headers=TOKENS[ALICE],
                       json=dict(op="retire")).status_code == 403
    r2 = client.post(f"/desk/api/tasks/{t['task_id']}/answer", headers=TOKENS[BOB], json=dict(op="retire"))
    assert r2.status_code == 200, r2.text
    assert client.get(f"/desk/api/decisions/{joined['decision_id']}", headers=TOKENS[BOB]).json()["status"] == \
        "superseded"

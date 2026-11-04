"""The Desk API (DESIGN §9), FastAPI, JSON, every route under /desk/api.

    .venv/bin/python -m desk.cli serve           # 127.0.0.1:8005 only

Auth (P1): one local token per actor, sent as `X-Desk-Token: <token>` (or `Authorization: Bearer <token>`); the
`tokens` table holds its sha256. Tokens are made with `python -m desk.cli actor add …` / `token …`.
TODO(P4): real accounts on the separate server — admin invitations by e-mail, a password and a second factor
(TOTP), expiring sessions, rate limits, login alerts, HTTPS (DESIGN §11). Nothing below may be exposed beyond
127.0.0.1 before that.

Review model (owner, 2026-10-21): one key — a decision is accepted when its corrector makes it; only its owner or an
admin can supersede or revert it (anyone else gets 403 naming the owner); a corrector who disagrees leaves a note.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime
from decimal import Decimal
from contextlib import contextmanager
from typing import Any

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from . import db, ops
from .keys import split_key

app = FastAPI(title="The Desk (experiment 49, P1 + P2)", version="0.2", docs_url="/desk/api/docs",
              openapi_url="/desk/api/openapi.json")
P = "/desk/api"
LEASE = "15 minutes"


@contextmanager
def pgc():
    con = db.connect()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


@app.exception_handler(ops.OpError)
def op_error(request, exc: ops.OpError):
    return JSONResponse(status_code=403 if isinstance(exc, ops.NotOwner) else 422, content=dict(detail=str(exc)))


def me(request: Request, x_desk_token: str | None = Header(default=None),
       authorization: str | None = Header(default=None), desk_token: str | None = Cookie(default=None),
       x_desk_client: str | None = Header(default=None)) -> dict:
    """The actor behind the token: from X-Desk-Token, a Bearer header, or (P2, the screens) the httpOnly cookie
    `desk_token` the web app sets at sign-in. A write that rides on the cookie must also carry `X-Desk-Client: web`
    (a page on another site cannot add that header, so it cannot make a decision in someone's name)."""
    tok = x_desk_token or (authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None)
    if not tok and desk_token:
        if request.method not in ("GET", "HEAD") and x_desk_client != "web":
            raise HTTPException(403, "a write from the browser needs the X-Desk-Client header")
        tok = desk_token
    if not tok:
        raise HTTPException(401, "send your token as X-Desk-Token")
    with pgc() as pg:
        a = pg.execute("""SELECT a.* FROM tokens t JOIN actors a USING (actor_id)
                          WHERE t.token_sha = %s AND NOT t.revoked AND a.active""",
                       (hashlib.sha256(tok.encode()).hexdigest(),)).fetchone()
    if not a:
        raise HTTPException(401, "unknown or revoked token")
    return dict(a)


def admin(actor: dict = Depends(me)) -> dict:
    if actor["role"] != "admin":
        raise HTTPException(403, "admins only")
    return actor


def jsonable(v) -> Any:
    if isinstance(v, list):
        return [jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def check_key(key: str) -> str:
    try:
        split_key(key)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return key


# ------------------------------------------------------------------ bodies
class Answer(BaseModel):
    op: str
    subject_keys: list[str] | None = None
    payload: dict = Field(default_factory=dict)
    reason_code: str | None = None
    note: str | None = None
    confidence: str = "sure"
    evidence: dict | None = None


class NewDecision(Answer):
    subject_keys: list[str]
    supersedes: str | None = None


class Text(BaseModel):
    note: str | None = None


class NoteIn(BaseModel):
    text: str
    decision_id: str | None = None


# ------------------------------------------------------------------ who am I
@app.get(f"{P}/me")
def get_me(actor: dict = Depends(me)):
    with pgc() as pg:
        st = {r["status"]: r["n"] for r in pg.execute(
            "SELECT status, count(*) n FROM decisions WHERE actor_id = %s GROUP BY 1", (actor["actor_id"],))}
        today = pg.execute("SELECT count(*) n FROM decisions WHERE actor_id = %s AND created_at > now() - interval "
                           "'1 day'", (actor["actor_id"],)).fetchone()["n"]
        claimed = pg.execute("SELECT task_id FROM tasks WHERE claimed_by = %s AND state = 'claimed' AND lease_until > "
                             "now()", (actor["actor_id"],)).fetchall()
        notes = len(ops.my_notes(pg, actor["actor_id"]))
        out = dict(actor_id=actor["actor_id"], name=actor["name"], role=actor["role"], skills=actor["skills"],
                   ui_lang=actor["ui_lang"], decisions=st, decisions_last_24h=today, open_notes_on_my_decisions=notes,
                   holding_tasks=[r["task_id"] for r in claimed])
        if actor["role"] == "admin":
            out["gold"] = ops.gold_accuracy(pg, actor["actor_id"])
    return jsonable(out)


@app.get(f"{P}/me/notes")
def get_my_notes(include_resolved: bool = False, actor: dict = Depends(me)):
    with pgc() as pg:
        return jsonable(ops.my_notes(pg, actor["actor_id"], include_resolved))


# ------------------------------------------------------------------ the queue
SKILL_MATCH = "NOT EXISTS (SELECT 1 FROM unnest(t.skills) req WHERE NOT (string_to_array(req, '|') && %(skills)s))"


@app.get(f"{P}/queue/next")
def queue_next(kind: str | None = None, lang: str | None = Query(default=None, pattern="^(ar|en|fr)$"),
               actor: dict = Depends(me)):
    """Claim the next task this person can do (their languages), highest priority first, for 15 minutes."""
    a = actor["actor_id"]
    with pgc() as pg:
        held = pg.execute("SELECT * FROM tasks WHERE claimed_by = %s AND state = 'claimed' AND lease_until > now() "
                          "AND (%s::text IS NULL OR kind = %s) ORDER BY task_id LIMIT 1", (a, kind, kind)).fetchone()
        if held:
            return jsonable(dict(held))
        t = pg.execute(f"""
            UPDATE tasks SET state = 'claimed', claimed_by = %(a)s, lease_until = now() + interval '{LEASE}',
                   updated_at = now()
            WHERE task_id = (
              SELECT t.task_id FROM tasks t
              WHERE (t.state = 'open' OR (t.state = 'claimed' AND t.lease_until < now()))
                AND NOT (%(a)s = ANY(t.excluded_actors)) AND NOT (%(a)s = ANY(t.skipped_by))
                AND (t.reserved_for IS NULL OR t.reserved_for = %(a)s OR %(admin)s)
                AND {SKILL_MATCH}
                AND (%(kind)s::text IS NULL OR t.kind = %(kind)s)
                AND (%(lang)s::text IS NULL OR EXISTS (SELECT 1 FROM unnest(t.skills) s
                                                       WHERE %(lang)s = ANY(string_to_array(s, '|'))))
              ORDER BY (t.reserved_for = %(a)s) DESC NULLS LAST, t.priority DESC, t.task_id
              LIMIT 1 FOR UPDATE SKIP LOCKED)
            RETURNING *""", dict(a=a, admin=actor["role"] == "admin", skills=list(actor["skills"]), kind=kind,
                                 lang=lang)).fetchone()
        if not t:
            return Response(status_code=204)
        ops.task_event(pg, t["task_id"], a, "claimed")
        return jsonable(dict(t))


def _task_for(pg, task_id: int, actor: dict) -> dict:
    t = pg.execute("SELECT * FROM tasks WHERE task_id = %s FOR UPDATE", (task_id,)).fetchone()
    if not t:
        raise HTTPException(404, "no such task")
    a = actor["actor_id"]
    if t["state"] == "claimed" and t["claimed_by"] != a and t["lease_until"] and \
            pg.execute("SELECT %s > now() AS live", (t["lease_until"],)).fetchone()["live"]:
        raise HTTPException(409, f"task {task_id} is held by {t['claimed_by']}")
    if t["state"] not in ("open", "claimed"):
        raise HTTPException(409, f"task {task_id} is {t['state']}")
    if t["reserved_for"] and t["reserved_for"] != a and actor["role"] != "admin":
        raise HTTPException(403, f"task {task_id} is for {t['reserved_for']} (the decision's owner) or an admin")
    return dict(t)


@app.post(f"{P}/tasks/{{task_id}}/answer")
def answer_task(task_id: int, body: Answer, actor: dict = Depends(me)):
    with pgc() as pg:
        t = _task_for(pg, task_id, actor)
        keys = body.subject_keys or t["subject_keys"]
        supersedes = t["about_decision"] if t["kind"] in ("orphaned_decision", "conflict") else None
        d = ops.decide(pg, actor["actor_id"], body.op, keys, body.payload, reason_code=body.reason_code,
                       note=body.note, confidence=body.confidence, evidence=body.evidence, task=t,
                       supersedes=supersedes, is_demo=t["is_demo"])
        pg.execute("UPDATE tasks SET state = 'answered', answered_by = %s, claimed_by = NULL, lease_until = NULL, "
                   "updated_at = now() WHERE task_id = %s", (d["decision_id"], task_id))
        ops.task_event(pg, task_id, actor["actor_id"], "answered", str(d["decision_id"]))
        return jsonable(d)


@app.post(f"{P}/tasks/{{task_id}}/skip")
def skip_task(task_id: int, body: Text | None = None, actor: dict = Depends(me)):
    """Give it back; it is not served to this person again."""
    with pgc() as pg:
        _task_for(pg, task_id, actor)
        pg.execute("UPDATE tasks SET state = 'open', claimed_by = NULL, lease_until = NULL, skipped_by = "
                   "array_append(skipped_by, %s), updated_at = now() WHERE task_id = %s", (actor["actor_id"], task_id))
        ops.task_event(pg, task_id, actor["actor_id"], "skip", body.note if body else None)
        return dict(task_id=task_id, state="open")


@app.post(f"{P}/tasks/{{task_id}}/unsure")
def unsure_task(task_id: int, body: Text | None = None, actor: dict = Depends(me)):
    """"Unsure" is an answer: the task goes to another corrector, with this person's note on the subject."""
    with pgc() as pg:
        t = _task_for(pg, task_id, actor)
        pg.execute("UPDATE tasks SET state = 'open', claimed_by = NULL, lease_until = NULL, excluded_actors = "
                   "array_append(excluded_actors, %s), updated_at = now() WHERE task_id = %s",
                   (actor["actor_id"], task_id))
        ops.task_event(pg, task_id, actor["actor_id"], "unsure", body.note if body else None)
        if body and body.note:
            ops.add_note(pg, actor["actor_id"], t["subject_keys"][0], f"unsure (task {task_id}): {body.note}",
                         is_demo=t["is_demo"])
        return dict(task_id=task_id, state="open", passed_on=True)


# ------------------------------------------------------------------ subjects
def _history(pg, key: str) -> dict:
    decs = [dict(r) for r in pg.execute("SELECT * FROM decisions WHERE %s = ANY(subject_keys) ORDER BY seq", (key,))]
    for d in decs:
        d["events"] = [dict(r) for r in pg.execute(
            "SELECT status, why, actor_id, at FROM decision_events WHERE decision_id = %s ORDER BY event_id",
            (d["decision_id"],))]
        d["applications"] = [dict(r) for r in pg.execute(
            "SELECT release_id, status, detail FROM applications WHERE decision_id = %s ORDER BY release_id",
            (d["decision_id"],))]
    notes = [dict(r) for r in pg.execute("SELECT * FROM notes WHERE subject_key = %s ORDER BY created_at", (key,))]
    tasks = [dict(r) for r in pg.execute(
        "SELECT task_id, kind, state, created_release, answered_by, created_at FROM tasks WHERE %s = ANY(subject_keys) "
        "ORDER BY task_id", (key,))]
    return dict(subject=key, decisions=decs, notes=notes, tasks=tasks)


@app.get(P + "/subjects/{key:path}/history")
def subject_history(key: str, actor: dict = Depends(me)):
    check_key(key)
    with pgc() as pg:
        return jsonable(_history(pg, key))


@app.get(P + "/subjects/{key:path}/notes")
def subject_notes(key: str, actor: dict = Depends(me)):
    check_key(key)
    with pgc() as pg:
        return jsonable([dict(r) for r in pg.execute("SELECT * FROM notes WHERE subject_key = %s ORDER BY created_at",
                                                     (key,))])


@app.post(P + "/subjects/{key:path}/notes")
def add_subject_note(key: str, body: NoteIn, actor: dict = Depends(me)):
    check_key(key)
    with pgc() as pg:
        return jsonable(ops.add_note(pg, actor["actor_id"], key, body.text, body.decision_id))


@app.get(P + "/subjects/{key:path}")
def subject(key: str, actor: dict = Depends(me)):
    """Current state (from the newest release on disk, else the machine's reading), standing decisions, open tasks."""
    check_key(key)
    with pgc() as pg:
        path = db.state_path(pg)
        R = ops.open_state(pg, path)
        try:
            state = R.describe(key)
        finally:
            R.con.close()
        sub = pg.execute("SELECT * FROM subjects WHERE subject_key = %s", (key,)).fetchone()
        return jsonable(dict(subject=key, read_from=str(path), state=state, desk=dict(sub) if sub else None,
                             standing=[dict(r) for r in ops.standing(pg, [key])],
                             open_tasks=[dict(r) for r in pg.execute(
                                 "SELECT task_id, kind, state, priority FROM tasks WHERE %s = ANY(subject_keys) AND "
                                 "state IN ('open', 'claimed')", (key,))],
                             open_notes=pg.execute("SELECT count(*) n FROM notes WHERE subject_key = %s AND "
                                                   "resolved_at IS NULL", (key,)).fetchone()["n"]))


@app.post(P + "/notes/{note_id}/resolve")
def resolve_note(note_id: int, actor: dict = Depends(me)):
    with pgc() as pg:
        return jsonable(ops.resolve_note(pg, actor["actor_id"], note_id))


# ------------------------------------------------------------------ decisions
@app.post(f"{P}/decisions")
def new_decision(body: NewDecision, actor: dict = Depends(me)):
    """A decision made outside a task (from an entity page). `supersedes` only for your own decisions (or as admin)."""
    with pgc() as pg:
        return jsonable(ops.decide(pg, actor["actor_id"], body.op, body.subject_keys, body.payload,
                                   reason_code=body.reason_code, note=body.note, confidence=body.confidence,
                                   evidence=body.evidence, supersedes=body.supersedes))


@app.get(f"{P}/decisions")
def list_decisions(actor_id: str | None = None, op: str | None = None, status: str | None = None,
                   limit: int = Query(default=50, le=500), actor: dict = Depends(me)):
    with pgc() as pg:
        return jsonable([dict(r) for r in pg.execute(
            """SELECT * FROM decisions WHERE (%(a)s::text IS NULL OR actor_id = %(a)s)
               AND (%(o)s::text IS NULL OR op = %(o)s) AND (%(s)s::text IS NULL OR status = %(s)s)
               ORDER BY seq DESC LIMIT %(n)s""", dict(a=actor_id, o=op, s=status, n=limit))])


@app.get(P + "/decisions/{decision_id}")
def get_decision(decision_id: str, actor: dict = Depends(me)):
    with pgc() as pg:
        d = pg.execute("SELECT * FROM decisions WHERE decision_id = %s", (decision_id,)).fetchone()
        if not d:
            raise HTTPException(404, "no such decision")
        d = dict(d)
        d["events"] = [dict(r) for r in pg.execute("SELECT * FROM decision_events WHERE decision_id = %s "
                                                    "ORDER BY event_id", (decision_id,))]
        d["notes"] = [dict(r) for r in pg.execute("SELECT * FROM notes WHERE decision_id = %s ORDER BY created_at",
                                                   (decision_id,))]
        d["applications"] = [dict(r) for r in pg.execute("SELECT * FROM applications WHERE decision_id = %s",
                                                          (decision_id,))]
        return jsonable(d)


@app.post(P + "/decisions/{decision_id}/revert")
def revert_decision(decision_id: str, body: Text | None = None, actor: dict = Depends(me)):
    """Owner or admin only; anyone else gets 403 naming the owner."""
    with pgc() as pg:
        return jsonable(ops.revert(pg, actor["actor_id"], decision_id, note=body.note if body else None))


# ------------------------------------------------------------------ the Overview screen and releases
@app.get(f"{P}/stats/overview")
def overview(actor: dict = Depends(me)):
    with pgc() as pg:
        q = lambda s, a=(): [dict(r) for r in pg.execute(s, a)]  # noqa: E731
        last = pg.execute("SELECT release_id, status, n_decisions, n_applied, n_superseded, n_orphaned, n_conflict, "
                          "checks->'fk_ok' fk_ok, checks->'decisions_hold' decisions_hold, fingerprint, finished_at, "
                          "counts_after FROM releases WHERE status = 'built' ORDER BY finished_at DESC LIMIT 1").fetchone()
        out = dict(
            open_tasks=q("""SELECT kind, count(*) n, round(sum(priority)::numeric, 1) priority_sum,
                            count(*) FILTER (WHERE state = 'claimed') claimed
                            FROM tasks WHERE state IN ('open', 'claimed') GROUP BY kind ORDER BY 3 DESC"""),
            decisions=q("SELECT status, count(*) n FROM decisions GROUP BY 1 ORDER BY 1"),
            decisions_today=pg.execute("SELECT count(*) n FROM decisions WHERE created_at > now() - interval '1 day'")
            .fetchone()["n"],
            decisions_by_op=q("SELECT op, count(*) n FROM decisions WHERE status = 'accepted' GROUP BY 1 ORDER BY 2 DESC"),
            orphaned_subjects=pg.execute("SELECT count(*) n FROM subjects WHERE status = 'orphaned'").fetchone()["n"],
            open_notes=pg.execute("SELECT count(*) n FROM notes WHERE resolved_at IS NULL").fetchone()["n"],
            last_release=dict(last) if last else None,
            review_rules=q("SELECT rule, count(*) n FROM review_rules GROUP BY 1"))
        if actor["role"] == "admin":
            out["gold"] = ops.gold_accuracy(pg)
        return jsonable(out)


@app.get(f"{P}/releases")
def releases(actor: dict = Depends(me)):
    with pgc() as pg:
        return jsonable([dict(r) for r in pg.execute(
            "SELECT release_id, status, reading_path, path, copy_deleted_at, n_decisions, n_applied, n_superseded, "
            "n_orphaned, n_conflict, fingerprint, timings, started_at, finished_at, note, is_demo FROM releases "
            "ORDER BY started_at DESC")])


@app.get(P + "/releases/{release_id}")
def release(release_id: str, actor: dict = Depends(me)):
    with pgc() as pg:
        r = pg.execute("SELECT * FROM releases WHERE release_id = %s", (release_id,)).fetchone()
        if not r:
            raise HTTPException(404, "no such release")
        r = dict(r)
        r["applications"] = [dict(x) for x in pg.execute(
            "SELECT a.*, d.op, d.subject_keys, d.actor_id FROM applications a JOIN decisions d USING (decision_id) "
            "WHERE release_id = %s ORDER BY ord", (release_id,))]
        return jsonable(r)


# ================================================================== P2: what the screens read and do
# Read routes read the newest release copy on disk, else platform_v2.db, always read-only (desk/pages.py). Each
# answer carries the subject key, so a page can show its History and Notes, and the standing decisions on it with
# their owners (a non-owner gets "Leave a note", an admin "Fix").
import threading  # noqa: E402
import time  # noqa: E402

from . import pages as pg_pages  # noqa: E402
from . import crops as pg_crops  # noqa: E402


def _desk(pg, keys: list[str]) -> dict:
    keys = [k for k in keys if k]
    return dict(
        standing=[dict(r) for r in pg.execute(
            "SELECT decision_id, op, subject_keys, payload, note, actor_id, role_at_time, created_at, status, "
            "confidence, task_id FROM decisions WHERE subject_keys && %s AND status IN ('proposed', 'accepted') "
            "AND op NOT IN ('revert', 'retire') ORDER BY seq DESC", (keys,))],
        open_tasks=[dict(r) for r in pg.execute(
            "SELECT task_id, kind, state, priority, claimed_by FROM tasks WHERE subject_keys && %s "
            "AND state IN ('open', 'claimed') ORDER BY priority DESC", (keys,))],
        open_notes=pg.execute("SELECT count(*) n FROM notes WHERE subject_key = ANY(%s) AND resolved_at IS NULL",
                              (keys,)).fetchone()["n"])


def _state(pg):
    path, rid = pg_pages.state_of(pg)
    return path, dict(read_from=str(path), release_id=rid)


@app.get(f"{P}/articles")
def articles(q: str | None = None, limit: int = Query(default=50, ge=1, le=5000), actor: dict = Depends(me)):
    """Search articles by title (printed, catalogue, translated) or author, with platform v2's Arabic folding. Each row
    carries its journal and whether it was built from the publisher's Word file; `total` is the number of articles in
    the state (experiment 73: the list said 700, the API's old limit, of 1,143)."""
    from . import index_pages as IX
    with pgc() as pg:
        path, st = _state(pg)
    rows = pg_pages.search_articles(path, q, limit)
    B = IX._base(path)
    for a in rows:
        p = B["pubs"].get(a.get("pub_id")) or {}
        a.update(journal_id=p.get("journal_id"), journal=B["jname"].get(p.get("journal_id")),
                 word_route=(p.get("run") or "").startswith("w"))
    return jsonable(dict(st, q=q, articles=rows, total=len(pg_pages._index(path)["articles"])))


@app.get(P + "/articles/{stem}")
def article(stem: str, actor: dict = Depends(me)):
    with pgc() as pg:
        path, st = _state(pg)
        a = pg_pages.article(path, stem)
        if not a:
            raise HTTPException(404, "no such article in the reading")
        keys, prefixes = pg_pages.article_keys(a)
        a.update(st)
        a["desk"] = _desk(pg, [a["subject"]])
        a["decisions"] = [dict(r) for r in pg.execute(
            """SELECT decision_id, op, subject_keys, payload, note, actor_id, role_at_time, created_at, status, confidence
               FROM decisions WHERE op NOT IN ('revert', 'retire') AND (subject_keys && %s OR EXISTS (
                 SELECT 1 FROM unnest(subject_keys) k WHERE k LIKE %s OR k LIKE %s)) ORDER BY seq DESC LIMIT 200""",
            (keys, prefixes[0].replace("_", r"\_") + "%", prefixes[1].replace("_", r"\_") + "%"))]
    return jsonable(a)


@app.get(P + "/articles/{stem}/history")
def article_history(stem: str, actor: dict = Depends(me)):
    """Every decision touching this article (its citations, bylines, the cards and persons it shows) and the notes
    on the article itself."""
    check_key(f"article:{stem}")
    with pgc() as pg:
        path, st = _state(pg)
        a = pg_pages.article(path, stem)
        if not a:
            raise HTTPException(404, "no such article in the reading")
        keys, prefixes = pg_pages.article_keys(a)
        decs = [dict(r) for r in pg.execute(
            """SELECT * FROM decisions WHERE subject_keys && %s OR EXISTS (
                 SELECT 1 FROM unnest(subject_keys) k WHERE k LIKE %s OR k LIKE %s) ORDER BY seq""",
            (keys, prefixes[0] + "%", prefixes[1] + "%"))]
        h = _history(pg, a["subject"])
        h["decisions"] = decs
        return jsonable(h)


def _pending_work(pg, cid: str) -> dict | None:
    pend = ops.pending_cards(pg)
    if cid not in pend:
        return None
    R = ops.open_state(pg)
    try:
        members = []
        for m in pend[cid]:
            r = R.mention(m)
            members.append(dict(key=f"mention:{m}", mention_id=m, stem=r["stem"] if r else None,
                                page=r["page"] if r else None, printed=r["printed"] if r else None,
                                anchor=r["anchor_key"] if r else None, authors=[]))
    finally:
        R.con.close()
    return dict(id=cid, subject=f"work:{cid}", status="pending build", title=None, members=members, authors=[],
                citing=[], links=[], relations=[], merged_from=[], n_citing_pubs=None, n_mentions=None, pending=True)


@app.get(P + "/works/{cid}")
def work_page(cid: str, actor: dict = Depends(me)):
    check_key(f"work:{cid}")
    with pgc() as pg:
        path, st = _state(pg)
        w = pg_pages.work(path, cid) or _pending_work(pg, cid)
        if not w:
            raise HTTPException(404, "no such cited work in the reading")
        w.update(st)
        w["desk"] = _desk(pg, [f"work:{cid}", w["subject"]])
    return jsonable(w)


@app.get(P + "/persons/{pid}")
def person_page(pid: str, actor: dict = Depends(me)):
    check_key(f"person:{pid}")
    with pgc() as pg:
        path, st = _state(pg)
        p = pg_pages.person(path, pid)
        if not p:
            raise HTTPException(404, "no such person in the reading")
        p.update(st)
        p["desk"] = _desk(pg, [f"person:{pid}", p["subject"]] + [b["key"] for w in p["works"] for b in w["bylines"]])
    return jsonable(p)


@app.get(f"{P}/top/works")
def top_works(limit: int = Query(default=30, ge=1, le=200), actor: dict = Depends(me)):
    """The most-cited works, by citing articles (then mentions, «المرجع السابق» included)."""
    with pgc() as pg:
        path, st = _state(pg)
    return jsonable(dict(st, works=pg_pages.top_works(path, limit)))


@app.get(f"{P}/search")
def search(q: str = Query(min_length=1, max_length=200), limit: int = Query(default=20, ge=1, le=100),
           actor: dict = Depends(me)):
    with pgc() as pg:
        path, st = _state(pg)
    return jsonable(dict(st, **pg_pages.search(path, q, limit)))


@app.get(f"{P}/evidence/crop")
def evidence_crop(stem: str = Query(pattern=r"^[0-9A-Za-z][0-9A-Za-z,\-]{2,60}$"), page: int = Query(ge=1, le=2000),
                  lines: str | None = Query(default=None, max_length=1200),
                  block: str | None = Query(default=None, max_length=20),
                  anchor: str | None = Query(default=None, max_length=200), wide: bool = False,
                  actor: dict = Depends(me)):
    """A JPEG of ALTO lines (lines=p3b6l1,p3b6l2), a block (block=p3b6) or an ink anchor (anchor=<stem>|p3|w5-9)
    from the page image; stem and page are checked against the reading; cached under DESK_CROPS."""
    with pgc() as pg:
        path, _ = _state(pg)
    con = pg_pages.open_ro(path)
    try:
        data, name = pg_crops.crop(con, stem, page, lines=lines, block=block, anchor=anchor, full_width=wide)
    except pg_crops.CropError as e:
        raise HTTPException(e.status, str(e))
    finally:
        con.close()
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=86400", "ETag": name})


# ------------------------------------------------------------------ notes I wrote, task kinds
@app.get(f"{P}/me/notes/written")
def my_written_notes(include_resolved: bool = True, actor: dict = Depends(me)):
    with pgc() as pg:
        return jsonable([dict(r) for r in pg.execute(
            """SELECT n.*, d.op, d.actor_id AS decision_owner FROM notes n LEFT JOIN decisions d USING (decision_id)
               WHERE n.author = %s AND (%s OR n.resolved_at IS NULL) ORDER BY n.created_at DESC LIMIT 300""",
            (actor["actor_id"], include_resolved))])


@app.get(f"{P}/stats/kinds")
def stats_kinds(actor: dict = Depends(me)):
    """Per task kind: open, held, answered (all, mine), and median seconds from claim to answer."""
    with pgc() as pg:
        return jsonable([dict(r) for r in pg.execute(
            """WITH ans AS (
                 SELECT t.kind, e.actor_id, extract(epoch FROM e.at - (
                   SELECT max(c.at) FROM task_events c WHERE c.task_id = e.task_id AND c.event = 'claimed'
                     AND c.actor_id = e.actor_id AND c.at <= e.at)) s
                 FROM task_events e JOIN tasks t USING (task_id) WHERE e.event = 'answered')
               SELECT t.kind, count(*) FILTER (WHERE t.state = 'open') open,
                      count(*) FILTER (WHERE t.state = 'claimed') claimed,
                      count(*) FILTER (WHERE t.state = 'answered') answered,
                      (SELECT count(*) FROM ans WHERE ans.kind = t.kind AND ans.actor_id = %s) answered_by_me,
                      (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY s) FROM ans WHERE ans.kind = t.kind) median_s,
                      round(sum(t.priority) FILTER (WHERE t.state IN ('open', 'claimed'))::numeric, 1) priority_open
               FROM tasks t GROUP BY t.kind ORDER BY priority_open DESC NULLS LAST""", (actor["actor_id"],))])


# ------------------------------------------------------------------ releases: before / after, and building one
def _summary_for(pg, label: str) -> dict:
    if label == "reading":
        return pg_pages.summarize(db.reading_path(), "reading")
    s = pg_pages.load_summary(label)
    if s:
        return s
    r = pg.execute("SELECT path, copy_deleted_at FROM releases WHERE release_id = %s AND status = 'built'",
                   (label,)).fetchone()
    if not r:
        raise HTTPException(404, f"no built release {label}")
    from pathlib import Path
    if r["copy_deleted_at"] or not r["path"] or not Path(r["path"]).exists():
        raise HTTPException(410, f"release {label}'s copy was deleted before it was summarised; compare newer ones")
    return pg_pages.summarize(Path(r["path"]), label)


@app.get(P + "/releases/{release_id}/diff")
def release_diff(release_id: str, vs: str | None = Query(default=None, max_length=40),
                 top: int = Query(default=30, ge=5, le=100), actor: dict = Depends(me)):
    """What changed between two releases (default: this one against the one built before it, else the machine's
    reading): the top-cited list before and after, cards split, merged or moved, persons merged."""
    with pgc() as pg:
        if not pg_pages.RELEASE_ID.fullmatch(release_id):
            raise HTTPException(422, "bad release id")
        if vs is None:
            prev = pg.execute("""SELECT release_id FROM releases WHERE status = 'built' AND finished_at < (
                                   SELECT finished_at FROM releases WHERE release_id = %s) ORDER BY finished_at DESC""",
                              (release_id,)).fetchall()
            vs = "reading"
            for p in prev:
                if pg_pages.load_summary(p["release_id"]) or pg.execute(
                        "SELECT 1 FROM releases WHERE release_id = %s AND copy_deleted_at IS NULL",
                        (p["release_id"],)).fetchone():
                    vs = p["release_id"]
                    break
        elif vs != "reading" and not pg_pages.RELEASE_ID.fullmatch(vs):
            raise HTTPException(422, "vs must be a release id or 'reading'")
        a, b = _summary_for(pg, vs), _summary_for(pg, release_id)
        rel = {r["release_id"]: dict(r) for r in pg.execute(
            "SELECT release_id, finished_at, n_applied, n_decisions, n_orphaned, n_conflict, note FROM releases "
            "WHERE release_id = ANY(%s)", ([vs, release_id],))}
    d = pg_pages.diff(a, b, top)
    d["releases"] = rel
    return jsonable(d)


BUILD: dict = dict(running=False)
_build_lock = threading.Lock()


class BuildIn(BaseModel):
    note: str | None = None
    run_detectors: bool = True


def _summarize_on_disk(pg) -> None:
    from pathlib import Path
    for r in pg.execute("SELECT release_id, path FROM releases WHERE status = 'built' AND copy_deleted_at IS NULL "
                        "AND path IS NOT NULL").fetchall():
        if not pg_pages.load_summary(r["release_id"]) and Path(r["path"]).exists():
            pg_pages.summarize(Path(r["path"]), r["release_id"])
    pg_pages.summarize(db.reading_path(), "reading")


def _run_build(actor_id: str, note: str | None, run_detectors: bool) -> None:
    import resource
    t0 = time.time()
    try:
        from . import detectors, release
        with db.connect() as pg:
            _summarize_on_disk(pg)       # before pruning can delete the oldest copy
            BUILD["phase"] = "building"
            r = release.build_release(pg, note=f"built from the Desk by {actor_id}" + (f": {note}" if note else ""))
            BUILD.update(release_id=r["release_id"], n_applied=r["n_applied"], n_decisions=r["n_decisions"],
                         n_orphaned=r["n_orphaned"], n_conflict=r["n_conflict"], phase="summarising")
            from pathlib import Path
            pg_pages.summarize(Path(r["path"]), r["release_id"])
            if run_detectors:
                BUILD["phase"] = "detectors"
                BUILD["detectors"] = detectors.run(pg, r["path"], release_id=r["release_id"])
                pg.commit()
        BUILD["error"] = None
    except Exception as e:  # noqa: BLE001  (shown on the Releases page)
        BUILD["error"] = f"{type(e).__name__}: {e}"
    finally:
        BUILD.update(running=False, phase="done", finished_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                     seconds=round(time.time() - t0, 1),
                     peak_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024))
        _build_lock.release()


@app.post(f"{P}/releases", status_code=202)
def build_release(body: BuildIn | None = None, actor: dict = Depends(admin)):
    """An admin builds a release from the screens: release.py's build in a background thread, one at a time
    (409 while one runs), then the detectors on it. At most 2 copies stay on disk (release.py prunes)."""
    if not _build_lock.acquire(blocking=False):
        raise HTTPException(409, "a release is being built; wait for it")
    try:
        with pgc() as pg:
            if pg.execute("SELECT 1 FROM releases WHERE status = 'building' AND started_at > now() - interval '30 min'"
                          ).fetchone():
                raise HTTPException(409, "a release is being built elsewhere (the command line); wait for it")
    except Exception:
        _build_lock.release()
        raise
    body = body or BuildIn()
    BUILD.clear()
    BUILD.update(running=True, phase="starting", by=actor["actor_id"], note=body.note,
                 started_at=time.strftime("%Y-%m-%d %H:%M:%S"), release_id=None, error=None)
    threading.Thread(target=_run_build, args=(actor["actor_id"], body.note, body.run_detectors), daemon=True,
                     name="desk-release").start()
    return dict(BUILD)


@app.get(f"{P}/build")
def build_status(actor: dict = Depends(me)):
    return jsonable(dict(BUILD))


@app.get(f"{P}/state")
def state(actor: dict = Depends(me)):
    """Which state the pages read (the newest release copy on disk, else the reading), and how many articles."""
    with pgc() as pg:
        path, st = _state(pg)
    return jsonable(dict(st, n_articles=len(pg_pages.search_articles(path, None, 100000))))


# the article beside its scan, and every field of an article (desk/article_api.py, 2026-10-23)
from . import article_api  # noqa: E402
app.include_router(article_api.router)


# the index pages: overview, journals, institutions, author records, most cited (desk/index_api.py, 2026-10-23)
from . import index_api  # noqa: E402
app.include_router(index_api.router)


# the Explorer: every field of articles, references, authors, institutions, journals and cited works, sortable,
# filterable, exportable (desk/explore.py, desk/explore_routes.py, 2026-10-23)
from . import explore_routes  # noqa: E402
app.include_router(explore_routes.router)


# the field guide: how every Explorer field is collected, and people's reviews of its label (desk/field_guide.py,
# /how-we-collect, 2026-10-23)
from . import field_guide  # noqa: E402
app.include_router(field_guide.router)


# the librarian: the AI curator's institution decisions (experiment 56), a sample for the owner to check (yes / no /
# unsure, append-only librarian_verdicts); proposals only, nothing applied (desk/librarian.py, /librarian, 2026-10-23)
from . import librarian  # noqa: E402
app.include_router(librarian.router)


# the project page: the Web-of-Science project at a glance, from desk/project/project.json (desk/project.py, /project,
# 2026-10-26)
from . import project  # noqa: E402
app.include_router(project.router)


# how a page is read: one page through the pipeline, stage by stage, for the /pipeline walk-through (desk/pipeline.py,
# 2026-10-30)
from . import pipeline  # noqa: E402
app.include_router(pipeline.router)


# nothing lost: where every printed line and every answer value ends up (experiment 61; desk/audit.py, /audit,
# 2026-11-02)
from . import audit  # noqa: E402
app.include_router(audit.router)


# the plan: a timeline of the project's work, read from desk/plan/plan.json (written by desk/plan_cli.py) plus live
# releases, deploys and heartbeats (desk/plan.py, /plan, 2026-11-02)
from . import plan  # noqa: E402
app.include_router(plan.router)


# the cited-works librarian: the AI curator's work decisions (experiment 62), checked automatically (blind second
# judgement, adjudication, consistency checks); a few escalated cases take Yes / No / Unsure (append-only
# librarian_works_verdicts); proposals only (desk/librarian_works.py, /librarian/works, 2026-11-02)
from . import librarian_works  # noqa: E402
app.include_router(librarian_works.router)


# the headline numbers every show page quotes, from one place (experiment 73; desk/headlines.py, 2026-11-03)
from . import headlines  # noqa: E402
app.include_router(headlines.router)

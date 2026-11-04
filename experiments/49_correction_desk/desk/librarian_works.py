"""The cited-works librarian (experiment 62, 2026-11-02): the AI curator's pass over the cited-work cards of the 780
articles, shown with its automatic verification. Experiment 67 applied the kinds the owner chose (2026-11-02).

Experiment 56 asked the owner to check a sample of 30. Here the check is automatic: a blind second judgement of a
stratified random sample, every disagreement adjudicated against the print, hard consistency checks, and a measured
precision per decision kind. The page shows those results and only the few cases left for the owner (escalated:
genuinely disputed, or a policy that moves many counts), with Yes / No / Unsure on those alone. Verdicts are rows of
the append-only table `librarian_works_verdicts`, made here (idempotent) so the shared schema is not touched.

Files read (from LIBRARIAN62_DIR, default experiments/62_librarian_works/out), cached by mtime:
    decisions62.jsonl   every decision, append-only (latest per `qkey`)
    numbers62.json      before / after on the 780 articles and gate 1
    precision62.json    measured precision per kind (blind check + adjudication), the APPLY rule
    blind62_adjudication.json  the disagreements of round 1, adjudicated; blind62b_adjudication.json round 2 (if any)
    checks62.json       the hard consistency checks
    rules62.json        the rules learned, with how many decisions each reproduces
    scale62.json        the scale report
    recall62.json, blocking62.json  how much the blocking misses
    escalate62.json     the cases left for the owner

    GET  /desk/api/librarian/works                          everything above, escalations with their latest verdicts
    GET  /desk/api/librarian/works/decisions?level=&kind=&confidence=&basis=&q=&offset=&limit=
    GET  /desk/api/librarian/works/decisions/{decision_id}  one decision (and the decisions it superseded)
    POST /desk/api/librarian/works/verdicts                 {decision_id, verdict: yes|no|unsure, comment?} (escalated only)
    GET  /desk/api/librarian/works/verdicts?decision_id=    every verdict on one decision, oldest first
"""
from __future__ import annotations

import json
import os
import re
import threading
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .api import P, jsonable, me, pgc

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "62_librarian_works" / "out"
DECISION_ID = re.compile(r"D62-[0-9a-f]{12}")
VERDICTS = ("yes", "no", "unsure")
LEVELS = ("pair", "card", "catalogue")
KINDS = ("same_work", "edition_of", "part_of", "different_work", "unsure", "split_card", "card_ok", "not_a_work",
         "links_to_publication", "relation", "no_link")
BASES = ("rule", "catalogue", "world", "context", "judgement")
B = f"{P}/librarian/works"

DDL = """
CREATE TABLE IF NOT EXISTS librarian_works_verdicts (
  verdict_id      bigserial PRIMARY KEY,
  decision_id     text NOT NULL CHECK (decision_id ~ '^D62-[0-9a-f]{12}$'),
  verdict         text NOT NULL CHECK (verdict IN ('yes', 'no', 'unsure')),
  comment         text CHECK (comment IS NULL OR length(comment) <= 4000),
  escalated       boolean NOT NULL DEFAULT true,
  author          text NOT NULL REFERENCES actors(actor_id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  is_demo         boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS librarian_works_verdicts_decision ON librarian_works_verdicts (decision_id, created_at);
CREATE OR REPLACE FUNCTION librarian_works_verdicts_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'librarian_works_verdicts is append-only: write a new verdict instead' USING ERRCODE = 'restrict_violation';
END $$;
DROP TRIGGER IF EXISTS librarian_works_verdicts_no_update ON librarian_works_verdicts;
CREATE TRIGGER librarian_works_verdicts_no_update BEFORE UPDATE OR DELETE ON librarian_works_verdicts
  FOR EACH ROW EXECUTE FUNCTION librarian_works_verdicts_append_only();
DROP TRIGGER IF EXISTS librarian_works_verdicts_no_truncate ON librarian_works_verdicts;
CREATE TRIGGER librarian_works_verdicts_no_truncate BEFORE TRUNCATE ON librarian_works_verdicts
  FOR EACH STATEMENT EXECUTE FUNCTION refuse_truncate();
"""

router = APIRouter()
_ready: set = set()
_cache: dict = {}
_lock = threading.Lock()


def lib_dir() -> Path:
    return Path(os.environ.get("LIBRARIAN62_DIR", str(DEFAULT_DIR)))


def _ensure_table(pg) -> None:
    """Once per schema (tests use scratch schemas): create the verdicts table if it is not there."""
    schema = pg.execute("SELECT current_schema() AS s").fetchone()["s"]
    if schema in _ready:
        return
    if pg.execute("SELECT to_regclass('librarian_works_verdicts') AS t").fetchone()["t"] is None:
        pg.execute(DDL)
        pg.commit()
    _ready.add(schema)


def _load(name: str, kind: str = "json"):
    f = lib_dir() / name
    if not f.exists():
        return None
    key = (str(f), f.stat().st_mtime)
    with _lock:
        if _cache.get(name, (None,))[0] == key:
            return _cache[name][1]
    if kind == "jsonl":
        val = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        val = json.loads(f.read_text(encoding="utf-8"))
    with _lock:
        _cache[name] = (key, val)
    return val


def decisions() -> list[dict]:
    """The standing decisions: the newest per question, in file order."""
    latest: dict = {}
    for d in _load("decisions62.jsonl", "jsonl") or []:
        latest[d.get("qkey") or d["decision_id"]] = d
    return list(latest.values())


def _by_id() -> dict:
    return {d["decision_id"]: d for d in (_load("decisions62.jsonl", "jsonl") or [])}


def _escalated() -> list[dict]:
    return (_load("escalate62.json") or {}).get("cases", [])


def _summary(d: dict) -> dict:
    keep = ("decision_id", "qkey", "level", "kind", "question", "decision", "reason", "confidence", "basis", "trivial",
            "printed", "subject_keys", "evidence_ids", "made_at", "supersedes", "found_while_judging")
    return {k: d.get(k) for k in keep if k in d}


def latest_verdicts(pg) -> dict:
    rows = pg.execute("""SELECT DISTINCT ON (v.decision_id) v.*, a.name AS author_name,
                           (SELECT count(*) FROM librarian_works_verdicts x WHERE x.decision_id = v.decision_id) AS n_verdicts
                         FROM librarian_works_verdicts v JOIN actors a ON a.actor_id = v.author
                         ORDER BY v.decision_id, v.created_at DESC, v.verdict_id DESC""").fetchall()
    return {r["decision_id"]: dict(r) for r in rows}


def _check_id(decision_id: str) -> None:
    if not DECISION_ID.fullmatch(decision_id):
        raise HTTPException(422, "a decision id is 'D62-' + 12 hex digits")


@router.get(B)
def overview(actor: dict = Depends(me)):
    ds = decisions()
    with pgc() as pg:
        _ensure_table(pg)
        lv = latest_verdicts(pg)
    esc = [dict(c, verdict=lv.get(c.get("decision_id"))) for c in _escalated()]
    checks = _load("checks62.json") or {}
    return jsonable(dict(
        numbers=_load("numbers62.json"), precision=_load("precision62.json"),
        blind=[x for x in (_load("blind62_adjudication.json"), _load("blind62b_adjudication.json")) if x],
        checks=dict(by_check=checks.get("by_check"), findings=(checks.get("findings") or [])[:40]),
        rules=(_load("rules62.json") or {}).get("rules"), scale=_load("scale62.json"), recall=_load("recall62.json"),
        blocking=_load("blocking62.json"), escalated=esc,
        counts=dict(total=len(ds), by_level=dict(Counter(d["level"] for d in ds)),
                    by_kind=dict(Counter(f"{d['level']}:{d['kind']}" for d in ds)),
                    by_confidence=dict(Counter(d.get("confidence") or "none" for d in ds)),
                    by_basis=dict(Counter(d.get("basis") or "none" for d in ds)),
                    trivial=sum(1 for d in ds if d.get("trivial")),
                    superseded=len(_load("decisions62.jsonl", "jsonl") or []) - len(ds)),
        applied="partly",
        note="Applied on 2026-11-02 (experiment 67) as decisions of agent:librarian, under the owner's APPLY rule and "
             "rules D40-D44: same work, editions, splits, one work, not a work, relations, part of, and the 696 links "
             "passing rule K1c. Still proposals here: the other 217 links, different works, no link, every unsure."))


@router.get(f"{B}/decisions")
def list_decisions(level: str | None = Query(default=None, pattern=r"^(pair|card|catalogue)$"),
                   kind: str | None = Query(default=None, max_length=40),
                   confidence: str | None = Query(default=None, pattern=r"^(high|medium|low)$"),
                   basis: str | None = Query(default=None, pattern=r"^(rule|catalogue|world|context|judgement)$"),
                   q: str | None = Query(default=None, max_length=200),
                   offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=500),
                   actor: dict = Depends(me)):
    if kind and kind not in KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(KINDS)}")
    rows = decisions()
    if level:
        rows = [d for d in rows if d["level"] == level]
    if kind:
        rows = [d for d in rows if d["kind"] == kind]
    if confidence:
        rows = [d for d in rows if d.get("confidence") == confidence]
    if basis:
        rows = [d for d in rows if d.get("basis") == basis]
    if q:
        ql = q.strip().lower()
        rows = [d for d in rows if ql in json.dumps(_summary(d), ensure_ascii=False).lower()]
    return jsonable(dict(total=len(rows), offset=offset, limit=limit,
                         rows=[_summary(d) for d in rows[offset:offset + limit]]))


@router.get(f"{B}/decisions/{{decision_id}}")
def get_decision(decision_id: str, actor: dict = Depends(me)):
    _check_id(decision_id)
    by = _by_id()
    d = by.get(decision_id)
    if not d:
        raise HTTPException(404, "no such librarian decision")
    chain, x = [], d
    while x.get("supersedes") and x["supersedes"] in by and len(chain) < 20:
        x = by[x["supersedes"]]
        chain.append(_summary(x))
    with pgc() as pg:
        _ensure_table(pg)
        vs = pg.execute("""SELECT v.*, a.name AS author_name FROM librarian_works_verdicts v
                           JOIN actors a ON a.actor_id = v.author
                           WHERE v.decision_id = %s ORDER BY v.created_at, v.verdict_id""", (decision_id,)).fetchall()
    standing = {s["decision_id"] for s in decisions()}
    return jsonable(dict(_summary(d), standing=decision_id in standing, superseded=chain,
                         escalated=decision_id in {c.get("decision_id") for c in _escalated()},
                         verdicts=[dict(v) for v in vs]))


class VerdictIn(BaseModel):
    decision_id: str = Field(max_length=20)
    verdict: str
    comment: str | None = Field(default=None, max_length=4000)


@router.post(f"{B}/verdicts")
def add_verdict(body: VerdictIn, actor: dict = Depends(me)):
    _check_id(body.decision_id)
    if body.verdict not in VERDICTS:
        raise HTTPException(422, f"verdict must be one of {', '.join(VERDICTS)}")
    if body.decision_id not in _by_id():
        raise HTTPException(404, "no such librarian decision")
    if body.decision_id not in {c.get("decision_id") for c in _escalated()}:
        raise HTTPException(409, "only the escalated cases take a verdict here; the rest are checked automatically")
    comment = (body.comment or "").strip() or None
    with pgc() as pg:
        _ensure_table(pg)
        r = pg.execute("""INSERT INTO librarian_works_verdicts (decision_id, verdict, comment, escalated, author, is_demo)
                          VALUES (%s, %s, %s, true, %s, %s) RETURNING *""",
                       (body.decision_id, body.verdict, comment, actor["actor_id"], bool(actor.get("is_demo")))).fetchone()
    return jsonable(dict(r, author_name=actor.get("name")))


@router.get(f"{B}/verdicts")
def get_verdicts(decision_id: str = Query(max_length=20), actor: dict = Depends(me)):
    _check_id(decision_id)
    with pgc() as pg:
        _ensure_table(pg)
        rows = pg.execute("""SELECT v.*, a.name AS author_name FROM librarian_works_verdicts v
                             JOIN actors a ON a.actor_id = v.author
                             WHERE v.decision_id = %s ORDER BY v.created_at, v.verdict_id""", (decision_id,)).fetchall()
    return jsonable([dict(r) for r in rows])

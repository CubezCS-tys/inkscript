"""The librarian (experiment 56, 2026-10-23): the AI curator's first pass over institutions, shown for the owner to check.

The librarian's decisions are proposals kept by experiment 56 (an append-only JSONL, newest answer per question wins);
nothing here applies them to the platform or a release. The owner reviews a stratified random sample of 30 and says
yes / no / unsure for each; those verdicts are rows of the append-only table `librarian_verdicts` (schema.sql).

Files read (from LIBRARIAN_DIR, default experiments/56_librarian_institutions/out), cached by mtime:
    decisions56.jsonl   every decision, append-only (latest per `qkey`; kind 'retired' withdraws a question)
    sample56.json       the 30 sampled decisions with their evidence (printed forms, where they sit on the scan)
    numbers56.json      before / after numbers on the 780 articles and gate 1
    rules56.json        the rules learned, with how many decisions each reproduces
    scale56.json        the scale report (tokens per packet, estimates)
    packets56.jsonl     the evidence packets (for one decision's full evidence)

    GET  /desk/api/librarian                          numbers, counts, rules, scale, the sample with latest verdicts
    GET  /desk/api/librarian/decisions?kind=&confidence=&level=&basis=&q=&offset=&limit=
    GET  /desk/api/librarian/decisions/{decision_id}  one decision with its evidence packets and verdicts
    POST /desk/api/librarian/verdicts                 {decision_id, verdict: yes|no|unsure, comment?}
    GET  /desk/api/librarian/verdicts?decision_id=    every verdict on one decision, oldest first
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

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "56_librarian_institutions" / "out"
DECISION_ID = re.compile(r"D56-[0-9a-f]{12}")
VERDICTS = ("yes", "no", "unsure")
KINDS = ("affiliation_institution", "unit_kept_apart", "not_an_institution", "unsure", "same_institution",
         "not_same_institution", "set_country", "set_parent", "set_type")

router = APIRouter()
_ensured = threading.Event()
_cache: dict = {}
_lock = threading.Lock()


def lib_dir() -> Path:
    return Path(os.environ.get("LIBRARIAN_DIR", str(DEFAULT_DIR)))


def _ensure_table(pg) -> None:
    """Made by `desk.cli init` (schema.sql's idempotent tail); run once here too for a Desk started before that."""
    if _ensured.is_set():
        return
    from . import db
    pg.execute(db.upgrades_sql())
    pg.commit()
    _ensured.set()


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
    """The standing decisions: the newest per question, retired questions left out, in file order."""
    rows = _load("decisions56.jsonl", "jsonl") or []
    latest: dict = {}
    for d in rows:
        latest[d.get("qkey") or d["decision_id"]] = d
    return [d for d in latest.values() if d.get("kind") != "retired"]


def _by_id() -> dict:
    rows = _load("decisions56.jsonl", "jsonl") or []
    return {d["decision_id"]: d for d in rows}


def _packets() -> dict:
    return {p["key"]: p for p in (_load("packets56.jsonl", "jsonl") or [])}


def _summary(d: dict) -> dict:
    keep = ("decision_id", "level", "kind", "question", "decision", "reason", "confidence", "basis", "trivial",
            "printed", "stem", "subject_keys", "evidence_ids", "made_at", "supersedes", "fix")
    return {k: d.get(k) for k in keep if k in d}


def latest_verdicts(pg) -> dict:
    rows = pg.execute("""SELECT DISTINCT ON (v.decision_id) v.*, a.name AS author_name,
                           (SELECT count(*) FROM librarian_verdicts x WHERE x.decision_id = v.decision_id) AS n_verdicts
                         FROM librarian_verdicts v JOIN actors a ON a.actor_id = v.author
                         ORDER BY v.decision_id, v.created_at DESC, v.verdict_id DESC""").fetchall()
    return {r["decision_id"]: dict(r) for r in rows}


@router.get(f"{P}/librarian")
def overview(actor: dict = Depends(me)):
    ds = decisions()
    sample = _load("sample56.json") or dict(items=[])
    with pgc() as pg:
        _ensure_table(pg)
        lv = latest_verdicts(pg)
    items = [dict(x, verdict=lv.get(x["decision_id"])) for x in sample.get("items", [])]
    vc = Counter(x["verdict"]["verdict"] if x["verdict"] else "not_reviewed" for x in items)
    return jsonable(dict(
        numbers=_load("numbers56.json"), rules=_load("rules56.json"), scale=_load("scale56.json"),
        counts=dict(total=len(ds), by_kind=dict(Counter(d["kind"] for d in ds)),
                    by_confidence=dict(Counter(d.get("confidence") or "none" for d in ds)),
                    by_basis=dict(Counter(d.get("basis") or "none" for d in ds)),
                    trivial=sum(1 for d in ds if d.get("trivial")),
                    kind_confidence={k: dict(Counter(d.get("confidence") or "none" for d in ds if d["kind"] == k))
                                     for k in sorted({d["kind"] for d in ds})}),
        sample=dict(seed=sample.get("seed"), strata=sample.get("strata"), items=items, verdicts=dict(vc)),
        applied=False,
        note="Proposals only: nothing here is applied to the platform or a release until the owner says so."))


@router.get(f"{P}/librarian/decisions")
def list_decisions(kind: str | None = Query(default=None, max_length=40),
                   confidence: str | None = Query(default=None, pattern=r"^(high|medium|low)$"),
                   level: str | None = Query(default=None, pattern=r"^(affiliation|institution)$"),
                   basis: str | None = Query(default=None, pattern=r"^(rule|catalogue|world|context|judgement)$"),
                   q: str | None = Query(default=None, max_length=200),
                   offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=500),
                   actor: dict = Depends(me)):
    if kind and kind not in KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(KINDS)}")
    rows = decisions()
    if kind:
        rows = [d for d in rows if d["kind"] == kind]
    if confidence:
        rows = [d for d in rows if d.get("confidence") == confidence]
    if level:
        rows = [d for d in rows if d.get("level") == level]
    if basis:
        rows = [d for d in rows if d.get("basis") == basis]
    if q:
        ql = q.strip().lower()
        rows = [d for d in rows if ql in json.dumps(_summary(d), ensure_ascii=False).lower()]
    with pgc() as pg:
        _ensure_table(pg)
        lv = latest_verdicts(pg)
    page = [dict(_summary(d), verdict=lv.get(d["decision_id"])) for d in rows[offset:offset + limit]]
    return jsonable(dict(total=len(rows), offset=offset, limit=limit, rows=page))


@router.get(f"{P}/librarian/decisions/{{decision_id}}")
def get_decision(decision_id: str, actor: dict = Depends(me)):
    if not DECISION_ID.fullmatch(decision_id):
        raise HTTPException(422, "a decision id is 'D56-' + 12 hex digits")
    d = _by_id().get(decision_id)
    if not d:
        raise HTTPException(404, "no such librarian decision")
    pk = _packets()
    keys = [k for k in (d.get("evidence_ids") or []) + (d.get("subject_keys") or []) if k.startswith("aff:")]
    keys += [k for ks in (d.get("decision", {}).get("groups") or {}).values() for k in ks]
    keys += d.get("decision", {}).get("affiliations") or []
    keys = list(dict.fromkeys(keys))[:20]
    with pgc() as pg:
        _ensure_table(pg)
        vs = pg.execute("""SELECT v.*, a.name AS author_name FROM librarian_verdicts v JOIN actors a ON a.actor_id = v.author
                           WHERE v.decision_id = %s ORDER BY v.created_at, v.verdict_id""", (decision_id,)).fetchall()
    standing = {x["decision_id"] for x in decisions()}
    return jsonable(dict(_summary(d), standing=decision_id in standing,
                         packets=[pk[k] for k in keys if k in pk], verdicts=[dict(v) for v in vs]))


class VerdictIn(BaseModel):
    decision_id: str = Field(max_length=20)
    verdict: str
    comment: str | None = Field(default=None, max_length=4000)


@router.post(f"{P}/librarian/verdicts")
def add_verdict(body: VerdictIn, actor: dict = Depends(me)):
    if not DECISION_ID.fullmatch(body.decision_id):
        raise HTTPException(422, "a decision id is 'D56-' + 12 hex digits")
    if body.verdict not in VERDICTS:
        raise HTTPException(422, f"verdict must be one of {', '.join(VERDICTS)}")
    if body.decision_id not in _by_id():
        raise HTTPException(404, "no such librarian decision")
    comment = (body.comment or "").strip() or None
    in_sample = body.decision_id in {x["decision_id"] for x in (_load("sample56.json") or {}).get("items", [])}
    with pgc() as pg:
        _ensure_table(pg)
        r = pg.execute("""INSERT INTO librarian_verdicts (decision_id, verdict, comment, in_sample, author, is_demo)
                          VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
                       (body.decision_id, body.verdict, comment, in_sample, actor["actor_id"],
                        bool(actor.get("is_demo")))).fetchone()
    return jsonable(dict(r, author_name=actor.get("name")))


@router.get(f"{P}/librarian/verdicts")
def get_verdicts(decision_id: str = Query(max_length=20), actor: dict = Depends(me)):
    if not DECISION_ID.fullmatch(decision_id):
        raise HTTPException(422, "a decision id is 'D56-' + 12 hex digits")
    with pgc() as pg:
        _ensure_table(pg)
        rows = pg.execute("""SELECT v.*, a.name AS author_name FROM librarian_verdicts v JOIN actors a ON a.actor_id = v.author
                             WHERE v.decision_id = %s ORDER BY v.created_at, v.verdict_id""", (decision_id,)).fetchall()
    return jsonable([dict(r) for r in rows])

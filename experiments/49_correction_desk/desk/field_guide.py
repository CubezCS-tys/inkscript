"""The field guide (/how-we-collect, owner 2026-10-23: "quite comprehensive so I can read and see if I agree,
because otherwise we will have data with wrong labels").

How every Explorer column is collected, traced by reading the code, one entry per column in
`desk/field_guide/<tab>.json` (tab = the Explorer's entity key: articles, references, persons, institutions, journals,
works). A file is a list of entries (or {"fields": [...]}) with the keys

    tab, key, label, group, meaning, source, how[], exact[], examples[], fill, caveats[], label_check{ok, why, better?}

`source` is one of SOURCES. The Explorer (desk/explore.py) stays the source of truth for which columns exist and what
they are called: every column is listed, an entry or not ("being written"), and its current label and group are
the Explorer's. Each person's review of a field (agree / wrong label / question, a comment) is a row of the
append-only table `field_reviews` (schema.sql); the latest one per field is shown.

    GET  /desk/api/field-guide                       the tabs, every column with its entry, latest review, counts
    GET  /desk/api/field-guide/reviews?field=…       every review of one field, oldest first
    POST /desk/api/field-guide/reviews               {field_key, verdict, comment?, proposed_label?}
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from . import explore as X
from .api import P, jsonable, me, pgc

GUIDE_DIR = Path(__file__).resolve().parent / "field_guide"
SOURCES = ["printed page (Azure words)", "AI reading (Gemini)", "code rule", "catalogue (MARC)", "linker", "corrector",
           "counted", "several"]
VERDICTS = ("agree", "wrong_label", "question")
FIELD_KEY = re.compile(r"[a-z]+\.[a-z][a-z0-9_]*")

router = APIRouter()
_ensured = threading.Event()


def _ensure_table(pg) -> None:
    """The table is made by `desk.cli init` (schema.sql's idempotent tail); a Desk started before that still works:
    the same statements are run once here (each is IF NOT EXISTS / OR REPLACE)."""
    if _ensured.is_set():
        return
    from . import db
    pg.execute(db.upgrades_sql())
    pg.commit()
    _ensured.set()


def load_tab(tab: str) -> list[dict] | None:
    """The entries written for a tab, or None when its file does not exist yet."""
    f = GUIDE_DIR / f"{tab}.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    rows = (d.get("fields") or d.get("entries") or []) if isinstance(d, dict) else d
    return [r for r in rows if isinstance(r, dict) and r.get("key")]


def guide() -> list[dict]:
    """Every Explorer tab with every column, in the Explorer's order; the entry when one is written."""
    tabs = []
    for tab, e in X.ENTITIES.items():
        entries = load_tab(tab)
        by = {r["key"]: r for r in entries or []}
        cols = []
        for c in e["cols"]:
            r = by.get(c["name"])
            cols.append(dict(key=c["name"], field_key=f"{tab}.{c['name']}", label=c["label"], group=c["group"],
                             type=c["type"], src=c["src"], entry=r))
        tabs.append(dict(tab=tab, label=e["label"], about=e["about"], explore_key=e["key"], written=entries is not None,
                         n_columns=len(cols), n_entries=sum(1 for c in cols if c["entry"]),
                         stale=sorted(set(by) - {c["name"] for c in e["cols"]}), columns=cols))
    return tabs


def latest_reviews(pg) -> dict:
    rows = pg.execute("""SELECT DISTINCT ON (r.field_key) r.*, a.name AS author_name,
                           (SELECT count(*) FROM field_reviews x WHERE x.field_key = r.field_key) AS n_reviews
                         FROM field_reviews r JOIN actors a ON a.actor_id = r.author
                         ORDER BY r.field_key, r.created_at DESC, r.review_id DESC""").fetchall()
    return {r["field_key"]: dict(r) for r in rows}


@router.get(f"{P}/field-guide")
def get_guide(actor: dict = Depends(me)):
    tabs = guide()
    with pgc() as pg:
        _ensure_table(pg)
        rev = latest_reviews(pg)
    counts = dict(agree=0, wrong_label=0, question=0, not_reviewed=0)
    for t in tabs:
        for c in t["columns"]:
            c["review"] = rev.get(c["field_key"])
            counts[c["review"]["verdict"] if c["review"] else "not_reviewed"] += 1
    return jsonable(dict(tabs=tabs, sources=SOURCES, counts=counts,
                         n_columns=sum(t["n_columns"] for t in tabs), n_entries=sum(t["n_entries"] for t in tabs)))


@router.get(f"{P}/field-guide/reviews")
def get_reviews(field: str = Query(max_length=100), actor: dict = Depends(me)):
    if not FIELD_KEY.fullmatch(field):
        raise HTTPException(422, "field must be '<tab>.<column>'")
    with pgc() as pg:
        _ensure_table(pg)
        rows = pg.execute("""SELECT r.*, a.name AS author_name FROM field_reviews r JOIN actors a ON a.actor_id = r.author
                             WHERE r.field_key = %s ORDER BY r.created_at, r.review_id""", (field,)).fetchall()
    return jsonable([dict(r) for r in rows])


class ReviewIn(BaseModel):
    field_key: str = Field(max_length=100)
    verdict: str
    comment: str | None = Field(default=None, max_length=4000)
    proposed_label: str | None = Field(default=None, max_length=200)


@router.post(f"{P}/field-guide/reviews")
def add_review(body: ReviewIn, actor: dict = Depends(me)):
    tab, _, col = body.field_key.partition(".")
    if tab not in X.ENTITIES or col not in X.ENTITIES[tab]["by"]:
        raise HTTPException(422, f"no Explorer column {body.field_key!r}")
    if body.verdict not in VERDICTS:
        raise HTTPException(422, f"verdict must be one of {', '.join(VERDICTS)}")
    comment = (body.comment or "").strip() or None
    label = (body.proposed_label or "").strip() or None
    if body.verdict == "question" and not comment:
        raise HTTPException(422, "a question needs its text in the comment")
    with pgc() as pg:
        _ensure_table(pg)
        r = pg.execute("""INSERT INTO field_reviews (field_key, verdict, comment, proposed_label, author, is_demo)
                          VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
                       (body.field_key, body.verdict, comment, label, actor["actor_id"], bool(actor.get("is_demo")))
                       ).fetchone()
        out = dict(r, author_name=actor.get("name"))
    return jsonable(out)

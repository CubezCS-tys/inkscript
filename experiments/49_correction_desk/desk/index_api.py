"""The index routes (2026-10-23): /desk/api/index/* — the Index overview, gate 1 against random, journals,
institutions, an author record and the most-cited lists. Read-only, from the state the Desk reads
(`desk/index_pages.py` holds the numbers and their definitions). Included by `api.py` with one line."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam

from . import index_pages as X

router = APIRouter()


def _deps():
    from .api import P, jsonable, me, pgc, _state   # noqa: F401  (api.py includes this router after defining them)
    return P, jsonable, me, pgc, _state


P, jsonable, me, pgc, _state = _deps()


def _path():
    with pgc() as pg:
        path, st = _state(pg)
    return path, st


@router.get(f"{P}/index/overview")
def index_overview(actor: dict = Depends(me)):
    """Headline numbers of the index, each with its definition, and the entry lists (top works, institutions)."""
    path, st = _path()
    return jsonable(dict(st, **X.overview(path)))


@router.get(f"{P}/index/gate1")
def index_gate1(actor: dict = Depends(me)):
    """Gate 1's journal against the random articles, measured now with experiment 52's code (a few seconds once
    per state, then cached)."""
    path, st = _path()
    return jsonable(dict(st, **X.gate1(path)))


@router.get(f"{P}/index/journals")
def index_journals(actor: dict = Depends(me)):
    path, st = _path()
    return jsonable(dict(st, journals=X.journals(path), defs=X.DEFS))


@router.get(P + "/index/journals/{jid}")
def index_journal(jid: str = PathParam(pattern=r"^J[0-9A-Za-z]{1,12}$"), actor: dict = Depends(me)):
    path, st = _path()
    j = X.journal(path, jid)
    if not j:
        raise HTTPException(404, "no such journal in the reading")
    return jsonable(dict(st, **j))


@router.get(f"{P}/index/institutions")
def index_institutions(limit: int = Query(default=200, ge=1, le=1000), actor: dict = Depends(me)):
    path, st = _path()
    return jsonable(dict(st, institutions=X.institutions(path, limit), defs=X.DEFS))


@router.get(P + "/index/institutions/{iid}")
def index_institution(iid: str = PathParam(pattern=r"^I[0-9A-Z]{4,16}$"), actor: dict = Depends(me)):
    path, st = _path()
    i = X.institution(path, iid)
    if not i:
        raise HTTPException(404, "no such institution in the reading")
    return jsonable(dict(st, **i))


@router.get(P + "/index/persons/{pid}")
def index_person(pid: str = PathParam(pattern=r"^A[0-9A-Z]{4,16}$"), actor: dict = Depends(me)):
    path, st = _path()
    p = X.person_record(path, pid)
    if not p:
        raise HTTPException(404, "no such person in the reading")
    return jsonable(dict(st, **p))


@router.get(f"{P}/index/most-cited")
def index_most_cited(kind: str = Query(default="works", pattern="^(works|pubs)$"),
                     limit: int = Query(default=100, ge=1, le=500),
                     journal: str | None = Query(default=None, pattern=r"^J[0-9A-Za-z]{1,12}$"),
                     actor: dict = Depends(me)):
    path, st = _path()
    return jsonable(dict(st, **X.most_cited(path, kind, limit, journal)))

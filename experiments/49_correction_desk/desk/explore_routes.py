"""The Explorer's routes (desk/explore.py does the work). Included at the end of api.py, so `me`, `pgc` and `_state`
exist when this is imported. Read-only: every route reads the state the pages read (the newest release copy on disk,
else platform_v2.db), opened read-only.

    GET /desk/api/explore                       entities, their columns (with where each field lives), row counts
    GET /desk/api/explore/{entity}              rows: cols= sort= desc= q= f=(JSON filters) offset= limit=
    GET /desk/api/explore/{entity}/groups       counts per value of by= (and the sum of measure=)
    GET /desk/api/explore/{entity}/csv          the whole current view as CSV
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from . import explore as X
from .api import P, _state, jsonable, me, pgc

router = APIRouter()


@router.on_event("startup")
def _warm_in_background():
    """Build the six tables for the current state in a background thread when the API starts (5-7 s, ~60 MB), so
    the first visit to /explore is instant. A failure here only means the first visit builds them."""
    import threading

    def run():
        try:
            X.warm(_path()[0])
        except Exception:
            pass
    threading.Thread(target=run, daemon=True, name="explore-warm").start()


def _path():
    with pgc() as pg:
        path, st = _state(pg)
    return path, st


def _run(fn, *a, **k):
    try:
        return fn(*a, **k)
    except X.ExploreError as e:
        raise HTTPException(422, str(e))


@router.get(f"{P}/explore")
def explore_meta(warm: bool = False, actor: dict = Depends(me)):
    path, st = _path()
    t0 = time.time()
    if warm:
        _run(X.warm, path)
    return jsonable(dict(st, entities=X.meta(path), warm_s=round(time.time() - t0, 2)))


@router.get(P + "/explore/{entity}")
def explore_rows(entity: str, cols: str | None = Query(default=None, max_length=4000),
                 sort: str | None = Query(default=None, max_length=64), desc: bool | None = None,
                 q: str | None = Query(default=None, max_length=200), f: str | None = Query(default=None, max_length=8000),
                 offset: int = Query(default=0, ge=0, le=10_000_000), limit: int = Query(default=50, ge=1, le=500),
                 actor: dict = Depends(me)):
    path, st = _path()
    r = _run(X.query, path, entity, X.parse_cols(cols) if cols else None, sort, desc, q,
             _run(X.parse_filters, f), offset, limit)
    return jsonable(dict(st, **r))


@router.get(P + "/explore/{entity}/groups")
def explore_groups(entity: str, by: str = Query(max_length=64), measure: str | None = Query(default=None, max_length=64),
                   q: str | None = Query(default=None, max_length=200), f: str | None = Query(default=None, max_length=8000),
                   limit: int = Query(default=200, ge=1, le=1000), actor: dict = Depends(me)):
    path, st = _path()
    r = _run(X.group, path, entity, by, q, _run(X.parse_filters, f), measure, limit)
    return jsonable(dict(st, **r))


@router.get(P + "/explore/{entity}/csv")
def explore_csv(entity: str, cols: str | None = Query(default=None, max_length=4000),
                sort: str | None = Query(default=None, max_length=64), desc: bool | None = None,
                q: str | None = Query(default=None, max_length=200), f: str | None = Query(default=None, max_length=8000),
                actor: dict = Depends(me)):
    path, st = _path()
    filters = _run(X.parse_filters, f)
    cols_ = _run(X.parse_cols, cols)
    # validate before streaming, so a bad request is a 422 and not a broken download
    _run(X.where, entity, q, filters) if entity in X.ENTITIES else _run(X.table, path, entity)
    _run(X._cols, entity, cols_)
    _run(X._order, entity, sort, desc)
    gen = X.csv_rows(path, entity, cols_, sort, desc, q, filters)
    name = f"desk_{entity}_{st.get('release_id') or 'reading'}.csv"
    return StreamingResponse(gen, media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})

"""Routes for the article beside its scan and the "All fields" tab (2026-10-23). Mounted by `api.py` with one
`include_router` line, so this module can grow without touching the shared file.

    GET /desk/api/articles/{stem}/scan        the pages and the boxes on each (desk/scan.py `layout`)
    GET /desk/api/articles/{stem}/fields      every field held for the article (desk/fields.py)
    GET /desk/api/evidence/page?stem=&page=&w= a page scan at 640 / 1000 / 1400 px wide, cached"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from . import api as A
from . import fields as F
from . import pages as P
from . import scan as S
from .crops import CropError

router = APIRouter()
STEM_Q = r"^[0-9A-Za-z][0-9A-Za-z,\-]{2,60}$"


@router.get(A.P + "/articles/{stem}/scan")
def article_scan(stem: str, actor: dict = Depends(A.me)):
    if not P.STEM.fullmatch(stem):
        raise HTTPException(404, "no such article in the reading")
    with A.pgc() as pg:
        path, st = A._state(pg)
    con = P.open_ro(path)
    try:
        out = S.layout(con, stem)
    except CropError as e:
        raise HTTPException(e.status, str(e))
    finally:
        con.close()
    return A.jsonable(dict(st, **out))


@router.get(A.P + "/articles/{stem}/fields")
def article_fields(stem: str, actor: dict = Depends(A.me)):
    with A.pgc() as pg:
        path, st = A._state(pg)
    out = F.article_fields(path, stem)
    if out is None:
        raise HTTPException(404, "no such article in the reading")
    return A.jsonable(dict(st, **out))


@router.get(A.P + "/evidence/page")
def evidence_page(stem: str = Query(pattern=STEM_Q), page: int = Query(ge=1, le=2000),
                  w: int = Query(default=1000, ge=200, le=2000), actor: dict = Depends(A.me)):
    with A.pgc() as pg:
        path, _ = A._state(pg)
    con = P.open_ro(path)
    try:
        data, name = S.page_image(con, stem, page, w)
    except CropError as e:
        raise HTTPException(e.status, str(e))
    finally:
        con.close()
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=86400", "ETag": name})

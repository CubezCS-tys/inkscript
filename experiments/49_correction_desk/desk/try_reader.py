"""Try our reader (2026-11-06): the /try-reader page sends one image; this forwards it to the final reader's local
service (experiment 89's serve_reader.py, v7-28M, 127.0.0.1:8171) and returns its reading.

    POST /desk/api/try-reader     body = the image bytes (PNG / JPEG / WebP / BMP, at most 5 MB); Desk sign-in needed
                                  -> the service's JSON (text, chars, alternatives, inverted, lines, ms)

    POST /desk/api/try-reader/write   JSON {crop, text} (one line the reader returned) -> experiment 87's writer:
                                  the reading written in the style fitted to the crop (written, overlay, IoU, ms)

Nothing is stored: the image is held in memory for the one request and dropped; neither this router nor the service
writes it anywhere or logs it.  The service address comes from DESK_READER_URL (default http://127.0.0.1:8171).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from . import api as A

router = APIRouter()
MAX_BYTES = 5 * 1024 * 1024
TYPES = ("image/png", "image/jpeg", "image/webp", "image/bmp", "application/octet-stream")


def service() -> str:
    return (os.environ.get("DESK_READER_URL") or "http://127.0.0.1:8171").rstrip("/")


@router.post("/desk/api/try-reader")
async def try_reader(request: Request, actor: dict = Depends(A.me)):
    ct = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if ct not in TYPES:
        raise HTTPException(415, "send a PNG, JPEG, WebP or BMP image")
    n = request.headers.get("content-length")
    if n and n.isdigit() and int(n) > MAX_BYTES:
        raise HTTPException(413, f"the image is {int(n) / 1e6:.1f} MB; the limit is 5 MB")
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BYTES:
            raise HTTPException(413, "the image is larger than 5 MB")
    if not body:
        raise HTTPException(400, "no image received")
    from starlette.concurrency import run_in_threadpool
    try:
        code, out = await run_in_threadpool(_forward, bytes(body))
    finally:
        body.clear()
    return JSONResponse(status_code=code, content=out)


@router.post("/desk/api/try-reader/write")
async def try_writer(request: Request, actor: dict = Depends(A.me)):
    n = request.headers.get("content-length")
    if n and n.isdigit() and int(n) > MAX_BYTES:
        raise HTTPException(413, "the line is too large")
    body = await request.body()
    if not body or len(body) > MAX_BYTES:
        raise HTTPException(400, "send the line crop and its reading")
    from starlette.concurrency import run_in_threadpool
    code, out = await run_in_threadpool(_forward, body, "/write", "application/json")
    return JSONResponse(status_code=code, content=out)


def _forward(b: bytes, path: str = "/read", ctype: str = "application/octet-stream"):
    req = urllib.request.Request(service() + path, data=b, method="POST", headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except ValueError:
            return 502, dict(detail=f"the reader answered {e.code}")
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return 503, dict(detail="the reader service is not running (experiment 89's serve_reader.sh)")

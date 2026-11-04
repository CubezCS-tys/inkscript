"""The plan page's API (/plan, 2026-11-02): desk/plan/plan.json served as it is, plus what can be read live on
this machine, read-only, on each call (cached 10 s):

    GET  /desk/api/plan          the file + `live`: Desk releases (names in DESK_RELEASES and its summaries/), the
                                 live web's last deploy (web-live/.next/BUILD_ID), each item's README time, the last
                                 sign of life of running items (a beat file, else the newest file in its `watch`
                                 folder), stalled items (nothing for 60 min), overdue promises; `counts` for headers
    POST /desk/api/plan/items    admins only: add one item (work, needs-you or promise) through desk/plan_cli.py,
                                 the same code path as the shell, logged with the admin's actor id

The view window is the page's business, always derived from "now" (never stored). Env: PLAN_DIR (plan_cli),
DESK_RELEASES (db.py), DESK_WEB_LIVE (default /home/appuser/data/desk/web-live).
"""
from __future__ import annotations

import calendar
import os
import re
import threading
import time
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import db, plan_cli
from .api import P, admin, me

router = APIRouter()
REPO = Path(__file__).resolve().parents[3]
STALE_AFTER = 60 * 60
_cache: dict = {}
_lock = threading.Lock()
REL_RE = re.compile(r"^(R(\d{8})T(\d{6}))\.(db|json)$")


def _mtime(p: Path) -> float | None:
    try:
        return p.stat().st_mtime
    except OSError:
        return None


def releases() -> list[dict]:
    """Every Desk release id seen on disk (copies and summaries), its time from its name (UTC); the newest copy
    on disk is the one the Desk reads."""
    root = db.releases_dir()
    seen: dict[str, dict] = {}
    for d in (root, root / "summaries"):
        if not d.is_dir():
            continue
        for f in d.iterdir():
            m = REL_RE.match(f.name)
            if not m:
                continue
            rid = m.group(1)
            t = _utc_epoch(m.group(2), m.group(3))
            r = seen.setdefault(rid, dict(id=rid, at=t, copy=False, summary=False))
            r["copy" if m.group(4) == "db" else "summary"] = True
    out = sorted(seen.values(), key=lambda r: r["at"])
    copies = [r for r in out if r["copy"]]
    for r in out:
        r["live"] = bool(copies) and r is copies[-1]
    return out


def _utc_epoch(d: str, t: str) -> float:
    return float(calendar.timegm(time.strptime(d + t, "%Y%m%d%H%M%S")))


def deploys() -> list[dict]:
    live = Path(os.environ.get("DESK_WEB_LIVE", "/home/appuser/data/desk/web-live"))
    t = _mtime(live / ".next" / "BUILD_ID")
    if t is None:
        return []
    return [dict(at=t, label="Live Desk rebuilt", detail=f"{live}/.next/BUILD_ID")]


def newest_in(folder: Path) -> float | None:
    """The newest file time directly in a folder or one level down (cheap: no deep walk)."""
    best = None
    try:
        for f in folder.iterdir():
            if f.name.startswith("."):
                continue
            if f.is_file():
                t = _mtime(f)
            elif f.is_dir() and f.name not in ("out", "node_modules", "__pycache__"):
                t = max([_mtime(g) or 0 for g in list(f.iterdir())[:500] if g.is_file()] or [0]) or None
            else:
                continue
            if t and (best is None or t > best):
                best = t
    except OSError:
        return best
    return best


def live_layer(data: dict, now: float) -> dict:
    beats = plan_cli.read_beats()
    activity, stale, results = {}, [], []
    for it in data.get("items", []):
        if it.get("readme"):
            t = _mtime(REPO / it["readme"])
            if t:
                results.append(dict(item=it["id"], at=t, readme=it["readme"]))
        if it.get("status") != "running":
            continue
        cands = []
        b = beats.get(it["id"])
        if b and b.get("at"):
            cands.append(dict(at=plan_cli.to_epoch(b["at"]), source="beat", note=b.get("note"), by=b.get("by")))
        if it.get("watch"):
            t = newest_in(REPO / it["watch"])
            if t:
                cands.append(dict(at=t, source="folder", note=f"newest file in {it['watch']}"))
        st = plan_cli.to_epoch(it.get("start"))
        if st:
            cands.append(dict(at=st, source="start", note="started"))
        if cands:
            last = max(cands, key=lambda c: c["at"])
            activity[it["id"]] = last
            if now - last["at"] > STALE_AFTER:
                stale.append(it["id"])
    overdue = [p["id"] for p in data.get("promises", [])
               if p.get("status") == "open" and p.get("due") and plan_cli.to_epoch(p["due"]) < now]
    return dict(releases=releases(), deploys=deploys(), results=results, activity=activity, stale=stale,
                overdue=overdue, stale_after_s=STALE_AFTER)


def counts(data: dict, live: dict) -> dict:
    items = data.get("items", [])
    return dict(running=sum(1 for i in items if i.get("status") == "running"),
                needs_you=sum(1 for i in items if i.get("status") == "blocked-on-owner"),
                next=sum(1 for i in items if i.get("status") == "planned"),
                live=sum(1 for i in items if i.get("status") == "live"),
                stale=len(live["stale"]), overdue=len(live["overdue"]),
                promises_open=sum(1 for p in data.get("promises", []) if p.get("status") == "open"))


def plan_payload() -> dict:
    p = plan_cli.plan_path()
    key = (str(p), _mtime(p), str(plan_cli.beats_dir()))
    now = time.time()
    with _lock:
        c = _cache.get("plan")
        if c and c[0] == key and now - c[1] < 10:
            return c[2]
    if not p.exists():
        raise HTTPException(404, f"no plan file at {p}")
    data = plan_cli.read_plan(p)
    data = dict(data, log=(data.get("log") or [])[-30:])
    live = live_layer(data, now)
    out = dict(now=now, server_tz=_server_tz(), owner_tz="Europe/London", file=str(p), file_mtime=_mtime(p),
               plan=data, live=live, counts=counts(data, live), problems=plan_cli.validate(data))
    with _lock:
        _cache["plan"] = (key, now, out)
    return out


def _server_tz() -> str:
    tz = os.environ.get("TZ")
    if tz:
        return tz
    try:
        return Path("/etc/timezone").read_text().strip() or time.tzname[0]
    except OSError:
        try:
            return str(Path("/etc/localtime").resolve()).split("zoneinfo/")[-1]
        except OSError:
            return time.tzname[0]


@router.get(f"{P}/plan")
def get_plan(actor: dict = Depends(me)):
    return plan_payload()


class NewItem(BaseModel):
    kind: Literal["work", "needs_you", "promise"] = "work"
    id: str | None = Field(default=None, max_length=48)
    title: str = Field(min_length=2, max_length=60)
    desc: str | None = Field(default=None, max_length=400)
    lane: str | None = None
    status: Literal["planned", "running"] = "planned"
    planned_start: str | None = None
    planned_end: str | None = None
    due: str | None = None
    urgency: str | None = Field(default=None, max_length=40)
    link_label: str | None = Field(default=None, max_length=40)
    link_href: str | None = Field(default=None, max_length=200)


def _slug(title: str, data: dict) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:36] or "item"
    taken = {i["id"] for i in data.get("items", [])} | {p["id"] for p in data.get("promises", [])}
    s, n = base, 2
    while s in taken:
        s, n = f"{base}-{n}", n + 1
    return s


@router.post(f"{P}/plan/items", status_code=201)
def add_item(body: NewItem, actor: dict = Depends(admin)):
    by = actor["actor_id"]
    data = plan_cli.read_plan()
    iid = body.id or _slug(body.title, data)
    if any(i["id"] == iid for i in data.get("items", []) + data.get("promises", [])):
        raise HTTPException(409, f"{iid} exists already")
    if not plan_cli.ID_RE.match(iid):
        raise HTTPException(422, "the id is lower-case letters, digits, '.', '_' or '-'")
    links = [f"{body.link_label}={body.link_href}"] if body.link_label and body.link_href else None
    if links and not body.link_href.startswith("/"):
        raise HTTPException(422, "a link is a Desk path starting with /")
    src = [f"added in the Desk by {by}"]
    try:
        if body.kind == "promise":
            r = plan_cli.promise_add(iid, body.title, body.due, by=by, detail=body.desc, source=src)
        elif body.kind == "needs_you":
            r = plan_cli.needs_you_add(iid, body.title, by=by, question=body.desc, urgency=body.urgency,
                                       links=links, source=src, due=body.due)
        else:
            if body.lane not in plan_cli.LANE_KEYS or body.lane == "needs_you":
                raise HTTPException(422, "choose a lane")
            if body.status == "running":
                r = plan_cli.start(iid, body.title, body.lane, by=by, desc=body.desc, links=links, source=src,
                                   planned_end=body.planned_end)
            else:
                r = plan_cli.plan(iid, body.title, body.lane, by=by, desc=body.desc, start_at=body.planned_start,
                                  end_at=body.planned_end, links=links, source=src)
    except plan_cli.PlanError as e:
        raise HTTPException(422, str(e)) from e
    with _lock:
        _cache.pop("plan", None)
    return r

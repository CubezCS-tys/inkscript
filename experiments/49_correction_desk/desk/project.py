"""The project page's API (/project, 2026-10-26): the Web-of-Science project at a glance for the owner.

The page's content is one hand-kept file, `desk/project/project.json` (what we have done, the decisions and ideas,
what waits on the owner, the plan, the money), in which every item carries its source. This module serves it as it
is, plus one live figure computed on each call: the Gemini spend from the log, so the page can say when the log has
moved past the figure written in the file. Nothing is written anywhere.

    GET /desk/api/project       the file, with `live.spend` (sum, rows, last entry of gemini_spend.jsonl)

Env: PROJECT_JSON (default desk/project/project.json), GEMINI_SPEND_LOG (default
experiments/43_rehearsal/out/gemini_spend.jsonl).
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .api import P, me

HERE = Path(__file__).resolve().parent
DEFAULT_JSON = HERE / "project" / "project.json"
DEFAULT_LOG = HERE.parents[1] / "43_rehearsal" / "out" / "gemini_spend.jsonl"

router = APIRouter()
_cache: dict = {}
_lock = threading.Lock()


def project_path() -> Path:
    return Path(os.environ.get("PROJECT_JSON", str(DEFAULT_JSON)))


def spend_log_path() -> Path:
    return Path(os.environ.get("GEMINI_SPEND_LOG", str(DEFAULT_LOG)))


def _mtime(p: Path) -> float | None:
    try:
        return p.stat().st_mtime
    except OSError:
        return None


def load_project() -> dict:
    """project.json, cached by mtime (an edit shows at once)."""
    p = project_path()
    mt = _mtime(p)
    if mt is None:
        raise HTTPException(404, f"no project file at {p}")
    with _lock:
        c = _cache.get("project")
        if c and c[0] == (str(p), mt):
            return c[1]
        data = json.loads(p.read_text(encoding="utf-8"))
        _cache["project"] = ((str(p), mt), data)
        return data


def spend_now() -> dict | None:
    """The Gemini log's total: every row's `usd` summed, read-only, cached by mtime."""
    p = spend_log_path()
    mt = _mtime(p)
    if mt is None:
        return None
    with _lock:
        c = _cache.get("spend")
        if c and c[0] == (str(p), mt):
            return c[1]
    total, rows, first, last = 0.0, 0, None, None
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            total += float(r.get("usd") or 0)
            rows += 1
            w = r.get("when")
            if w:
                first = first or w
                last = w
    out = dict(usd=round(total, 4), rows=rows, first_entry=first, last_entry=last, log=str(p))
    with _lock:
        _cache["spend"] = ((str(p), mt), out)
    return out


@router.get(f"{P}/project")
def project(actor: dict = Depends(me)):
    data = dict(load_project())
    data["live"] = dict(spend=spend_now())
    return data

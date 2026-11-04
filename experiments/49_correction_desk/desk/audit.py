"""Nothing lost (2026-11-02, experiment 61): the audit of where every printed line and every value of Gemini's answer
ends up, for the Desk's /audit page.

    GET /desk/api/audit                       the corpus: totals, the leak table, the fix list, answer drops,
                                              bilingual pairs, platform gaps, one row per article (for filters)
    GET /desk/api/audit/articles/{stem}       one article: its flow (Azure lines -> Gemini's roles -> JATS fields ->
                                              platform records), its leaks, every line with its box on the scan

Read-only. The numbers are precomputed by experiment 61 (no recomputation per request):
    .venv/bin/python experiments/61_nothing_lost/audit61.py run --workers 3 --force
    .venv/bin/python experiments/61_nothing_lost/aggregate61.py
write `out/audit.json` and `out/articles/<stem>.json`; this module reads them (cached until the file changes).
`DESK_AUDIT_DIR` points elsewhere; so does the file /home/appuser/data/desk/audit_current (experiment 68: the audit
of the live release, experiments/68_go_live/out/audit). The stem is checked against the files the audit wrote; no path comes from the
request."""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from . import api as A

router = APIRouter()
STEM = re.compile(r"^[0-9A-Za-z][0-9A-Za-z,\-]{2,60}$")
_lock = threading.Lock()
_cache: dict = {}


POINTER = Path("/home/appuser/data/desk/audit_current")     # experiment 68: one line, the folder the page reads


def audit_dir() -> Path:
    """DESK_AUDIT_DIR, else the folder named in POINTER (read per request: re-pointing needs no restart), else
    experiment 61's own out/ (the first audit, kept as the "before")."""
    if os.environ.get("DESK_AUDIT_DIR"):
        return Path(os.environ["DESK_AUDIT_DIR"])
    try:
        p = Path(POINTER.read_text(encoding="utf-8").strip())
        if (p / "audit.json").is_file():
            return p
    except OSError:
        pass
    return Path(__file__).resolve().parents[2] / "61_nothing_lost" / "out"


def _load(path: Path):
    try:
        mt = path.stat().st_mtime
    except OSError:
        return None
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] == mt:
            return hit[1]
    data = json.loads(path.read_text(encoding="utf-8"))
    with _lock:
        if len(_cache) > 40:
            _cache.clear()
        _cache[path] = (mt, data)
    return data


def summary() -> dict:
    d = _load(audit_dir() / "audit.json")
    if d is None:
        raise HTTPException(404, "the audit has not been run on this machine (experiment 61)")
    score = _load(audit_dir() / "verify" / "score.json") or {}
    out = {k: d.get(k) for k in ("made", "release", "n_articles", "totals", "journals", "fixes", "bilingual",
                                 "platform", "columns", "alto_wrong_page", "answer_counts", "index")}
    out["leak_table"] = [dict(r, examples=r["examples"][:8]) for r in d["leak_table"]]
    out["answers"] = [dict(r, **{k: dict(v, examples=v.get("examples", [])[:3]) for k, v in r.items()
                                 if isinstance(v, dict)}) for r in d["answers"][:30]]
    out["works"] = [dict(w, examples=w["examples"][:2]) for w in d["works"][:12]]
    out["verify"] = score.get("total")
    return out


def article(stem: str) -> dict:
    if not STEM.fullmatch(stem):
        raise HTTPException(404, "no such article in the audit")
    base = (audit_dir() / "articles").resolve()
    f = (base / f"{stem}.json").resolve()
    if f.parent != base or not f.is_file():
        raise HTTPException(404, "no such article in the audit")
    r = _load(f)
    if r is None or "error" in r:
        raise HTTPException(404, "the audit could not read this article")
    keep = ("id", "page", "n", "text", "box", "bucket", "field", "gemini", "plat", "words")
    return dict({k: r.get(k) for k in ("stem", "run", "journal", "prompt", "pages", "page_size", "totals", "leaks",
                                        "flows", "bilingual", "platform", "alto_wrong_page")},
                lines=[{k: L.get(k) for k in keep} for L in r["lines"]],
                answer=dict(summary=r["answer"]["summary"],
                            values=[v for v in r["answer"]["values"] if v["status"] != "stored"],
                            counts=r["answer"]["counts"]))


@router.get(A.P + "/audit")
def audit_summary(actor: dict = Depends(A.me)):
    return A.jsonable(summary())


@router.get(A.P + "/audit/articles/{stem}")
def audit_article(stem: str, actor: dict = Depends(A.me)):
    return A.jsonable(article(stem))

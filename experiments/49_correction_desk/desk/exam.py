"""The extraction exam (experiment 97; 2026-11-10): the scorecard and real examples behind it, for the /exam page.

    GET /desk/api/exam                         everything the page needs (out/page/exam.json, built by page97.py)
                                               + the triage (out/triage/TRIAGE.md, read when it changes, so the
                                               section appears without a rebuild), and the key revision note
                                               (out/keys/REVISION_V2.md)
    GET /desk/api/exam/structure/{name}        one exam page's boxes: answer key and pipeline (out/page/structure)
    GET /desk/api/exam/img/{kind}/{name}       one picture cut by page97.py (out/page/img/<kind>/<name>.jpg)

Read-only. Everything comes from experiment 97's out/ folder (gitignored, private): the pictures are our scans and
are served only through the local Desk, behind the same sign-in as every other page. Names are checked against a
pattern and a fixed list of folders; no path comes from the request.

Rebuild after the scorer is re-run:
    cd experiments/97_extraction_evals && nice -n 19 ionice -c3 /home/appuser/inkscript/.venv/bin/python page97.py
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response

from . import api as A

router = APIRouter()
X97 = Path(__file__).resolve().parents[2] / "97_extraction_evals" / "out"
PAGE = X97 / "page"
DATA = PAGE / "exam.json"
TRIAGE = X97 / "triage" / "TRIAGE.md"
REVISION = X97 / "keys" / "REVISION_V2.md"
SCORECARD = X97 / "scores" / "scorecard.json"
KINDS = {"pages", "ink", "inkthumb", "inkcrop", "line", "cut"}
NAME = re.compile(r"^[0-9A-Za-z,_.\-]{1,120}\.jpg$")
SNAME = re.compile(r"^[0-9A-Za-z,_\-]{1,80}_p\d{3}$")

_lock = threading.Lock()
_cache: dict = {}


def _md_table(lines: list[str]) -> dict | None:
    rows = [l.strip() for l in lines if l.strip().startswith("|")]
    if len(rows) < 2:
        return None
    cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
    head, body = cells[0], [r for r in cells[1:] if not all(re.fullmatch(r":?-+:?", c or "-") for c in r)]
    return dict(head=head, rows=body)


def _sections(md: str) -> dict[str, list[str]]:
    out, cur = {}, "_top"
    for line in md.splitlines():
        m = re.match(r"^##\s+(.*)", line)
        if m:
            cur = m.group(1).strip()
            out[cur] = []
        else:
            out.setdefault(cur, []).append(line)
    return out


def _triage() -> dict | None:
    """TRIAGE.md as data: its first table (measure, raw, misses by class, estimated true score), the class list,
    the ranked real pipeline errors (their bold titles and first sentence), and when it was written."""
    if not TRIAGE.is_file():
        return None
    md = TRIAGE.read_text(encoding="utf-8")
    sec = _sections(md)
    first = next((v for k, v in sec.items() if k.startswith("1.")), [])
    errors = []
    for k, v in sec.items():
        if k.startswith("4."):
            for line in v:
                m = re.match(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*(.*)", line)
                if m:
                    errors.append(dict(n=int(m.group(1)), title=m.group(2).rstrip("."), rest=m.group(3)))
                elif errors and re.match(r"^ {3,}\S", line) and not re.match(r"^\s*- ", line) and not errors[-1].get("_done"):
                    errors[-1]["rest"] += " " + line.strip()          # the item's sentence runs on to the next line
                elif errors and (not line.strip() or re.match(r"^\s*- ", line)):
                    errors[-1]["_done"] = True                         # its examples (sub-bullets) are not shown
            for e in errors:
                e.pop("_done", None)
    intro = [l for l in sec.get("_top", []) if l.strip() and not l.startswith("#")]
    classes = [re.sub(r"\*\*", "", l[2:]) for l in intro if l.startswith("- **")]
    estimate_note = next((l for l in intro if l.startswith('The "true" scores')), None)
    if estimate_note:   # it may run over several lines
        i = intro.index(estimate_note)
        while i + 1 < len(intro) and not intro[i + 1].startswith(("- ", "#")):
            i += 1
            estimate_note += " " + intro[i].strip()
    return dict(table=_md_table(first), classes=classes, errors=errors, estimate_note=estimate_note,
                done=(next((l for l in intro if l.startswith("Done")), "") .split(".")[0] or None),
                mtime=TRIAGE.stat().st_mtime,
                scored_after=SCORECARD.is_file() and SCORECARD.stat().st_mtime > TRIAGE.stat().st_mtime)


def _revision() -> dict | None:
    """REVISION_V2.md (a key revision after the triage): its title, the 'all' row of its counts table, and whether
    the scorecard on disk was made after it (then the scores include it)."""
    if not REVISION.is_file():
        return None
    md = REVISION.read_text(encoding="utf-8")
    title = next((l.lstrip("# ").strip() for l in md.splitlines() if l.startswith("# ")), "Key revision")
    tab = _md_table(next((v for k, v in _sections(md).items() if k.lower().startswith("counts")), []))
    allrow = next((r for r in (tab or {}).get("rows", []) if "all" in r[0].lower()), None)
    counts = dict(zip([h.strip() for h in tab["head"]], [c.replace("*", "").strip() for c in allrow])) if allrow else None
    scored_after = SCORECARD.is_file() and SCORECARD.stat().st_mtime >= REVISION.stat().st_mtime
    return dict(title=title, counts=counts, scored_after=scored_after)


def _bundle() -> dict:
    with _lock:
        st = tuple(f.stat().st_mtime if f.is_file() else 0 for f in (DATA, TRIAGE, REVISION, SCORECARD))
        if _cache.get("stamp") != st:
            if not DATA.is_file():
                raise HTTPException(404, "the exam page has not been built yet: run experiments/97_extraction_evals/page97.py")
            d = json.loads(DATA.read_text(encoding="utf-8"))
            d["triage"] = _triage()
            d["revision"] = _revision()
            _cache.update(stamp=st, data=d)
        return _cache["data"]


@router.get(A.P + "/exam")
def exam(actor: dict = Depends(A.me)):
    return _bundle()


@router.get(A.P + "/exam/structure/{name}")
def exam_structure(name: str, actor: dict = Depends(A.me)):
    p = PAGE / "structure" / f"{name}.json"
    if not SNAME.fullmatch(name) or not p.is_file():
        raise HTTPException(404, "no such exam page")
    return Response(content=p.read_bytes(), media_type="application/json")


@router.get(A.P + "/exam/img/{kind}/{name}")
def exam_img(kind: str, name: str, actor: dict = Depends(A.me)):
    p = PAGE / "img" / kind / name
    if kind not in KINDS or not NAME.fullmatch(name) or not p.is_file():
        raise HTTPException(404, "no such picture")
    return FileResponse(str(p), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})

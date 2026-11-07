"""The OCR lab (experiment 75, 2026-11-04): our own readers beside ours, one document at a time, and the owner's fresh
correction of each page.  Serves the /lab page.

    GET  /desk/api/lab                                   the documents in the lab (one per bundle)
    GET  /desk/api/lab/{dataset}/{page_id}               the page bundle: every engine's blocks, text, boxes, timing,
                                                         cost, failures, disagreements; the correction history and
                                                         the latest correction; the scores against it (if any)
    GET  /desk/api/lab/{dataset}/{page_id}/scan          the page image (display copy; ?full=1 the canonical render)
    POST /desk/api/lab/{dataset}/{page_id}/annotations   save the owner's correction as a NEW revision (who / when);
                                                         predictions are never touched; then re-score
    GET  /desk/api/lab/{dataset}/{page_id}/scores        the scores against the latest revision (re-computed if stale)

Data: experiment 75's data root (`DESK_LAB_ROOT`, default experiments/75_ocr_lab/out/data): bundles written by
`python -m labocr compare`, corrections in its lab.sqlite (append-only `annotations`, labocr/annotations.py).
Scoring runs in the repo's venv as a subprocess with a fixed argument list (ids validated; nothing from the request
reaches a shell).  Only paths under the data root are read.  Demo accounts cannot save.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from . import api as A

router = APIRouter()
LAB = Path(__file__).resolve().parents[2] / "75_ocr_lab"
REPO_PY = Path(__file__).resolve().parents[3] / ".venv" / "bin" / "python"
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_,\-]{0,80}$")
_lock = threading.Lock()

if str(LAB) not in sys.path:
    sys.path.insert(0, str(LAB))
from labocr import annotations as ANN  # noqa: E402  (pydantic + sqlite only)


def root() -> Path:
    return Path(os.environ.get("DESK_LAB_ROOT") or (LAB / "out" / "data")).resolve()


def _ids(dataset: str, page_id: str):
    if not ID.fullmatch(dataset) or not ID.fullmatch(page_id):
        raise HTTPException(404, "no such page in the lab")


def _bundle_path(dataset: str, page_id: str) -> Path:
    _ids(dataset, page_id)
    base = (root() / "bundles").resolve()
    f = (base / dataset / f"{page_id}.json").resolve()
    if base not in f.parents or not f.is_file():
        raise HTTPException(404, "no such page in the lab")
    return f


def _scores_file(dataset: str, page_id: str, rev_no: int) -> Path:
    return root() / "scores" / dataset / f"{page_id}.{rev_no}.json"


def _score(dataset: str, page_id: str) -> dict:
    """Run the scorer (repo venv) for the latest revision; returns its JSON."""
    rev = ANN.latest(root(), page_id)
    if not rev:
        return dict(available=False, reason="no correction saved for this page yet")
    with _lock:
        p = subprocess.run([str(REPO_PY), "-m", "labocr", "--root", str(root()), "evaluate", "--dataset", dataset,
                            "--page", page_id], cwd=str(LAB), capture_output=True, text=True, timeout=300)
    f = _scores_file(dataset, page_id, rev["rev_no"])
    if p.returncode != 0 or not f.is_file():
        return dict(available=False, reason="the scorer failed: " + (p.stderr or "")[-600:])
    return json.loads(f.read_text(encoding="utf-8"))


def _cached_scores(dataset: str, page_id: str):
    rev = ANN.latest(root(), page_id)
    if not rev:
        return dict(available=False, reason="no correction saved for this page yet")
    f = _scores_file(dataset, page_id, rev["rev_no"])
    if f.is_file():
        d = json.loads(f.read_text(encoding="utf-8"))
        # a run added after the scores were made -> re-score
        b = json.loads(_bundle_path(dataset, page_id).read_text(encoding="utf-8"))
        have = {r.get("run_id") for r in d.get("engines", [])}
        if all(e["run_id"] in have for e in b["engines"]):
            return d
    return _score(dataset, page_id)


@router.get(A.P + "/lab")
def lab_index(actor: dict = Depends(A.me)):
    out = []
    base = root() / "bundles"
    for f in sorted(base.glob("*/*.json")) if base.is_dir() else []:
        b = json.loads(f.read_text(encoding="utf-8"))
        pid = b["page"]["page_id"]
        rev = ANN.latest(root(), pid)
        out.append(dict(dataset=b["dataset"], page_id=pid, document_id=b["page"]["document_id"],
                        page_number=b["page"]["page_number"], category=b["page"]["category"],
                        engines=[dict(label=e["label"], state=e["state"]) for e in b["engines"]],
                        corrected=bool(rev), rev_no=rev["rev_no"] if rev else None))
    return out


@router.get(A.P + "/lab/{dataset}/{page_id}")
def lab_page(dataset: str, page_id: str, actor: dict = Depends(A.me)):
    b = json.loads(_bundle_path(dataset, page_id).read_text(encoding="utf-8"))
    rev = ANN.latest(root(), page_id)
    b["history"] = ANN.history(root(), page_id)
    b["correction"] = rev
    b["scores"] = _cached_scores(dataset, page_id) if rev else dict(available=False,
                                                                    reason="no correction saved for this page yet")
    b["region_types"] = ANN.REGION_TYPES
    return A.jsonable(b)


@router.get(A.P + "/lab/{dataset}/{page_id}/scan")
def lab_scan(dataset: str, page_id: str, full: int = Query(0), actor: dict = Depends(A.me)):
    b = json.loads(_bundle_path(dataset, page_id).read_text(encoding="utf-8"))
    r = root()
    rel = b["page"]["render"] if full else f"bundles/{dataset}/{b['page']['display']['file']}"
    f = (r / rel).resolve()
    if r not in f.parents or not f.is_file():
        raise HTTPException(404, "no image")
    return FileResponse(str(f), media_type="image/png" if f.suffix == ".png" else "image/jpeg",
                        headers={"Cache-Control": "private, max-age=3600"})


@router.post(A.P + "/lab/{dataset}/{page_id}/annotations")
def lab_save(dataset: str, page_id: str, body: dict = Body(...), actor: dict = Depends(A.me)):
    _bundle_path(dataset, page_id)
    if actor.get("is_demo"):
        raise HTTPException(403, "a demo account cannot save corrections")
    try:
        ab = ANN.AnnotationBody.model_validate(body)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"the correction is not valid: {str(e)[:600]}")
    rev = ANN.save(root(), page_id, ab, actor.get("name") or actor["actor_id"], actor["actor_id"])
    return A.jsonable(dict(saved=dict(revision_id=rev["revision_id"], rev_no=rev["rev_no"], actor=rev["actor"],
                                      created_at=rev["created_at"]),
                           history=ANN.history(root(), page_id), scores=_score(dataset, page_id)))


@router.get(A.P + "/lab/{dataset}/{page_id}/scores")
def lab_scores(dataset: str, page_id: str, actor: dict = Depends(A.me)):
    _bundle_path(dataset, page_id)
    return A.jsonable(_cached_scores(dataset, page_id))

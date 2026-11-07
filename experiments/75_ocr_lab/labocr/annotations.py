"""The owner's corrections: append-only annotation revisions in the lab's SQLite (the same lab.sqlite as the runs).

Every save is a new revision (rev 1, 2, …) with who and when; nothing is edited in place, predictions are never
touched.  A revision holds the corrected lines (text exactly as printed, optional box, optional region, unreadable
flag with a reason), their reading order, and the regions (box, type, order, unreadable).  It records which
candidate it started from (`started_from`, `layout_from`) because that candidate is flattered by any score.

Standard library + pydantic only, so the Desk's API process can import it.  Scoring (labocr.evaluation) runs in the
repo's venv; `to_truth()` turns a revision into the TruthPage the scorer reads.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ANNOTATION_SCHEMA = "labocr-annotation/1"
REGION_TYPES = ["paragraph", "heading", "title", "list", "footnote", "header", "footer", "page_number", "table",
                "equation", "figure", "caption", "bibliography", "abstract", "unknown"]
COARSE = {"header": "furniture", "footer": "furniture", "page_number": "furniture", "footnote": "footnote"}
_ID = re.compile(r"^[A-Za-z0-9_.:\-]{1,80}$")

DDL = """
CREATE TABLE IF NOT EXISTS annotations (
  revision_id TEXT PRIMARY KEY, page_id TEXT NOT NULL, rev_no INTEGER NOT NULL, parent TEXT,
  created_at TEXT NOT NULL, actor TEXT NOT NULL, actor_id TEXT, started_from TEXT, layout_from TEXT,
  reviewed INTEGER DEFAULT 0, note TEXT, body_json TEXT NOT NULL, UNIQUE (page_id, rev_no));
"""


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnnLine(_M):
    line_id: str
    text: str = Field(max_length=4000)
    box: Optional[list[float]] = None
    region: Optional[str] = None
    unreadable: bool = False
    reason: Optional[str] = Field(default=None, max_length=500)
    source: Optional[str] = Field(default=None, max_length=200)   # "<run_id>#<block or line id>" it started from

    @field_validator("line_id")
    @classmethod
    def _id(cls, v):
        if not _ID.fullmatch(v):
            raise ValueError("bad line id")
        return v

    @field_validator("box")
    @classmethod
    def _box(cls, v):
        if v is not None and (len(v) != 4 or v[2] <= v[0] or v[3] <= v[1]):
            raise ValueError("bad box")
        return v


class AnnRegion(_M):
    region_id: str
    type: str
    box: list[float]
    unreadable: bool = False
    reason: Optional[str] = Field(default=None, max_length=500)
    source: Optional[str] = Field(default=None, max_length=200)

    @field_validator("type")
    @classmethod
    def _type(cls, v):
        if v not in REGION_TYPES:
            raise ValueError(f"unknown region type {v}")
        return v

    @field_validator("region_id")
    @classmethod
    def _rid(cls, v):
        if not _ID.fullmatch(v):
            raise ValueError("bad region id")
        return v

    @field_validator("box")
    @classmethod
    def _box(cls, v):
        if len(v) != 4 or v[2] <= v[0] or v[3] <= v[1]:
            raise ValueError("bad box")
        return v


class AnnotationBody(_M):
    """What the correction screen sends.  Lines are in reading order; regions are in reading order."""
    schema_version: str = ANNOTATION_SCHEMA
    lines: list[AnnLine] = Field(max_length=2000)
    regions: list[AnnRegion] = Field(default=[], max_length=500)
    started_from: Optional[str] = Field(default=None, max_length=120)
    layout_from: Optional[str] = Field(default=None, max_length=120)
    reviewed: bool = False
    note: Optional[str] = Field(default=None, max_length=2000)
    parent: Optional[str] = Field(default=None, max_length=200)   # the revision the editor started from (if any)

    @model_validator(mode="after")
    def _check(self):
        ids = [ln.line_id for ln in self.lines]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate line ids")
        rids = [r.region_id for r in self.regions]
        if len(set(rids)) != len(rids):
            raise ValueError("duplicate region ids")
        for ln in self.lines:
            if ln.region is not None and ln.region not in set(rids):
                ln.region = None          # a region deleted in the editor: the line keeps its text
        return self


def connect(root: Path) -> sqlite3.Connection:
    root.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(root / "lab.sqlite"), timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(DDL)
    return con


def save(root: Path, page_id: str, body: AnnotationBody, actor: str, actor_id: Optional[str]) -> dict:
    """Append a new revision; returns its row.  The previous revisions stay as they were."""
    if not _ID.fullmatch(page_id):
        raise ValueError("bad page id")
    con = connect(root)
    try:
        con.execute("BEGIN IMMEDIATE")
        n = con.execute("SELECT COALESCE(MAX(rev_no),0) FROM annotations WHERE page_id=?", (page_id,)).fetchone()[0] + 1
        latest = con.execute("SELECT revision_id FROM annotations WHERE page_id=? ORDER BY rev_no DESC LIMIT 1",
                             (page_id,)).fetchone()
        rid = f"{page_id}:rev{n}"
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        con.execute("INSERT INTO annotations (revision_id, page_id, rev_no, parent, created_at, actor, actor_id, "
                    "started_from, layout_from, reviewed, note, body_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, page_id, n, body.parent or (latest[0] if latest else None), now, actor, actor_id,
                     body.started_from, body.layout_from, int(body.reviewed), body.note, body.model_dump_json()))
        con.commit()
    finally:
        con.close()
    return get(root, rid)


def _row(r) -> dict:
    d = dict(r)
    d["body"] = json.loads(d.pop("body_json"))
    return d


def get(root: Path, revision_id: str) -> Optional[dict]:
    con = connect(root)
    try:
        r = con.execute("SELECT * FROM annotations WHERE revision_id=?", (revision_id,)).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def latest(root: Path, page_id: str) -> Optional[dict]:
    con = connect(root)
    try:
        r = con.execute("SELECT * FROM annotations WHERE page_id=? ORDER BY rev_no DESC LIMIT 1", (page_id,)).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def history(root: Path, page_id: str) -> list[dict]:
    con = connect(root)
    try:
        return [dict(r) for r in con.execute(
            "SELECT revision_id, rev_no, parent, created_at, actor, started_from, layout_from, reviewed, note "
            "FROM annotations WHERE page_id=? ORDER BY rev_no", (page_id,))]
    finally:
        con.close()


def to_truth(rev: dict, document_id: str, page_number: int, width: int, height: int):
    """A revision as the TruthPage the scorer reads.  Unreadable lines are left out of the text (and counted)."""
    from .schemas import TruthLine, TruthPage, TruthRegion
    b = AnnotationBody.model_validate(rev["body"])
    lines = [TruthLine(line_id=ln.line_id, text=ln.text, box=ln.box, region=ln.region,
                       kind="furniture" if _coarse_of(b, ln.region) == "furniture" else "text")
             for ln in b.lines if not ln.unreadable and ln.text.strip()]
    regions = [TruthRegion(region_id=r.region_id, type=r.type, coarse=COARSE.get(r.type, "body"), box=r.box, order=i)
               for i, r in enumerate(b.regions)]
    return TruthPage(page_id=rev["page_id"], document_id=document_id, page_number=page_number, width=width,
                     height=height, revision=rev["revision_id"],
                     status=("reviewed by " if rev.get("reviewed") else "saved by ") + rev["actor"],
                     provenance=f"owner correction on /lab, started from {rev.get('started_from')}, layout from "
                                f"{rev.get('layout_from')}, {rev['created_at']}",
                     conventions=["text exactly as printed, in Unicode logical order (as corrected on /lab)",
                                  f"{sum(ln.unreadable for ln in b.lines)} line(s) marked unreadable: left out"],
                     lines=lines, order=[ln.line_id for ln in lines], regions=regions)


def _coarse_of(b: AnnotationBody, region: Optional[str]) -> Optional[str]:
    for r in b.regions:
        if r.region_id == region:
            return COARSE.get(r.type, "body")
    return None

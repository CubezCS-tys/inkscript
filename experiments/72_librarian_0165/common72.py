"""Experiment 72: shared paths and helpers (the first production librarian pass, journal 0165).

Nothing here writes outside experiments/72_librarian_0165/out/.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
E = HERE.parent
DESK = E / "49_correction_desk"
E56, E62, E63, E64, E67, E71 = (E / "56_librarian_institutions", E / "62_librarian_works", E / "63_verify_institutions",
                                E / "64_apply_institutions", E / "67_apply_works", E / "71_librarian_models")
# the release the pass is made on: the live one after experiment 70 (0165 loaded)
RELEASE = Path(os.environ.get("LIB72_RELEASE", "/home/appuser/data/desk/releases/R20261103T023001.db"))
MARC = Path("/home/appuser/data/marc/marc.db")
JOURNAL = "0165"
JID = "J0165"


def ro(path: Path | str = RELEASE) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def jl(p):
    p = Path(p)
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if p.exists() else []


def wjl(p, rows):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=list) + "\n")


def js(p):
    return json.load(open(p, encoding="utf-8"))


def wjs(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=list), encoding="utf-8")


def add_paths(*dirs):
    for d in dirs:
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))

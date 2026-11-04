"""Experiment 66: shared paths and the four current runs (read-only on everything outside this folder)."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E43 = REPO / "experiments" / "43_rehearsal"
OUT = HERE / "out"
RELEASE = Path(os.path.expanduser("~/data/desk/releases/R20261102T155701.db"))

# current run (the release's is_current) -> (folder whose raw/ holds the answers, run43 set)
RUNS = {
    "v33_300_final_lettersfix": ("v33_300", "b"),
    "v33_300b_fix3_lettersfix": ("v33_300b_fix3", "c"),
    "j0130_final": ("j0130_final", "d"),
    "v2_55": ("v2_55", "a"),
}


def db():
    return sqlite3.connect(f"file:{RELEASE}?mode=ro", uri=True)


def current_stems() -> dict:
    """stem -> current run, from the release."""
    with db() as c:
        return dict(c.execute("select stem, run from versions where is_current=1"))


def e43_path():
    if str(E43) not in sys.path:
        sys.path.insert(0, str(E43))


def jdump(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=0), encoding="utf-8")


def jlines(p: Path):
    with open(p, encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                yield json.loads(ln)

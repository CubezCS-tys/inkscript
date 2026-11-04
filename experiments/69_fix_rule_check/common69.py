"""Experiment 69: shared paths. Read-only on everything outside this folder (answers are written to out/ only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E43 = REPO / "experiments" / "43_rehearsal"
E66 = REPO / "experiments" / "66_d30_guard"
OUT = HERE / "out"
for p in (E43, E66):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# exp 66's current runs -> (folder of saved answers, run43 set)
RUNS = {
    "v33_300_final_lettersfix": ("v33_300", "b"),
    "v33_300b_fix3_lettersfix": ("v33_300b_fix3", "c"),
    "j0130_final": ("j0130_final", "d"),
    "v2_55": ("v2_55", "a"),
}


def jdump(p: Path, obj, indent=1):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=indent), encoding="utf-8")
    tmp.replace(p)


def jlines(p: Path):
    with open(p, encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                yield json.loads(ln)


def judged() -> dict:
    """sid -> exp 66's fix record with its label (G / B / M / U) and reason."""
    out = {}
    for f, lf in (("sample.jsonl", "labels.tsv"), ("validate.jsonl", "vlabels.tsv")):
        lab = {}
        for ln in open(E66 / "out" / lf, encoding="utf-8"):
            if ln.strip():
                s, l, *why = ln.rstrip("\n").split("\t")
                lab[int(s)] = (l, why[0] if why else "")
        for r in jlines(E66 / "out" / f):
            r["lab"], r["lab_why"] = lab.get(r["sid"], (None, ""))
            out[r["sid"]] = r
    return out


# which comparison set: "units.jsonl" (v36 / nofix, 44 pages) or e.g. "units_r.jsonl" (the replicate)
import os  # noqa: E402
UNITS = OUT / os.environ.get("EXP69_UNITS", "units.jsonl")
FIXES = OUT / ("fixes69" + UNITS.stem[len("units"):] + ".jsonl")
ORDER = OUT / ("todo_order" + UNITS.stem[len("units"):] + ".json")
SHEETS = OUT / ("sheets" + UNITS.stem[len("units"):])

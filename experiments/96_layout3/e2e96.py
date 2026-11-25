"""Experiment 96, goal 3: experiment 94's end-to-end reader test (e2e94.main, imported unchanged) on the gap-filled
line sets of cut96.py.  e2e94 reads its inputs from its OUT folder; here OUT is pointed at this experiment's out/,
with experiment 94's predictions and reads linked or merged in (nothing in experiment 94's folder is written).

    python e2e96.py dev|test TAG   -> out/e2e94[dev]TAG.json (+ _lines.jsonl)
"""
from __future__ import annotations

import json
import os
import sys

from common96 import E, O94, OUT

sys.path.insert(0, str(E / "94_layout2"))
import e2e94  # noqa: E402


def main(which, tag):
    (OUT / "read").mkdir(exist_ok=True)
    for f in ("pred94_line.json", "pred94_line_val.json"):
        if not (OUT / f).exists():
            os.symlink(O94 / f, OUT / f)
    if not (OUT / "read/az.jsonl").exists():
        os.symlink(O94 / "read/az.jsonl", OUT / "read/az.jsonl")
    with open(OUT / f"read/ln94{tag}.jsonl", "w", encoding="utf-8") as f:
        for src in (O94 / "read/ln94.jsonl", OUT / f"read/ln94{tag}.jsonl.added"):
            if src.exists():
                f.write(src.read_text(encoding="utf-8"))
    e2e94.OUT = OUT
    import cut94
    cut94.OUT = O94          # dev_pages() reads experiment 94's train94.jsonl
    e2e94.main(which, tag)


if __name__ == "__main__":
    main(*sys.argv[1:])

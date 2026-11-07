"""Experiment 85, step 4a: a reader's greedy reading of experiment 81's held-out lines, here on the CPU (niced, 2
threads), with experiment 81's read81.run_one (imported unchanged; only its output folder is pointed here).

    nice -n 19 ionice -c3 experiments/81_heldout_scale/out/venv/bin/python experiments/85_disputes/read85.py NAME CKPT
        -> out/read/image_NAME.jsonl  ({key, NAME})
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "81_heldout_scale"))
import read81  # noqa: E402

if __name__ == "__main__":
    read81.RD = HERE / "out/read"
    read81.RD.mkdir(parents=True, exist_ok=True)
    read81.run_one(sys.argv[1], sys.argv[2], threads=2)

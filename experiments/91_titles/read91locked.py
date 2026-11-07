"""Experiment 91: a reader on experiment 90's LOCKED title lines only (local CPU, niced, 2 threads).  The locked set
was opened once (experiment 90); here it is RE-SCORED as a second read, never tuned on: everything about the new
reader was fixed before this runs.

    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python read91locked.py NAME CKPT
        -> out/locked/image_NAME.jsonl  ({key, NAME})

experiment 81's read81.image_reader / image_logprobs (greedy CTC, the CPU path experiment 90 used), with this
folder's train91.py as the network code (the network is experiment 89's).  Keys: experiment 90's title90.json (674
lines kept after looking); every key is checked to be locked (this is the locked set and nothing else).  Nothing is
written in experiment 90's folder.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "81_heldout_scale"))
sys.path.insert(0, str(E / "79_signal_reader"))
sys.path.insert(0, str(E / "88_truth_and_lock"))
import read81  # noqa: E402


def main(name: str, ckpt: str, threads: int = 2):
    from locked_old import is_locked_any
    torch.set_num_threads(threads)
    m = read81.module("train91", HERE / "train91.py")
    cs, model = read81.image_reader(m, ckpt)
    st = m.Store(str(E / "90_locked_final/out/crops48"), "test90")
    want = set(json.loads((E / "90_locked_final/out/title90.json").read_text()))
    idx = [i for i, k in enumerate(st.keys) if k in want]
    assert all(is_locked_any(st.keys[i]) for i in idx), "a crop outside the locked sets"
    out = HERE / "out/locked"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"image_{name}.jsonl", "w", encoding="utf-8") as f:
        for c in range(0, len(idx), 200):
            chunk = idx[c:c + 200]
            with torch.no_grad():
                lp = read81.image_logprobs(m, model, st, chunk)
            for i in chunk:
                k = st.keys[i]
                f.write(json.dumps({"key": k, name: m.from_visual(cs.decode(lp[k].argmax(-1).tolist()))},
                                   ensure_ascii=False) + "\n")
            print(f"{c + len(chunk)}/{len(idx)}", flush=True)
    print("READ_DONE", name, len(idx), "of", len(want), "title keys")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

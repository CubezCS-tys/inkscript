"""Experiment 90, step 2: one image reader on every locked line (local CPU, niced, 2 threads).

    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python read90.py NAME CKPT [MODULE=train84]
        -> out/read/image_NAME.jsonl  ({key, NAME: greedy reading})

Experiment 81's read81.image_reader / image_logprobs, unchanged (greedy CTC, the same batching, the CPU path that
experiment 81 checked against the GPU).  The network code is experiment 84's train84.py (= train83 plus fine-tune
options; the network is the same) unless MODULE names another file (experiment 89's final reader, if it needs one).
The weights are read only; nothing is trained.  Every key is checked against the locked guards first (this set must
be the locked set, and nothing else).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "81_heldout_scale"))
sys.path.insert(0, str(E / "79_signal_reader"))
sys.path.insert(0, str(E / "88_truth_and_lock"))
import read81  # noqa: E402

RD = HERE / "out/read"


def main(name: str, ckpt: str, module_path: str | None = None, threads: int = 2):
    from locked_old import is_locked_any
    torch.set_num_threads(threads)
    mp = Path(module_path) if module_path else E / "84_display_fonts/train84.py"
    m = read81.module(mp.stem, mp)
    cs, model = read81.image_reader(m, ckpt)
    st = m.Store(str(HERE / "out/crops48"), "test90")
    assert all(is_locked_any(k) for k in st.keys), "a crop outside the locked sets"
    RD.mkdir(parents=True, exist_ok=True)
    fo = RD / f"image_{name}.jsonl"
    done = {json.loads(l)["key"] for l in open(fo, encoding="utf-8")} if fo.exists() else set()
    todo = [i for i, k in enumerate(st.keys) if k not in done]
    print(f"{name}: {len(st.keys)} crops, {len(todo)} to read ({ckpt})", flush=True)
    t0 = time.time()
    with open(fo, "a", encoding="utf-8") as f:
        for c in range(0, len(todo), 500):
            chunk = todo[c:c + 500]
            with torch.no_grad():
                lp = read81.image_logprobs(m, model, st, chunk)
            for i in chunk:
                k = st.keys[i]
                f.write(json.dumps({"key": k, name: m.from_visual(cs.decode(lp[k].argmax(-1).tolist()))},
                                   ensure_ascii=False) + "\n")
            f.flush()
            print(f"{c + len(chunk)}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
    print("ONE_DONE", name, flush=True)


if __name__ == "__main__":
    import os
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None, int(os.environ.get("THREADS", "2")))

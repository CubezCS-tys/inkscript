"""Experiment 96 (copy of experiment 94's read94.py, output in this folder): the final reader (experiment 89's v7-28M, FINAL_READER.json, sha-checked, frozen) on crops, local
CPU, niced, THREADS threads (default 2).  experiment 92's read92.py with the crop folder as an argument.

    python read94.py CROPS_DIR SPLIT [SPLIT ...]   -> out/read/<split>.jsonl  ({key, pred})
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import torch

from common96 import E, OUT, assert_not_locked

sys.path.insert(0, str(E / "81_heldout_scale"))
sys.path.insert(0, str(E / "79_signal_reader"))
import read81  # noqa: E402

ROOT = E.parent


def main(crops, splits, threads=2):
    torch.set_num_threads(threads)
    fr = json.loads((E / "89_final_reader/FINAL_READER.json").read_text())
    ckpt = ROOT / fr["weights"]
    assert hashlib.sha256(ckpt.read_bytes()).hexdigest() == fr["weights_sha256"], "the final reader's weights changed"
    m = read81.module("train89", E / "89_final_reader/train89.py")
    cs, model = read81.image_reader(m, str(ckpt))
    (OUT / "read").mkdir(parents=True, exist_ok=True)
    for split in splits:
        st = m.Store(str(crops), split)
        assert_not_locked(st.keys)
        fo = OUT / "read" / f"{split}.jsonl"
        done = {json.loads(l)["key"] for l in open(fo, encoding="utf-8")} if fo.exists() else set()
        todo = [i for i, k in enumerate(st.keys) if k not in done]
        print(f"{split}: {len(st.keys)} crops, {len(todo)} to read", flush=True)
        t0 = time.time()
        with open(fo, "a", encoding="utf-8") as f:
            for c in range(0, len(todo), 500):
                chunk = todo[c:c + 500]
                with torch.no_grad():
                    lp = read81.image_logprobs(m, model, st, chunk)
                for i in chunk:
                    k = st.keys[i]
                    f.write(json.dumps({"key": k, "pred": m.from_visual(cs.decode(lp[k].argmax(-1).tolist()))},
                                       ensure_ascii=False) + "\n")
                f.flush()
                print(f"{split} {c + len(chunk)}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
    print("READ96_DONE", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2:], int(os.environ.get("THREADS", "2")))

"""Experiment 84, step B4b: read experiment 81's 22,783 held-out lines with a reader (local CPU, niced, 2 threads).

    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python read84.py one NAME CKPT [--flip] [--only-flipped]

-> out/read/image_NAME.jsonl ({key, NAME: greedy reading}).  Experiment 81's crops (out/crops48, read only) and its
read81.image_logprobs / image_reader, unchanged; the model code is this folder's train84.py (= train83 + fine-tune
options; the network is the same).

--flip: test-time polarity normalisation, fixed BEFORE any result was seen (diag81's threshold): in each 48-px-wide
        window of the crop whose median grey is below 110 (light text on a dark ground), the columns are inverted
        (255 - x); a crop with no such window is unchanged.  --only-flipped: read only the crops the flip changes
        (the others keep the reading of the same model without the flip; give it as --base FILE NAME).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
E = HERE.parent
E81 = E / "81_heldout_scale"
sys.path.insert(0, str(E81))
sys.path.insert(0, str(E / "79_signal_reader"))
import read81  # noqa: E402

RD = HERE / "out/read"
WIN, THR = 48, 110


def flip(img: np.ndarray) -> tuple[np.ndarray, bool]:
    h, w = img.shape
    if w < 4:
        return img, False
    col = np.median(img, axis=0)
    k = min(WIN, w)
    # median of each window, approximated by the mean of column medians over the window (cheap, smooth)
    c = np.convolve(col, np.ones(k) / k, mode="same")
    m = c < THR
    if not m.any():
        return img, False
    out = img.copy()
    out[:, m] = 255 - out[:, m]
    return out, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("name")
    ap.add_argument("ckpt")
    ap.add_argument("--flip", action="store_true")
    ap.add_argument("--only-flipped", action="store_true")
    ap.add_argument("--base", nargs=2, metavar=("FILE", "NAME"))
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    m = read81.module("train84", HERE / "train84.py")
    cs, model = read81.image_reader(m, a.ckpt)
    st = m.Store(str(E81 / "out/crops48"), "test81")
    changed = set()
    if a.flip:
        orig = st.image

        def image(i):
            im, ch = flip(orig(i))
            return im
        for i in range(len(st.keys)):
            if flip(orig(i))[1]:
                changed.add(i)
        st.image = image
        print(f"flip changes {len(changed)} of {len(st.keys)} crops", flush=True)
    RD.mkdir(parents=True, exist_ok=True)
    fo = RD / f"image_{a.name}.jsonl"
    done = {json.loads(l)["key"] for l in open(fo, encoding="utf-8")} if fo.exists() else set()
    todo = [i for i in range(len(st.keys)) if st.keys[i] not in done]
    base = {}
    if a.only_flipped:
        base = {d["key"]: d[a.base[1]] for d in map(json.loads, open(a.base[0], encoding="utf-8"))}
    t0 = time.time()
    with open(fo, "a", encoding="utf-8") as f:
        if a.only_flipped:
            for i in todo:
                if i not in changed:
                    f.write(json.dumps({"key": st.keys[i], a.name: base[st.keys[i]]}, ensure_ascii=False) + "\n")
            todo = [i for i in todo if i in changed]
        for c in range(0, len(todo), 500):
            chunk = todo[c:c + 500]
            with torch.no_grad():
                lp = read81.image_logprobs(m, model, st, chunk)
            for i in chunk:
                k = st.keys[i]
                f.write(json.dumps({"key": k, a.name: m.from_visual(cs.decode(lp[k].argmax(-1).tolist()))},
                                   ensure_ascii=False) + "\n")
            f.flush()
            print(f"{c + len(chunk)}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
    print("ONE_DONE", a.name, flush=True)


if __name__ == "__main__":
    main()

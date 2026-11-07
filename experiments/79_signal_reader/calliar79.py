"""Experiment 79, round 2 input: Calliar's traced strokes (MIT; github.com/ARBML/Calliar) as pen signals in the
reader's own 12-feature format, for pretraining.

    nice -n 19 ionice -c3 python calliar79.py      -> data/calliar/calliar-00.npz + .jsonl (split "calliar")

Plain JSON only (data/calliar/json/dataset/{train,valid,test}/<sentence>_<n>.json: a list of {shape: [[x, y], ...]}
strokes in the annotator's order); the package's .npz files are never opened (pickle).  The label is the sentence in
the file name.  Calliar draws each letter shape as its own stroke, so a stroke that starts where the previous main
stroke ended (within a fifth of the rise) continues it without a pen lift, as a printed joined piece does.
Coordinates: y grows downward (image); the baseline is the median height of the main strokes' lowest points, the
rise a third of the ink's height (calligraphy has tall ascenders and deep descenders).  Only line-shaped samples are
kept (width >= 1.8 x height): many are stacked or circular compositions.
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

import numpy as np

from sig79 import features, resample, smooth
from data79 import clean_label

HERE = Path(__file__).resolve().parent
SRC = HERE / "data/calliar/json/dataset"


def convert(path: str):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    S = [(k, np.array(v, float)) for s in d for k, v in s.items() if len(v)]
    if not S:
        return None
    allp = np.vstack([p for _, p in S])
    h = allp[:, 1].max() - allp[:, 1].min()
    if np.ptp(allp[:, 0]) < 1.8 * h:
        return None                                       # a stacked or round composition, not a line
    rise = max(4.0, h / 3)
    mains = [p for k, p in S if k != "." and len(p) > 3]
    base = float(np.median([p[:, 1].max() for p in mains])) if mains else float(allp[:, 1].mean())
    step = 0.12 * rise
    strokes, last = [], None
    for k, p in S:
        yx = np.c_[p[:, 1], p[:, 0]]
        if k == "." or len(yx) <= 3 or (np.ptp(yx[:, 0]) < 0.25 * rise and np.ptp(yx[:, 1]) < 0.25 * rise):
            q = resample(yx, step) if len(yx) > 1 else yx
            strokes.append(dict(kind="mark", pts=q, retrace=np.zeros(len(q), int), above=bool(yx[:, 0].mean() < base - 0.3 * rise)))
            continue
        q = smooth(resample(yx, step))
        cont = last is not None and np.linalg.norm(q[0] - last) < 0.2 * rise
        strokes.append(dict(kind="main", pts=q, retrace=np.zeros(len(q), int), cont=bool(cont)))
        last = q[-1]
    return features(dict(strokes=strokes, M=dict(baseline=base, rise=rise)))


def main():
    out = HERE / "data/calliar"
    feats, meta = [], []
    for sp in ("train", "valid", "test"):
        for f in sorted(glob.glob(str(SRC / sp / "*.json"))):
            text = re.sub(r"_\d+$", "", Path(f).stem)
            F = convert(f)
            if F is None or len(F) < 8:
                continue
            feats.append(F.astype(np.float16))
            meta.append(dict(text=text, label=clean_label(text), font="calliar", level="none", px=0, src=sp))
    np.savez(out / "calliar-00.npz", truth=np.concatenate(feats),
             truth_off=np.cumsum([0] + [len(x) for x in feats]).astype(np.int64))
    with open(out / "calliar-00.jsonl", "w", encoding="utf-8") as fo:
        for m in meta:
            fo.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(len(meta), "sentences;", sum(len(x) for x in feats), "points; mean", int(np.mean([len(x) for x in feats])))


if __name__ == "__main__":
    sys.exit(main())

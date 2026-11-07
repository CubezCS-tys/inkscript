"""Experiment 79: ADAB (CC BY 4.0; IEEE DataPort, REGIM-Lab; cite Boubaker et al. 2012, Kherallah et al. ICDAR 2011,
El Abed et al. IJDAR 2010) as pen signals in the reader's own feature format, for stroke pretraining (shippable).

    PYTHONPATH=data/pylib nice -n 19 ionice -c3 python adab79.py   -> data/adab/adab-00.npz + .jsonl (split "adab")

data/adab/ADAB DATABASE/set_{1,2,3}/inkml/<id>.inkml (traces = real pen-down strokes, X Y, 125 Hz, y downward) and
upx/<id>.upx (label: <alternate value="..."> , a Tunisian town name, IFN/ENIT vocabulary).  Each trace is one
pen-down: real pen lifts are kept (a writer lifts between joined pieces, as print's pieces are separate).  Short
traces are dots/marks.  Baseline and rise as in calliar79 (lowest points of the main strokes; a third of the height).
"""
from __future__ import annotations

import glob
import html
import json
import re
import sys
from pathlib import Path

import numpy as np

from sig79 import features, resample, smooth
from data79 import clean_label

HERE = Path(__file__).resolve().parent
SRC = HERE / "data/adab/ADAB DATABASE"
TRACE = re.compile(r"<trace[^>]*>([^<]*)</trace>")
LABEL = re.compile(r'<alternate value="([^"]*)"')


def strokes_of(path: str):
    out = []
    for t in TRACE.findall(Path(path).read_text(encoding="ascii", errors="ignore")):
        pts = [p.split() for p in t.strip().split(",") if p.strip()]
        a = np.array([[float(p[0]), float(p[1])] for p in pts if len(p) >= 2])
        if len(a):
            out.append(a)
    return out


def convert(S: list[np.ndarray]):
    allp = np.vstack(S)
    h = np.ptp(allp[:, 1])
    rise = max(4.0, h / 3)
    mains = [p for p in S if len(p) > 3 and max(np.ptp(p[:, 0]), np.ptp(p[:, 1])) >= 0.25 * rise]
    base = float(np.median([p[:, 1].max() for p in mains])) if mains else float(allp[:, 1].mean())
    step = 0.12 * rise
    strokes = []
    for p in S:
        yx = np.c_[p[:, 1], p[:, 0]]
        q = resample(yx, step) if len(yx) > 1 else yx
        if len(p) <= 3 or max(np.ptp(p[:, 0]), np.ptp(p[:, 1])) < 0.25 * rise:
            strokes.append(dict(kind="mark", pts=q, retrace=np.zeros(len(q), int), above=bool(yx[:, 0].mean() < base - 0.3 * rise)))
        else:
            q = smooth(q)
            strokes.append(dict(kind="main", pts=q, retrace=np.zeros(len(q), int)))
    return features(dict(strokes=strokes, M=dict(baseline=base, rise=rise)))


def main():
    feats, meta = [], []
    for f in sorted(glob.glob(str(SRC / "set_*/inkml/*.inkml"))):
        u = Path(f).parent.parent / "upx" / (Path(f).stem + ".upx")
        if not u.exists():
            continue
        m = LABEL.search(u.read_text(encoding="utf-8", errors="ignore"))
        if not m:
            continue
        text = html.unescape(m.group(1))
        S = strokes_of(f)
        if not S:
            continue
        F = convert(S)
        if len(F) < 8:
            continue
        feats.append(F.astype(np.float16))
        meta.append(dict(text=text, label=clean_label(text), font="adab", level="none", px=0, src=Path(f).parts[-3]))
    out = HERE / "data/adab"
    np.savez(out / "adab-00.npz", truth=np.concatenate(feats), truth_off=np.cumsum([0] + [len(x) for x in feats]).astype(np.int64))
    with open(out / "adab-00.jsonl", "w", encoding="utf-8") as fo:
        for m in meta:
            fo.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(len(meta), "words;", len({m["label"] for m in meta}), "distinct;", sum(len(x) for x in feats), "points; mean", int(np.mean([len(x) for x in feats])))


if __name__ == "__main__":
    sys.exit(main())

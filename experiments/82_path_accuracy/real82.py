"""Experiment 82: the learned rebuilder against the rule one on REAL old lines (no truth; judged by eye).

    python real82.py --model out/learned/u1/model.pt --out out/real
Lines: experiment 79's 96-px crops of the two old pages the owner pointed at (read only):
  0718 (1937): the head of و in «كانوا» printed as a filled blob;  0673 (1953): heavy print, the head of غ in «غاية» filled.
For each line: the ink; the skeleton's path; the learned centre line's path; the network's centre-line probability.
The path is drawn coloured by time (red first -> purple last), retraces thin black, pen lifts thin grey (sig79.draw).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import path82 as P  # noqa: E402
from learn82 import load_model  # noqa: E402
from net82 import decode, predict  # noqa: E402
from sig79 import draw  # noqa: E402

REAL = HERE.parent / "79_signal_reader/out/real"
LINES = {"1937": "0718-003-003-002_p006_l023_crop.png", "1953": "0673-002-000-015_p003_l003_crop.png"}


def label(img, text):
    bar = np.full((26, img.shape[1], 3), 255, np.uint8)
    cv2.putText(bar, text, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    return np.vstack([bar, img])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", default=str(HERE / "out/real"))
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--x0", type=float, default=0.0, help="crop: share of the width to start at")
    ap.add_argument("--x1", type=float, default=1.0)
    a = ap.parse_args()
    torch.set_num_threads(2)
    model = load_model(a.model, "cpu")
    od = Path(a.out)
    od.mkdir(parents=True, exist_ok=True)
    for year, f in LINES.items():
        g = cv2.imread(str(REAL / f), cv2.IMREAD_GRAYSCALE)
        y = predict(model, g)
        cl = decode(y, a.thr)
        rs = P.rebuild(g, "skeleton")
        rl = P.rebuild(g, "learned", cl=cl)
        s = 3
        ink = cv2.cvtColor(cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
        heat = cv2.applyColorMap((255 * y[0]).astype(np.uint8), cv2.COLORMAP_MAGMA)
        heat = cv2.resize(heat, None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST)
        tiles = [label(ink, f"{year}: the ink"), label(draw(g, rs, scale=s), "rules: skeleton path (exp 79 today)"),
                 label(draw(g, rl, scale=s), "learned: the network's centre line, the same walk"),
                 label(heat, "the network's centre line (bright = sure)")]
        W = max(t.shape[1] for t in tiles)
        img = np.vstack([np.pad(t, ((0, 6), (0, W - t.shape[1]), (0, 0)), constant_values=255) for t in tiles])
        if a.x0 > 0 or a.x1 < 1:
            img = img[:, int(a.x0 * W):int(a.x1 * W)]
        cv2.imwrite(str(od / f"real_{year}.png"), img)
        print(od / f"real_{year}.png")


if __name__ == "__main__":
    main()

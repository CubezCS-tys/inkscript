"""Experiment 82: close-ups of one loop letter under filled ink: the damaged ink, the rule path, the learned path.

    python figure82.py --lines out/shape_traced/lines.json --cl out/learned/u1/shape_traced/cl --font 0737 --ch و
            --level fill --out out/fig_filled_waw.png
Each row is one occurrence: the truth (thick green) under the rebuilt path (red), loop kept (blue ring) or lost
(orange cross), for the skeleton and, when --cl is given, for the learned rebuilder.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lines82 as L  # noqa: E402
import metric82 as MM  # noqa: E402
import path82 as P  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", required=True)
    ap.add_argument("--cl", default="")
    ap.add_argument("--font", default="0737")
    ap.add_argument("--ch", default="و")
    ap.add_argument("--level", default="fill")
    ap.add_argument("--rows", type=int, default=5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    specs = json.loads(Path(a.lines).read_text(encoding="utf-8"))
    rows = []
    for i, spec in enumerate(specs):
        if a.font not in spec["font"] or a.ch not in spec["text"]:
            continue
        grey, owner, ink = L.render(spec)
        truth = MM.truth82(ink, owner, spec["text"])
        g = L.damaged(grey, a.level, spec["seed"] + 7919 * L.LEVELS.index(a.level))
        recs = [("skeleton (rules)", P.rebuild(g, "skeleton"))]
        f = Path(a.cl) / f"{i:04d}_{a.level}.npz"
        if a.cl and f.exists():
            recs.append(("learned", P.rebuild(g, "learned", cl=np.load(f)["cl"])))
        for c in MM.counters(owner, spec["text"]):
            if c["ch"] != a.ch:
                continue
            y0, y1 = int(max(0, c["cy"] - 30)), int(min(grey.shape[0], c["cy"] + 40))
            x0, x1 = int(max(0, c["cx"] - 40)), int(min(grey.shape[1], c["cx"] + 40))
            sc = 5
            tiles = [cv2.cvtColor(cv2.resize(g[y0:y1, x0:x1], None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST),
                                  cv2.COLOR_GRAY2BGR)]
            for name, rec in recs:
                img = MM.overlay(g, rec, truth, owner, spec["text"], ink, scale=sc)
                tiles.append(img[y0 * sc:y1 * sc, x0 * sc:x1 * sc])
            row = np.hstack([np.pad(t, ((4, 4), (4, 4), (0, 0)), constant_values=255) for t in tiles])
            rows.append(row)
            break
        if len(rows) >= a.rows:
            break
    if not rows:
        raise SystemExit("no occurrence found")
    W = max(r.shape[1] for r in rows)
    head = np.full((34, W, 3), 255, np.uint8)
    names = ["ink (" + a.level + ")"] + [n for n, _ in recs]
    for k, n in enumerate(names):
        cv2.putText(head, n, (10 + k * (rows[0].shape[1] // len(names)), 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.imwrite(a.out, np.vstack([head] + [np.pad(r, ((0, 0), (0, W - r.shape[1]), (0, 0)), constant_values=255) for r in rows]))
    print(a.out, len(rows))


if __name__ == "__main__":
    main()

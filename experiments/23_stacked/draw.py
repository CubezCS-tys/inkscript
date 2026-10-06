"""Piece pictures (experiment 21's cells.draw on 21's stored plans of today's cutter): ink by letter, pen path, cuts,
cells under it. Written to this folder.

    ../../.venv/bin/python draw.py NAME WORDID ...      -> out/draw_NAME.png
"""
import sys
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; E21 = HERE.parent / "21_better_boxes"
sys.path.insert(0, str(E21))
import cells as C

if __name__ == "__main__":
    name, wids = sys.argv[1], sys.argv[2:]; tiles = []
    for wid in wids:
        s, w = C.find_word(wid); m = C.match(w, w["doc"], "new")
        for k, (idx, p) in m.items():
            t = C.draw(p, [C.cells_orig]); t = cv2.copyMakeBorder(t, 0, 18, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            cv2.putText(t, f"{wid}"[:40], (2, t.shape[0] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
            tiles.append(t)
    Wd = max(t.shape[1] for t in tiles)
    cv2.imwrite(str(HERE / f"out/draw_{name}.png"), np.vstack([cv2.copyMakeBorder(t, 4, 4, 0, Wd - t.shape[1], cv2.BORDER_CONSTANT, value=(235, 235, 235)) for t in tiles]))

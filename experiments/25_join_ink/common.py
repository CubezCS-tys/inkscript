"""Shared helpers: the sample (experiment 18), the 112 stacked letters (experiment 23), my replayed plans matched to
sample words (experiment 21's cells.match), drawings of a piece with each letter's ink in its own colour."""
import sys, json, pickle
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
E18, E21, E23 = REPO / "experiments/18_boxes", REPO / "experiments/21_better_boxes", REPO / "experiments/23_stacked"
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(E21)); sys.path.insert(0, str(E18))
import cells as C
import run18 as R18
P = C.P
COLS = [(200, 60, 60), (60, 160, 60), (60, 60, 220), (200, 140, 0), (160, 0, 160), (0, 150, 170), (120, 120, 120)]


def load(variant, doc):
    if (doc, variant) not in C._PL:
        pl = pickle.load(open(HERE / f"out/plans/{variant}_{doc}.pkl", "rb"))
        for p in pl: p["cache"] = {}
        C._PL[(doc, variant)] = pl
    return C._PL[(doc, variant)]


def sample():
    return json.load(open(E18 / "out/sample.json"))


def words():
    return {R18.wid(w): (s, w) for s, ws in sample().items() for w in ws}


def stacked_rows():
    return json.load(open(E23 / "out/summary23.json"))["rows"]


def match(w, variant):
    load(variant, w["doc"]); return C.match(w, w["doc"], variant)


def draw_piece(p, scale=4, cells=True):
    """Each letter's ink (as the PDF draws it) in its own colour, pen path black, cut points red, cells under it."""
    ink = p["ink_s"]; H, W = ink.shape; img = np.full((H, W, 3), 255, np.uint8)
    for k, (a, b) in enumerate(P.intervals(p)):
        img[P._mask(p, a, b, owner=k) > 0] = COLS[k % len(COLS)]
    for (y, x) in p["trunk"]: img[y, x] = (0, 0, 0)
    for c in p["cuts"]: y, x = p["trunk"][c]; cv2.circle(img, (x, y), 1, (0, 0, 255), -1)
    img = cv2.resize(img, (W * scale, H * scale), interpolation=cv2.INTER_NEAREST)
    if not cells: return img
    bar = np.full((12, W * scale, 3), 255, np.uint8)
    for k, (a, b) in enumerate(C.cells_orig(p) or []):
        a -= p["off"][0]; b -= p["off"][0]; cv2.rectangle(bar, (int(a * scale), 2), (int(b * scale) - 1, 9), COLS[k % len(COLS)], -1)
    return np.vstack([img, bar])


def label(img, text, h=16):
    img = cv2.copyMakeBorder(img, 0, h, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.putText(img, text[:60], (2, img.shape[0] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1); return img


def grid(tiles, width=1400, pad=6, bg=(235, 235, 235)):
    rows, row, x = [], [], 0
    for t in tiles:
        t = t[:, :width]
        if row and x + t.shape[1] > width: rows.append(row); row = []; x = 0
        row.append(t); x += t.shape[1] + pad
    if row: rows.append(row)
    out = []
    for rr in rows:
        h = max(t.shape[0] for t in rr); line = np.full((h + pad, width, 3), bg, np.uint8); x = 0
        for t in rr: line[:t.shape[0], x:x + t.shape[1]] = t; x += t.shape[1] + pad
        out.append(line)
    return np.vstack(out) if out else np.full((10, width, 3), 255, np.uint8)

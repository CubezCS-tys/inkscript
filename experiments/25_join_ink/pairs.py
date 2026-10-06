"""Side-by-side sheets: each stacked word's pieces today (left) and under a variant (right), each letter's ink in its own
colour (reading order: blue, green, red, teal, purple, olive, grey). Numbered for the eye count.
    pairs.py VARIANT NAME [START] [END]  -> out/pairs_<name>.png"""
import sys
from common import *

variant, name = sys.argv[1], sys.argv[2]; a0 = int(sys.argv[3]) if len(sys.argv) > 3 else 0; a1 = int(sys.argv[4]) if len(sys.argv) > 4 else 999
W = words(); rows = stacked_rows(); byw = {}
for r in rows: byw.setdefault(r["w"], []).append(r)
tiles = []; n = 0
for wid, rs in byw.items():
    s, w = W[wid]; m0 = match(w, "today"); m1 = match(w, variant)
    for k, (idx, p) in m0.items():
        ks = [r["k"] for r in rs if r["k"] - 1 in idx]
        if not ks or k not in m1: continue
        q = m1[k][1]
        if a0 <= n < a1:
            A, B = draw_piece(p, 3), draw_piece(q, 3); h = max(A.shape[0], B.shape[0])
            A = cv2.copyMakeBorder(A, 0, h - A.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)); B = cv2.copyMakeBorder(B, 0, h - B.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            t = np.hstack([A, np.full((h, 8, 3), 180, np.uint8), B])
            same = list(p["cuts"]) == list(q["cuts"])
            tiles.append(label(t, f"#{n} {wid} stacked k={','.join(str(x - idx[0]) for x in ks)}{' (same cuts)' if same else ''}"))
        n += 1
cv2.imwrite(str(HERE / f"out/pairs_{name}.png"), grid(tiles, 1500)); print(n)

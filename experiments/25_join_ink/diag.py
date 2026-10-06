"""Sheet of the stacked words (experiment 23's 112 letters in 50 words): pieces coloured by letter under a variant,
with experiment 21's verdict on each stacked letter (today).   diag.py VARIANT NAME"""
import sys
from common import *

variant, name = sys.argv[1], sys.argv[2]
W = words(); rows = stacked_rows(); byw = {}
for r in rows: byw.setdefault(r["w"], []).append(r)
tiles = []
for wid, rs in byw.items():
    s, w = W[wid]; m = match(w, variant)
    for k, (idx, p) in m.items():
        lab = " ".join(f"{r['k']}{'+' if r['old'] else '-'}" for r in rs if r["k"] - 1 in idx)
        if not lab: continue
        tiles.append(label(draw_piece(p, 3), f"{wid} {lab}"))
cv2.imwrite(str(HERE / f"out/diag_{name}.png"), grid(tiles))
print(len(tiles))

"""Random pieces of the sample pages whose cuts the variant changed: today (left) / variant (right), for an eye count
of collateral changes.  changed.py VARIANT NAME [N] [SEED]  -> out/changed_<name>.png, prints counts per doc"""
import sys, random
from common import *

variant, name = sys.argv[1], sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 40; seed = int(sys.argv[4]) if len(sys.argv) > 4 else 25
ch = []; tot = {}
for doc in ("0582", "0618", "1036", "0772"):
    A = {(p["page"], tuple(p["off"])): p for p in load("today", doc)}; n = 0
    for q in load(variant, doc):
        p = A.get((q["page"], tuple(q["off"])))
        if p is not None and list(p["cuts"]) != list(q["cuts"]): ch.append((doc, p, q)); n += 1
    tot[doc] = (n, len(A))
print("pieces with changed cuts (sample pages):", tot)
random.Random(seed).shuffle(ch); tiles = []
for i, (doc, p, q) in enumerate(ch[:N]):
    A, B = draw_piece(p, 3), draw_piece(q, 3); h = max(A.shape[0], B.shape[0])
    A = cv2.copyMakeBorder(A, 0, h - A.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)); B = cv2.copyMakeBorder(B, 0, h - B.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    tiles.append(label(np.hstack([A, np.full((h, 8, 3), 180, np.uint8), B]), f"#{i} {doc} p{q['page']}"))
cv2.imwrite(str(HERE / f"out/changed_{name}.png"), grid(tiles, 1500))

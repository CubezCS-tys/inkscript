"""Contact sheet of the own-height crops (judge_heights items) for chosen letters, with verdicts.
    look_heights.py VARIANT LETTERS NAME"""
import sys, json
import numpy as np, cv2
import judge_heights as H
from common import grid, label, HERE
v, letters, name = sys.argv[1:4]
its, ref = H.items(v); S = json.load(open(HERE / f"out/heights_summary_{v}.json"))["rows"]; vd = {(x["w"], x["k"]): x for x in S}
tiles = []
for r, i0, i1 in ref:
    if r["letter"] not in letters: continue
    x = vd[(r["w"], r["k"])]
    for iid, tag in ((i0, "full"), (i1, "own")):
        img = H.J.item_image(its[iid]); img = cv2.resize(img, (int(img.shape[1] * 100 / img.shape[0]), 100))
        tiles.append(label(img, f"{r['w']} k{r['k']} {tag} {'OK' if x[tag] else 'x'}"))
cv2.imwrite(str(HERE / f"out/look_heights_{name}.png"), grid(tiles, 1500))

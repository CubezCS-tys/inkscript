"""Draw Azure line boxes (green) and LiteParse word boxes scaled 300/72 (red) on a page image, to check the unit
conversion by eye.  Dev pages take Azure lines from the fetch JSON (inches x 300); exam pages from the packet.
    49 desk venv python check_boxes.py <set_mode> <stem> <page> [dev|exam]
-> out/pictures/box_check/<set_mode>_<stem>_pNNN.png"""
import json
import os
import sys

from PIL import Image, ImageDraw

X = "/home/appuser/inkscript/experiments"
E = f"{X}/99_liteparse_baseline"
sm, stem, page, kind = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
img = Image.open(f"{X}/43_rehearsal/out/pages/{stem}_p{page:03d}.jpg").convert("RGB")
if kind == "dev":
    p = json.load(open(f"{X}/74_gate2_full/out/fetch/{stem}/{stem}.json"))["pages"][page - 1]
    az = []
    for l in p["lines"]:
        xs, ys = l["polygon"][0::2], l["polygon"][1::2]
        az.append((min(xs) * 300, min(ys) * 300, max(xs) * 300, max(ys) * 300))
else:
    pk = json.load(open(f"{X}/97_extraction_evals/out/packets/{stem}/packet.json"))
    pp = next(q for q in pk["pages"] if q["page"] == page)
    az = [(l["x"], l["y"], l["x"] + l["w"], l["y"] + l["h"]) for l in pp["azure_lines"]]
lp = json.load(open(f"{E}/out/runs/{sm}/{stem}.json"))["pages"][str(page)]
sc = img.width / lp["width"]
d = ImageDraw.Draw(img)
for b in az:
    d.rectangle(b, outline=(0, 170, 0), width=3)
for it in lp["text_items"]:
    for w in it.get("words") or [it]:
        d.rectangle([w["x"] * sc, w["y"] * sc, (w["x"] + w["width"]) * sc, (w["y"] + w["height"]) * sc], outline=(220, 0, 0), width=2)
os.makedirs(f"{E}/out/pictures/box_check", exist_ok=True)
f = f"{E}/out/pictures/box_check/{sm}_{stem}_p{page:03d}.png"
img.resize((img.width // 2, img.height // 2)).save(f)
print(f, "scale", round(sc, 4), "expected", round(300 / 72, 4))

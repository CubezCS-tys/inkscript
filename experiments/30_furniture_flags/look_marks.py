"""Contact sheets of blocks marked handwritten / vowelled on printed pages (trust.regions), cropped from the scan, to
check the marks by eye.  -> out/look/marks_<kind>_<n>.png

    PYTHONPATH=src .venv/bin/python experiments/30_furniture_flags/look_marks.py KIND [N]
"""
import random
import sys
from pathlib import Path

import pymupdf

from inkscript.enrich import trust as T
from inkscript.enrich.document import load
from inkscript.enrich.structure import _box

HERE = Path(__file__).resolve().parent
DATA = Path("/home/yassine/inkscript/experiments/28_scale/out")
kind = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 16
items = []
for d in sorted((DATA / "azure").iterdir()):
    doc = load(d / f"{d.name}.json")
    reg = T.regions(doc)
    for i, ms in reg["blocks"].items():
        p = doc["paras"][i]
        pg = doc["words"][p["words"][0]]["page"]
        if kind in ms and pg not in reg["pages"]:
            ws = [doc["words"][k] for k in p["words"] if doc["words"][k]["page"] == pg]
            items.append((d.name, pg, _box(ws), doc["pages"][pg]["w"], doc["pages"][pg]["h"],
                          " ".join(w["text"] for w in ws)[:60]))
random.Random(30).shuffle(items)
print(len(items), "blocks")
(HERE / "out" / "look").mkdir(parents=True, exist_ok=True)
sample = items[:N]
for k in range(0, len(sample), 8):
    out = pymupdf.open()
    sp = out.new_page(width=1200, height=4 * 230)
    for j, (s, p, b, W, H, t) in enumerate(sample[k:k + 8]):
        src = pymupdf.open(str(DATA / "azure" / s / f"{s}.pdf"))
        R = src[p - 1].rect
        sx, sy = R.width / W, R.height / H
        y0, y1 = max(0, b[1] - 60), min(H, b[3] + 60)
        x0, x1 = max(0, b[0] - 200), min(W, b[2] + 200)
        clip = pymupdf.Rect(x0 * sx, y0 * sy, x1 * sx, y1 * sy)
        x, y = (j % 2) * 600, (j // 2) * 230
        sp.show_pdf_page(pymupdf.Rect(x + 4, y + 4, x + 596, y + 210), src, p - 1, clip=clip)
        sp.insert_text((x + 6, y + 222), f"{k + j}: {s} p{p}", fontsize=9)
        print(k + j, s, p, t)
    sp.get_pixmap(matrix=pymupdf.Matrix(1, 1)).save(str(HERE / "out" / "look" / f"marks_{kind}_{k // 8}.png"))

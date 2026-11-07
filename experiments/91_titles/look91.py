"""Experiment 91: contact sheets to LOOK at title crops with their labels (the crop as printed, then the strict label
rendered in Noto Naskh Arabic under it, with Azure's line and the reader's when they differ from the label).

    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python look91.py RESDIR N SEED [differ]
        RESDIR holds labels91_titles.jsonl, manifest91*.jsonl and look91/ (unpacked look91*.tgz); N crops are drawn
        at random from the looked-at documents (one in 40) -> RESDIR/sheets/look91_NN.png, RESDIR/sheets/list.jsonl
        `differ`: draw only lines whose label is not Azure's line (the catalogue-corrected ones), plus every dropped
        differ line's Azure text is listed.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"


def main(res: str, n: int, seed: int, only_differ: bool = False):
    R = Path(res)
    L = {d["key"]: d for d in map(json.loads, open(R / "labels91_titles.jsonl", encoding="utf-8"))}
    M = {}
    for f in R.glob("manifest91*.jsonl"):
        for l in open(f, encoding="utf-8"):
            d = json.loads(l)
            M[d["key"]] = d
    keys = sorted(k for k in L if (R / "look91" / f"{k}.png").exists())
    if only_differ:
        keys = [k for k in keys if L[k]["label"] != M[k]["azure"]]
    random.Random(seed).shuffle(keys)
    keys = keys[:n]
    out = R / "sheets"
    out.mkdir(exist_ok=True)
    f_ar = ImageFont.truetype(FONT, 26, layout_engine=ImageFont.Layout.RAQM)
    f_sm = ImageFont.truetype(FONT, 18, layout_engine=ImageFont.Layout.RAQM)
    f_la = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    W, per = 1500, 10
    tag = "differ" if only_differ else "look"
    with open(out / f"list_{tag}.jsonl", "w", encoding="utf-8") as fl:
        for s in range(0, len(keys), per):
            part = keys[s:s + per]
            Hh = 170
            cv = Image.new("L", (W, Hh * len(part)), 255)
            d = ImageDraw.Draw(cv)
            for j, k in enumerate(part):
                y = j * Hh
                im = cv2.imread(str(R / "look91" / f"{k}.png"), cv2.IMREAD_GRAYSCALE)
                sc = min(1.0, (W - 10) / im.shape[1])
                im = cv2.resize(im, (max(1, int(im.shape[1] * sc)), max(1, int(im.shape[0] * sc))))
                cv.paste(Image.fromarray(im), (W - im.shape[1] - 5, y + 2))
                d.text((W - 8, y + 78), L[k]["label"], font=f_ar, fill=0, anchor="ra", direction="rtl")
                if L[k]["label"] != M[k]["azure"]:
                    d.text((W - 8, y + 118), "Azure: " + M[k]["azure"], font=f_sm, fill=90, anchor="ra", direction="rtl")
                m = M[k]
                d.text((5, y + 80), f"{s + j}  {k}", font=f_la, fill=0)
                d.text((5, y + 98), f"{m['era']} {m['set']} {L[k]['why']} rel {m['rel']}", font=f_la, fill=0)
                d.line([(0, y + Hh - 1), (W, y + Hh - 1)], fill=150)
                fl.write(json.dumps(dict(n=s + j, key=k, label=L[k]["label"], azure=M[k]["azure"], why=L[k]["why"],
                                         era=m["era"]), ensure_ascii=False) + "\n")
            cv.save(out / f"{tag}91_{s // per:02d}.png")
    print(len(keys), "crops on", (len(keys) + per - 1) // per, "sheets in", out)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), len(sys.argv) > 4 and sys.argv[4] == "differ")

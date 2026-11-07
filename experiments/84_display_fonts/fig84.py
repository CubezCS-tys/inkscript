"""Experiment 84: the owner's picture (out/look/result84.png): real held-out lines, what v3 and v5 read, and the numbers."""
import ast, json, sys, tarfile
from pathlib import Path
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
H = Path(__file__).resolve().parent
E81 = H.parent / "81_heldout_scale/out"
AR = ImageFont.truetype("/home/appuser/.local/share/fonts/Amiri-Regular.ttf", 24, layout_engine=ImageFont.Layout.RAQM)
LA = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", 17)
LB = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", 20)
W = 1500
rows = json.loads(sys.argv[1]) if len(sys.argv) > 1 else None


def judge_crop(k):
    return Image.open(E81 / "judge/crops" / f"{k}.png").convert("RGB")


def test_crop(k):
    with tarfile.open(H.parent / "77_scratch_reader/out/test/test-0-000.tar") as t:
        b = t.extractfile(k + ".jpg").read()
    return Image.fromarray(cv2.imdecode(np.frombuffer(b, np.uint8), 0)).convert("RGB").resize((0, 0)) if False else \
        Image.fromarray(cv2.resize(cv2.imdecode(np.frombuffer(b, np.uint8), 0), None, fx=1.6, fy=1.6)).convert("RGB")


def main():
    spec = json.loads((H / "out/fig84_rows.json").read_text(encoding="utf-8"))
    blocks = []
    for sec in spec["sections"]:
        blocks.append(("title", sec["title"]))
        for r in sec["rows"]:
            im = judge_crop(r["key"]) if sec["src"] == "judge" else test_crop(r["key"])
            blocks.append(("row", im, r))
    blocks.append(("title", spec["numbers_title"]))
    for l in spec["numbers"]:
        blocks.append(("text", l))
    h = 30
    for b in blocks:
        h += 44 if b[0] == "title" else 30 if b[0] == "text" else b[1].height * min(1, (W - 60) / b[1].width) + 3 * 34 + 18
    page = Image.new("RGB", (W, int(h) + 30), "#fcfcfb")
    d = ImageDraw.Draw(page)
    y = 20
    for b in blocks:
        if b[0] == "title":
            d.text((24, y + 10), b[1], font=LB, fill="#0b0b0b"); y += 44
        elif b[0] == "text":
            d.text((24, y), b[1], font=LA, fill="#0b0b0b"); y += 30
        else:
            _, im, r = b
            s = min(1, (W - 60) / im.width)
            im = im.resize((int(im.width * s), int(im.height * s)))
            page.paste(im, (W - 30 - im.width, y)); y += im.height + 4
            for lab, t, col in (("truth", r["truth"], "#0b0b0b"), ("v3 (before)", r["v3"], "#b4471b"), ("v5 (after)", r["v5"], "#1f7a3a")):
                d.text((24, y + 6), lab, font=LA, fill=col)
                d.text((W - 30, y), t, font=AR, fill=col, anchor="ra", direction="rtl")
                y += 34
            y += 14
    page.save(H / "out/look/result84.png")
    print(page.size)


main()

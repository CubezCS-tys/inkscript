"""A stratified random sample of the blocks the structure step set aside as page furniture on the 205 documents
(census_before.json), each cropped from the scan with its neighbourhood and boxed in red, to judge by eye.

    .venv/bin/python experiments/30_furniture_flags/furniture_sample.py
      -> out/furniture_sample.json (the blocks, in sheet order) and out/look/furniture_<n>.png (10 per sheet)

Strata (by the rule that set the block aside and whether its letters repeat 3+ times among the document's
furniture, as experiment 28's furniture.py counts): rep-lone 40, rep-repeated 30, top8 15, bottom6 12, side 12,
masthead 8, speck-digit 15, page-number 8. The verdicts are in truth/furniture_truth.json.
"""
import json
import random
import re
from collections import Counter
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
DATA = Path("/home/yassine/inkscript/experiments/28_scale/out")
norm = lambda s: re.sub(r"[^ء-يa-zA-Z]", "", s or "")
STRATA = {"rep-lone": 40, "rep-repeated": 30, "top8": 15, "bottom6": 12, "side": 12, "masthead": 8,
          "speck-digit": 15, "page-number": 8}


def stratum(b, cnt):
    L = len(norm(b["text"])) >= 3
    w = b["why"]
    if w.startswith("repeats"):
        return "rep-lone" if L and cnt[norm(b["text"])] <= 2 else ("rep-repeated" if L else None)
    if w.startswith("short text in the top"):
        return "top8" if L else None
    if w.startswith("short text in the bottom"):
        return "bottom6" if L else None
    if w.startswith("text on its side"):
        return "side" if L else None
    if w.startswith("the journal"):
        return "masthead"
    if w.startswith("a speck"):
        return "speck-digit"
    if w.startswith("digits alone"):
        return "page-number"
    return None


def draw(sample, prefix):
    """Contact sheets, 10 blocks each: the page's full width around the block, the block boxed in red."""
    (HERE / "out" / "look").mkdir(parents=True, exist_ok=True)
    for k in range(0, len(sample), 10):
        out = pymupdf.open()
        sp = out.new_page(width=1400, height=5 * 260)
        for j, x in enumerate(sample[k:k + 10]):
            src = pymupdf.open(str(DATA / "azure" / x["doc"] / f"{x['doc']}.pdf"))
            R = src[x["page"] - 1].rect
            W, H = x["W"], x["H"]
            sx, sy = R.width / W, R.height / H
            b = x["box"]
            h = max(b[3] - b[1], 70)
            y0, y1 = max(0, b[1] - 2.5 * h), min(H, b[3] + 2.5 * h)
            clip = pymupdf.Rect(0, y0 * sy, R.width, y1 * sy)
            X, Y = (j % 2) * 700, (j // 2) * 260
            box = pymupdf.Rect(X + 4, Y + 4, X + 696, Y + 236)
            sp.show_pdf_page(box, src, x["page"] - 1, clip=clip)
            # where the block lands inside the drawn crop (show_pdf_page keeps the aspect ratio, centred)
            cw, ch = clip.width, clip.height
            s_ = min(box.width / cw, box.height / ch)
            ox, oy = box.x0 + (box.width - cw * s_) / 2, box.y0 + (box.height - ch * s_) / 2
            rr = pymupdf.Rect(ox + b[0] * sx * s_, oy + (b[1] * sy - clip.y0) * s_,
                              ox + b[2] * sx * s_, oy + (b[3] * sy - clip.y0) * s_)
            sp.draw_rect(rr, color=(1, 0, 0), width=1.5)
            sp.insert_text((X + 6, Y + 250), f"{x['n']}: {x['doc']} p{x['page']} y={b[1] / H:.2f}-{b[3] / H:.2f} "
                                             f"[{x['stratum']}] h={x['h_rel']}", fontsize=10)
            src.close()
        sp.get_pixmap(matrix=pymupdf.Matrix(1, 1)).save(str(HERE / "out" / "look" / f"{prefix}_{k // 10:02d}.png"))


if __name__ == "__main__":
    census = json.loads((HERE / "out" / "census_before.json").read_text(encoding="utf-8"))
    pools = {k: [] for k in STRATA}
    for stem, r in sorted(census.items()):
        cnt = Counter(norm(b["text"]) for b in r["furniture"])
        for b in r["furniture"]:
            s = stratum(b, cnt)
            if s:
                pools[s].append(dict(doc=stem, stratum=s, **b))
    rng = random.Random(30)
    sample = []
    for s, n in STRATA.items():
        rng.shuffle(pools[s])
        sample += pools[s][:n]
    for k, x in enumerate(sample):
        x["n"] = k
    (HERE / "out" / "furniture_sample.json").write_text(json.dumps(sample, ensure_ascii=False, indent=1), encoding="utf-8")
    draw(sample, "furniture")
    for x in sample:
        print(x["n"], x["stratum"], x["doc"], x["page"], x["text"][:70])

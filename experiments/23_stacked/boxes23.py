"""Experiment 18's sample words read back from the post-processed PDFs (post.py, variant cell): for each letter its
box as Chromium 153 draws it when that letter alone is selected. x: the glyph's declared box (unchanged); y: for a
stacked letter its own font's FontBBox (its whole ink), for every other letter None = the line's full height (what
experiment 18's crop already draws: a band over the word's height).

    ../../.venv/bin/python boxes23.py [variant=cell]     -> out/boxes_<variant>.json {word id: {"cells": [[x0,x1]..], "ys": [[y0,y1]|None..]}}
"""
import sys, json
from pathlib import Path
import fitz
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]; E18 = REPO / "experiments/18_boxes"; E21 = REPO / "experiments/21_better_boxes"
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(E18))
import glyphs as G
import run18 as R


def pdf_words(doc, pno, stacked):
    """21's boxes.pdf_words on glyphs read with the multi-TJ reader, plus each letter's stacked box (or None)."""
    gl = G.glyphs(doc, pno); words = []; by_font = {}
    for g in gl: by_font.setdefault(g["font"], []).append(g)
    for fn, gs in by_font.items():
        gs = sorted(gs, key=lambda g: g["box_px"][0]); cur = []
        for g in gs:
            if cur and g["box_px"][0] - cur[-1]["box_px"][2] > 0.6: words.append(cur); cur = []
            cur.append(g)
        if cur: words.append(cur)
    out = []
    for ws in words:
        vis = "".join(g["text"] for g in ws); cells = []; ys = []
        for g in ws:
            x0, x1 = g["box_px"][0], g["box_px"][2]; n = max(1, len(g["text"]))
            cells += [((x0 + (x1 - x0) * i / n), (x0 + (x1 - x0) * (i + 1) / n)) for i in range(n)]
            st = stacked.get((round(x0, 1), round(x1, 1), g["text"]))
            ys += [st] * n
        if len(cells) != len(vis): continue
        out.append(dict(text=vis[::-1], cells=cells[::-1], ys=ys[::-1], x0=ws[0]["box_px"][0], x1=ws[-1]["box_px"][2],
                        y=sum((g["box_px"][1] + g["box_px"][3]) / 2 for g in ws) / len(ws)))
    return out


def main(variant="cell"):
    S = json.load(open(E18 / "out/sample.json")); res = {}; miss = []; cache = {}
    for s, ws in S.items():
        for w in ws:
            key = (w["doc"], w["page"]); path = HERE / f"out/post/{w['doc']}_{variant}.pdf"
            if key not in cache:
                rep = json.load(open(path.with_suffix(".json")))[str(w["page"])]
                stacked = {(round(c["adv_px"][0], 1), round(c["adv_px"][2], 1), c["text"]): [c["box_px"][1], c["box_px"][3]] for c in rep}
                cache[key] = pdf_words(fitz.open(str(path)), w["page"], stacked)
            ox0, ox1 = min(a for a, _ in w["cutter"]), max(b for _, b in w["cutter"]); y0, y1 = w["box"][1], w["box"][3]
            best = None
            for pw in cache[key]:
                if pw["text"] != w["text"]: continue
                ov = min(ox1, pw["x1"]) - max(ox0, pw["x0"])
                if ov > 0.6 * min(ox1 - ox0, pw["x1"] - pw["x0"]) and y0 - 10 <= pw["y"] <= y1 + 10 and (best is None or ov > best[0]): best = (ov, pw)
            if best is None: miss.append(R.wid(w)); continue
            res[R.wid(w)] = dict(cells=[list(c) for c in best[1]["cells"]], ys=best[1]["ys"])
    json.dump(res, open(HERE / f"out/boxes_{variant}.json", "w"))
    N = json.load(open(E21 / "out/boxes_new.json"))
    same_x = sum(1 for k, v in res.items() if k in N and all(abs(a - c) < 0.6 and abs(b - d) < 0.6 for (a, b), (c, d) in zip(v["cells"], N[k]["cells"])))
    nst = sum(1 for v in res.values() for y in v["ys"] if y); nw = sum(1 for v in res.values() if any(v["ys"]))
    print(f"{len(res)} words read back, {len(miss)} not found {miss[:8]}; x boxes identical to 21's after-build: {same_x}; stacked letters {nst} in {nw} words")


if __name__ == "__main__":
    main(*sys.argv[1:])

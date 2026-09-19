"""Why pieces are or are not cut in the build: python diagnose.py <azure.json> <scan.pdf> [text-to-print]"""
import sys, json, numpy as np, fitz, cv2
from collections import Counter
from pathlib import Path
from inkscript.geometry import penpath as P
from inkscript.geometry.letters import letters_of, line_geometry
from inkscript.text import pieces, MARKS
from inkscript.ocr.azure import load_azure
from inkscript.geometry.trace import page_blobs
from inkscript.geometry.layout import layout_page, split_word

azure, scan = Path(sys.argv[1]), sys.argv[2]; show = sys.argv[3] if len(sys.argv) > 3 else None
words, _, dims = load_azure(azure); j = json.load(open(azure)); ar = j.get("analyzeResult", j); az = {p["pageNumber"]: p for p in ar["pages"]}
doc = fitz.open(scan); plans = []; tried = 0
for pno in range(doc.page_count):
    pn = pno + 1; pw = [w for w in words if w["page"] == pn]; pix = doc[pno].get_pixmap(dpi=300, colorspace=fitz.csGRAY); gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); ink = ink > 0
    W_in, H_in = dims[pn]; blobs = page_blobs(gray); lines, _ = layout_page(pw, [w["text"] for w in pw], az[pn].get("lines", []), blobs, gray.shape[1] / W_in, gray.shape[0] / H_in)
    for L in lines:
        bl = [b for w in L if w["blobs"] for b in w["blobs"]]
        if not bl: continue
        lh = max(1.0, max(b["y"] + b["h"] for b in bl) - min(b["y"] for b in bl)); lg = line_geometry(ink, bl)
        for w in L:
            if not w["blobs"] or MARKS.search(w["text"]): continue
            for pc in split_word(w, lh):
                t = pc["text"].strip(); u = letters_of(t)
                if len(pieces(t)) != 1 or len(u) < 2: continue
                tried += 1; p = P.plan(u, pc["blobs"], lg)
                if p: p["text"] = t; plans.append(p)
P.solve(plans); why = Counter(); fails = Counter()
for p in plans:
    fl = [tuple(ok or not r for ok, r in zip(P._facts(p, k, a, b)[:4], p["reliable"].get(P.key(p, k), (True,) * 4))) for k, (a, b) in enumerate(P.intervals(p))]; fk = all(all(f) for f in fl)
    sk = all(s is not None and s >= P.AGREE for s in p["scores"])
    why["accepted" if P.accepted(p) else "facts fail" if not fk else "unlike the atlas" if not sk else "no positive fact"] += 1
    for f in fl:
        for name, ok in zip(("tall stroke", "bowl", "dots above", "dots below"), f): fails[name] += not ok
print("pieces of 2+ letters", tried, "| on a pen path", len(plans), "|", dict(why)); print("failed facts by kind:", dict(fails))
for p in [p for p in plans if p["text"] == show][:6]:
    print(show, "cuts", p["cuts"], "of", p["G"]["W"], "scores", [round(s, 2) if s is not None else None for s in p["scores"]], "facts", [tuple(bool(v) for v in P._facts(p, k, a, b)[:4]) for k, (a, b) in enumerate(P.intervals(p))])

import random, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from penpath import picture
from atlas import sheet
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(out, exist_ok=True); random.seed(21)
def tiles(ps):
    r = []
    for p in ps:
        im = picture(p["F"], p["ink_s"], p["cuts"], p["G"], p["n"], up=4); r.append(cv2.copyMakeBorder(im, 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
    return r
acc = [p for p in plans if P.accepted(p)]; rej = [p for p in plans if not P.accepted(p)]
sheet(tiles(random.sample(acc, min(90, len(acc)))), f"{out}/accepted90_{azure.stem[:4]}.png"); sheet(tiles(random.sample(rej, min(45, len(rej)))), f"{out}/rejected45_{azure.stem[:4]}.png")

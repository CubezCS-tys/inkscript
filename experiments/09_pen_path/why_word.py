"""For given words on a page: how they split, and what happens to each piece. python why_word.py <azure.json> <scan.pdf> <page> <word,word>"""
import sys, json, numpy as np, fitz, cv2
from pathlib import Path
from inkscript.geometry import penpath as P
from inkscript.geometry.letters import line_geometry, piece_mask, analyse
from inkscript.text import MARKS
from inkscript.ocr.azure import load_azure
from inkscript.geometry.trace import page_blobs
from inkscript.geometry.layout import layout_page, split_word, ink_pieces
azure, scan, pn, want = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4].split(",")
words, _, dims = load_azure(azure); j = json.load(open(azure)); ar = j.get("analyzeResult", j); az = {p["pageNumber"]: p for p in ar["pages"]}
doc = fitz.open(scan); pw = [w for w in words if w["page"] == pn]; pix = doc[pn - 1].get_pixmap(dpi=300, colorspace=fitz.csGRAY); gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
_, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); ink = ink > 0
W_in, H_in = dims[pn]; blobs = page_blobs(gray); lines, _ = layout_page(pw, [w["text"] for w in pw], az[pn].get("lines", []), blobs, gray.shape[1] / W_in, gray.shape[0] / H_in)
for L in lines:
    bl = [b for w in L if w["blobs"] for b in w["blobs"]]
    if not bl: continue
    lh = max(1.0, max(b["y"] + b["h"] for b in bl) - min(b["y"] for b in bl)); lg = line_geometry(ink, bl)
    for w in L:
        if w["text"] not in want or not w["blobs"]: continue
        pcs = split_word(w, lh); print(f"\n{w['text']}: {len(w['blobs'])} blobs, {len(ink_pieces(w, lh))} ink pieces -> pieces {[pc['text'] for pc in pcs]}  line rise {lg and round(lg['rise'])}")
        for pc in pcs:
            uf = P.units_forms(pc["text"].strip())
            if not uf or len(uf[0]) < 2: continue
            p = P.plan(uf[0], pc["blobs"], lg, uf[1])
            if p is None:
                m, off = piece_mask(pc["blobs"]); F = analyse(m, lg, off[1]) if lg else None
                print("   ", pc["text"], "no plan:", "no line" if not lg or lg["rise"] < 10 else "not one main blob" if F is None else "no path" if P.unroll(F, lg, off[1]) is None else f"candidates too few")
            else:
                lb = P.letter_blobs(p, pc["blobs"]); print("   ", pc["text"], "cuts", p["cuts"], "of", p["G"]["W"], "->", "letters ok" if len(lb) == p["n"] else "letter_blobs refused (cell under 2 px: path doubles back)")

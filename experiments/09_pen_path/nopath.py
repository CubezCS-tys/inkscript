"""Why pieces of a document end up without letters: python nopath.py <azure.json> <scan.pdf> <pages e.g. 2,3>"""
import sys, json, numpy as np, fitz, cv2
from collections import Counter
from pathlib import Path
from inkscript.geometry import penpath as P
from inkscript.geometry.letters import line_geometry, piece_mask, analyse
from inkscript.text import MARKS
from inkscript.ocr.azure import load_azure
from inkscript.geometry.trace import page_blobs
from inkscript.geometry.layout import layout_page, split_word
azure, scan, pages = Path(sys.argv[1]), sys.argv[2], [int(p) for p in sys.argv[3].split(",")]
words, _, dims = load_azure(azure); j = json.load(open(azure)); ar = j.get("analyzeResult", j); az = {p["pageNumber"]: p for p in ar["pages"]}
doc = fitz.open(scan); why = Counter(); ex = {}
for pn in pages:
    pw = [w for w in words if w["page"] == pn]; pix = doc[pn - 1].get_pixmap(dpi=300, colorspace=fitz.csGRAY); gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); ink = ink > 0
    W_in, H_in = dims[pn]; blobs = page_blobs(gray); lines, _ = layout_page(pw, [w["text"] for w in pw], az[pn].get("lines", []), blobs, gray.shape[1] / W_in, gray.shape[0] / H_in)
    for L in lines:
        bl = [b for w in L if w["blobs"] for b in w["blobs"]]
        if not bl: continue
        lh = max(1.0, max(b["y"] + b["h"] for b in bl) - min(b["y"] for b in bl)); lg = line_geometry(ink, bl)
        for w in L:
            if not w["blobs"]: why["word has no ink matched"] += 1; continue
            if MARKS.search(w["text"]): why["word has vowel marks (never tried)"] += 1; continue
            pcs = split_word(w, lh)
            for pc in pcs:
                t = pc["text"].strip(); uf = P.units_forms(t)
                if not uf:
                    if len(t) > 1 and any("ء" <= c <= "ي" for c in t): why["piece text is not plain Arabic runs (digits, Latin, punctuation inside, or a space)"] += 1; ex.setdefault("mixed", []).append(t)
                    continue
                if len(uf[0]) < 2: continue
                p = P.plan(uf[0], pc["blobs"], lg, uf[1])
                if p:
                    r = "cut" if len(P.letter_blobs(p, pc["blobs"])) == p["n"] else "cut refused: path doubles back (a cell under 2 px)"
                else:
                    m, off = piece_mask(pc["blobs"])
                    if not lg or lg["rise"] < 10: r = "line too small or not measured"
                    elif m.shape[1] < 4 * len(uf[0]): r = "ink narrower than 4 px per letter"
                    else:
                        F = analyse(m, lg, off[1]); br = None
                        if F is None:
                            br = P.bridge(m, 0.5 * lg["rise"]); F = analyse(br, lg, off[1]) if br is not None else None
                        r = ("ink in several blobs too far apart to bridge" + (" (word not split into its runs)" if len(pcs) == 1 and len(uf[1]) and uf[1].count("init") + uf[1].count("iso") > 1 else "")) if F is None else "no path across the ink" if P.unroll(F, lg, off[1]) is None else "fewer cut places than cuts"
                why[r] += 1; ex.setdefault(r, []).append(t)
tot = sum(why.values())
for k, v in why.most_common(): print(f"{v:5d} {100 * v / tot:5.1f}%  {k}   {ex.get(k, [])[:10]}")

"""Label-once test: group WORD shapes (all ink inside a word box) across a
document with no OCR input, then check against the OCR words whether shapes
grouped together really carry the same text."""
import sys, json, unicodedata, re
from pathlib import Path
import numpy as np, cv2, fitz
sys.path.insert(0, "/home/cubez/Desktop/AI-Search-Mandumah/scripts")
import ocr_native_pdf as NP, ocr_frontpage as F
from ocr_hybrid import load_azure, norm

B = Path("/home/cubez/Desktop/OCR_gem_json/output/bakeoff_full"); FP = Path("/home/cubez/Desktop/OCR_gem_json/output/frontpage_set")
DOCS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["0582-004-009-012"]
IOU_T = float(sys.argv[2]) if len(sys.argv) > 2 else 0.80
C = 48

def canvas(blobs):
    x0 = min(b["x"] for b in blobs); y0 = min(b["y"] for b in blobs)
    x1 = max(b["x"] + b["w"] for b in blobs); y1 = max(b["y"] + b["h"] for b in blobs)
    w, h = x1 - x0, y1 - y0; s = (C - 2) / max(w, h, 1); ox, oy = (C - w * s) / 2, (C - h * s) / 2
    img = np.zeros((C, C), np.uint8)
    for b in blobs:
        for p, hole in zip(b["paths"], b["holes"]):
            cv2.fillPoly(img, [((p - [x0, y0]) * s + [ox, oy]).astype(np.int32)], 0 if hole else 255)
    return img > 0, w, h

items = []            # (fill, w_units, h_units, text)
for S in DOCS:
    words, _, dims = load_azure(B / "azure" / S / f"{S}.json")
    j = json.load(open(B / "azure" / S / f"{S}.json")); ar = j.get("analyzeResult", j)
    src = fitz.open(B / "input" / f"{S}.pdf")
    for pno in range(src.page_count):
        pn = pno + 1; pw = [w for w in words if w["page"] == pn]
        if not pw: continue
        texts = None
        if pn == 1 and (FP / f"{S}.gemini.p1.md").exists():
            texts, _ = F.page1_text(pw, F.fold_digits((FP / f"{S}.gemini.p1.md").read_text()), 0.6)
        if texts is None: texts = [w["text"] for w in pw]
        pix = src[pno].get_pixmap(dpi=300, colorspace=fitz.csGRAY); gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
        blobs = NP.page_blobs(gray)
        lines, _ = NP.layout_page(pw, texts, ar["pages"][pno].get("lines", []), blobs, pix.w / dims[pn][0], pix.h / dims[pn][1])
        unit = np.median([w["y1"] - w["y0"] for L in lines for w in L if w["blobs"]])
        for L in lines:
            for w in L:
                if not w["blobs"]: continue
                t = norm(w["text"].strip() or w["az"])
                if not t: continue
                fill, ww, hh = canvas(w["blobs"])
                items.append(dict(fill=fill, w=ww / unit, h=hh / unit, text=t, raw=(w["text"].strip() or w["az"])))
print(f"{len(items)} words with ink across {DOCS}")

# greedy grouping, no text used
clusters = []
F_ = []
for it in items:
    best, bi = 0.0, -1
    for ci, c in enumerate(clusters):
        p = c["proto"]
        if abs(p["h"] - it["h"]) > 0.12 * max(p["h"], 0.3) or abs(p["w"] - it["w"]) > 0.12 * max(p["w"], 0.3): continue
        inter = np.logical_and(p["fill"], it["fill"]).sum(); union = np.logical_or(p["fill"], it["fill"]).sum()
        s = inter / union if union else 0
        if s > best: best, bi = s, ci
    if best >= IOU_T: clusters[bi]["m"].append(it)
    else: clusters.append(dict(proto=it, m=[it]))
multi = [c for c in clusters if len(c["m"]) > 1]
in_multi = sum(len(c["m"]) for c in multi)
agree = 0; bad = []
for c in multi:
    from collections import Counter
    cnt = Counter(m["text"] for m in c["m"]); top, n = cnt.most_common(1)[0]
    agree += n
    if n < len(c["m"]): bad.append((len(c["m"]), [m["raw"] for m in c["m"]][:6]))
print(f"IoU>={IOU_T}: {len(clusters)} shape groups for {len(items)} words; {len(multi)} groups have 2+ members covering {in_multi} words ({in_multi/len(items):.0%})")
print(f"label-once accuracy inside those groups: {agree}/{in_multi} = {agree/max(1,in_multi):.1%}  (words whose text matches the group's majority text)")
print(f"groups that mix different words: {len(bad)}; examples:")
for n, ex in sorted(bad, key=lambda x: -x[0])[:12]: print(f"   {n} members: {ex}")

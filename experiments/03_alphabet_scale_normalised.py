"""Shape alphabet v2: scale-normalised per page, matched on outlines.

1. Each page's unit = median height of its letter-sized blobs. Blob sizes are
   compared in units, so a page scanned 10% larger still matches.
2. Shapes are compared as outlines: every blob's polygon paths are drawn into a
   48x48 canvas (aspect preserved, scaled by the blob's box), then two scores:
   IoU of the filled outline, and symmetric chamfer distance between the two
   boundaries (mean distance from each boundary pixel to the other's nearest).
"""
import sys, json
from pathlib import Path
import numpy as np, cv2, fitz

IN = Path("/home/cubez/Desktop/OCR_gem_json/output/bakeoff_full/input")
OUT = Path(__file__).parent
DPI, C = 300, 48
IOU_T = float(sys.argv[1]) if len(sys.argv) > 1 else 0.75
CH_T = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
DOCS = ["0582-004-009-012", "0582-006-015-002", "0664-012-003-020", "0664-015-008-036", "0664-016-006-031"]

def canvas(paths, holes, w, h):
    """Outline drawn into CxC, aspect preserved. Returns (fill bool, boundary dist transform)."""
    s = (C - 2) / max(w, h, 1)
    ox, oy = (C - w * s) / 2, (C - h * s) / 2
    img = np.zeros((C, C), np.uint8)
    for p, hole in zip(paths, holes):
        pts = (p * s + [ox, oy]).astype(np.int32)
        cv2.fillPoly(img, [pts], 0 if hole else 255)
    fill = img > 0
    edge = fill ^ cv2.erode(img, np.ones((3, 3), np.uint8)).astype(bool)
    dist = cv2.distanceTransform((~edge).astype(np.uint8), cv2.DIST_L2, 3)
    return fill, edge, dist

def page_blobs(gray):
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 6: continue
        mask = (lab[y:y+h, x:x+w] == i).astype(np.uint8)
        cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        keep = [(cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2), int(hier[0][k][3] >= 0)) for k, c in enumerate(cs)]
        keep = [(p, hh) for p, hh in keep if len(p) >= 3]
        if not keep: continue
        out.append(dict(x=int(x), y=int(y), w=int(w), h=int(h), area=int(area),
                        paths=[p for p, _ in keep], holes=[hh for _, hh in keep]))
    unit = float(np.median([b["h"] for b in out if b["area"] >= 40])) if out else 1.0
    for b in out:
        b["hu"], b["wu"] = b["h"] / unit, b["w"] / unit
        b["fill"], b["edge"], b["dist"] = canvas(b["paths"], b["holes"], b["w"], b["h"])
    return ink, out, unit

# dictionary
protos, fills, edges, dists, counts, index = [], [], [], [], [], {}
def key(b): return (int(b["hu"] * 8), int(b["wu"] * 8))
def assign(b):
    kh, kw = key(b); cands = []
    for dh in (-1, 0, 1):
        for dw in (-1, 0, 1):
            cands += index.get((kh + dh, kw + dw), [])
    cands = [c for c in cands if abs(protos[c]["hu"] - b["hu"]) <= 0.12 * max(b["hu"], 0.3)
             and abs(protos[c]["wu"] - b["wu"]) <= 0.12 * max(b["wu"], 0.3)]
    if cands:
        F = np.stack([fills[c] for c in cands])
        inter = np.logical_and(F, b["fill"]).sum((1, 2)); union = np.logical_or(F, b["fill"]).sum((1, 2))
        iou = inter / np.maximum(union, 1)
        order = np.argsort(-iou)[:5]
        for o in order:
            if iou[o] < IOU_T: break
            c = cands[o]
            ch = 0.5 * (dists[c][b["edge"]].mean() + b["dist"][edges[c]].mean())
            if ch <= CH_T:
                counts[c] += 1; return c
    protos.append(b); fills.append(b["fill"]); edges.append(b["edge"]); dists.append(b["dist"]); counts.append(1)
    ci = len(protos) - 1; index.setdefault(key(b), []).append(ci); return ci

curve, tot, pages = [], 0, []
for doc in DOCS:
    pdf = fitz.open(IN / f"{doc}.pdf")
    for pno in range(pdf.page_count):
        pix = pdf[pno].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
        gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
        ink, blobs, unit = page_blobs(gray)
        before = len(protos)
        for b in blobs: b["cid"] = assign(b)
        tot += len(blobs)
        curve.append(dict(doc=doc, page=pno + 1, blobs=tot, shapes=len(protos), new=len(protos) - before, page_blobs=len(blobs), unit=unit))
        pages.append((doc, pno, gray, ink, blobs))
        print(f"{doc} p{pno+1}: unit {unit:4.1f}px {len(blobs):>4} blobs, {len(protos)-before:>4} new -> {tot:>5} blobs / {len(protos):>4} shapes", flush=True)

# rebuild page 1 of doc 1 from prototypes only
doc, pno, gray, ink, blobs = pages[0]
H, W = ink.shape; rebuilt = np.full((H, W), 255, np.uint8)
for b in blobs:
    p = protos[b["cid"]]; sx, sy = b["w"] / max(1, p["w"]), b["h"] / max(1, p["h"])
    for path, hole in zip(p["paths"], p["holes"]):
        cv2.fillPoly(rebuilt, [(path * [sx, sy] + [b["x"], b["y"]]).astype(np.int32)], 255 if hole else 0)
agree = 1 - np.logical_xor(ink > 0, rebuilt < 128).sum() / max(1, (ink > 0).sum())
print(f"\npage 1 redrawn from prototypes only: {100*agree:.1f}% ink match")
y0, y1, x0, x1 = 250, 900, 150, 1500
cv2.imwrite(str(OUT / "compare_alphabet_title_v2.png"), np.hstack([gray[y0:y1, x0:x1], np.full((y1-y0, 12), 128, np.uint8), rebuilt[y0:y1, x0:x1]]))

# also: page 1 of the SECOND 0582 doc rebuilt from prototypes — cross-document proof
doc2, pno2, gray2, ink2, blobs2 = pages[5]
from_other = sum(1 for b in blobs2 if protos[b["cid"]] is not b and b["cid"] < curve[4]["shapes"])
print(f"{doc2} p1: {from_other}/{len(blobs2)} blobs ({100*from_other/len(blobs2):.0f}%) matched a shape first seen in {DOCS[0]}")

# curve
Wc, Hc = 900, 420; img = np.full((Hc, Wc, 3), 255, np.uint8)
mx_b, mx_s = curve[-1]["blobs"], curve[-1]["shapes"]
pt = lambda c: (60 + int(c["blobs"] / mx_b * (Wc - 100)), Hc - 50 - int(c["shapes"] / mx_s * (Hc - 100)))
for a, b in zip(curve, curve[1:]): cv2.line(img, pt(a), pt(b), (180, 60, 20) if b["doc"].startswith("0582") else (20, 90, 200), 2)
for c in curve: cv2.circle(img, pt(c), 4, (0, 0, 0), -1)
cv2.line(img, (60, Hc-50), (Wc-40, Hc-50), (0,0,0), 1); cv2.line(img, (60, Hc-50), (60, 40), (0,0,0), 1)
cv2.putText(img, "cumulative ink blobs ->", (Wc//2-90, Hc-15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1, cv2.LINE_AA)
cv2.putText(img, "distinct shapes (v2: scale-normalised, outline-matched)", (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1, cv2.LINE_AA)
cv2.putText(img, "journal 0582 (10 pages)", (80, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180,60,20), 1, cv2.LINE_AA)
cv2.putText(img, "then journal 0664 (10 pages)", (80, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20,90,200), 1, cv2.LINE_AA)
cv2.putText(img, f"{mx_b} blobs / {mx_s} shapes", (Wc-250, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1, cv2.LINE_AA)
cv2.imwrite(str(OUT / "saturation_curve_v2.png"), img)
(OUT / "saturation_v2.json").write_text(json.dumps(curve, indent=1))

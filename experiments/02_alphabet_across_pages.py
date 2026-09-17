"""Does the shape alphabet saturate across pages of one journal?
Builds one dictionary page by page over journal 0582 (10 pages), then keeps
going into journal 0664 (10 pages, a different typeface) to see the jump."""
import sys, json, math
from pathlib import Path
import numpy as np, cv2, fitz

IN = Path("/home/cubez/Desktop/OCR_gem_json/output/bakeoff_full/input")
OUT = Path(__file__).parent
DPI, IOU = 300, 0.70
DOCS = ["0582-004-009-012", "0582-006-015-002", "0664-012-003-020", "0664-015-008-036", "0664-016-006-031"]

def page_blobs(gray):
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 6: continue
        mask = (lab[y:y+h, x:x+w] == i).astype(np.uint8)
        cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        paths = [cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2) for c in cs]
        keep = [(p, int(hier[0][k][3] >= 0)) for k, p in enumerate(paths) if len(p) >= 3]
        norm = cv2.resize(mask * 255, (32, 32), interpolation=cv2.INTER_AREA) > 96
        out.append(dict(x=int(x), y=int(y), w=int(w), h=int(h), area=int(area), mask=mask, norm=norm,
                        paths=[p for p, _ in keep], holes=[hh for _, hh in keep]))
    return ink, out

clusters = []            # shared dictionary across pages
# size-gated index: bucket by (h//4, w//4) neighbourhood to keep matching fast
index = {}
def key(b): return (b["h"] // 4, b["w"] // 4)
def assign(b):
    best, bi = 0.0, -1
    kh, kw = key(b)
    for dh in (-1, 0, 1):
        for dw in (-1, 0, 1):
            for ci in index.get((kh + dh, kw + dw), ()):
                p = clusters[ci]["proto"]
                if abs(p["h"] - b["h"]) > max(2, 0.15 * p["h"]) or abs(p["w"] - b["w"]) > max(2, 0.15 * p["w"]): continue
                inter = np.logical_and(p["norm"], b["norm"]).sum(); union = np.logical_or(p["norm"], b["norm"]).sum()
                s = inter / union if union else 0
                if s > best: best, bi = s, ci
    if best >= IOU:
        clusters[bi]["n"] += 1; return bi
    clusters.append(dict(proto=b, n=1)); ci = len(clusters) - 1
    index.setdefault(key(b), []).append(ci); return ci

curve = []; tot_blobs = 0; pages = []
for doc in DOCS:
    pdf = fitz.open(IN / f"{doc}.pdf")
    for pno in range(pdf.page_count):
        pix = pdf[pno].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
        gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
        ink, blobs = page_blobs(gray)
        new_before = len(clusters)
        for b in blobs: b["cid"] = assign(b)
        tot_blobs += len(blobs)
        curve.append(dict(doc=doc, page=pno + 1, blobs=tot_blobs, shapes=len(clusters), new=len(clusters) - new_before,
                          page_blobs=len(blobs)))
        pages.append((doc, pno, gray, ink, blobs))
        print(f"{doc} p{pno+1}: {len(blobs):>4} blobs, {len(clusters)-new_before:>4} new shapes -> cumulative {tot_blobs:>5} blobs / {len(clusters):>4} shapes", flush=True)

# --- rebuild page 1 of the first doc from PROTOTYPES ONLY (the alphabet, not the page's own ink)
doc, pno, gray, ink, blobs = pages[0]
H, W = ink.shape
rebuilt = np.full((H, W), 255, np.uint8)
for b in blobs:
    p = clusters[b["cid"]]["proto"]
    # place the prototype's outline at this blob's position, scaled to this blob's box
    sx, sy = b["w"] / max(1, p["w"]), b["h"] / max(1, p["h"])
    for path, hole in zip(p["paths"], p["holes"]):
        pts = (path * [sx, sy] + [b["x"], b["y"]]).astype(np.int32)
        cv2.fillPoly(rebuilt, [pts], 255 if hole else 0)
agree = 1 - np.logical_xor(ink > 0, rebuilt < 128).sum() / max(1, (ink > 0).sum())
cv2.imwrite(str(OUT / "p1_from_alphabet.png"), rebuilt)
y0, y1, x0, x1 = 250, 900, 150, 1500
cv2.imwrite(str(OUT / "compare_alphabet_title.png"),
            np.hstack([gray[y0:y1, x0:x1], np.full((y1 - y0, 12), 128, np.uint8), rebuilt[y0:y1, x0:x1]]))
print(f"\npage 1 redrawn from shared prototypes only: {100*agree:.1f}% of ink pixels match the scan")

# --- how much of journal 0582's ink is covered by its top-N shapes
j = [c for c in clusters]  # counts include 0664 pages, but the top shapes are 0582's (seen first)
n0582 = sum(c["page_blobs"] for c in curve if c["doc"].startswith("0582"))
s0582 = next(c["shapes"] for c in reversed(curve) if c["doc"].startswith("0582"))
print(f"journal 0582 alone: {n0582} blobs -> {s0582} shapes; then 0664's first page added {curve[10]['new']} new shapes at once")

# --- curve image
Wc, Hc = 900, 420
img = np.full((Hc, Wc, 3), 255, np.uint8)
mx_b, mx_s = curve[-1]["blobs"], curve[-1]["shapes"]
def pt(c): return (60 + int(c["blobs"] / mx_b * (Wc - 100)), Hc - 50 - int(c["shapes"] / mx_s * (Hc - 100)))
for a, b in zip(curve, curve[1:]):
    cv2.line(img, pt(a), pt(b), (180, 60, 20) if b["doc"].startswith("0582") else (20, 90, 200), 2)
for c in curve: cv2.circle(img, pt(c), 4, (0, 0, 0), -1)
cv2.line(img, (60, Hc - 50), (Wc - 40, Hc - 50), (0, 0, 0), 1); cv2.line(img, (60, Hc - 50), (60, 40), (0, 0, 0), 1)
cv2.putText(img, "cumulative ink blobs ->", (Wc // 2 - 90, Hc - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1, cv2.LINE_AA)
cv2.putText(img, "distinct shapes", (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1, cv2.LINE_AA)
cv2.putText(img, f"journal 0582 (10 pages)", (80, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 60, 20), 1, cv2.LINE_AA)
cv2.putText(img, f"then journal 0664 (10 pages, other typeface)", (80, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 90, 200), 1, cv2.LINE_AA)
cv2.putText(img, f"{mx_b} blobs / {mx_s} shapes", (Wc - 250, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1, cv2.LINE_AA)
cv2.imwrite(str(OUT / "saturation_curve.png"), img)
(OUT / "saturation.json").write_text(json.dumps(curve, indent=1))

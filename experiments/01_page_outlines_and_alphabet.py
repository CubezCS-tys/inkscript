"""Page 1 as geometry: ink blobs -> outlines -> shape alphabet -> placements."""
import sys, json, math
from pathlib import Path
import numpy as np, cv2, fitz

PDF = Path("/home/cubez/Desktop/OCR_gem_json/output/bakeoff_full/input/0582-004-009-012.pdf")
OUT = Path(__file__).parent
DPI = 300
IOU = float(sys.argv[1]) if len(sys.argv) > 1 else 0.80

# 1. render + binarize
pix = fitz.open(PDF)[0].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
cv2.imwrite(str(OUT / "scan.png"), gray)
_, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

# 2. blobs
n, lab, stats, cent = cv2.connectedComponentsWithStats(ink, connectivity=8)
blobs = []
for i in range(1, n):
    x, y, w, h, area = stats[i]
    if area < 6:                       # scanner speckle
        continue
    mask = (lab[y:y+h, x:x+w] == i).astype(np.uint8)
    cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    paths = [cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2) for c in cs]
    paths = [p for p in paths if len(p) >= 3]
    norm = cv2.resize(mask * 255, (32, 32), interpolation=cv2.INTER_AREA) > 96
    blobs.append(dict(x=int(x), y=int(y), w=int(w), h=int(h), area=int(area),
                      mask=mask, norm=norm, paths=paths,
                      holes=[int(hier[0][k][3] >= 0) for k in range(len(cs))]))
blobs.sort(key=lambda b: -b["area"])
print(f"ink blobs: {len(blobs)}  (small <40px: {sum(b['area']<40 for b in blobs)})")
print(f"outline points total: {sum(len(p) for b in blobs for p in b['paths']):,}")

# 3. shape alphabet: greedy clustering on normalised bitmaps, gated by size
clusters = []   # each: dict(proto=blob, members=[idx])
for i, b in enumerate(blobs):
    best, bi = 0.0, -1
    for ci, c in enumerate(clusters):
        p = c["proto"]
        if abs(p["h"] - b["h"]) > max(2, 0.15 * p["h"]) or abs(p["w"] - b["w"]) > max(2, 0.15 * p["w"]):
            continue
        inter = np.logical_and(p["norm"], b["norm"]).sum()
        union = np.logical_or(p["norm"], b["norm"]).sum()
        s = inter / union if union else 0
        if s > best:
            best, bi = s, ci
    if best >= IOU:
        clusters[bi]["members"].append(i); b["cid"] = bi
    else:
        clusters.append(dict(proto=b, members=[i])); b["cid"] = len(clusters) - 1
clusters_sorted = sorted(range(len(clusters)), key=lambda c: -len(clusters[c]["members"]))
sizes = [len(clusters[c]["members"]) for c in clusters_sorted]
tot_ink = sum(b["area"] for b in blobs)
cum = np.cumsum([sum(blobs[m]["area"] for m in clusters[c]["members"]) for c in clusters_sorted]) / tot_ink
singles = sum(1 for s in sizes if s == 1)
print(f"\nIoU>={IOU}: {len(clusters)} distinct shapes for {len(blobs)} blobs; "
      f"{singles} appear once; top 50 shapes cover {cum[min(49,len(cum)-1)]:.0%} of ink, top 100 {cum[min(99,len(cum)-1)]:.0%}")
print("most frequent shape counts:", sizes[:15])

# 4. renders: page from outlines only (black), and coloured by shape id
H, W = ink.shape
outline = np.full((H, W), 255, np.uint8)
colour = np.full((H, W, 3), 255, np.uint8)
rng = np.random.default_rng(1)
pal = rng.integers(30, 220, (len(clusters), 3))
for b in blobs:
    for p, hole in zip(b["paths"], b["holes"]):
        pts = (p + [b["x"], b["y"]]).astype(np.int32)
        cv2.fillPoly(outline, [pts], 255 if hole else 0)
        cv2.fillPoly(colour, [pts], (255,255,255) if hole else tuple(int(v) for v in pal[b["cid"]]))
cv2.imwrite(str(OUT / "from_geometry.png"), outline)
cv2.imwrite(str(OUT / "by_shape.png"), colour)
# fidelity: pixel agreement between scan ink and geometry render
diff = np.logical_xor(ink > 0, outline < 128)
print(f"\ngeometry render vs scan ink: {100*(1-diff.sum()/max(1,(ink>0).sum())):.1f}% of ink pixels reproduced exactly")

# 5. glyph sheet: prototypes of the most frequent shapes
cell, cols = 64, 16
rows = math.ceil(min(len(clusters), 160) / cols)
sheet = np.full((rows * (cell + 18), cols * cell), 255, np.uint8)
for k, c in enumerate(clusters_sorted[:cols * rows]):
    p = clusters[c]["proto"]; m = p["mask"] * 255
    s = min((cell - 8) / max(p["w"], p["h"]), 3.0)
    g = cv2.resize(m, (max(1, int(p["w"] * s)), max(1, int(p["h"] * s))), interpolation=cv2.INTER_AREA)
    r, q = divmod(k, cols)
    y0, x0 = r * (cell + 18) + 4, q * cell + (cell - g.shape[1]) // 2
    sheet[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] = 255 - g
    cv2.putText(sheet, f"{k}:{len(clusters[c]['members'])}", (q * cell + 2, r * (cell + 18) + cell + 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, 0, 1, cv2.LINE_AA)
cv2.imwrite(str(OUT / "alphabet.png"), sheet)

# 6. the numbers: alphabet + placements
alphabet = {str(k): dict(w=clusters[c]["proto"]["w"], h=clusters[c]["proto"]["h"], count=len(clusters[c]["members"]),
                         paths=[(p - [0, 0]).tolist() for p in clusters[c]["proto"]["paths"]])
            for k, c in enumerate(clusters_sorted)}
rank = {c: k for k, c in enumerate(clusters_sorted)}
placements = [dict(s=rank[b["cid"]], x=b["x"], y=b["y"]) for b in sorted(blobs, key=lambda b: (b["y"] // 20, -b["x"]))]
doc = dict(dpi=DPI, page=[W, H], alphabet=alphabet, placements=placements)
(OUT / "page_geometry.json").write_text(json.dumps(doc, separators=(",", ":")))
print(f"\npage_geometry.json: {(OUT/'page_geometry.json').stat().st_size/1024:.0f} KB "
      f"(alphabet {len(alphabet)} shapes + {len(placements)} placements)  vs scan PNG {(OUT/'scan.png').stat().st_size/1024:.0f} KB")

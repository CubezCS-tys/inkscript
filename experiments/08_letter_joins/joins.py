"""Where does a connected run of Arabic ink break into letters?

Inside a piece (one connected blob, letters joined along the baseline), a
join is a stretch of the baseline stroke with nothing above or below it:
the ink there is only the connecting stroke. Candidate cuts are the
midpoints of such stretches. A piece is "cut cleanly" when the number of
cuts equals its letters minus one (marks folded onto letters, lam-alef as
one). Measures how often that happens on the fixture, page by page, and
draws a few examples.

    python experiments/08_letter_joins/joins.py OUT/native_set  (uses shapes.json + the scan)
"""
import json, sys, re
from pathlib import Path
import numpy as np, cv2, fitz

O = Path(sys.argv[1]); STEM = "0582-004-009-012"; SCAN = Path("/home/cubez/Desktop/OCR_gem_json/output/bakeoff_full/input") / f"{STEM}.pdf"
sys.path.insert(0, "src"); from inkscript.text import MARKS, ARABIC_LETTER
LIG = ("لا", "لأ", "لإ", "لآ")


def letters(t):
    t = MARKS.sub("", t); t = re.sub(r"[^؀-ۿ]", "", t)
    for l in LIG: t = t.replace(l, "L")
    return len(t)


def joins(ink, baseline_band=0.45):
    """ink: binary crop of one piece (True = ink). Columns whose ink lies
    entirely within a thin band around the baseline stroke are join columns."""
    H, W = ink.shape
    col_ink = ink.sum(0)
    rows = np.where(ink.any(1))[0]
    # the baseline stroke: the row band with the most ink across the piece
    prof = ink.sum(1); base = int(np.argmax(prof)); stroke = max(2, int(np.median([ink[:, x].sum() for x in range(W) if col_ink[x] > 0]) if col_ink.any() else 3))
    band = (max(0, base - stroke), min(H, base + stroke + 1))
    thin = np.array([col_ink[x] > 0 and ink[:band[0], x].sum() == 0 and ink[band[1]:, x].sum() == 0 for x in range(W)])
    # runs of thin columns at least `stroke` wide, not touching the ends
    cuts = []; x = 0
    while x < W:
        if thin[x]:
            j = x
            while j < W and thin[j]: j += 1
            if j - x >= max(2, stroke // 2) and x > 1 and j < W - 1:
                cuts.append((x + j) // 2)
            x = j
        else:
            x += 1
    return cuts, base, stroke


s = json.load(open(O / f"{STEM}.shapes.json"))
doc = fitz.open(SCAN); stats = dict(pieces=0, clean=0, over=0, under=0); examples = []
pages = {}
for p in s["placements"]:
    if p["page"] not in pages:
        pix = doc[p["page"] - 1].get_pixmap(dpi=300, colorspace=fitz.csGRAY); img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
        _, ink = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); pages[p["page"]] = ink > 0
    ink = pages[p["page"]]; x0, y0, x1, y1 = p["box"]; crop = ink[y0:y1, x0:x1]
    n = letters(p["text"])
    if n < 2 or not ARABIC_LETTER.search(p["text"]) or MARKS.search(p["text"]):
        continue
    # only pieces that are one connected component (letters joined)
    ncomp, lab = cv2.connectedComponents(crop.astype(np.uint8), connectivity=8)
    big = [k for k in range(1, ncomp) if (lab == k).sum() > 0.15 * crop.sum()]
    if len(big) != 1:
        continue
    cuts, base, stroke = joins(lab == big[0])
    stats["pieces"] += 1
    if len(cuts) == n - 1: stats["clean"] += 1
    elif len(cuts) > n - 1: stats["over"] += 1
    else: stats["under"] += 1
    if len(examples) < 12 and n >= 3:
        examples.append((p["text"], n, cuts, crop.copy(), base))
print(stats, "clean share %.1f%%" % (100 * stats["clean"] / max(1, stats["pieces"])))
# a sheet of examples with the cuts drawn
tiles = []
for text, n, cuts, crop, base in examples:
    im = cv2.cvtColor((255 - crop.astype(np.uint8) * 255), cv2.COLOR_GRAY2BGR)
    for c in cuts: cv2.line(im, (c, 0), (c, im.shape[0] - 1), (0, 0, 255), 1)
    cv2.line(im, (0, base), (im.shape[1] - 1, base), (255, 160, 0), 1)
    tiles.append(cv2.copyMakeBorder(im, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=(200, 200, 200)))
    print(f"  {text!r}: {n} letters, {len(cuts)} cuts")
h = max(t.shape[0] for t in tiles); sheet = np.hstack([cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles])
cv2.imwrite(str(Path(sys.argv[2]) / "joins.png"), sheet) if len(sys.argv) > 2 else None

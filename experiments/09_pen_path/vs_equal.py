"""Does the pen path beat equal slicing? The test that retired the column cutter, applied to its replacement.

    python vs_equal.py <built_dir> <azure_dir> <stem> [--page N]

D7 killed the free column alignment because it did not beat what Chrome does with an UNCUT glyph — equal
slices of the word's width, one per character: 91.6% of equal slices landed within a stroke of a real join
against the alignment's 90.9%. The pen path replaced that cutter and was never put to the same test; this is
the test, in the same units (experiment 08's thin-join reference, `joins()` copied from it unchanged).

Reference: a "clean" piece, where the thin-join detector finds exactly letters-1 joins — the only places where
an independent answer exists. Both methods are then scored against those joins.

The cuts measured are the ones the READER gets: the boundaries between consecutive character boxes as pdfium
reports them from the finished PDF, not the planner's intentions.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
import numpy as np, cv2, fitz, pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from inkscript.text import MARKS, pieces as text_pieces
LIG = ("لا", "لأ", "لإ", "لآ")
DPI = 300


def n_letters(t: str) -> int:
    t = MARKS.sub("", t); t = re.sub(r"[^؀-ۿ]", "", t)
    for l in LIG: t = t.replace(l, "L")
    return len(t)


def joins(ink, ):
    """Experiment 08's thin-join detector, unchanged: columns whose ink is only the connecting stroke."""
    H, W = ink.shape
    col_ink = ink.sum(0)
    if not col_ink.any(): return [], 0, 3
    prof = ink.sum(1); base = int(np.argmax(prof))
    stroke = max(2, int(np.median([ink[:, x].sum() for x in range(W) if col_ink[x] > 0])))
    band = (max(0, base - stroke), min(H, base + stroke + 1))
    thin = np.array([col_ink[x] > 0 and ink[:band[0], x].sum() == 0 and ink[band[1]:, x].sum() == 0 for x in range(W)])
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


def pdf_char_boxes(pdf: Path, page: int, scale: float):
    """Every character's box on a page, in scan pixels, with its text — what a reader's drag actually covers."""
    d = pdfium.PdfDocument(str(pdf)); pg = d[page - 1]; _, H = pg.get_size()
    tp = pg.get_textpage(); t = tp.get_text_range()
    boxes = [tp.get_charbox(i) for i in range(len(t))]
    words = []; cur = []
    for i, c in enumerate(t):
        if c.isspace():
            if cur: words.append(cur); cur = []
        else: cur.append(i)
    if cur: words.append(cur)
    out = []
    for w in words:
        bs = [(boxes[i][0] * scale, (H - boxes[i][3]) * scale, boxes[i][2] * scale, (H - boxes[i][1]) * scale) for i in w]
        out.append(("".join(t[i] for i in w), bs))
    tp.close(); pg.close(); d.close()
    return out


def internal_edges(bs):
    """The x positions a reader's selection changes at: between consecutive character boxes, in text order."""
    xs = sorted(bs, key=lambda b: b[0])
    return [(xs[i][2] + xs[i + 1][0]) / 2 for i in range(len(xs) - 1)]


def page_rows(place, ink, by_box):
    """Every word of a page that has an independent join reference AND was cut per letter in the PDF."""
    rows = []
    for p in place:
        txt = p["text"].strip()
        n = n_letters(txt)
        if n < 2 or MARKS.search(txt):
            continue
        # ONE joined run only. A word like `أول` or `داخل` is several runs with white between them; it has no
        # joins to find, and the thin-column detector's noise there passed the count test and became a
        # "reference" for cuts that cannot exist. Experiment 08 measured single connected pieces; so must this.
        if len(text_pieces(txt)) != 1:
            continue
        x0, y0, x1, y1 = p["box"]
        crop = ink[y0:y1, x0:x1]
        # and its ink must really be one blob (plus dots): a broken letter would split it
        nlab, lab = cv2.connectedComponents(crop.astype(np.uint8))
        big = sum(1 for k in range(1, nlab) if (lab == k).sum() >= 0.08 * crop.sum())
        if big != 1:
            continue
        ref, base, stroke = joins(crop)
        if len(ref) != n - 1 or not ref:
            continue                                        # no independent answer for this piece
        cand = [c for c in by_box.get(txt, []) if not (c[2] < x0 or c[0] > x1 or c[3] < y0 or c[1] > y1)]
        if len(cand) != 1 or len(cand[0][4]) != n:
            continue                                        # cannot pair this word, or it is not cut per letter
        bs = cand[0][4]
        mine = [e - x0 for e in internal_edges(bs)]
        equal = [(x1 - x0) * (k + 1) / n for k in range(n - 1)]
        rows.append(dict(text=txt, stroke=stroke, ref=ref, mine=mine, equal=equal, width=x1 - x0))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("built"); ap.add_argument("azure"); ap.add_argument("stem")
    ap.add_argument("--page", type=int, default=0, help="0 = every page")
    ap.add_argument("--scan", default=None, help="where the scans are, if not beside the Azure JSON")
    a = ap.parse_args()

    built = Path(a.built); stem = a.stem
    shapes = json.load(open(built / f"{stem}.shapes.json"))
    scan = (Path(a.scan) / f"{stem}.pdf") if a.scan else (Path(a.azure) / stem / f"{stem}.pdf")
    pages = sorted({p["page"] for p in shapes["placements"]}) if not a.page else [a.page]
    pt_to_px = DPI / 72.0
    rows = []
    for pageno in pages:
        place = [p for p in shapes["placements"] if p["page"] == pageno and not p.get("rot")]
        if not place:
            continue
        src = fitz.open(scan)
        pix = src[pageno - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
        gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
        src.close()
        _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); ink = ink > 0
        ours = pdf_char_boxes(built / f"{stem}_vector.pdf", pageno, pt_to_px)
        by_box = {}
        for txt, bs in ours:
            x0 = min(b[0] for b in bs); x1 = max(b[2] for b in bs); y0 = min(b[1] for b in bs); y1 = max(b[3] for b in bs)
            by_box.setdefault(txt, []).append((x0, y0, x1, y1, bs))
        rows += page_rows(place, ink, by_box)
        del ink, gray
        pass
    def evenness(r):
        """How equal are this piece's real letter widths? The gaps the REFERENCE implies, edges included.
        Equal slicing is right by construction where they are equal, so this is the axis the two methods
        must be compared along — a reference that only exists for regular pieces flatters equal slicing."""
        e = [0.0] + sorted(float(x) for x in r["ref"]) + [float(r["width"])]
        g = np.diff(e)
        return float(np.std(g) / max(1e-9, np.mean(g)))

    def score(name, key, subset=None):
        ds = []
        for r in (subset if subset is not None else rows):
            for j in r["ref"]:
                ds.append((min(abs(j - c) for c in r[key]), r["stroke"]))
        if not ds: return
        d = np.array([x for x, _ in ds]); st = np.array([s for _, s in ds])
        print(f"  {name:<14} within a stroke {100 * (d <= st).mean():5.1f}%   within 3 px {100 * (d <= 3).mean():5.1f}%   "
              f"median {np.median(d):4.1f} px   p90 {np.percentile(d, 90):5.1f} px")

    if rows:
        cv = sorted(rows, key=evenness)
        half = len(cv) // 2
        for label, sub in (("letters of EQUAL width (equal slicing is right by construction)", cv[:half]),
                           ("letters of UNEQUAL width (where a real cutter must earn its place)", cv[half:])):
            print(f"\n  --- {label}: {len(sub)} pieces, {sum(len(r['ref']) for r in sub)} joins")
            score("pen path", "mine", sub)
            score("equal slicing", "equal", sub)

    print(f"{stem} p{a.page}: {len(rows)} pieces with an independent join reference, "
          f"{sum(len(r['ref']) for r in rows)} joins\n")
    score("pen path", "mine")
    score("equal slicing", "equal")
    json.dump(rows, open(built / "vs_equal.json", "w"), ensure_ascii=False, default=float)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

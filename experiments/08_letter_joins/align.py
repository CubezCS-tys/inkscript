"""Forced alignment of a piece's letters to its ink.

We know the letters of every piece (the OCR's text, split where the script
cannot join). Each letter has signatures visible in any typeface: dots
above or below and how many, an ascender, a descending bowl, a width class.
So the cut points are not searched for — the ink's width is divided into
one interval per letter, and the division that best matches the letters'
signatures (dots inside the interval, tall or deep ink there, plausible
width, a thin join at the cut) is the alignment. Dynamic programme over the
columns, right to left, one interval per letter.

Measured against the thin-join cuts where those are clean (cuts = letters -
1): how often the alignment puts its cuts within a few pixels of them.

    python experiments/08_letter_joins/align.py OUT/native_set <out-dir>
"""
import json, sys, re
from pathlib import Path
from collections import defaultdict
import numpy as np, cv2, fitz

sys.path.insert(0, "src")
from inkscript.text import MARKS, ARABIC_LETTER, pieces

STEM = "0582-004-009-012"; SCAN = Path("/home/cubez/Desktop/OCR_gem_json/output/bakeoff_full/input") / f"{STEM}.pdf"

# ---- letter signatures (script facts, not typeface facts)
ASC = set("اأإآلكطظ")                                   # tall stroke above the x-height
DESC_ANY = set("جحخ")                                   # bowl below the baseline in every form
DESC_END = set("عغمنيسشصضقلىورز")                       # below the baseline only when the piece ends there
DOTS_ABOVE = {"ت": 2, "ث": 3, "ن": 1, "ذ": 1, "ز": 1, "ض": 1, "ظ": 1, "غ": 1, "خ": 1, "ف": 1, "ق": 2, "ش": 3, "ة": 2, "ئ": 1, "ؤ": 1}
DOTS_BELOW = {"ب": 1, "ج": 1, "ي": 2, "پ": 3, "چ": 3}
WIDE = set("سشصضطظ"); MEDIUM = set("جحخعغفقكمهةلا"); NARROW = set("ابتثنيلدذرزوىأإآ")


def letters_of(piece: str) -> list[str]:
    """One unit per glyph: lam-alef ligatures as one, marks folded on."""
    out = []; i = 0
    while i < len(piece):
        two = piece[i:i + 2]
        if two in ("لا", "لأ", "لإ", "لآ"):
            out.append(two); i += 2; continue
        ch = piece[i]
        if (MARKS.match(ch) or ch == "ـ") and out:            # marks and kashida ride on the letter before
            out[-1] += ch
        elif ARABIC_LETTER.match(ch):
            out.append(ch)
        i += 1
    return out


def width_class(u: str) -> float:
    c = u[0] if u[:2] not in ("لا", "لأ", "لإ", "لآ") else "لا"
    return 2.6 if c in WIDE else 1.6 if c in MEDIUM else 1.0


def analyse(crop: np.ndarray):
    """Main component(s), dots, baseline band, stroke, per-column features."""
    n, lab, stats, cent = cv2.connectedComponentsWithStats(crop.astype(np.uint8), connectivity=8)
    if n < 2:
        return None
    areas = stats[1:, cv2.CC_STAT_AREA]; big = 1 + int(np.argmax(areas))
    main = lab == big
    prof = main.sum(1); b = int(np.argmax(prof)); thr = 0.5 * prof[b]; b0 = b1 = b
    while b0 > 0 and prof[b0 - 1] >= thr: b0 -= 1
    while b1 < crop.shape[0] - 1 and prof[b1 + 1] >= thr: b1 += 1
    stroke = max(2, b1 - b0 + 1)
    H, W = crop.shape
    top = np.array([np.argmax(main[:, x]) if main[:, x].any() else H for x in range(W)])
    bot = np.array([H - 1 - np.argmax(main[::-1, x]) if main[:, x].any() else -1 for x in range(W)])
    has = main.any(0)
    asc = has & (top < b0 - 1.5 * stroke)               # ink above the stroke band (an ascender: ا ل ك ط)
    tall = has & (top < b0 - 3 * stroke)                # far above it (never a loop: ف ق م ه rise less)
    desc = has & (bot > b1 + 1.0 * stroke)              # ink below the band (final ن ى ي dip modestly)
    deep = has & (bot > b1 + 2.5 * stroke)              # far below it (a real bowl or tail)
    thin = has & (top >= b0 - 1) & (bot <= b1 + 1)      # only the connecting stroke
    dots = []                                           # (x centre, above?)
    for k in range(1, n):
        if k == big or areas[k - 1] > 0.25 * areas[big - 1]:
            continue
        cy = cent[k][1]; cx = cent[k][0]
        if areas[k - 1] < 3: continue
        dots.append((cx, cy < b0))
    # other large components (a second main piece: the word was really two pieces) -> keep as "extra"
    extra = [k for k in range(1, n) if k != big and areas[k - 1] > 0.25 * areas[big - 1]]
    return dict(main=main, b0=b0, b1=b1, stroke=stroke, asc=asc, tall=tall, desc=desc, deep=deep, thin=thin, has=has, dots=dots, extra=extra, W=W)


def align(units: list[str], F: dict, unit_px: float):
    """DP over columns right to left. Returns (cuts as x positions left->right, score, per-letter consistency)."""
    W = F["W"]; n = len(units)
    # work in right-to-left coordinates: r = W-1-x
    asc = F["asc"][::-1]; desc = F["desc"][::-1]; thin = F["thin"][::-1]; has = F["has"][::-1]; tall = F["tall"][::-1]; deep = F["deep"][::-1]
    dots_r = [(W - 1 - cx, above) for cx, above in F["dots"]]
    cum = lambda v: np.concatenate([[0], np.cumsum(v)])
    cum_asc, cum_desc, cum_has, cum_tall, cum_deep = cum(asc), cum(desc), cum(has), cum(tall), cum(deep)
    def agree(i, a, b):
        """(asc ok, desc ok, dots-above ok, dots-below ok): tolerant bands — an ascender letter must reach above the
        band; a non-ascender may rise a little (a loop) but not far; likewise below."""
        u = units[i]; c = u[:2] if u[:2] in ("لا", "لأ", "لإ", "لآ") else u[0]; w = max(1, b - a); last = i == n - 1
        want_asc = c in ASC or c.startswith("ل")
        asc_ok = (cum_asc[b] - cum_asc[a]) > 0.1 * w if want_asc else (cum_tall[b] - cum_tall[a]) <= 0.1 * w
        want_desc = c in DESC_ANY or (last and c in DESC_END)
        desc_ok = (cum_desc[b] - cum_desc[a]) > 0.1 * w if want_desc else (cum_deep[b] - cum_deep[a]) <= 0.1 * w
        da = sum(1 for x, above in dots_r if a <= x < b and above); db = sum(1 for x, above in dots_r if a <= x < b and not above)
        wa = DOTS_ABOVE.get(c, 0); wb = DOTS_BELOW.get(c, 0)
        if c == "ي" and last: wb = db if db in (0, 2) else 2
        near = lambda got, want: got == want or (want >= 2 and 1 <= got <= want)      # two or three dots often print as one blob
        return asc_ok, desc_ok, near(da, wa), near(db, wb)
    def seg_flags(i, a, b):
        """Does the ink of [a,b) agree with letter i's signatures? (asc, desc, dots above, dots below, thin cut)"""
        last = i == n - 1
        thin_cut = last or bool(thin[min(b, W - 1)] or thin[max(b - 1, 0)])
        return (*agree(i, a, b), thin_cut)

    def seg_score(i, a, b):                              # letter i on columns [a,b) (right-to-left)
        u = units[i]; c = u[:2] if u[:2] in ("لا", "لأ", "لإ", "لآ") else u[0]
        w = b - a; exp = width_class(u) * unit_px
        s = -1.2 * abs(np.log(max(w, 1) / exp)) ** 2 * 2        # width prior
        if cum_has[b] - cum_has[a] < 0.3 * w: s -= 2            # mostly empty interval
        asc_ok, desc_ok, da_ok, db_ok = agree(i, a, b)
        s += 1.5 if asc_ok else -1.5
        s += 1.0 if desc_ok else -1.0
        s += 2.0 if da_ok else -2.0
        s += 2.0 if db_ok else -2.0
        if i < n - 1:                                                 # the cut column: a thin join is what a cut should be
            s += 1.0 if thin[min(b, W - 1)] or thin[max(b - 1, 0)] else -0.5
        return s
    NEG = -1e9; best = np.full((n + 1, W + 1), NEG); back = np.zeros((n + 1, W + 1), int); best[0][0] = 0
    minw = max(2, int(0.35 * unit_px))
    for i in range(n):
        for a in range(W + 1):
            if best[i][a] == NEG: continue
            for b in range(a + minw, W + 1):
                if i == n - 1 and b != W: continue
                v = best[i][a] + seg_score(i, a, b)
                if v > best[i + 1][b]: best[i + 1][b] = v; back[i + 1][b] = a
    if best[n][W] == NEG:
        return None, NEG
    bounds = [W]; b = W
    for i in range(n, 0, -1):
        b = back[i][b]; bounds.append(b)
    bounds = bounds[::-1]                                # right-to-left column bounds
    cuts = [W - 1 - c for c in bounds[1:-1]]             # as x (left->right frame)
    flags = [seg_flags(i, bounds[i], bounds[i + 1]) for i in range(n)]
    align.last_flags = flags                             # every letter's agreement with its signatures
    return sorted(cuts), best[n][W] / n


def observe(units, F, cuts):
    """What the ink of each letter's interval actually shows: (asc share, tall share, desc share, deep share,
    dots above, dots below, width in strokes), in reading order. The material a document learns its own
    signatures from."""
    W = F["W"]; bounds = [0] + list(cuts) + [W]; out = []
    for k in range(len(units)):
        a, b = bounds[len(units) - 1 - k], bounds[len(units) - k]; w = max(1, b - a)
        seg = lambda v: float(v[a:b].sum()) / w
        da = sum(1 for x, above in F["dots"] if a <= x < b and above); db = sum(1 for x, above in F["dots"] if a <= x < b and not above)
        out.append(dict(asc=seg(F["asc"]), tall=seg(F["tall"]), desc=seg(F["desc"]), deep=seg(F["deep"]), da=da, db=db, w=w / F["stroke"]))
    return out


def thin_cuts(F):
    thin = F["thin"]; W = F["W"]; stroke = F["stroke"]; cuts = []; x = 0
    while x < W:
        if thin[x]:
            j = x
            while j < W and thin[j]: j += 1
            if j - x >= max(2, stroke // 2) and x > 1 and j < W - 1: cuts.append((x + j) // 2)
            x = j
        else: x += 1
    return cuts


def aligned_pieces(shapes_json, scan):
    """Every single-piece unvowelled word of the document with its alignment: (placement, units, cuts, crop, F)."""
    s = json.load(open(shapes_json)); doc = fitz.open(scan); pages = {}; out = []
    for p in s["placements"]:
        if p["page"] not in pages:
            pix = doc[p["page"] - 1].get_pixmap(dpi=300, colorspace=fitz.csGRAY); img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
            _, ink = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); pages[p["page"]] = ink > 0
        text = p["text"]
        if MARKS.search(text) or not ARABIC_LETTER.search(text): continue
        pcs = [q for q in pieces(text) if ARABIC_LETTER.search(q)]
        if len(pcs) != 1: continue
        units = letters_of(pcs[0])
        if len(units) < 2: continue
        x0, y0, x1, y1 = p["box"]; crop = pages[p["page"]][y0:y1, x0:x1]
        F = analyse(crop)
        if F is None or F["extra"]: continue
        cuts, score = align(units, F, F["W"] / sum(width_class(u) for u in units))
        if cuts is None: continue
        out.append((p, units, [int(c) for c in cuts], crop.copy(), F, align.last_flags))
    return out


if __name__ == "__main__":
    O = Path(sys.argv[1]); OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    s = json.load(open(O / f"{STEM}.shapes.json")); doc = fitz.open(SCAN); pages = {}
    stats = defaultdict(int); agree = []; sheet = []
    for p in s["placements"]:
        if p["page"] not in pages:
            pix = doc[p["page"] - 1].get_pixmap(dpi=300, colorspace=fitz.csGRAY); img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
            _, ink = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); pages[p["page"]] = ink > 0
        text = p["text"]
        if MARKS.search(text) or not ARABIC_LETTER.search(text): continue
        pcs = [q for q in pieces(text) if ARABIC_LETTER.search(q)]
        if len(pcs) != 1: continue                            # first pass: words that are a single connected piece
        units = letters_of(pcs[0])
        if len(units) < 2: continue
        x0, y0, x1, y1 = p["box"]; crop = pages[p["page"]][y0:y1, x0:x1]
        F = analyse(crop)
        if F is None or F["extra"]: continue
        stats["pieces"] += 1
        unit_px = F["W"] / sum(width_class(u) for u in units)
        cuts, score = align(units, F, unit_px)
        if cuts is None: stats["failed"] += 1; continue
        tc = thin_cuts(F)
        if len(tc) == len(units) - 1:
            stats["clean_reference"] += 1
            ok = sum(1 for c, t in zip(cuts, tc) if abs(c - t) <= max(3, F["stroke"]))
            agree.append(ok / len(tc))
        if len(sheet) < 18 and len(units) >= 3:
            sheet.append((text, units, cuts, tc, crop.copy(), F))
    print(dict(stats), "| on the clean reference: mean agreement %.1f%% (cuts within a stroke of the thin-join cut)" % (100 * np.mean(agree)) if agree else "")
    if OUT:
        tiles = []
        for text, units, cuts, tc, crop, F in sheet:
            im = cv2.cvtColor((255 - crop.astype(np.uint8) * 255), cv2.COLOR_GRAY2BGR)
            for c in tc: cv2.line(im, (c, 0), (c, im.shape[0] - 1), (200, 200, 200), 1)
            for c in cuts: cv2.line(im, (c, 0), (c, im.shape[0] - 1), (0, 0, 255), 1)
            tiles.append(cv2.copyMakeBorder(im, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=(180, 180, 180)))
            print(f"  {text!r}: {len(units)} letters, dp cuts {cuts}, thin cuts {tc}")
        h = max(t.shape[0] for t in tiles); rows = []
        for k in range(0, len(tiles), 6):
            row = [cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles[k:k + 6]]
            rows.append(np.hstack(row))
        w = max(r.shape[1] for r in rows); rows = [cv2.copyMakeBorder(r, 0, 0, 0, w - r.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for r in rows]
        cv2.imwrite(str(OUT / "align.png"), np.vstack(rows))
    
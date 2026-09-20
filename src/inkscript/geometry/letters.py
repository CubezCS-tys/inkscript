"""Letters inside a connected run of ink: forced alignment, and the document
as witness.

A piece's letters are known (the OCR's text, split where the script cannot
join). Each letter has signatures visible in any typeface — dots above or
below and how many, an ascender, a descending bowl, a width class — so the
piece's width is divided into one interval per letter by a dynamic
programme that scores each interval against its letter (`align`). No
signature table is trusted on its own: what each letter-form actually
shows in THIS document is learned by majority over all its aligned
occurrences (`learn`), and a piece's cuts are accepted only when every
letter shows its usual signature (`accepted`). A wrong cut can only move
a highlight — the letters' texts concatenate to the same word — but the
bar is still: nothing adopted without the document's agreement.
Experiment 08 has the measurements.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import numpy as np, cv2

from ..text import MARKS, ARABIC_LETTER

LIG = ("لا", "لأ", "لإ", "لآ")
ASC = set("اأإآلكطظ")                                   # tall stroke above the x-height
DESC_ANY = set("جحخ")                                   # bowl below the baseline in every form
DESC_END = set("عغمنيسشصضقلىورز")                       # below the baseline when the piece ends there
DOTS_ABOVE = {"ت": 2, "ث": 3, "ن": 1, "ذ": 1, "ز": 1, "ض": 1, "ظ": 1, "غ": 1, "خ": 1, "ف": 1, "ق": 2, "ش": 3, "ة": 2, "ئ": 1, "ؤ": 1}
DOTS_BELOW = {"ب": 1, "ج": 1, "ي": 2, "پ": 3, "چ": 3}
WIDE = set("سشصضطظ"); MEDIUM = set("جحخعغفقكمهةلا")
MIN_EXAMPLES = 5                                        # a letter-form's signature counts once seen this often


def letters_of(piece: str) -> list[str]:
    """One unit per glyph: lam-alef as one, marks and kashida on the letter before."""
    out = []; i = 0
    while i < len(piece):
        if piece[i:i + 2] in LIG:
            out.append(piece[i:i + 2]); i += 2; continue
        ch = piece[i]
        if (MARKS.match(ch) or ch == "ـ") and out:
            out[-1] += ch
        elif ARABIC_LETTER.match(ch):
            out.append(ch)
        i += 1
    return out


def _base(u: str) -> str:
    return "لا" if u[:2] in LIG else u[0]


def width_class(u: str) -> float:
    c = _base(u)
    if c in "اأإآ":
        return 0.5                                       # a bare stroke: counted as wide as a `ب`, a light face's alef drew in its neighbours' blobs
    return 2.6 if c in WIDE else 1.6 if c in MEDIUM else 1.0


def form(k: int, n: int) -> str:
    return "iso" if n == 1 else "init" if k == 0 else "fin" if k == n - 1 else "med"


def piece_mask(blobs: list[dict]):
    """The piece's ink as a binary crop from its blobs' outlines, plus the crop's page offset."""
    x0 = min(int(p[:, 0].min()) for b in blobs for p in b["paths"]); y0 = min(int(p[:, 1].min()) for b in blobs for p in b["paths"])
    x1 = max(int(p[:, 0].max()) for b in blobs for p in b["paths"]) + 2; y1 = max(int(p[:, 1].max()) for b in blobs for p in b["paths"]) + 2
    m = np.zeros((y1 - y0, x1 - x0), np.uint8)
    for b in blobs:
        for p, hole in zip(b["paths"], b["holes"]):
            pts = (np.asarray(p) - [x0, y0]).astype(np.int32); cv2.fillPoly(m, [pts], 0 if hole else 1)
            if hole:
                # a hole's outline runs through the ink pixels around it; filling the polygon erased them, and
                # every hole of a cut letter came out a pixel wider (0.9% of a page's ink)
                cv2.polylines(m, [pts], True, 1)
    return m.astype(bool), (x0, y0)


def analyse(crop: np.ndarray, line: dict | None = None, y_off: int = 0):
    """Main component, dots, baseline band, stroke, per-column features; None if the ink is not one main run.
    `line` (baseline row in page pixels, rise and drop of the line's ink) makes "tall" and "deep" relative to
    the line the piece sits in: a threshold taken from a two-letter piece's own ink missed about half of the
    real ascenders (the kaf's arm or the alef itself shifts the piece's row profile)."""
    n, lab, stats, cent = cv2.connectedComponentsWithStats(crop.astype(np.uint8), connectivity=8)
    if n < 2:
        return None
    areas = stats[1:, cv2.CC_STAT_AREA]; big = 1 + int(np.argmax(areas)); main = lab == big
    if any(k != big and areas[k - 1] > 0.25 * areas[big - 1] for k in range(1, n)):
        return None                                                  # two main runs: not one piece
    prof = main.sum(1); b = int(np.argmax(prof)); thr = 0.5 * prof[b]; b0 = b1 = b
    while b0 > 0 and prof[b0 - 1] >= thr: b0 -= 1
    while b1 < crop.shape[0] - 1 and prof[b1 + 1] >= thr: b1 += 1
    stroke = max(2, b1 - b0 + 1); H, W = crop.shape
    top = np.array([np.argmax(main[:, x]) if main[:, x].any() else H for x in range(W)])
    bot = np.array([H - 1 - np.argmax(main[::-1, x]) if main[:, x].any() else -1 for x in range(W)])
    has = main.any(0)
    if line and line["rise"] >= 10:                   # any real line; the piece's own stroke estimate is not a reason to distrust it
        base = line["baseline"] - y_off; rise = line["rise"]; drop = max(line["drop"], stroke)
        up = base - top; down = bot - base
        asc, tall = has & (up >= 0.6 * rise), has & (up >= 0.8 * rise)
        # measured on the fixture: tall letters rise to a median 0.84 of the line's rise (others 0.36, 95th
        # percentile 0.67); descending letters drop to a median 0.64 of the line's drop (others 0.27, 75th 0.43)
        desc, deep = has & (down >= 0.5 * drop) & (down > stroke), has & (down >= 0.75 * drop) & (down > 2 * stroke)
    else:
        asc, tall = has & (top < b0 - 1.5 * stroke), has & (top < b0 - 3 * stroke)
        desc, deep = has & (bot > b1 + 1.0 * stroke), has & (bot > b1 + 2.5 * stroke)
    F = dict(main=main, b0=b0, b1=b1, stroke=stroke, has=has, W=W, asc=asc, tall=tall, desc=desc, deep=deep,
             thin=has & (top >= b0 - 1) & (bot <= b1 + 1), dots=[], dot_labels=[])
    for k in range(1, n):
        if k != big and areas[k - 1] >= 3:
            F["dots"].append((cent[k][0], cent[k][1] < b0)); F["dot_labels"].append(k)
    F["lab"] = lab
    return F


def align(units: list[str], F: dict):
    """Cut columns (crop x, left to right) dividing the piece into one interval per letter, or None."""
    W = F["W"]; n = len(units); unit_px = W / sum(width_class(u) for u in units)
    r = lambda v: v[::-1]
    asc, desc, thin, has, tall, deep = r(F["asc"]), r(F["desc"]), r(F["thin"]), r(F["has"]), r(F["tall"]), r(F["deep"])
    dots_r = [(W - 1 - cx, above) for cx, above in F["dots"]]
    cum = lambda v: np.concatenate([[0], np.cumsum(v)])
    c_asc, c_desc, c_has, c_tall, c_deep = cum(asc), cum(desc), cum(has), cum(tall), cum(deep)

    def agree(i, a, b):
        c = _base(units[i]); w = max(1, b - a); last = i == n - 1
        # presence is a count of columns, not a share of the interval: an alef is three pixels of ink in an
        # interval that may be thirty wide
        want_asc = c in ASC or c.startswith("ل")
        asc_ok = (c_asc[b] - c_asc[a]) >= 2 if want_asc else (c_tall[b] - c_tall[a]) < 2
        want_desc = c in DESC_ANY or (last and c in DESC_END)
        desc_ok = (c_desc[b] - c_desc[a]) >= 2 if want_desc else (c_deep[b] - c_deep[a]) < 2
        da = sum(1 for x, ab in dots_r if a <= x < b and ab); db = sum(1 for x, ab in dots_r if a <= x < b and not ab)
        wa = DOTS_ABOVE.get(c, 0); wb = DOTS_BELOW.get(c, 0)
        if c == "ي" and last: wb = db if db in (0, 2) else 2
        near = lambda got, want: got == want or (want >= 2 and 1 <= got <= want)
        return asc_ok, desc_ok, near(da, wa), near(db, wb)

    def score(i, a, b):
        w = b - a; s = -2.4 * abs(np.log(max(w, 1) / (width_class(units[i]) * unit_px))) ** 2
        if c_has[b] - c_has[a] < 0.3 * w: s -= 2
        a_ok, d_ok, da_ok, db_ok = agree(i, a, b)
        # An ascender or a dot is a hard fact about where a letter is: a
        # missing one costs far more than a width that is off. With equal
        # weights the programme traded a final alef's stroke for a nicer
        # width and final ا came out inconsistent half the time.
        s += (1.5 if a_ok else -6.0) + (1.0 if d_ok else -2.0) + (2.0 if da_ok else -5.0) + (2.0 if db_ok else -5.0)
        return s

    # A cut may only fall where the ink is nothing but the connecting stroke (`joins`): the geometry offers
    # the places, the letters' signatures choose among them. Left free over every column the programme was
    # no nearer the joins than equal slices were (experiment 08: 90.9% against 91.6% of cuts within a stroke).
    pos = [0] + sorted({W - 1 - x for x in joins(F)} - {0, W}) + [W]; m = len(pos)
    if m - 2 < n - 1:
        return None                                                  # fewer joins than cuts: the piece stays whole
    NEG = -1e9; best = np.full((n + 1, m), NEG); back = np.zeros((n + 1, m), int); best[0][0] = 0
    for i in range(n):
        for ai in range(m - 1):
            if best[i][ai] == NEG: continue
            for bi in range(ai + 1, m):
                if (i == n - 1) != (bi == m - 1): continue
                if pos[bi] - pos[ai] < 2: continue
                v = best[i][ai] + score(i, pos[ai], pos[bi])
                if v > best[i + 1][bi]: best[i + 1][bi] = v; back[i + 1][bi] = ai
    if best[n][m - 1] == NEG:
        return None
    bounds = []; bi = m - 1
    for i in range(n, 1, -1):
        bi = back[i][bi]; bounds.append(pos[bi])
    return sorted(W - 1 - c for c in bounds)


def joins(F: dict) -> list[int]:
    """Columns where a cut crosses only the connecting stroke: the middle of each short run of thin columns,
    and places a stroke apart along a long one (a kashida, or the flat body of a final ba, where the letter
    boundary is somewhere along it and the widths decide)."""
    thin, W, stroke = F["thin"], F["W"], F["stroke"]; out = []; x = 0
    while x < W:
        if not thin[x]:
            x += 1; continue
        j = x
        while j < W and thin[j]: j += 1
        if x > 1 and j < W - 1:                                      # a run touching the piece's edge is a tail, not a join
            k = max(1, -(-(j - x) // (2 * stroke)))
            out += [int(round(v)) for v in (np.linspace(x, j - 1, 2 * k + 1)[1::2])]
        x = j
    return out


def observe(units: list[str], F: dict, cuts: list[int]) -> list[tuple]:
    """Each letter's structural signature as the ink shows it: (ascender, descender, dots above, dots below)."""
    W = F["W"]; bounds = [0] + list(cuts) + [W]; out = []
    for k in range(len(units)):
        a, b = bounds[len(units) - 1 - k], bounds[len(units) - k]; w = max(1, b - a)
        da = sum(1 for x, ab in F["dots"] if a <= x < b and ab); db = sum(1 for x, ab in F["dots"] if a <= x < b and not ab)
        out.append((int(F["asc"][a:b].sum()) >= 2, int(F["desc"][a:b].sum()) >= 2, min(da, 3), min(db, 3)))
    return out


def line_geometry(ink: np.ndarray, blobs: list[dict]) -> dict | None:
    """A line's baseline (the row with the most ink across the whole line), and how far its ink rises above
    and drops below it. `ink` is the page's binary image, `blobs` the line's blobs."""
    if not blobs:
        return None
    x0 = min(b["x"] for b in blobs); x1 = max(b["x"] + b["w"] for b in blobs); y0 = min(b["y"] for b in blobs); y1 = max(b["y"] + b["h"] for b in blobs)
    rows = ink[y0:y1, x0:x1].sum(1)
    if rows.size < 4 or rows.max() == 0:
        return None
    base = y0 + int(np.argmax(rows))
    # How far the line's ink usually rises and drops, not how far its tallest blob does: a bracket or a
    # footnote marker above the line inflated the rise and real lams fell under the bar (0.58 of it).
    ups = [base - b["y"] for b in blobs if base - b["y"] > 0.35 * (base - y0)]
    downs = [b["y"] + b["h"] - base for b in blobs if b["y"] + b["h"] - base > 0.35 * (y1 - base)]
    rise = float(np.percentile(ups, 60)) if ups else float(base - y0)
    drop = float(np.percentile(downs, 60)) if downs else float(y1 - base)
    return dict(baseline=base, rise=rise, drop=drop)


def plan(units: list[str], blobs: list[dict], line: dict | None = None):
    """Alignment of one piece: dict(units, cuts (page x), obs, mask, off, F) or None."""
    if len(units) < 2:
        return None
    mask, off = piece_mask(blobs)
    if mask.shape[1] < 4 * len(units) or mask.shape[1] > 1500:
        return None
    F = analyse(mask, line, off[1])
    if F is None:
        return None
    cuts = align(units, F)
    if cuts is None:
        return None
    return dict(units=units, cuts=cuts, obs=observe(units, F, cuts), mask=mask, off=off, F=F)


RELIABLE = 0.85                                         # a feature is evidence for a letter-form when this share of its occurrences agree


def learn(plans: list[dict]) -> dict:
    """The document's own signatures. For each (letter, form) seen often enough, each feature — ascender,
    descender, dots above, dots below — gets its majority value IF that value holds for at least RELIABLE
    of the form's occurrences, else None: in this typeface that feature says nothing about this form
    (a final nun whose bowl hovers at the threshold), and it must not veto a cut."""
    seen = defaultdict(list)
    for p in plans:
        n = len(p["units"])
        for k, o in enumerate(p["obs"]):
            seen[(_base(p["units"][k]), form(k, n))].append(o)
    out = {}
    for c, obs in seen.items():
        if len(obs) < MIN_EXAMPLES:
            continue
        sig = []
        for i in range(4):
            v, cnt = Counter(o[i] for o in obs).most_common(1)[0]
            sig.append(v if cnt >= RELIABLE * len(obs) else None)
        out[c] = tuple(sig)
    return out


def accepted(p: dict, majority: dict) -> bool:
    """Every letter's form is known to the document, and the letter shows every feature that is reliable for
    that form; at least one letter must be confirmed by a positive feature (a tall stroke, a bowl, a dot),
    so that a run of featureless letters is not accepted on nothing."""
    n = len(p["units"]); positive = False
    for k, (u, o) in enumerate(zip(p["units"], p["obs"])):
        sig = majority.get((_base(u), form(k, n)))
        if sig is None:
            return False
        for want, got in zip(sig, o):
            if want is None:
                continue
            if want != got:
                return False
            positive = positive or bool(want)
    return positive


def letter_blobs(p: dict, blobs: list[dict]) -> list[list[dict]]:
    """The piece's ink cut at the plan's columns: one list of blob dicts per letter, in reading order
    (right to left). The main run is cut at the columns; dots go with the interval that holds their centre."""
    F = p["F"]; mask = F["main"]; x_off, y_off = p["off"]; W = F["W"]
    bounds = [0] + list(p["cuts"]) + [W]; n = len(p["units"]); out = []
    dots = [(F["dot_labels"][i], F["dots"][i][0]) for i in range(len(F["dots"]))]
    for k in range(n):
        a, b = bounds[n - 1 - k], bounds[n - k]
        sub = np.zeros_like(mask, np.uint8); sub[:, a:b] = mask[:, a:b]
        for lab_id, cx in dots:
            if a <= cx < b:
                sub |= (F["lab"] == lab_id).astype(np.uint8)
        cs, hier = cv2.findContours(sub, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        paths = [(cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2) + [x_off, y_off]) for c in cs]
        keep = [(pth, int(hier[0][i][3] >= 0)) for i, pth in enumerate(paths) if len(pth) >= 3]
        if not keep:
            return []                                                # an empty letter: the cut is not usable
        xs = np.concatenate([pth[:, 0] for pth, _ in keep]); ys = np.concatenate([pth[:, 1] for pth, _ in keep])
        out.append([dict(x=int(xs.min()), y=int(ys.min()), w=int(xs.max() - xs.min()), h=int(ys.max() - ys.min()),
                         cx=float(xs.mean()), cy=float(ys.mean()), paths=[pth for pth, _ in keep], holes=[h for _, h in keep], word=blobs[0].get("word"))])
    return out

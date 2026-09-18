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
            cv2.fillPoly(m, [(np.asarray(p) - [x0, y0]).astype(np.int32)], 0 if hole else 1)
    return m.astype(bool), (x0, y0)


def analyse(crop: np.ndarray):
    """Main component, dots, baseline band, stroke, per-column features; None if the ink is not one main run."""
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
    F = dict(main=main, b0=b0, b1=b1, stroke=stroke, has=has, W=W,
             asc=has & (top < b0 - 1.5 * stroke), tall=has & (top < b0 - 3 * stroke),
             desc=has & (bot > b1 + 1.0 * stroke), deep=has & (bot > b1 + 2.5 * stroke),
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
        want_asc = c in ASC or c.startswith("ل")
        asc_ok = (c_asc[b] - c_asc[a]) > 0.1 * w if want_asc else (c_tall[b] - c_tall[a]) <= 0.1 * w
        want_desc = c in DESC_ANY or (last and c in DESC_END)
        desc_ok = (c_desc[b] - c_desc[a]) > 0.1 * w if want_desc else (c_deep[b] - c_deep[a]) <= 0.1 * w
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
        if i < n - 1:
            s += 1.0 if (thin[min(b, W - 1)] or thin[max(b - 1, 0)]) else -0.5
        return s

    NEG = -1e9; best = np.full((n + 1, W + 1), NEG); back = np.zeros((n + 1, W + 1), int); best[0][0] = 0
    minw = max(2, int(0.35 * unit_px))
    for i in range(n):
        for a in range(W + 1):
            if best[i][a] == NEG: continue
            for b in range(a + minw, W + 1):
                if i == n - 1 and b != W: continue
                v = best[i][a] + score(i, a, b)
                if v > best[i + 1][b]: best[i + 1][b] = v; back[i + 1][b] = a
    if best[n][W] == NEG:
        return None
    bounds = [W]; b = W
    for i in range(n, 0, -1):
        b = back[i][b]; bounds.append(b)
    bounds = bounds[::-1]
    return sorted(W - 1 - c for c in bounds[1:-1])


def observe(units: list[str], F: dict, cuts: list[int]) -> list[tuple]:
    """Each letter's structural signature as the ink shows it: (ascender, descender, dots above, dots below)."""
    W = F["W"]; bounds = [0] + list(cuts) + [W]; out = []
    for k in range(len(units)):
        a, b = bounds[len(units) - 1 - k], bounds[len(units) - k]; w = max(1, b - a)
        da = sum(1 for x, ab in F["dots"] if a <= x < b and ab); db = sum(1 for x, ab in F["dots"] if a <= x < b and not ab)
        out.append((float(F["asc"][a:b].sum()) / w > 0.1, float(F["desc"][a:b].sum()) / w > 0.1, min(da, 3), min(db, 3)))
    return out


def plan(units: list[str], blobs: list[dict]):
    """Alignment of one piece: dict(units, cuts (page x), obs, mask, off, F) or None."""
    if len(units) < 2:
        return None
    mask, off = piece_mask(blobs)
    if mask.shape[1] < 4 * len(units) or mask.shape[1] > 1500:
        return None
    F = analyse(mask)
    if F is None:
        return None
    cuts = align(units, F)
    if cuts is None:
        return None
    return dict(units=units, cuts=cuts, obs=observe(units, F, cuts), mask=mask, off=off, F=F)


def learn(plans: list[dict]) -> dict:
    """The document's own signatures: majority (asc, desc, dots above, dots below) per (letter, form)."""
    seen = defaultdict(Counter)
    for p in plans:
        n = len(p["units"])
        for k, o in enumerate(p["obs"]):
            seen[(_base(p["units"][k]), form(k, n))][o] += 1
    return {c: cnt.most_common(1)[0][0] for c, cnt in seen.items() if sum(cnt.values()) >= MIN_EXAMPLES}


def accepted(p: dict, majority: dict) -> bool:
    n = len(p["units"])
    return all((_base(u), form(k, n)) in majority and majority[(_base(u), form(k, n))] == o for k, (u, o) in enumerate(zip(p["units"], p["obs"])))


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

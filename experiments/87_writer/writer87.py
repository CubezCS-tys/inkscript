"""Experiment 87, stage 1: the writer.  Letters + style settings -> ink, differentiably (PyTorch, batch- and GPU-ready).

A LETTER PROGRAM is a list of pen strokes in em units (baseline y = 0, y up): each stroke an ordered polyline of
points (x, y, r0), r0 the program's own half-width there (AlQalam: the half-extent of its broad square nib across
the stroke's direction; a font: the ink's half-width at the centre line).  A stroke is flagged `mark` (a dot, hamza,
madda) or body.  Libraries (`Library`):
  alqalam      - AlQalam 0.2's METAFONT pen strokes (alqalam87.py), shaped here by our own joining rules, dots placed
                 at anchors computed from each body's geometry;
  font:<file>  - strokes recovered from a font's glyphs with exp 82's learned centre line (fontprog87.py), shaped by
                 HarfBuzz.

STYLE SETTINGS (`Style`, all differentiable):
  size (px per em), xscale, slant, baseline (offset, tilt, curve), width (pen-width multiplier), spread (ink
  spread +, erosion -, in px), nib (angle, thin/thick ratio, width in em) and contrast (0 = the program's own widths,
  1 = a pure broad nib), mark placement (dx, dy above, dy below, scale), noise (render-time only), kashida (extra
  join length, em) and stacking (letter pairs lifted onto each other, calligraphy demo; layout-time).
ALIGNMENT (fitted per line, `Warp`): a monotone piecewise-linear map of the layout's x (knots every `knot_em`).

render(segs, style, warp, H, W) -> soft ink [B?, H, W] in 0..1: every segment is a tapered capsule; a pixel's ink is
sigmoid((r(t*) - d) / tau), max over segments, computed in column tiles so memory stays O(W * H * segs per tile).
"""
from __future__ import annotations

import json
import math
import os
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
PROG = OUT / "programs"

# ------------------------------------------------------------------------------------------------ AlQalam shaping
# AlQalam codes (qarbsymb.mf): base + form, form 0 isolated, 1 final, 2 medial, 3 initial
F_ISO, F_END, F_MID, F_BEG = 0, 1, 2, 3
RASM = {  # letter -> (base code or {form: code}, dots, dual-joining)
    "ا": (64, None, False), "أ": (64, "hamza_up", False), "إ": (64, "hamza_down", False), "آ": (64, "madda", False),
    "ٱ": (64, None, False),
    "ب": (72, "1d", True), "ت": (72, "2u", True), "ث": (72, "3u", True),
    "ن": ({F_ISO: 224, F_END: 225, F_MID: 74, F_BEG: 75}, "1u", True),
    "ي": ({F_ISO: 248, F_END: 249, F_MID: 74, F_BEG: 75}, "2d", True),
    "ى": ({F_ISO: 248, F_END: 249, F_MID: 74, F_BEG: 75}, None, True),
    "ئ": ({F_ISO: 248, F_END: 249, F_MID: 74, F_BEG: 75}, "hamza_up", True),
    "ج": (104, "1in", True), "ح": (104, None, True), "خ": (104, "1u", True),
    "د": (88, None, False), "ذ": (88, "1u", False), "ر": (80, None, False), "ز": (80, "1u", False),
    "س": (128, None, True), "ش": (128, "3u", True), "ص": (144, None, True), "ض": (144, "1u", True),
    "ط": (160, None, True), "ظ": (160, "1u", True), "ع": (168, None, True), "غ": (168, "1u", True),
    "ف": (172, "1u", True), "ق": ({F_ISO: 244, F_END: 245, F_MID: 174, F_BEG: 175}, "2u", True),
    "ك": ({F_ISO: 188, F_END: 189, F_MID: 186, F_BEG: 187}, None, True),
    "ل": (200, None, True), "م": (208, None, True), "ه": (232, None, True),
    "ة": ({F_ISO: 232, F_END: 233}, "2u", False), "و": (240, None, False), "ؤ": (240, "hamza_up", False),
    "ء": ({F_ISO: 90}, None, False),
}
MARKS = {"1u": 9, "2u": 16, "3u": 17, "1d": 46, "2d": 10, "3d": 18, "1in": 46, "hamza_up": 13, "hamza_down": 13,
         "madda": 14}
DIGITS = {**{str(i): 48 + i for i in range(10)}, **{chr(0x660 + i): 48 + i for i in range(10)},
          **{chr(0x6F0 + i): 48 + i for i in range(10)}}
PUNCT = {".": 46, ":": 58, "(": 41, ")": 40, "،": 44, ",": 44, "؛": 59, ";": 59, "؟": 63, "?": 63, "!": 33, "-": 45,
         "/": 47, "«": 34, "»": 34, "\"": 34, "*": 42, "+": 43, "=": 61, "[": 93, "]": 91, "%": 37}
HARAKAT = set(chr(c) for c in range(0x064B, 0x0653)) | {"ٰ", "ـ"}


@lru_cache(maxsize=1)
def aq_chars():
    d = json.loads((PROG / "alqalam_strokes.json").read_text())
    return {int(k): v for k, v in d["chars"].items()}


def _strokes_of(code: int):
    """[(pts [N,3] em, is_mark)] of an AlQalam char code (fills already turned into width-carrying strokes)."""
    c = aq_chars().get(code)
    if c is None:
        return [], 0.0
    return [(np.asarray(s["pts"], np.float32), False) for s in c["strokes"]], float(c["w"])


@lru_cache(maxsize=None)
def aq_anchor(code: int, form: int):
    """(x above, y above, x below, y below, x inside, y inside) for dots, from the body's geometry (em)."""
    S, w = _strokes_of(code)
    if not S:
        return (0.0, 0.5, 0.0, -0.1, 0.0, -0.1)
    P = np.vstack([s for s, _ in S])
    x, y, r = P[:, 0], P[:, 1], P[:, 2]
    gap = 0.07
    base = code - form
    if base in (72, 224, 248) and form in (F_ISO, F_END):
        xa = 0.5 * w if base != 248 else 0.38 * w           # bowls: the middle (ي: under the tail's belly)
    elif base in (128, 144, 160):
        sel = y > 0.04
        xa = float(x[sel].mean()) if sel.any() else 0.5 * w
        if base == 160:                                      # ط ظ: beside the ascender, over the loop
            sel = (y > 0.03) & (y < 0.2)
            xa = float(np.median(x[sel])) if sel.any() else 0.5 * w
    else:
        xa = float(x[np.argmax(y)])
    near = np.abs(x - xa) < 0.12
    ya = float((y + r)[near].max()) + gap if near.any() else float(y.max()) + gap
    yb = float((y - r)[near].min()) - gap if near.any() else float(y.min()) - gap
    if base in (72,) and form in (F_MID, F_BEG):
        yb = min(yb, -0.06 - gap)
    # inside (ج): the bowl's centre
    sel = y < -0.08
    xi = float(x[sel].mean()) if sel.any() else xa
    yi = float(0.5 * (y[sel].min() + y[sel].max())) if sel.any() else -0.15
    return (xa, ya, xa, yb, xi, yi)


def aq_shape(text: str, stack: set[tuple[str, str]] | None = None, kashida: float = 0.0):
    """Text -> glyph instances, visual order irrelevant (each carries its own x):
    [dict(strokes=[(pts, is_mark)], x=left edge em, y=0, char=index, word=k)] and the line width (em).
    Right to left: the first letter's right edge is at x = width."""
    items = []                                              # (char index, code, dots, form) in logical order
    words = text.split(" ")
    ci = 0
    out_words = []
    for wi, wd in enumerate(words):
        letters = [(ci + j, ch) for j, ch in enumerate(wd) if ch not in HARAKAT]
        ci += len(wd) + 1
        glyphs = []
        k = 0
        while k < len(letters):
            i, ch = letters[k]
            nxt = letters[k + 1][1] if k + 1 < len(letters) else None
            prv = glyphs[-1] if glyphs else None
            joins_prev = prv is not None and prv["dual"]
            if ch == "ل" and nxt in ("ا", "أ", "إ", "آ"):     # lam-alif
                code = 67 if joins_prev else 66
                dots = {"أ": "hamza_up", "إ": "hamza_down", "آ": "madda"}.get(nxt)
                glyphs.append(dict(i=i, code=code, form=F_END if joins_prev else F_ISO, dots=dots, dual=False, ch=ch + nxt))
                k += 2
                continue
            if ch in RASM:
                base, dots, dual = RASM[ch]
                joins_next = dual and nxt is not None and (nxt in RASM)
                form = (F_MID if joins_next else F_END) if joins_prev else (F_BEG if joins_next else F_ISO)
                if isinstance(base, dict):
                    code = base.get(form, base.get(F_ISO))
                    if form not in base:
                        form = F_END if form == F_MID else F_ISO
                else:
                    code = base + form
                    if not dual:
                        code = base + (F_END if joins_prev else F_ISO)
                        form = F_END if joins_prev else F_ISO
                glyphs.append(dict(i=i, code=code, form=form, dots=dots, dual=dual and joins_next, ch=ch))
            elif ch in DIGITS or ch in PUNCT:
                glyphs.append(dict(i=i, code=DIGITS.get(ch, PUNCT.get(ch)), form=F_ISO, dots=None, dual=False, ch=ch))
            else:
                glyphs.append(dict(i=i, code=None, form=F_ISO, dots=None, dual=False, ch=ch))   # unsupported
            k += 1
        out_words.append(glyphs)
    # place right to left
    x = 0.0
    space = 0.3
    inst = []
    for wi, glyphs in enumerate(out_words):
        for gi, g in enumerate(glyphs):
            S, w = _strokes_of(g["code"]) if g["code"] is not None else ([], 0.25)
            # numbers and Latin run left to right inside an RTL line; kept as single glyphs here (approximation)
            joined = gi + 1 < len(glyphs) and g["dual"]
            x -= w
            S = list(S)
            if g["dots"]:
                S += _dots(g["dots"], g["code"], g["form"])
            dy = 0.0
            if stack and gi > 0 and (glyphs[gi - 1]["ch"], g["ch"]) in stack:
                dy = 0.35
            inst.append(dict(strokes=S, x=x, y=dy, char=g["i"], word=wi, ch=g["ch"], code=g["code"]))
            if joined and kashida > 0:
                inst.append(dict(strokes=[(np.array([[x, 0, 0.022], [x - kashida, 0, 0.022]], np.float32) - [x, 0, 0], False)],
                                 x=x - kashida, y=0.0, char=g["i"], word=wi, ch="ـ", code=4))
                inst[-1]["strokes"] = [(np.array([[kashida, 0, 0.022], [0, 0, 0.022]], np.float32), False)]
                x -= kashida
        x -= space
    width = -x - space
    for g in inst:
        g["x"] += width
    return inst, width


def _dots(kind: str, code: int, form: int):
    S, w = _strokes_of(MARKS[kind])
    if not S:
        return []
    P = np.vstack([s for s, _ in S])
    mx0, mx1 = P[:, 0].min(), P[:, 0].max()
    my0, my1 = P[:, 1].min(), P[:, 1].max()
    xa, ya, xb, yb, xi, yi = aq_anchor(code, form)
    if kind in ("1d", "2d", "3d", "hamza_down"):
        ox, oy = xb - 0.5 * (mx0 + mx1), yb - my1
    elif kind == "1in":
        ox, oy = xi - 0.5 * (mx0 + mx1), yi - 0.5 * (my0 + my1)
    else:
        ox, oy = xa - 0.5 * (mx0 + mx1), ya - my0
    return [((s + np.array([ox, oy, 0], np.float32)).astype(np.float32), True) for s, _ in S]


# ------------------------------------------------------------------------------------------------ font libraries
@lru_cache(maxsize=None)
def font_lib(name: str):
    """A font's glyph programs (fontprog87.py): {gid: [(pts [N,3] em, is_mark)]} + the font file."""
    d = json.loads((PROG / f"font_{name}.json").read_text())
    if os.environ.get("FONTS87"):                      # on the GPU host the font files sit in one folder
        d["path"] = str(Path(os.environ["FONTS87"]) / d["font"])
    G = {int(k): [(np.asarray(s["pts"], np.float32), bool(s["mark"])) for s in v] for k, v in d["glyphs"].items()}
    return G, d


@lru_cache(maxsize=None)
def _hb_font(path: str):
    import uharfbuzz as hb
    blob = hb.Blob.from_file_path(path)
    face = hb.Face(blob)
    f = hb.Font(face)
    return f, face.upem


def font_shape(text: str, name: str):
    import uharfbuzz as hb
    G, d = font_lib(name)
    if not text.strip():                               # an empty reading writes nothing (HarfBuzz gives no infos)
        return [], 0.0
    f, upm = _hb_font(d["path"])
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(f, buf, {})
    if buf.glyph_infos is None:
        return [], 0.0
    x = 0.0
    inst = []
    # word index of each character
    wid, k = [], 0
    for ch in text:
        wid.append(k)
        if ch == " ":
            k += 1
    for inf, ps in zip(buf.glyph_infos, buf.glyph_positions):
        S = G.get(inf.codepoint)
        if S is None:
            S = []
        inst.append(dict(strokes=S, x=(x + ps.x_offset) / upm, y=ps.y_offset / upm, char=inf.cluster,
                         word=wid[min(inf.cluster, len(wid) - 1)] if wid else 0, gid=inf.codepoint,
                         missing=inf.codepoint not in G))
        x += ps.x_advance
    return inst, x / upm


def shape(text: str, lib: str, **kw):
    if lib == "alqalam":
        return aq_shape(text, **kw)
    assert lib.startswith("font:")
    return font_shape(text, lib[5:])


# ------------------------------------------------------------------------------------------------ segments
@dataclass
class Segs:
    """Flattened capsules of one written line (em units, y up)."""
    a: torch.Tensor          # [S, 2]
    b: torch.Tensor          # [S, 2]
    ra: torch.Tensor         # [S]
    rb: torch.Tensor         # [S]
    mark: torch.Tensor       # [S] bool
    above: torch.Tensor      # [S] bool  (mark above the baseline)
    glyph: torch.Tensor      # [S] long  (instance index)
    char: torch.Tensor       # [S] long  (character index in the text)
    width: float             # line width, em
    n_glyph: int = 0
    words: list = field(default_factory=list)   # per glyph instance: word index


def segments(inst, width: float, device="cpu") -> Segs:
    A, B, RA, RB, M, U, GI, CI = [], [], [], [], [], [], [], []
    for gi, g in enumerate(inst):
        for pts, is_mark in g["strokes"]:
            p = np.asarray(pts, np.float32).copy()
            if len(p) == 0:
                continue
            p[:, 0] += g["x"]
            p[:, 1] += g["y"]
            if len(p) == 1:
                p = np.vstack([p, p + [1e-4, 0, 0]])
            A.append(p[:-1, :2]); B.append(p[1:, :2]); RA.append(p[:-1, 2]); RB.append(p[1:, 2])
            n = len(p) - 1
            M.append(np.full(n, is_mark)); U.append(np.full(n, is_mark and p[:, 1].mean() > 0.15))
            GI.append(np.full(n, gi)); CI.append(np.full(n, g["char"]))
    if not A:
        z = torch.zeros((1, 2))
        return Segs(z, z + 1e-4, torch.zeros(1), torch.zeros(1), torch.zeros(1, dtype=torch.bool),
                    torch.zeros(1, dtype=torch.bool), torch.zeros(1, dtype=torch.long), torch.zeros(1, dtype=torch.long),
                    width, len(inst), [g["word"] for g in inst])
    t = lambda L, dt=torch.float32: torch.as_tensor(np.concatenate(L), dtype=dt, device=device)
    return Segs(t(A), t(B), t(RA), t(RB), t(M, torch.bool), t(U, torch.bool), t(GI, torch.long), t(CI, torch.long),
                width, len(inst), [g["word"] for g in inst])


# ------------------------------------------------------------------------------------------------ style
STYLE0 = dict(size=40.0, xscale=1.0, slant=0.0, base=0.0, tilt=0.0, curve=0.0, width=1.0, spread=0.0,
              nib_angle=math.radians(70), nib_ratio=0.18, nib_w=0.075, contrast=0.0,
              mark_dx=0.0, mark_dy_up=0.0, mark_dy_down=0.0, mark_scale=1.0, x0=0.0)


class Style(torch.nn.Module):
    def __init__(self, init: dict | None = None, fixed: set | None = None, device="cpu"):
        super().__init__()
        v = dict(STYLE0, **(init or {}))
        self.fixed = set(fixed or ())
        self.p = torch.nn.ParameterDict({k: torch.nn.Parameter(torch.tensor(float(x), device=device),
                                                              requires_grad=k not in self.fixed) for k, x in v.items()})

    def __getitem__(self, k):
        return self.p[k]

    def as_dict(self):
        return {k: round(float(v.detach()), 5) for k, v in self.p.items()}


class Warp(torch.nn.Module):
    """Monotone piecewise-linear map of layout x (em) -> x (em): knots every knot_em, increments softplus(theta)."""

    def __init__(self, width: float, knot_em: float = 0.5, device="cpu"):
        super().__init__()
        self.k = max(2, int(math.ceil(width / knot_em)) + 1)
        self.step = width / (self.k - 1) if width > 0 else 1.0
        self.theta = torch.nn.Parameter(torch.full((self.k - 1,), math.log(math.e - 1), device=device))  # softplus=1

    def knots(self):
        inc = torch.nn.functional.softplus(self.theta) * self.step
        return torch.cat([inc.new_zeros(1), torch.cumsum(inc, 0)])

    def forward(self, x):
        K = self.knots()
        u = (x / self.step).clamp(0, self.k - 1 - 1e-6)
        i = u.floor().long()
        f = u - i
        y = K[i] * (1 - f) + K[i + 1] * f
        # outside the line: linear continuation
        y = torch.where(x < 0, x * (K[1] / self.step), y)
        y = torch.where(x > (self.k - 1) * self.step, K[-1] + (x - (self.k - 1) * self.step) * ((K[-1] - K[-2]) / self.step), y)
        return y

    def set_from(self, xs_em: np.ndarray, ys_em: np.ndarray):
        """Initialise the knots from matched points (layout x -> target x, em), monotone least squares (approx)."""
        kx = np.arange(self.k) * self.step
        ky = np.interp(kx, xs_em, ys_em)
        ky = np.maximum.accumulate(ky)
        inc = np.maximum(np.diff(ky), 0.05 * self.step) / self.step
        with torch.no_grad():
            self.theta.copy_(torch.as_tensor(np.log(np.expm1(inc)), dtype=torch.float32))
        return ky[0]


def nib_halfwidth(dirx, diry, st: Style):
    """Half the extent across the stroke of a broad nib of width nib_w (em) and thin ratio, at nib_angle."""
    ang = torch.atan2(diry, dirx)
    rel = ang - st["nib_angle"]
    s = torch.sqrt(torch.sin(rel) ** 2 + 1e-4)
    c = torch.sqrt(torch.cos(rel) ** 2 + 1e-4)
    return 0.5 * st["nib_w"] * (s + st["nib_ratio"].clamp(0.02, 1.0) * c)


def place(sg: Segs, st: Style, warp: Warp | None, H: int):
    """Segments in em -> pixel coordinates (x right, y down) and radii in px."""
    def tr(p, mark, up):
        x, y = p[:, 0], p[:, 1]
        # marks: shift and scale about their glyph-local position (approximation: shift only + scale about anchor)
        mdx = st["mark_dx"] * mark
        mdy = torch.where(up, st["mark_dy_up"], st["mark_dy_down"]) * mark
        x = x + mdx
        y = y + mdy
        xw = warp(x) if warp is not None else x
        X = st["x0"] + st["size"] * st["xscale"] * (xw + st["slant"] * y)
        u = X / max(1.0, float(H) * 10)
        base = H * 0.62 + st["base"] + st["tilt"] * (X - X.detach().mean()) + st["curve"] * ((X - X.detach().mean()) / (5 * H)) ** 2 * H
        Y = base - st["size"] * y
        return torch.stack([X, Y], 1)
    m = sg.mark.float()
    A = tr(sg.a, m, sg.above)
    B = tr(sg.b, m, sg.above)
    d = sg.b - sg.a
    nib = nib_halfwidth(d[:, 0], d[:, 1], st)
    c = st["contrast"].clamp(0, 1)
    msc = 1 + (st["mark_scale"] - 1) * m
    ra = st["size"] * st["width"] * msc * ((1 - c) * sg.ra + c * nib) + st["spread"]
    rb = st["size"] * st["width"] * msc * ((1 - c) * sg.rb + c * nib) + st["spread"]
    return A, B, ra.clamp(min=0.3), rb.clamp(min=0.3)


def render(sg: Segs, st: Style, warp: Warp | None, H: int, W: int, tau: float = 0.6, tile: int = 16,
           need_ids: bool = False):
    """Soft ink [H, W] (and, if need_ids, the index of the segment that inks each pixel most, -1 for none)."""
    A, B, ra, rb = place(sg, st, warp, H)
    dev = A.device
    out = torch.zeros((H, W), device=dev)
    ids = torch.full((H, W), -1, dtype=torch.long, device=dev) if need_ids else None
    xmin = torch.minimum(A[:, 0], B[:, 0]) - torch.maximum(ra, rb) - 3 * tau
    xmax = torch.maximum(A[:, 0], B[:, 0]) + torch.maximum(ra, rb) + 3 * tau
    ys = torch.arange(H, device=dev, dtype=torch.float32) + 0.5
    ntile = (W + tile - 1) // tile
    with torch.no_grad():
        t0 = torch.arange(ntile, device=dev) * tile
        hit = (xmax[None, :] >= t0[:, None]) & (xmin[None, :] <= (t0 + tile)[:, None])      # [T, S]
        cnt = hit.sum(1)
        smax = int(cnt.max()) if len(cnt) else 0
    if smax == 0:
        return (out, ids) if need_ids else out
    # padded segment index per tile
    with torch.no_grad():
        order = torch.argsort((~hit).to(torch.int8), dim=1, stable=True)[:, :smax]         # hit ones first
        valid = torch.gather(hit, 1, order)
    Ai, Bi = A[order], B[order]                                                             # [T, s, 2]
    rai, rbi = ra[order], rb[order]
    xs = (t0[:, None].float() + torch.arange(tile, device=dev)[None, :].float() + 0.5)      # [T, tile]
    PX = xs[:, None, :].expand(ntile, H, tile).reshape(ntile, H * tile)                    # [T, P]
    PY = ys[None, :, None].expand(ntile, H, tile).reshape(ntile, H * tile)
    ab = Bi - Ai                                                                            # [T, s, 2]
    L2 = (ab ** 2).sum(-1).clamp(min=1e-6)                                                 # [T, s]
    apx = PX[:, :, None] - Ai[:, None, :, 0]                                                # [T, P, s]
    apy = PY[:, :, None] - Ai[:, None, :, 1]
    t = ((apx * ab[:, None, :, 0] + apy * ab[:, None, :, 1]) / L2[:, None, :]).clamp(0, 1)
    dx = apx - t * ab[:, None, :, 0]
    dy = apy - t * ab[:, None, :, 1]
    d = torch.sqrt(dx * dx + dy * dy + 1e-6)
    r = rai[:, None, :] * (1 - t) + rbi[:, None, :] * t
    v = torch.sigmoid((r - d) / tau) * valid[:, None, :]
    best, arg = v.max(-1)                                                                   # [T, P]
    img = best.reshape(ntile, H, tile).permute(1, 0, 2).reshape(H, ntile * tile)[:, :W]
    if need_ids:
        sid = torch.gather(order, 1, arg)
        sid = torch.where(best > 0.5, sid, torch.full_like(sid, -1))
        ids = sid.reshape(ntile, H, tile).permute(1, 0, 2).reshape(H, ntile * tile)[:, :W]
        return img, ids
    return img


def write_line(text: str, lib: str, style: dict | None = None, H: int = 96, pad_em: float = 0.4, noise: float = 0.0,
               seed: int = 0, **kw):
    """Convenience: text -> grey uint8 image (no fitting)."""
    inst, width = shape(text, lib, **kw)
    sg = segments(inst, width)
    st = Style(style)
    with torch.no_grad():
        if "x0" not in (style or {}):
            st.p["x0"].fill_(pad_em * float(st["size"]))
        W = int(float(st["size"]) * float(st["xscale"]) * (width + 2 * pad_em)) + 2
        img = render(sg, st, None, H, W).numpy()
    if noise > 0:
        rng = np.random.default_rng(seed)
        img = np.clip(img + noise * rng.normal(size=img.shape), 0, 1)
    return (255 * (1 - img)).astype(np.uint8), inst, width

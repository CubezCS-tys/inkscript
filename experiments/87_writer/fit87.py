"""Experiment 87: fitting the writer to real ink, many lines at once (GPU batches; CPU for looks).

An ITEM is (crop, text, lib, style group).  For a batch of items:
  1. the target ink: sig79.binarise of the 96-px crop (exp 81's judge-crop recipe);
  2. the text is shaped and turned into capsules (writer87);
  3. initial size and baseline: the written line's body height and baseline matched to the real one's
     (sig79.line_metrics); initial alignment: DTW of column ink profiles (4 bands round the baseline);
  4. Adam on the soft IoU of written and real ink, blurred coarse to fine (sigma 3 -> 0.5 px), with priors that keep
     the warp smooth and the settings plausible.
Per-line settings (always free): x0, baseline offset, tilt, curve, the warp.  Style settings (shared by a style
group): size, slant, width, spread, nib angle / ratio / width, contrast, mark dx / dy up / dy down / scale.
mode "free": style free (the ceiling: true text, fitted settings); mode "frozen": style given (re-write to verify).

Outputs per item: the fitted settings, the written soft ink, and the scores:
  iou       - |W and R| / |W or R| (W = written ink > 0.5, R = real ink)
  recall    - share of real ink within 1.5 px of writing (1 - "missing")
  precision - share of writing within 1.5 px of real ink (1 - "invented")
  chamfer   - mean of the two directed mean nearest-ink distances (px at 96 px)
"""
from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import writer87 as W  # noqa: E402


def binarise(grey: np.ndarray) -> np.ndarray:
    """exp 79's sig79.binarise, copied: Otsu on the darkness against the local paper."""
    g = cv2.GaussianBlur(grey, (3, 3), 0)
    bg = cv2.medianBlur(cv2.dilate(g, np.ones((7, 7), np.uint8)), 21)
    d = np.clip(bg.astype(int) - g.astype(int), 0, 255)
    d = (255 * d / max(8, d.max())).astype(np.uint8)
    t, b = cv2.threshold(d, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return b.astype(bool)


def line_metrics(ink: np.ndarray) -> dict:
    """exp 79's sig79.line_metrics, copied (thinning by scikit-image instead of the repo's Zhang-Suen, so the GPU
    host needs no repo code): baseline row, rise (body height), stroke width."""
    try:
        from skimage.morphology import skeletonize
    except ImportError:                                    # the reader service's venv has no scikit-image:
        skeletonize = None                                 # the distance transform's ridge stands in for the skeleton
    ink = ink.astype(bool)
    rows = ink.sum(1).astype(float)
    rows[rows > 0.6 * ink.shape[1]] = 0
    rows = np.convolve(rows, np.ones(3) / 3, mode="same")
    base = int(np.argmax(rows))
    dt = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3)
    if skeletonize is not None:
        sk = skeletonize(ink) if ink.any() else ink
    else:
        sk = (dt > 0) & (dt >= cv2.dilate(dt, np.ones((3, 3), np.uint8)) - 1e-6)
    stroke = float(2 * np.median(dt[sk])) if sk.any() else 2.0
    r = base
    while r > 0 and rows[r] > rows[base] / 4:
        r -= 1
    rise = max(4.0, float(base - r) * 1.6, 2.5 * stroke)
    return dict(baseline=base, rise=rise, stroke=max(1.0, stroke))

WARP_FLOOR = float(os.environ.get("WARP87", 0))   # round 2: 0.6
H = int(os.environ.get("H87", 96))     # working height; crops are 96 px and are resized when H differs
STYLE_KEYS = ["size", "slant", "width", "spread", "nib_angle", "nib_ratio", "nib_w", "contrast",
              "mark_dx", "mark_dy_up", "mark_dy_down", "mark_scale"]
LINE_KEYS = ["x0", "base", "tilt", "curve"]
LR = dict(size=0.4, slant=0.01, width=0.015, spread=0.04, nib_angle=0.03, nib_ratio=0.01, nib_w=0.003, contrast=0.02,
          mark_dx=0.004, mark_dy_up=0.004, mark_dy_down=0.004, mark_scale=0.01, x0=0.6, base=0.3, tilt=0.0008,
          curve=0.02, theta=0.03)
LIM = dict(size=(15, 140), slant=(-0.35, 0.35), width=(0.4, 2.5), spread=(-0.6, 3.5), nib_angle=(-0.5, 3.6),
           nib_ratio=(0.05, 0.9), nib_w=(0.02, 0.2), contrast=(0.0, 1.0), mark_dx=(-0.08, 0.08),
           mark_dy_up=(-0.08, 0.12), mark_dy_down=(-0.12, 0.08), mark_scale=(0.8, 1.4), tilt=(-0.03, 0.03),
           curve=(-2.0, 2.0))


def target_of(grey: np.ndarray) -> np.ndarray:
    """The line's own ink: binarise, then drop the neighbour lines' ink that the crop's padding catches (a piece
    lying wholly outside Azure's polygon band, or touching the crop's top/bottom edge with its centre outside it)."""
    ink = binarise(grey).astype(np.uint8)
    h = ink.shape[0]
    lo, hi = 0.153 * h, 0.847 * h                          # common77.cut_line: PAD_V = 0.22 of the polygon height
    n, lab, st, cen = cv2.connectedComponentsWithStats(ink, connectivity=8)
    keep = np.zeros(n, bool)
    for k in range(1, n):
        y, hh = st[k, 1], st[k, 3]
        out_band = y + hh <= lo or y >= hi
        edge = (y == 0 or y + hh >= h) and not (lo <= cen[k, 1] <= hi)
        keep[k] = not (out_band or edge)
    return keep[lab].astype(np.float32)


# ------------------------------------------------------------------------------------------------ batched geometry
class Batch:
    def __init__(self, items, device):
        """items: list of dict(grey, text, lib, group, [style init dict]); groups index the style table."""
        self.dev = device
        self.items = items
        self.B = len(items)
        segs, self.widths = [], []
        for it in items:
            inst, width = W.shape(it["text"], it["lib"], **it.get("shape_kw", {}))
            it["inst"] = inst
            it["n_missing"] = sum(1 for g in inst if g.get("missing")) + sum(1 for g in inst if g.get("code") is None and g.get("ch", "") not in " ")
            sg = W.segments(inst, width)
            segs.append(sg)
            self.widths.append(width)
        self.segs = segs
        n = [len(s.a) for s in segs]
        self.line = torch.cat([torch.full((k,), i, dtype=torch.long) for i, k in enumerate(n)]).to(device)
        cat = lambda f: torch.cat([getattr(s, f) for s in segs]).to(device)
        self.a, self.b, self.ra, self.rb = cat("a"), cat("b"), cat("ra"), cat("rb")
        self.mark, self.above = cat("mark"), cat("above")
        self.char = cat("char")
        self.seg_off = np.concatenate([[0], np.cumsum(n)])
        for it in items:
            if it["grey"].shape[0] != H:
                f = H / it["grey"].shape[0]
                it["grey"] = cv2.resize(it["grey"], (max(8, int(round(it["grey"].shape[1] * f))), H), interpolation=cv2.INTER_AREA)
        self.Wd = [it["grey"].shape[1] for it in items]
        self.Wmax = max(self.Wd)
        T = np.zeros((self.B, H, self.Wmax), np.float32)
        M = np.zeros((self.B, 1, self.Wmax), np.float32)
        for i, it in enumerate(items):
            if it["grey"].shape[0] != H:
                f = H / it["grey"].shape[0]
                it["grey"] = cv2.resize(it["grey"], (max(8, int(round(it["grey"].shape[1] * f))), H), interpolation=cv2.INTER_AREA)
            t = it.get("target")
            if t is None:
                t = target_of(it["grey"])
            T[i, :, :t.shape[1]] = t
            M[i, :, :t.shape[1]] = 1
        self.T = torch.as_tensor(T, device=device)
        self.colmask = torch.as_tensor(M, device=device)
        groups = sorted({it.get("group", i) for i, it in enumerate(items)})
        self.gidx = {g: k for k, g in enumerate(groups)}
        self.group = torch.as_tensor([self.gidx[it.get("group", i)] for i, it in enumerate(items)], device=device)
        # warp: knots every 0.5 em
        self.kstep, self.kn = [], []
        for w in self.widths:
            k = max(2, int(math.ceil(max(w, 0.1) / 0.5)) + 1)
            self.kn.append(k)
            self.kstep.append(max(w, 0.1) / (k - 1))
        self.Kmax = max(self.kn)
        self.kstep_t = torch.as_tensor(self.kstep, dtype=torch.float32, device=device)
        self.kn_t = torch.as_tensor(self.kn, dtype=torch.long, device=device)


class Params(torch.nn.Module):
    def __init__(self, bt: Batch, style_init: dict | list | None = None):
        super().__init__()
        G = len(bt.gidx)
        dev = bt.dev
        S0 = dict(W.STYLE0)
        if isinstance(style_init, dict):
            S0.update(style_init)
        self.style = torch.nn.ParameterDict({k: torch.nn.Parameter(torch.full((G,), float(S0[k]), device=dev)) for k in STYLE_KEYS})
        if isinstance(style_init, list):                # per group
            with torch.no_grad():
                for g, d in enumerate(style_init):
                    for k in STYLE_KEYS:
                        if k in d:
                            self.style[k][g] = float(d[k])
        self.linep = torch.nn.ParameterDict({k: torch.nn.Parameter(torch.zeros(bt.B, device=dev)) for k in LINE_KEYS})
        self.theta = torch.nn.Parameter(torch.full((bt.B, bt.Kmax - 1), math.log(math.e - 1), device=dev))

    def clamp_(self):
        with torch.no_grad():
            for k, (a, b) in LIM.items():
                t = self.style[k] if k in self.style else (self.linep[k] if k in self.linep else None)
                if t is not None:
                    t.clamp_(a, b)


def knots(P: Params, bt: Batch):
    inc = F.softplus(P.theta) * bt.kstep_t[:, None]
    j = torch.arange(bt.Kmax - 1, device=bt.dev)[None, :]
    inc = torch.where(j < (bt.kn_t[:, None] - 1), inc, torch.zeros_like(inc))
    return torch.cat([inc.new_zeros(bt.B, 1), torch.cumsum(inc, 1)], 1)          # [B, Kmax]


def warp_x(x, line, P, bt, K):
    st = bt.kstep_t[line]
    kn = bt.kn_t[line]
    u = (x / st).clamp(min=0)
    u = torch.minimum(u, (kn - 1).float() - 1e-4)
    i = u.floor().long()
    f = u - i
    y = K[line, i] * (1 - f) + K[line, i + 1] * f
    first = (K[line, 1] - K[line, 0]) / st
    last = (K[line, kn - 1] - K[line, kn - 2]) / st
    xend = (kn - 1).float() * st
    y = torch.where(x < 0, x * first, y)
    y = torch.where(x > xend, K[line, kn - 1] + (x - xend) * last, y)
    return y


def place_batch(bt: Batch, P: Params):
    K = knots(P, bt)
    g = bt.group[bt.line]
    s = {k: v[g] for k, v in P.style.items()}
    lp = {k: v[bt.line] for k, v in P.linep.items()}
    m = bt.mark.float()

    def tr(p):
        x, y = p[:, 0], p[:, 1]
        x = x + s["mark_dx"] * m
        y = y + torch.where(bt.above, s["mark_dy_up"], s["mark_dy_down"]) * m
        xw = warp_x(x, bt.line, P, bt, K)
        X = lp["x0"] + s["size"] * (xw + s["slant"] * y)
        Wc = torch.as_tensor(bt.Wd, dtype=torch.float32, device=bt.dev)[bt.line]
        u = (X - 0.5 * Wc) / H
        Y = H * 0.62 + lp["base"] + lp["tilt"] * (X - 0.5 * Wc) + lp["curve"] * u * u * 4 - s["size"] * y
        return torch.stack([X, Y], 1)
    A, B = tr(bt.a), tr(bt.b)
    d = bt.b - bt.a
    ang = torch.atan2(d[:, 1], d[:, 0])
    rel = ang - s["nib_angle"]
    nib = 0.5 * s["nib_w"] * (torch.sqrt(torch.sin(rel) ** 2 + 1e-4) + s["nib_ratio"] * torch.sqrt(torch.cos(rel) ** 2 + 1e-4))
    c = s["contrast"]
    msc = 1 + (s["mark_scale"] - 1) * m
    ra = s["size"] * s["width"] * msc * ((1 - c) * bt.ra + c * nib) + s["spread"]
    rb = s["size"] * s["width"] * msc * ((1 - c) * bt.rb + c * nib) + s["spread"]
    return A, B, ra.clamp(min=0.35), rb.clamp(min=0.35)


def _tile_index(bt: Batch, A, B, ra, rb, tile: int, tau: float):
    """Per (line, column tile): the global indices of the segments that can reach it, padded."""
    with torch.no_grad():
        rr = torch.maximum(ra, rb) + 3 * tau
        xmin = torch.minimum(A[:, 0], B[:, 0]) - rr
        xmax = torch.maximum(A[:, 0], B[:, 0]) + rr
        T = (bt.Wmax + tile - 1) // tile
        lists, smax = [], 1
        t0 = torch.arange(T, device=bt.dev) * tile
        for i in range(bt.B):
            a, b = int(bt.seg_off[i]), int(bt.seg_off[i + 1])
            hit = (xmax[None, a:b] >= t0[:, None]) & (xmin[None, a:b] <= (t0 + tile)[:, None])   # [T, s_i]
            cnt = hit.sum(1)
            smax = max(smax, int(cnt.max()) if b > a else 1)
            lists.append((a, hit))
        idx = torch.zeros((bt.B, T, smax), dtype=torch.long, device=bt.dev)
        val = torch.zeros((bt.B, T, smax), dtype=torch.bool, device=bt.dev)
        for i, (a, hit) in enumerate(lists):
            if hit.shape[1] == 0:
                continue
            order = torch.argsort((~hit).to(torch.int8), dim=1, stable=True)[:, :smax]
            k = order.shape[1]
            idx[i, :, :k] = order + a
            val[i, :, :k] = torch.gather(hit, 1, order)
        return idx.reshape(bt.B * T, smax), val.reshape(bt.B * T, smax), T


def _render_tiles(A, B, ra, rb, idx, val, x0s, tile, tau):
    Ai, Bi, rai, rbi = A[idx], B[idx], ra[idx], rb[idx]                         # [N, s, 2]
    xs = x0s[:, None] + torch.arange(tile, device=A.device)[None, :].float() + 0.5
    ys = torch.arange(H, device=A.device, dtype=torch.float32) + 0.5
    N = idx.shape[0]
    PX = xs[:, None, :].expand(N, H, tile).reshape(N, H * tile)
    PY = ys[None, :, None].expand(N, H, tile).reshape(N, H * tile)
    ab = Bi - Ai
    L2 = (ab ** 2).sum(-1).clamp(min=1e-6)
    apx = PX[:, :, None] - Ai[:, None, :, 0]
    apy = PY[:, :, None] - Ai[:, None, :, 1]
    t = ((apx * ab[:, None, :, 0] + apy * ab[:, None, :, 1]) / L2[:, None, :]).clamp(0, 1)
    dx = apx - t * ab[:, None, :, 0]
    dy = apy - t * ab[:, None, :, 1]
    d = torch.sqrt(dx * dx + dy * dy + 1e-6)
    r = rai[:, None, :] * (1 - t) + rbi[:, None, :] * t
    v = torch.sigmoid((r - d) / tau) * val[:, None, :]
    best, arg = v.max(-1)
    return best, arg


def render_batch(bt: Batch, P: Params, tau: float = 0.6, tile: int = 16, chunk: int = 256, need_ids: bool = False):
    """Tiles are sorted by how many segments reach them and rendered in chunks, each padded only to its own largest
    count (most tiles hold a few segments, a dense one many: one global padding wasted ~3/4 of the work)."""
    A, B, ra, rb = place_batch(bt, P)
    idx, val, T = _tile_index(bt, A, B, ra, rb, tile, tau)
    x0s = (torch.arange(T, device=bt.dev) * tile).float().repeat(bt.B)
    N = idx.shape[0]
    with torch.no_grad():
        cnt = val.sum(1)
        order = torch.argsort(cnt)
        cnt_sorted = cnt[order].cpu().numpy()
    first = int(np.searchsorted(cnt_sorted, 1))                  # tiles with no segment stay blank
    flat = torch.zeros((N, H * tile), device=bt.dev)
    sidf = torch.full((N, H * tile), -1, dtype=torch.long, device=bt.dev) if need_ids else None
    from torch.utils.checkpoint import checkpoint
    for c0 in range(first, N, chunk):
        o = order[c0:c0 + chunk]
        sm = int(cnt_sorted[min(N, c0 + chunk) - 1])
        ii, vv = idx[o, :sm], val[o, :sm]
        if torch.is_grad_enabled() and A.is_cuda:
            best, arg = checkpoint(_render_tiles, A, B, ra, rb, ii, vv, x0s[o], tile, tau, use_reentrant=False)
        else:
            best, arg = _render_tiles(A, B, ra, rb, ii, vv, x0s[o], tile, tau)
        flat = flat.index_put((o,), best)
        if need_ids:
            sid = torch.gather(ii, 1, arg)
            sidf[o] = torch.where(best > 0.5, sid, torch.full_like(sid, -1))
    img = flat.reshape(bt.B, T, H, tile).permute(0, 2, 1, 3).reshape(bt.B, H, T * tile)[:, :, :bt.Wmax]
    img = img * bt.colmask
    if need_ids:
        sid = sidf.reshape(bt.B, T, H, tile).permute(0, 2, 1, 3).reshape(bt.B, H, T * tile)[:, :, :bt.Wmax]
        return img, sid
    return img


# ------------------------------------------------------------------------------------------------ initialisation
def _bands(ink: np.ndarray, base: float, rise: float) -> np.ndarray:
    """Column features: ink in 4 bands round the baseline (high, body, base, below), smoothed."""
    Hh = ink.shape[0]
    e = [0, max(0, base - 2.0 * rise), max(0, base - 0.6 * rise), min(Hh, base + 0.25 * rise), Hh]
    f = np.stack([ink[int(e[k]):int(e[k + 1])].sum(0) for k in range(4)], 1).astype(np.float32) / max(1.0, rise)
    return cv2.blur(f, (1, 3))


try:
    from numba import njit
except Exception:  # noqa: BLE001
    def njit(*a, **k):                                     # no numba: plain Python (slower DTW)
        return a[0] if a and callable(a[0]) else (lambda f: f)


@njit(cache=True)
def _dtw(C):
    n, m = C.shape
    D = np.full((n + 1, m + 1), 1e18)
    D[0, :] = 0.0                       # free start in the target (the written line may begin later)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c = C[i - 1, j - 1]
            D[i, j] = c + min(D[i - 1, j - 1], D[i - 1, j] + 0.3, D[i, j - 1] + 0.3)
    # free end in the target
    j = 1 + np.argmin(D[n, 1:])
    i = n
    path = []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        a, b, c = D[i - 1, j - 1], D[i - 1, j] + 0.3, D[i, j - 1] + 0.3
        if a <= b and a <= c:
            i, j = i - 1, j - 1
        elif b <= c:
            i -= 1
        else:
            j -= 1
    return path[::-1]


def _extent(ink: np.ndarray):
    cols = np.nonzero(ink.sum(0) > 0)[0]
    return (int(cols[0]), int(cols[-1]) + 1) if len(cols) else (0, ink.shape[1])


def _set_warp(P: Params, bt: Batch, i: int, kx_to_ky):
    st, kn = bt.kstep[i], bt.kn[i]
    kx = np.arange(kn) * st
    ky = np.maximum.accumulate(kx_to_ky(kx))
    inc = np.clip(np.diff(ky) / st, 0.12, 20)
    P.theta[i, :kn - 1] = torch.as_tensor(np.log(np.expm1(inc)), dtype=torch.float32)
    return float(ky[0])


def init_items(bt: Batch, P: Params, use_dtw: bool = True, fix_size: bool = False):
    """Initial size, baseline and warp of every line (no gradients).
    1. horizontal size s_h = the real ink's extent / the layout's width; written at s_h from the ink's first column;
    2. vertical size s_v = s_h x (real body height / written body height) (line_metrics 'rise'), averaged over a
       style group (unless the size is given: fix_size); the warp's slope s_h / s_v keeps the extent;
    3. DTW of column profiles (4 bands round each baseline) refines the warp."""
    with torch.no_grad():
        for k in LINE_KEYS:
            P.linep[k].zero_()
        Tn = bt.T.cpu().numpy() > 0.5
        ext = [_extent(Tn[i, :, :bt.Wd[i]]) for i in range(bt.B)]
        sh = np.array([max(4.0, (e[1] - e[0]) / max(0.2, w)) for e, w in zip(ext, bt.widths)])
        G = len(bt.gidx)
        grp = bt.group.cpu().numpy()
        if not fix_size:
            P.style["size"].copy_(torch.as_tensor([np.median(sh[grp == g]) for g in range(G)], dtype=torch.float32))
        S = P.style["size"][bt.group].cpu().numpy()
        for i in range(bt.B):
            r = sh[i] / S[i]
            _set_warp(P, bt, i, lambda kx: kx * r)
            P.linep["x0"][i] = float(ext[i][0])
        R = (render_batch(bt, P) > 0.5).cpu().numpy()
        if not fix_size:
            ratio = np.ones(bt.B)
            for i in range(bt.B):
                mr, mt = line_metrics(R[i, :, :bt.Wd[i]]), line_metrics(Tn[i, :, :bt.Wd[i]])
                ratio[i] = np.clip(mt["rise"] / max(1.0, mr["rise"]), 0.5, 2.0)
            sv = [float(np.median((S * ratio)[grp == g])) for g in range(G)]
            P.style["size"].copy_(torch.as_tensor(np.clip(sv, 15 * H / 96, 130 * H / 96), dtype=torch.float32))
            S = P.style["size"][bt.group].cpu().numpy()
            for i in range(bt.B):
                r = sh[i] / S[i]
                _set_warp(P, bt, i, lambda kx: kx * r)
            R = (render_batch(bt, P) > 0.5).cpu().numpy()
        for i in range(bt.B):
            w = bt.Wd[i]
            mr, mt = line_metrics(R[i, :, :w]), line_metrics(Tn[i, :, :w])
            P.linep["base"][i] = float(mt["baseline"] - mr["baseline"])
        if not use_dtw:
            return
        R = (render_batch(bt, P) > 0.5).cpu().numpy()
        K = knots(P, bt).cpu().numpy()
        for i in range(bt.B):
            w = bt.Wd[i]
            mr, mt = line_metrics(R[i, :, :w]), line_metrics(Tn[i, :, :w])
            fr = _bands(R[i, :, :w], mr["baseline"], mr["rise"])
            ft = _bands(Tn[i, :, :w], mt["baseline"], mt["rise"])
            cr, ct = np.nonzero(fr.sum(1) > 0)[0], np.nonzero(ft.sum(1) > 0)[0]
            if len(cr) < 4 or len(ct) < 4:
                continue
            r0, r1, t0, t1 = cr[0], cr[-1] + 1, ct[0], ct[-1] + 1
            C = np.abs(fr[r0:r1, None, :] - ft[None, t0:t1, :]).sum(-1).astype(np.float64)
            path = np.array(_dtw(C))
            xr = path[:, 0] + r0 + 0.5
            xt = path[:, 1] + t0 + 0.5
            x0 = float(P.linep["x0"][i])
            # written column -> warped em (X - x0) / size -> layout em through the current knots (inverse)
            kn, st = bt.kn[i], bt.kstep[i]
            Ki = K[i, :kn]
            kx = np.arange(kn) * st
            em_w = (xr - x0) / S[i]
            lay = np.interp(em_w, Ki, kx)
            tgt = (xt - x0) / S[i]
            o = np.argsort(lay, kind="stable")
            lay, tgt = lay[o], tgt[o]
            off = _set_warp(P, bt, i, lambda q: np.interp(q, lay, tgt))
            P.linep["x0"][i] = float(x0 + off * S[i])

# ------------------------------------------------------------------------------------------------ fitting
def _blur(x, sigma):
    if sigma <= 0.3:
        return x
    k = int(2 * math.ceil(2.5 * sigma) + 1)
    g = torch.exp(-0.5 * (torch.arange(k, device=x.device) - k // 2).float() ** 2 / sigma ** 2)
    g = g / g.sum()
    x = x[:, None]
    x = F.conv2d(x, g[None, None, None, :], padding=(0, k // 2))
    x = F.conv2d(x, g[None, None, :, None], padding=(k // 2, 0))
    return x[:, 0]


def fit(bt: Batch, P: Params, mode: str = "free", iters: int = 160, log: bool = False, free_keys=None,
        fine_only: bool = False):
    """mode free: style + line + warp; frozen: line + warp only (style fixed).  free_keys: override."""
    groups = []
    if mode == "free":
        sk = STYLE_KEYS if free_keys is None else [k for k in STYLE_KEYS if k in free_keys]
    else:
        sk = [] if free_keys is None else [k for k in STYLE_KEYS if k in free_keys]
    for k in STYLE_KEYS:
        P.style[k].requires_grad_(k in sk)
        if k in sk:
            groups.append(dict(params=[P.style[k]], lr=LR[k]))
    for k in LINE_KEYS:
        groups.append(dict(params=[P.linep[k]], lr=LR[k]))
    groups.append(dict(params=[P.theta], lr=LR["theta"]))
    opt = torch.optim.Adam(groups, betas=(0.8, 0.95))
    sched = [(0.0, 3.0), (0.3, 2.0), (0.55, 1.2), (0.8, 0.6)] if not fine_only else [(0.0, 1.2), (0.5, 0.6)]
    th0 = P.theta.detach().clone()
    floor = None
    if mode == "frozen" and WARP_FLOOR > 0:
        # round 2: in the checker a letter may not be squeezed below WARP_FLOOR of the line's typical width, so an
        # added word must take room (and show as writing on paper) instead of being folded away
        with torch.no_grad():
            inc0 = F.softplus(th0)
            j = torch.arange(bt.Kmax - 1, device=bt.dev)[None, :]
            valid = j < (bt.kn_t[:, None] - 1)
            med = torch.stack([inc0[i][valid[i]].median() for i in range(bt.B)])
            fl = (WARP_FLOOR * med).clamp(min=0.05)
            floor = torch.log(torch.expm1(fl))[:, None]
    with torch.no_grad():
        dens = _blur(bt.T, 4.0)
        Wt = 1.0 / (0.15 + dens / dens.amax((1, 2), keepdim=True).clamp(min=1e-3))
    for it in range(iters):
        sig = [s for f, s in sched if it >= f * iters][-1]
        opt.zero_grad(set_to_none=True)
        R = render_batch(bt, P)
        Rb, Tb = _blur(R, sig), _blur(bt.T, sig)
        # weighted: a pixel counts more where the real ink is sparse, so dots, teeth and thin joins are not given
        # up for the heavy strokes (with plain IoU the fit eroded every dot away)
        inter = (Wt * Rb * Tb).sum((1, 2))
        union = (Wt * (Rb + Tb - Rb * Tb)).sum((1, 2)).clamp(min=1.0)
        loss_l = 1 - inter / union
        # warp smoothness (log increments change slowly) and staying near the DTW start
        lt = torch.log(F.softplus(P.theta) + 1e-4)
        smooth = ((lt[:, 1:] - lt[:, :-1]) ** 2).mean(1)
        reg = 0.02 * smooth + 0.002 * ((P.theta - th0) ** 2).mean(1)
        loss = (loss_l + reg).sum()
        loss.backward()
        opt.step()
        P.clamp_()
        if floor is not None:
            with torch.no_grad():
                P.theta.copy_(torch.maximum(P.theta, floor))
        if log and (it % 40 == 0 or it == iters - 1):
            print(f"  it {it} sigma {sig} loss {float(loss_l.detach().mean()):.4f}", flush=True)
    return P


def scores(bt: Batch, P: Params, need_maps: bool = False):
    with torch.no_grad():
        R, ids = render_batch(bt, P, need_ids=True)
    Rn = (R > 0.5).cpu().numpy()
    Tn = bt.T.cpu().numpy() > 0.5
    out = []
    for i in range(bt.B):
        w = bt.Wd[i]
        r, t = Rn[i, :, :w], Tn[i, :, :w]
        inter, uni = (r & t).sum(), (r | t).sum()
        dr = cv2.distanceTransform((~r).astype(np.uint8), cv2.DIST_L2, 3)
        dtt = cv2.distanceTransform((~t).astype(np.uint8), cv2.DIST_L2, 3)
        rec = float((dr[t] <= 1.5).mean()) if t.any() else 0.0
        prec = float((dtt[r] <= 1.5).mean()) if r.any() else 0.0
        ch = 0.5 * (float(dr[t].mean()) if t.any() else 50.0) + 0.5 * (float(dtt[r].mean()) if r.any() else 50.0)
        d = dict(iou=float(inter / max(1, uni)), recall=rec, precision=prec, chamfer=ch,
                 n_missing=bt.items[i].get("n_missing", 0))
        # round 2: per word and per letter, the writing that lands on paper and the ink its columns leave unwritten
        idl = ids[i, :, :w].cpu().numpy()
        sg = bt.segs[i]
        g_of = sg.glyph.cpu().numpy()
        wd = np.asarray(sg.words) if len(sg.words) else np.zeros(1, int)
        has = idl >= 0
        loc = np.where(has, idl - int(bt.seg_off[i]), 0)
        loc = np.clip(loc, 0, len(g_of) - 1)
        gl = np.where(has, g_of[loc], -1)
        wl = np.where(gl >= 0, wd[np.clip(gl, 0, len(wd) - 1)], -1)
        precs, recs, gprecs = [], [], []
        for lab_map, store in ((wl, "w"), (gl, "g")):
            for u in np.unique(lab_map[lab_map >= 0]):
                m = lab_map == u
                n = m.sum()
                if n < 8:
                    continue
                pr = float((dtt[m] <= 1.5).mean())
                if store == "g":
                    gprecs.append(pr)
                    continue
                precs.append(pr)
                cols = np.nonzero(m.any(0))[0]
                tc = t[:, cols[0]:cols[-1] + 1]
                if tc.sum() >= 8:
                    recs.append(float((dr[:, cols[0]:cols[-1] + 1][tc] <= 1.5).mean()))
                else:
                    recs.append(0.0)                   # a written word over columns with no ink at all
        srt = lambda v, k: float(np.mean(sorted(v)[:k])) if v else 1.0
        d.update(word_prec_min=srt(precs, 1), word_prec_min2=srt(precs, 2), word_rec_min=srt(recs, 1),
                 word_rec_min2=srt(recs, 2), glyph_prec_min=srt(gprecs, 1), glyph_prec_min3=srt(gprecs, 3))
        if need_maps:
            d["written"] = R[i, :, :w].cpu().numpy()
            d["ids"] = ids[i, :, :w].cpu().numpy()
            d["dist_to_writing"] = dr
            d["dist_to_ink"] = dtt
        out.append(d)
    return out


def params_of(P: Params, bt: Batch, i: int) -> dict:
    g = int(bt.group[i])
    d = {k: round(float(v[g]), 5) for k, v in P.style.items()}
    d.update({k: round(float(v[i]), 5) for k, v in P.linep.items()})
    return d


def style_of_group(P: Params, g: int) -> dict:
    return {k: float(v[g]) for k, v in P.style.items()}


def overlay(grey: np.ndarray, written: np.ndarray, ink: np.ndarray) -> np.ndarray:
    """Real ink black where explained, red where no writing covers it (missing); writing on paper in blue
    (invented); writing on ink dark grey."""
    w = written > 0.5
    t = ink > 0.5
    dr = cv2.distanceTransform((~w).astype(np.uint8), cv2.DIST_L2, 3)
    dtt = cv2.distanceTransform((~t).astype(np.uint8), cv2.DIST_L2, 3)
    img = np.full(grey.shape + (3,), 255, np.uint8)
    img[t & (dr <= 1.5)] = (40, 40, 40)
    img[t & (dr > 1.5)] = (30, 30, 230)
    img[w & ~t & (dtt > 1.5)] = (230, 120, 30)
    img[w & ~t & (dtt <= 1.5)] = (170, 170, 170)
    return img


def device():
    if torch.cuda.is_available():
        return "cuda"
    torch.set_num_threads(int(os.environ.get("THREADS", 2)))
    return "cpu"

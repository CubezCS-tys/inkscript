"""Experiment 94, goal 2: reading order by rules (no model).

order_page(boxes, labels, rtl, W, H) -> list of indices in reading order.  boxes: [x0, y0, x1, y1] (any units, y down);
labels: fine types (common94.FINE) or None.

Rules, in this order:
1. Furniture out of the flow: header / page-number lines in the top band go first (top to bottom), those in the bottom
   band go last; footnotes are read after the body (before the bottom furniture).
2. Tables and verse are atoms: their lines are grouped into regions (touching boxes of the same kind), and a region
   is read row by row: lines -> cells (stacked lines that overlap horizontally, small gap) -> rows (cells overlapping
   vertically), cells right to left (left to right on a Latin page), lines inside a cell top to bottom.
3. Columns before bands: a recursive XY-cut over the remaining lines and the region atoms, which cuts along a vertical
   gutter whenever one exists with real text on both sides (each side >= 15% of the group's width and >= 2 items, or
   a region), and only otherwise at the widest horizontal gap; columns right to left (left to right on a Latin page).
"""
from __future__ import annotations

import numpy as np

FURN = {"header", "page_number"}
ATOM = {"table", "verse"}


def _overlap(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0)


def _regions(ix, B, mh):
    """Connected groups of boxes: in the same row, or near each other (2 line heights across, 1.5 down)."""
    ix = list(ix)
    parent = {i: i for i in ix}

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a in range(len(ix)):
        for b in range(a + 1, len(ix)):
            i, j = ix[a], ix[b]
            if (_overlap(B[i, 1], B[i, 3], B[j, 1], B[j, 3]) > 0 or      # same row, however far apart the cells
                    (_overlap(B[i, 0], B[i, 2], B[j, 0], B[j, 2]) > -2 * mh and
                     _overlap(B[i, 1], B[i, 3], B[j, 1], B[j, 3]) > -1.5 * mh)):
                parent[f(i)] = f(j)
    g = {}
    for i in ix:
        g.setdefault(f(i), []).append(i)
    return list(g.values())


def _groups(ix, link):
    parent = {i: i for i in ix}

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a in range(len(ix)):
        for b in range(a + 1, len(ix)):
            if link(ix[a], ix[b]):
                parent[f(ix[a])] = f(ix[b])
    g = {}
    for i in ix:
        g.setdefault(f(i), []).append(i)
    return list(g.values())


def table_order(ix, B, rtl):
    """Row by row: row bands = lines chained by vertical overlap (a line spanning two bands, like a tall header cell,
    joins them); inside a band, cells = lines chained by horizontal overlap, read right to left (left to right on a
    Latin page), lines inside a cell top to bottom."""
    ix = list(ix)
    if len(ix) <= 1:
        return ix

    def vlink(i, j):
        h = min(B[i, 3] - B[i, 1], B[j, 3] - B[j, 1])
        return _overlap(B[i, 1], B[i, 3], B[j, 1], B[j, 3]) > 0.25 * h

    def hlink(i, j):
        w = min(B[i, 2] - B[i, 0], B[j, 2] - B[j, 0])
        return _overlap(B[i, 0], B[i, 2], B[j, 0], B[j, 2]) > 0.3 * w
    out = []
    for band in sorted(_groups(ix, vlink), key=lambda g: min(B[i, 1] for i in g)):
        cells = _groups(band, hlink)
        cells.sort(key=lambda c: -max(B[i, 2] for i in c) if rtl else min(B[i, 0] for i in c))
        for c in cells:
            out += sorted(c, key=lambda i: B[i, 1])
    return out


COLMIN = dict(lines=2, hfrac=0.0)   # what a side of a vertical gutter needs to count as a column (set by the dev runs)


def xycut(items, rtl, mh, minfrac=0.15):
    """items: [(box, payload, is_atom)].  Returns payloads in order."""
    if not items:
        return []
    if len(items) == 1:
        return [items[0][1]]
    B = np.array([it[0] for it in items], dtype=float)

    def gaps(a, b):
        iv = sorted((B[i, a], B[i, b]) for i in range(len(items)))
        out, end = [], iv[0][1]
        for lo, hi in iv[1:]:
            if lo > end:
                out.append((end, lo))
            end = max(end, hi)
        return out
    gw = B[:, 2].max() - B[:, 0].min()
    gh = B[:, 3].max() - B[:, 1].min()
    best_v = None
    for g0, g1 in gaps(0, 2):
        if g1 - g0 < 0.5 * mh:
            continue
        c = (g0 + g1) / 2
        R = [i for i in range(len(items)) if (B[i, 0] + B[i, 2]) / 2 >= c]
        L = [i for i in range(len(items)) if (B[i, 0] + B[i, 2]) / 2 < c]

        def ok(S):
            if any(items[i][2] for i in S):
                return True
            w = B[S, 2].max() - B[S, 0].min()
            h = B[S, 3].max() - B[S, 1].min()
            return len(S) >= COLMIN["lines"] and w >= minfrac * gw and h >= COLMIN["hfrac"] * gh
        if R and L and ok(R) and ok(L) and (best_v is None or g1 - g0 > best_v[1] - best_v[0]):
            best_v = (g0, g1, R, L)
    if best_v:
        _, _, R, L = best_v
        first, second = (R, L) if rtl else (L, R)
        return xycut([items[i] for i in first], rtl, mh, minfrac) + xycut([items[i] for i in second], rtl, mh, minfrac)
    hg = [g for g in gaps(1, 3) if g[1] - g[0] >= 0.3 * mh]
    if hg:
        g0, g1 = max(hg, key=lambda g: g[1] - g[0])
        c = (g0 + g1) / 2
        T = [items[i] for i in range(len(items)) if (B[i, 1] + B[i, 3]) / 2 < c]
        D = [items[i] for i in range(len(items)) if (B[i, 1] + B[i, 3]) / 2 >= c]
        if T and D:
            return xycut(T, rtl, mh, minfrac) + xycut(D, rtl, mh, minfrac)
    # no gap: top to bottom, then right to left
    o = sorted(range(len(items)), key=lambda i: ((B[i, 1] + B[i, 3]) / 2, -B[i, 2] if rtl else B[i, 0]))
    return [items[i][1] for i in o]


def flatten(seq):
    out = []
    for s in seq:
        out += s if isinstance(s, list) else [s]
    return out


def order_page(boxes, labels, rtl=True, H=None, band=0.12, rules=("furn", "foot", "atom", "cols")):
    n = len(boxes)
    if n == 0:
        return []
    B = np.array(boxes, dtype=float)
    labels = list(labels) if labels is not None else [None] * n
    mh = float(np.median(np.maximum(1e-6, B[:, 3] - B[:, 1])))
    top = B[:, 1].min() if H is None else 0.0
    bot = B[:, 3].max() if H is None else H
    span = max(1e-6, bot - top)
    head, tail, foot, rest = [], [], [], []
    for i in range(n):
        yc = (B[i, 1] + B[i, 3]) / 2
        if "furn" in rules and labels[i] in FURN and yc < top + band * span:
            head.append(i)
        elif "furn" in rules and labels[i] in FURN and yc > bot - band * span:
            tail.append(i)
        elif "foot" in rules and labels[i] == "footnote":
            foot.append(i)
        else:
            rest.append(i)
    items = []
    if "atom" in rules:
        at = [i for i in rest if labels[i] in ATOM]
        for g in _regions(at, B, mh):
            if len(g) == 1:
                items.append((list(B[g[0]]), g[0], False))
                continue
            box = [B[g, 0].min(), B[g, 1].min(), B[g, 2].max(), B[g, 3].max()]
            items.append((box, table_order(g, B, rtl), True))
        rest = [i for i in rest if labels[i] not in ATOM]
    items += [(list(B[i]), i, False) for i in rest]
    if "cols" in rules:
        body = flatten(xycut(items, rtl, mh))
    else:
        body = flatten(_plain_xycut(items, rtl, mh))
    simple = lambda S: flatten(xycut([(list(B[i]), i, False) for i in S], rtl, mh))  # noqa: E731
    return simple(head) + body + simple(foot) + simple(tail)


XY = dict(vmin=0.5, hmin=0.3)   # experiment 92's thresholds (line heights); set by the dev runs


def _plain_xycut(items, rtl, mh):
    """Experiment 92's XY-cut (common92.xycut_order: one cut per level at the widest gap, horizontal when it is at
    least as wide as the vertical one), re-implemented over items with its two thresholds as parameters (XY)."""
    if not items:
        return []
    B = np.array([it[0] for it in items], dtype=float)
    mh = float(np.median(np.maximum(1e-6, B[:, 3] - B[:, 1])))

    def widest_gap(ix, a, b):
        iv = sorted((B[i, a], B[i, b]) for i in ix)
        best, end = None, iv[0][1]
        for lo, hi in iv[1:]:
            if lo > end and (best is None or lo - end > best[1] - best[0]):
                best = (end, lo)
            end = max(end, hi)
        return best

    def rec(ix):
        if len(ix) <= 1:
            return ix
        h = widest_gap(ix, 1, 3)
        v = widest_gap(ix, 0, 2)
        hw = (h[1] - h[0]) / mh if h else 0
        vw = (v[1] - v[0]) / mh if v else 0
        if h and hw >= XY["hmin"] and (hw >= vw or vw < XY["vmin"]):
            c = (h[0] + h[1]) / 2
            top = [i for i in ix if (B[i, 1] + B[i, 3]) / 2 < c]
            bot = [i for i in ix if (B[i, 1] + B[i, 3]) / 2 >= c]
            if top and bot:
                return rec(top) + rec(bot)
        if v and vw >= XY["vmin"]:
            c = (v[0] + v[1]) / 2
            right = [i for i in ix if (B[i, 0] + B[i, 2]) / 2 >= c]
            left = [i for i in ix if (B[i, 0] + B[i, 2]) / 2 < c]
            if right and left:
                return rec(right) + rec(left) if rtl else rec(left) + rec(right)
        return sorted(ix, key=lambda i: ((B[i, 1] + B[i, 3]) / 2, -B[i, 2] if rtl else B[i, 0]))

    return [items[i][1] for i in rec(list(range(len(items))))]

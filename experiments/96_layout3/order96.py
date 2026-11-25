"""Experiment 96, goal 2 candidate (a): columns from line-box edges that line up down the page, then experiment 94's
frozen rules (XY-cut, tables and verse read row by row as atoms) inside each column.

order_cols(boxes, labels, rtl, H) -> indices in reading order.  Boxes [x0, y0, x1, y1], y down.

The page is mirrored for a left-to-right page, so the rule only ever reads right to left.
1. Atoms: table / verse regions as in order94 (one item each, read row by row inside).
2. Gutter search (recursive, on a set of items): the left edges x0 and the right edges x1 of the narrow items (not
   wider than 70% of the set) are clustered (tolerance TOL line heights).  A gutter is a pair (a cluster of right
   edges at a = the left column's right margin, a cluster of left edges at b = the right column's left margin) with
   -0.2 <= b - a <= GMAX line heights, each cluster with >= MIN_LINES lines, and the two clusters' lines sharing a
   vertical range.  Gutter g = (a + b) / 2; its support = lines of both clusters; the best supported one wins.
   Items that cross g by more than 0.3 line heights on both sides are SPANNING (a heading or a footnote across the
   columns).  If spanning items cover more than half of the set, there is no gutter.
3. Spanning items cut the set into bands top to bottom; in each band the items right of g are read (recursively,
   step 2) before the items left of g; a spanning item is read where it falls.
4. No gutter: order94.xycut (white-gap XY-cut, vertical gutters first) on the set.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "94_layout2"))
import order94 as O94  # noqa: E402

P = dict(TOL=0.6, GMAX=3.0, MIN_LINES=3, WIDE=0.7, CROSS=0.3, SPAN_MAX=0.1, WHITE_FIRST=True, COLW=0.15)


def white_vertical(items, mh, minfrac=0.15):
    """order94.xycut's vertical white-gap test: (R, L) index lists for the widest white gutter, or None."""
    B = np.array([it[0] for it in items], dtype=float)
    iv = sorted((B[i, 0], B[i, 2]) for i in range(len(items)))
    gaps, end = [], iv[0][1]
    for lo, hi in iv[1:]:
        if lo > end:
            gaps.append((end, lo))
        end = max(end, hi)
    gw = B[:, 2].max() - B[:, 0].min()
    best = None
    for g0, g1 in gaps:
        if g1 - g0 < 0.5 * mh:
            continue
        c = (g0 + g1) / 2
        R = [i for i in range(len(items)) if (B[i, 0] + B[i, 2]) / 2 >= c]
        L = [i for i in range(len(items)) if (B[i, 0] + B[i, 2]) / 2 < c]

        def ok(S):
            return any(items[i][2] for i in S) or (len(S) >= 2 and B[S, 2].max() - B[S, 0].min() >= minfrac * gw)
        if R and L and ok(R) and ok(L) and (best is None or g1 - g0 > best[0]):
            best = (g1 - g0, R, L)
    return None if best is None else best[1:]


def horizontal(items, mh):
    B = np.array([it[0] for it in items], dtype=float)
    iv = sorted((B[i, 1], B[i, 3]) for i in range(len(items)))
    gaps, end = [], iv[0][1]
    for lo, hi in iv[1:]:
        if lo > end and lo - end >= 0.3 * mh:
            gaps.append((end, lo))
        end = max(end, hi)
    if not gaps:
        return None
    g0, g1 = max(gaps, key=lambda g: g[1] - g[0])
    c = (g0 + g1) / 2
    T = [i for i in range(len(items)) if (B[i, 1] + B[i, 3]) / 2 < c]
    D = [i for i in range(len(items)) if (B[i, 1] + B[i, 3]) / 2 >= c]
    return (T, D) if T and D else None


def _clusters(vals, tol):
    """[(center, [indices])] of 1-D values chained within tol."""
    o = np.argsort(vals)
    out, cur = [], [o[0]] if len(o) else []
    for a, b in zip(o, o[1:]):
        if vals[b] - vals[a] <= tol:
            cur.append(b)
        else:
            out.append(cur)
            cur = [b]
    if cur:
        out.append(cur)
    return [(float(np.median(vals[c])), list(c)) for c in out]


def find_gutter(B, mh):
    n = len(B)
    if n < 2 * P["MIN_LINES"]:
        return None
    gw = B[:, 2].max() - B[:, 0].min()
    nar = np.where(B[:, 2] - B[:, 0] <= P["WIDE"] * gw)[0]
    if len(nar) < 2 * P["MIN_LINES"]:
        return None
    rights = _clusters(B[nar, 2], P["TOL"] * mh)      # right edges: the right margin of a column on the left
    lefts = _clusters(B[nar, 0], P["TOL"] * mh)       # left edges: the left margin of a column on the right
    best = None
    for a, ca in rights:
        if len(ca) < P["MIN_LINES"]:
            continue
        ia = nar[ca]
        for b, cb in lefts:
            if len(cb) < P["MIN_LINES"] or not (-0.2 * mh <= b - a <= P["GMAX"] * mh):
                continue
            ib = nar[cb]
            if min(B[ia, 3].max(), B[ib, 3].max()) - max(B[ia, 1].min(), B[ib, 1].min()) <= 0:
                continue
            g = (a + b) / 2
            # columns are text, not a row of bullets or numbers: each cluster's lines are wide
            if min(np.median(B[ia, 2] - B[ia, 0]), np.median(B[ib, 2] - B[ib, 0])) < max(3 * mh, P["COLW"] * gw):
                continue
            # the left column's lines must lie left of g, the right column's right of g
            if (B[ia, 0] < g - 0.3 * mh).mean() < 0.9 or (B[ib, 2] > g + 0.3 * mh).mean() < 0.9:
                continue
            sup = np.concatenate([ia, ib])
            y0, y1 = B[sup, 1].min(), B[sup, 3].max()
            inside = ((B[:, 1] + B[:, 3]) / 2 >= y0) & ((B[:, 1] + B[:, 3]) / 2 <= y1)
            span = inside & (B[:, 0] < g - P["CROSS"] * mh) & (B[:, 2] > g + P["CROSS"] * mh)
            if span.sum() > max(2, P["SPAN_MAX"] * inside.sum()):
                continue
            sc = len(sup) - 3 * span.sum()
            if best is None or sc > best[1]:
                best = (g, sc, span, inside)
    if best is None:
        return None
    g, _, span, inside = best
    left = inside & (~span) & ((B[:, 0] + B[:, 2]) / 2 < g)
    right = inside & (~span) & ~left
    if left.sum() < P["MIN_LINES"] or right.sum() < P["MIN_LINES"]:
        return None
    return g, span, inside


def _rec(items, mh, depth=0):
    """items: [(box, payload, is_atom)] in the right-to-left frame.  XY-cut with the edge gutter inserted:
    white vertical gutter -> edge gutter (columns without a white gap) -> widest horizontal gap -> rows."""
    if len(items) <= 1:
        return [it[1] for it in items]
    B = np.array([it[0] for it in items], dtype=float)
    sub = lambda ix: _rec([items[i] for i in ix], mh, depth + 1)  # noqa: E731
    if P["WHITE_FIRST"]:
        wv = white_vertical(items, mh)
        if wv:
            return sub(wv[0]) + sub(wv[1])
    gut = find_gutter(B, mh) if depth < 12 else None
    if gut is not None:
        g, span, inside = gut
        yc = (B[:, 1] + B[:, 3]) / 2
        y0 = min(B[i, 1] for i in range(len(items)) if inside[i])
        top = [i for i in range(len(items)) if not inside[i] and yc[i] < y0]
        bot = [i for i in range(len(items)) if not inside[i] and yc[i] >= y0]
        out = sub(top) if top else []
        sp = sorted(np.where(span)[0], key=lambda i: B[i, 1])
        cuts = [-1e18] + [yc[i] for i in sp] + [1e18]
        rest = [i for i in range(len(items)) if inside[i] and not span[i]]
        for k in range(len(cuts) - 1):
            band = [i for i in rest if cuts[k] <= yc[i] < cuts[k + 1]]
            out += sub([i for i in band if (B[i, 0] + B[i, 2]) / 2 >= g])
            out += sub([i for i in band if (B[i, 0] + B[i, 2]) / 2 < g])
            if k < len(sp):
                out.append(items[sp[k]][1])
        return out + (sub(bot) if bot else [])
    h = horizontal(items, mh)
    if h:
        return sub(h[0]) + sub(h[1])
    return [items[i][1] for i in rows_rtl(B)]


def rows_rtl(B):
    """No gap at all: rows (boxes chained by vertical overlap > half the smaller height) top to bottom, right to left
    inside a row."""
    n = len(B)
    o = sorted(range(n), key=lambda i: B[i, 1])
    rows = []
    for i in o:
        h = B[i, 3] - B[i, 1]
        for r in rows:
            j = r[-1]
            if min(B[i, 3], B[j, 3]) - max(B[i, 1], B[j, 1]) > 0.5 * min(h, B[j, 3] - B[j, 1]):
                r.append(i)
                break
        else:
            rows.append([i])
    rows.sort(key=lambda r: min(B[i, 1] for i in r))
    return [i for r in rows for i in sorted(r, key=lambda i: -B[i, 2])]


def order_cols(boxes, labels, rtl=True, H=None, W=None):
    n = len(boxes)
    if n == 0:
        return []
    B = np.array(boxes, dtype=float)
    if not rtl:                                   # mirror: read every page right to left
        xmax = B[:, 2].max() + B[:, 0].min()
        B = np.stack([xmax - B[:, 2], B[:, 1], xmax - B[:, 0], B[:, 3]], 1)
    labels = list(labels) if labels is not None else [None] * n
    mh = float(np.median(np.maximum(1e-6, B[:, 3] - B[:, 1])))
    at = [i for i in range(n) if labels[i] in O94.ATOM]
    items = []
    for g in O94._regions(at, B, mh):
        if len(g) == 1:
            items.append((list(B[g[0]]), g[0], False))
        else:
            box = [B[g, 0].min(), B[g, 1].min(), B[g, 2].max(), B[g, 3].max()]
            items.append((box, O94.table_order(g, B, True), True))
    items += [(list(B[i]), i, False) for i in range(n) if labels[i] not in O94.ATOM]
    return O94.flatten(_rec(items, mh))

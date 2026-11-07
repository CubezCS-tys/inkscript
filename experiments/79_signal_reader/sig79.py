"""Experiment 79: ink -> an ordered pen signal (the shared machinery of the real and the synthetic paths).

The picture: a finger feeling the strokes written on your back.  A printed line is turned into the movement a pen
would make writing it: piece by piece from right to left, each piece's centre line travelled from its first letter
to its last (side strokes such as an alef, lam or kaf's tall stroke go up and come back; loops of ه م و ف ق are
travelled round), then the piece's dots and marks, right to left, each a short stroke with the pen lifted between.

  binarise -> pieces and marks (connected ink) -> the centre line of every piece (Zhang-Suen, src penpath.thin)
  -> a graph (ends and junctions as nodes, centre-line runs as edges) -> a walk that covers every edge
  (trunk from the start to the left end, as experiment 09's pen path; branches before the trunk goes on)
  -> points resampled at an even step -> per-point features.

CPU only, numpy + cv2 + networkx.  No training here.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import networkx as nx
import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
ROOT = E.parent
OUT = HERE / "out"
sys.path.insert(0, str(ROOT / "src"))
try:
    from inkscript.geometry.penpath import thin  # noqa: E402  (Zhang-Suen, the pen path's own thinning)
except ImportError:                                                    # the rented host has no src/: the same function
    def thin(img: np.ndarray) -> np.ndarray:
        """Zhang-Suen thinning (a copy of src/inkscript/geometry/penpath.thin)."""
        I = img.astype(np.uint8).copy(); changed = True
        while changed:
            changed = False
            for it in (0, 1):
                P = np.pad(I, 1); p2, p3, p4, p5, p6, p7, p8, p9 = P[:-2, 1:-1], P[:-2, 2:], P[1:-1, 2:], P[2:, 2:], P[2:, 1:-1], P[2:, :-2], P[1:-1, :-2], P[:-2, :-2]
                B = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9; seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
                A = sum(((seq[k] == 0) & (seq[k + 1] == 1)).astype(int) for k in range(8))
                c = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0) if it == 0 else (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
                m = (I == 1) & (B >= 2) & (B <= 6) & (A == 1) & c
                if m.any(): I[m] = 0; changed = True
        return I

NB8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


# ------------------------------------------------------------------------------------------------ ink and line metrics

def binarise(grey: np.ndarray) -> np.ndarray:
    """Ink mask (bool) of a grey crop: Otsu after a light blur, tiny specks removed."""
    g = cv2.GaussianBlur(grey, (3, 3), 0)
    bg = cv2.dilate(g, np.ones((1, 1), np.uint8))
    bg = cv2.medianBlur(cv2.dilate(g, np.ones((7, 7), np.uint8)), 21)        # the paper, ink removed
    d = np.clip(bg.astype(int) - g.astype(int), 0, 255)                      # darkness against the local paper
    d = (255 * d / max(8, d.max())).astype(np.uint8)
    t, b = cv2.threshold(d, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return b.astype(bool)


def line_metrics(ink: np.ndarray) -> dict:
    """baseline row (the densest row of ink), rise (body height above the baseline), stroke width."""
    rows = ink.sum(1).astype(float)
    rows[rows > 0.6 * ink.shape[1]] = 0                                # a printed rule is not the baseline
    rows = np.convolve(rows, np.ones(3) / 3, mode="same")
    base = int(np.argmax(rows))
    dt = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3)
    sk = thin(ink)
    stroke = float(2 * np.median(dt[sk > 0])) if sk.any() else 2.0
    # rise: the row above the baseline where the ink falls below a third of the peak (the body of the letters)
    r = base
    while r > 0 and rows[r] > rows[base] / 4:
        r -= 1
    rise = max(4.0, float(base - r) * 1.6, 2.5 * stroke)
    return dict(baseline=base, rise=rise, stroke=max(1.0, stroke))


def components(ink: np.ndarray, M: dict):
    """Connected ink, split into pieces (letters' bodies) and marks (dots, hamza, harakat, shadda...)."""
    n, lab, st, cen = cv2.connectedComponentsWithStats(ink.astype(np.uint8), 8)
    base, rise, sw = M["baseline"], M["rise"], M["stroke"]
    pieces, marks = [], []
    for k in range(1, n):
        x, y, w, h, a = st[k]
        if a < max(2, 0.3 * sw * sw):
            continue                                                   # a speck of noise
        top, bot = y, y + h - 1
        Hc = ink.shape[0]
        crosses = top <= base + 0.1 * rise and bot >= base - 0.6 * rise
        if (top <= 1 or bot >= Hc - 2) and not crosses:
            continue                                                   # a neighbour line's descender or dot
        if (w > 3 * rise and h < 1.5 * sw + 2) or (h >= 0.85 * Hc and w < 2.5 * sw + 2):
            continue                                                   # a printed rule (table, underline, column)
        if w > 0.6 * ink.shape[1] and h > 2 * rise and a < 0.1 * w * h:
            continue                                                   # a printed frame round the text
        on_base = top <= base + 0.15 * rise and bot >= base - 0.15 * rise
        small = max(w, h) < 0.65 * rise and a < 2.2 * rise * sw
        c = dict(k=k, x0=int(x), x1=int(x + w - 1), y0=int(top), y1=int(bot), area=int(a),
                 cx=float(cen[k][0]), cy=float(cen[k][1]))
        if small and (not on_base or a < 1.2 * sw * sw * 2):
            c["above"] = c["cy"] < base - 0.3 * rise
            marks.append(c)
        else:
            pieces.append(c)
    return lab, pieces, marks


# ------------------------------------------------------------------------------------------------ centre-line graph

def skeleton_graph(mask: np.ndarray, spur: float):
    """Cropped to the ink's box first (speed); positions come back in the full mask's coordinates."""
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    y0, x0 = max(0, ys.min() - 2), max(0, xs.min() - 2)
    G = _skeleton_graph(mask[y0:ys.max() + 3, x0:xs.max() + 3], spur)
    if G is None:
        return None
    off = np.array([y0, x0], float)
    for n in G.nodes:
        p = G.nodes[n]["p"]
        G.nodes[n]["p"] = (p[0] + y0, p[1] + x0)
    for u, v, k, d in G.edges(keys=True, data=True):
        d["pts"] = d["pts"] + off
    return G


def _skeleton_graph(mask: np.ndarray, spur: float):
    """Graph of a centre line: nodes = ends and junction clusters (with a position), edges = pixel runs between them.
    Spurs (end branches shorter than `spur` pixels: thinning noise on thick strokes) are pruned."""
    sk = thin(mask).astype(bool)
    if sk.sum() < 2:
        ys, xs = np.where(mask)
        if len(xs) == 0:
            return None
        G = nx.MultiGraph()
        G.add_node(0, p=(float(ys.mean()), float(xs.mean())))
        return G
    H, W = sk.shape
    P = np.pad(sk, 1).astype(np.uint8)
    deg = sum(P[1 + dy:H + 1 + dy, 1 + dx:W + 1 + dx] for dy, dx in NB8) * sk
    nodepix = sk & (deg != 2)
    if not nodepix.any():                                              # a pure loop (o): any pixel as the node
        ys, xs = np.where(sk)
        nodepix = np.zeros_like(sk)
        nodepix[ys[0], xs[0]] = True
    nl_n, nl = cv2.connectedComponents(nodepix.astype(np.uint8), connectivity=8)
    G = nx.MultiGraph()
    for j in range(1, nl_n):
        ys, xs = np.where(nl == j)
        G.add_node(j, p=(float(ys.mean()), float(xs.mean())))
    seen = set()

    def nbrs(y, x):
        for dy, dx in NB8:
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W and sk[yy, xx]:
                yield yy, xx

    for y, x in zip(*np.where(nodepix)):
        a = nl[y, x]
        for q in nbrs(y, x):
            if nodepix[q]:
                continue
            if ((y, x), q) in seen:
                continue
            path = [(y, x), q]
            prev, cur = (y, x), q
            while not nodepix[cur]:
                nxt = [r for r in nbrs(*cur) if r != prev and r not in path[-3:]]
                if not nxt:
                    break
                # prefer a node pixel, then a 4-neighbour (keeps the run on the line)
                nxt.sort(key=lambda r: (not nodepix[r], abs(r[0] - cur[0]) + abs(r[1] - cur[1])))
                prev, cur = cur, nxt[0]
                path.append(cur)
                if len(path) > 4 * sk.sum():
                    break
            if not nodepix[cur]:
                continue
            b = nl[cur]
            seen.add((path[-1], path[-2]))
            seen.add(((y, x), q))
            G.add_edge(a, b, pts=np.array(path, float), L=float(len(path)))
    # junction clusters that touch directly (no deg-2 pixel between): join them with a short edge
    for y, x in zip(*np.where(nodepix)):
        for q in nbrs(y, x):
            if nodepix[q] and nl[q] != nl[y, x] and not G.has_edge(nl[y, x], nl[q]):
                G.add_edge(nl[y, x], nl[q], pts=np.array([(y, x), q], float), L=1.0)
    # prune spurs
    for _ in range(2):
        for n in [n for n in G.nodes if G.degree(n) == 1]:
            if n not in G or G.degree(n) != 1:
                continue
            (u, v, k, d), = list(G.edges(n, keys=True, data=True))
            other = v if u == n else u
            if d["L"] < spur and G.degree(other) >= 3:
                G.remove_node(n)
    return G


def _edge_pts(G, u, v, k):
    """The edge's pixels oriented from u to v."""
    d = G.edges[u, v, k]
    p = d["pts"]
    pu = np.array(G.nodes[u]["p"])
    if np.linalg.norm(p[0] - pu) > np.linalg.norm(p[-1] - pu):
        p = p[::-1]
    return p


def walk(G, start_rule: str, M: dict, y_off: float = 0.0):
    """Cover every edge of a piece's centre line with one pen-down movement.

    start_rule 'baseline': where the first letter's body meets the baseline at the piece's right end (experiment 09);
               'top':      the top of a tall stroke at the right end if there is one (as a hand writes an initial
                           alef or lam: from the top down), else as 'baseline'.
    The trunk is the shortest route from the start to the piece's left end; at every node the walk first takes the
    edges that leave the trunk (a tall stroke, the far side of a loop, a tail), returns along them (a retrace, pen
    down), and only then goes on along the trunk.  Returns a list of (points[N,2] (y,x), retrace flag)."""
    if G is None or G.number_of_nodes() == 0:
        return []
    if G.number_of_edges() == 0:
        n = next(iter(G.nodes))
        return [(np.array([G.nodes[n]["p"]]), 0)]
    pos = {n: np.array(G.nodes[n]["p"]) for n in G.nodes}
    xs = {n: p[1] for n, p in pos.items()}
    base, rise = M["baseline"] - y_off, M["rise"]
    xmax = max(xs.values())
    right = [n for n in G.nodes if xs[n] >= xmax - 0.45 * rise]
    near = [n for n in right if abs(pos[n][0] - base) <= 0.4 * rise] or right
    start = max(near, key=lambda n: xs[n])
    if start_rule == "top":
        tall = [n for n in right if pos[n][0] < base - 0.9 * rise and G.degree(n) == 1]
        if tall:
            start = min(tall, key=lambda n: pos[n][0])
    end = min(G.nodes, key=lambda n: xs[n])
    try:
        trunk = nx.shortest_path(G, start, end, weight="L")
    except nx.NetworkXNoPath:
        trunk = [start]
    trunk_e = {frozenset((a, b)) for a, b in zip(trunk, trunk[1:])}
    t_index = {n: i for i, n in enumerate(trunk)}
    used = set()
    out = []
    stack = [start]
    path_stack = []                                                    # edges taken, for retracing
    total = G.number_of_edges()
    last_dir = np.array([0.0, -1.0])                                   # the pen moves right to left

    def rank(u, v, k):
        fwd = frozenset((u, v)) in trunk_e and t_index.get(v, -1) > t_index.get(u, -1)
        p = _edge_pts(G, u, v, k)
        d = p[min(len(p) - 1, 4)] - p[0]
        n = np.linalg.norm(d)
        turn = 0.0 if n == 0 else 1 - float(np.dot(d / n, last_dir))
        return (fwd, frozenset((u, v)) in trunk_e, turn)

    while len(used) < total and stack:
        u = stack[-1]
        cand = [(u, v, k) for _, v, k in G.edges(u, keys=True) if (min(u, v), max(u, v), k) not in used]
        if cand:
            u, v, k = min(cand, key=lambda e: rank(*e))
            used.add((min(u, v), max(u, v), k))
            p = _edge_pts(G, u, v, k)
            out.append((p, 0))
            if len(p) > 3:
                d = p[-1] - p[-4]
                last_dir = d / (np.linalg.norm(d) + 1e-9)
            stack.append(v)
            path_stack.append((u, v, k))
        else:
            stack.pop()
            if path_stack and len(used) < total:
                a, b, k = path_stack.pop()
                p = _edge_pts(G, b, a, k)
                out.append((p, 1))
    return out


# ------------------------------------------------------------------------------------------------ the line's signal

def resample(p: np.ndarray, step: float) -> np.ndarray:
    if len(p) < 2:
        return p
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    if d[-1] < step:
        return p[[0, -1]]
    t = np.arange(0, d[-1] + 1e-9, step)
    return np.c_[np.interp(t, d, p[:, 0]), np.interp(t, d, p[:, 1])]


def smooth(p: np.ndarray, k: int = 2) -> np.ndarray:
    """Moving average over 2k+1 points (ends kept): takes the pixel staircase out of the centre line."""
    if len(p) < 2 * k + 2:
        return p
    q = p.copy()
    c = np.cumsum(np.vstack([np.zeros((1, 2)), p]), axis=0)
    q[k:-k] = (c[2 * k + 1:] - c[:-2 * k - 1]) / (2 * k + 1)
    return q


def line_signal(grey: np.ndarray, start_rule: str = "top", marks_after: str = "piece", ink: np.ndarray | None = None,
                centre: str = "skeleton", flags: bool = False):
    """The ordered pen signal of one line crop.

    Returns dict(strokes=[dict(kind, pts[N,2] y,x, retrace[N], piece)], M=metrics, order of pieces).
    centre 'skeleton': thinning (Zhang-Suen); 'mcr': the minimum covering run centre line (mcr79.py), whose run
                lengths then give the thickness feature; 'hybrid': MCR's centre line for HEAVY pieces only (HEAVY_SHARE of
                the piece's ink at least 2 x HEAVY_R x the stroke width across), thinning elsewhere; thickness from the
                distance transform throughout (it flags filled heads as well at a matched false-flag rate).
    flags: add per-point end-point / junction / on-a-loop flags and the turn's sign (features 13-16).
    marks_after 'piece': a piece's dots and marks right after it (right to left);
                'line':  all marks after all pieces (as some writers dot a whole word at the end)."""
    if ink is None:
        ink = binarise(grey)
    M = line_metrics(ink)
    lab, pieces, marks = components(ink, M)
    pieces.sort(key=lambda c: -c["x1"])                                # right to left by the right edge
    # each mark to the piece whose ink is nearest horizontally (overlap first)
    owner = {}
    for m in marks:
        best, bd = None, 1e9
        for j, c in enumerate(pieces):
            dx = max(0, c["x0"] - m["cx"], m["cx"] - c["x1"])
            if dx < bd:
                bd, best = dx, j
        owner[m["k"]] = best
    step = max(1.0, 0.12 * M["rise"])
    strokes = []
    thick_map = np.zeros(ink.shape, np.float32) if centre == "mcr" else None

    def add_mark(m):
        mk = lab == m["k"]
        G = skeleton_graph(mk, spur=M["stroke"])
        segs = walk(G, "baseline", dict(M, baseline=m["cy"]), 0.0)
        pts = np.vstack([s for s, _ in segs]) if segs else np.array([[m["cy"], m["cx"]]])
        if len(pts) > 1 and pts[0][1] < pts[-1][1]:                   # a mark is drawn right to left
            pts = pts[::-1]
        pts = resample(pts, step)
        strokes.append(dict(kind="mark", pts=pts, retrace=np.zeros(len(pts), int), piece=owner[m["k"]],
                            above=bool(m["above"]), size=float(m["area"])))

    dtl = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3) if centre == "hybrid" else None
    for j, c in enumerate(pieces):
        mk = lab == c["k"]
        use_mcr = centre == "mcr" or (centre == "hybrid" and float((dtl[mk] >= HEAVY_R * M["stroke"]).mean()) >= HEAVY_SHARE)
        if use_mcr:
            from mcr79 import mcr_centerline
            ys_, xs_ = np.where(mk)
            y0, x0 = max(0, ys_.min() - 2), max(0, xs_.min() - 2)
            cl, th = mcr_centerline(mk[y0:ys_.max() + 3, x0:xs_.max() + 3])
            full = np.zeros_like(mk)
            full[y0:y0 + cl.shape[0], x0:x0 + cl.shape[1]] = cl
            if thick_map is not None:
                tm = thick_map[y0:y0 + th.shape[0], x0:x0 + th.shape[1]]
                np.maximum(tm, th, out=tm)
            G = skeleton_graph(full, spur=1.6 * M["stroke"])
        else:
            G = skeleton_graph(mk, spur=1.6 * M["stroke"])
        segs = walk(G, start_rule, M, 0.0)
        P, R = [], []
        for s, rt in segs:
            s = resample(s, step)
            if P and len(s) and np.linalg.norm(s[0] - P[-1][-1]) > 3 * M["stroke"]:
                pass
            P.append(s)
            R.append(np.full(len(s), rt))
        if P:
            strokes.append(dict(kind="main", pts=smooth(np.vstack(P)), retrace=np.concatenate(R), piece=j))
        if marks_after == "piece":
            for m in sorted([m for m in marks if owner[m["k"]] == j], key=lambda m: -m["cx"]):
                add_mark(m)
    if marks_after == "line":
        for m in sorted(marks, key=lambda m: -m["cx"]):
            add_mark(m)
    sig = add_thickness(dict(strokes=strokes, M=M, n_pieces=len(pieces), n_marks=len(marks)), ink, thick_map)
    return add_flags(sig, ink) if flags else sig


def add_flags(sig: dict, ink: np.ndarray) -> dict:
    """Per-point structure flags from the line's centre line (Zaafouri et al.'s end points / junctions / loops):
    end = near a centre-line end, junc = near a junction (3+ branches), loop = on a closed cycle (what is left after
    peeling every end branch away)."""
    sk = thin(ink).astype(np.uint8)
    H, W = sk.shape

    def degree(m):
        P = np.pad(m, 1)
        return sum(P[1 + dy:H + 1 + dy, 1 + dx:W + 1 + dx] for dy, dx in NB8) * m

    d = degree(sk)
    end = ((d == 1) & (sk > 0)).astype(np.uint8)
    junc = ((d >= 3) & (sk > 0)).astype(np.uint8)
    # loops: real holes in the ink (a counter of >= 4 px that touches no edge), and the ink ring round them
    n, hl, st_, _ = cv2.connectedComponentsWithStats((~ink.astype(bool)).astype(np.uint8), connectivity=4)
    holes = np.zeros((H, W), np.uint8)
    for k in range(1, n):
        x, y, w, h, a = st_[k]
        if a >= 4 and x > 0 and y > 0 and x + w < W and y + h < H:
            holes[hl == k] = 1
    r = int(max(2, round(sig["M"]["stroke"]))) * 2 + 1
    cyc = cv2.dilate(holes, np.ones((r, r), np.uint8)) & ink.astype(np.uint8)
    k3 = np.ones((3, 3), np.uint8)
    maps = dict(end=cv2.dilate(end, k3), junc=cv2.dilate(junc, k3), loop=cyc)
    for st in sig["strokes"]:
        p = np.round(st["pts"]).astype(int)
        y = np.clip(p[:, 0], 0, H - 1)
        x = np.clip(p[:, 1], 0, W - 1)
        for k, m in maps.items():
            st[k] = m[y, x].astype(np.float32)
    sig["flags"] = True
    return sig


HEAVY_R, HEAVY_SHARE = 0.75, 0.10   # hybrid: a piece is heavy when this share of its ink is >= 1.5 x the stroke across
BLOB = 1.8          # a point whose ink is this many times the line's stroke width sits in a filled head or closed counter


def add_thickness(sig: dict, ink: np.ndarray, thick_map: np.ndarray | None = None) -> dict:
    """Each point's ink thickness: twice the distance-transform radius at the point (the largest in its 3x3, since
    smoothing moves points a little off the centre line), over the line's median stroke width.  A filled head
    (و ف ق م, a counter closed by heavy print) has no loop left in its centre line, but stays thick here."""
    if thick_map is not None:                                         # MCR: the covering run's length (already a width)
        dt = cv2.dilate(thick_map / 2.0, np.ones((3, 3), np.uint8))
        dt = np.where(dt > 0, dt, cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3))   # marks: distance
    else:
        dt = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3)
        dt = cv2.dilate(dt, np.ones((3, 3), np.uint8))
    sw = max(1.0, sig["M"]["stroke"])
    if thick_map is not None and (thick_map > 0).any():
        sw = max(1.0, float(np.median(thick_map[thick_map > 0])))       # MCR widths on their own scale
    for st in sig["strokes"]:
        p = np.round(st["pts"]).astype(int)
        y = np.clip(p[:, 0], 0, dt.shape[0] - 1)
        x = np.clip(p[:, 1], 0, dt.shape[1] - 1)
        st["thick"] = (2 * dt[y, x] / sw).astype(np.float32)
    return sig


def features(sig: dict) -> np.ndarray:
    """Per-point features (one row per point, in time order):
      0 x  (from the line's right end, in rises, growing to the left)   1 y (above the baseline, in rises)
      2 dx 3 dy (step, in rises)  4 cos 5 sin (direction)  6 curvature (turn per step, radians)
      7 pen_down_start (1 on a stroke's first point: a pen lift happened before it)  8 retrace
      9 is_mark  10 mark_above  11 ink thickness / the line's stroke width (1.0 where unknown: pen data)
     12 blob (thickness >= BLOB: a filled head or closed counter)"""
    M = sig["M"]
    rise, base = M["rise"], M["baseline"]
    rows = []
    xr = max((s["pts"][:, 1].max() for s in sig["strokes"] if len(s["pts"])), default=0)
    for s in sig["strokes"]:
        p = s["pts"]
        for i in range(len(p)):
            y, x = p[i]
            rows.append([(xr - x) / rise, (base - y) / rise, 0, 0, 0, 0, 0, 1.0 if (i == 0 and not s.get("cont")) else 0.0,
                         float(s["retrace"][i]), 1.0 if s["kind"] == "mark" else 0.0,
                         1.0 if s.get("above") else 0.0, float(s["thick"][i]) if "thick" in s else 1.0, 0.0])
    F = np.array(rows, dtype=np.float32) if rows else np.zeros((0, 13), np.float32)
    if len(F):
        F[:, 11] = np.clip(F[:, 11], 0, 6)
        F[:, 12] = (F[:, 11] >= BLOB).astype(np.float32)
    if len(F) > 1:
        d = np.diff(F[:, :2], axis=0, prepend=F[:1, :2])
        F[:, 2:4] = d
        ang = np.arctan2(d[:, 1], d[:, 0])
        F[:, 4], F[:, 5] = np.cos(ang), np.sin(ang)
        turn = np.diff(ang, prepend=ang[:1])
        F[:, 6] = (turn + np.pi) % (2 * np.pi) - np.pi
        F[F[:, 7] == 1, 2:7] = 0                                       # no movement feature across a pen lift
    if sig.get("flags"):                                               # 13 end 14 junction 15 loop 16 turn sign
        ex = [np.concatenate([s_[k] for s_ in sig["strokes"]]) if sig["strokes"] else np.zeros(0) for k in ("end", "junc", "loop")]
        sgn = np.where(F[:, 6] > 0.15, 1.0, np.where(F[:, 6] < -0.15, -1.0, 0.0)) if len(F) else np.zeros(0)
        F = np.c_[F, *ex, sgn].astype(np.float32) if len(F) else np.zeros((0, 17), np.float32)
    return F


# ------------------------------------------------------------------------------------------------ drawing

def draw(grey: np.ndarray, sig: dict, scale: int = 3, label: str = "") -> np.ndarray:
    """The ink in pale grey, the pen path coloured by time (red = first, through yellow and green, to blue/purple =
    last), retraces thin and black, pen lifts as thin grey lines, stroke numbers at each stroke's start."""
    h, w = grey.shape
    base = cv2.resize(grey, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)
    img = cv2.cvtColor((255 - (255 - base) * 0.35).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    allp = [(s, i) for s in sig["strokes"] for i in range(len(s["pts"]))]
    N = max(1, len(allp))
    t = 0
    prev_end = None
    for n, s in enumerate(sig["strokes"]):
        p = s["pts"] * scale
        if prev_end is not None and len(p):
            cv2.line(img, (int(prev_end[1]), int(prev_end[0])), (int(p[0][1]), int(p[0][0])), (190, 190, 190), 1, cv2.LINE_AA)
        for i in range(len(p)):
            hue = int(170 * (t / N))                                   # 0 red .. 170 purple in OpenCV's hue
            col = cv2.cvtColor(np.uint8([[[hue, 255, 230]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()
            if i > 0:
                a, b = p[i - 1], p[i]
                if s["retrace"][i]:
                    cv2.line(img, (int(a[1]), int(a[0])), (int(b[1]), int(b[0])), (40, 40, 40), 1, cv2.LINE_AA)
                else:
                    cv2.line(img, (int(a[1]), int(a[0])), (int(b[1]), int(b[0])), col, max(2, scale - 1), cv2.LINE_AA)
            elif s["kind"] == "mark" and len(p) == 1:
                cv2.circle(img, (int(p[0][1]), int(p[0][0])), scale + 1, col, -1, cv2.LINE_AA)
            t += 1
        if len(p):
            cv2.circle(img, (int(p[0][1]), int(p[0][0])), 3, (0, 0, 0), -1)
            cv2.putText(img, str(n + 1), (int(p[0][1]) + 2, int(p[0][0]) - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                        (0, 0, 160) if s["kind"] == "main" else (120, 0, 0), 1, cv2.LINE_AA)
            prev_end = p[-1]
    if label:
        bar = np.full((22, img.shape[1], 3), 255, np.uint8)
        cv2.putText(bar, label, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        img = np.vstack([bar, img])
    return img


def signal_strip(F: np.ndarray, width: int, h: int = 90) -> np.ndarray:
    """The line as a signal over time: x (grey), y (blue), curvature (red), pen lifts (black ticks)."""
    img = np.full((h, width, 3), 255, np.uint8)
    n = len(F)
    if n < 2:
        return img
    tx = np.linspace(4, width - 4, n)

    def plot(v, col, lo, hi):
        v = np.clip((v - lo) / (hi - lo + 1e-9), 0, 1)
        pts = np.c_[tx, (h - 6) - v * (h - 12)].astype(np.int32)
        cv2.polylines(img, [pts], False, col, 1, cv2.LINE_AA)

    plot(F[:, 0], (150, 150, 150), F[:, 0].min(), F[:, 0].max())
    plot(F[:, 1], (200, 80, 0), -1.0, 2.5)
    plot(np.clip(F[:, 6], -1.5, 1.5), (0, 0, 220), -1.5, 1.5)
    for i in np.where(F[:, 7] == 1)[0]:
        cv2.line(img, (int(tx[i]), 0), (int(tx[i]), 8), (0, 0, 0), 1)
    cv2.putText(img, "time ->  x (grey)  y (blue)  turn (red)  | pen lift", (4, h - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                (0, 0, 0), 1, cv2.LINE_AA)
    return img

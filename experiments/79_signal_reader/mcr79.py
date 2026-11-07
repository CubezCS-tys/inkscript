"""Experiment 79: the Minimum Covering Run (MCR) centre line (Zidouri, "ORAN: a basis for an Arabic OCR system",
IEEE ISIMP 2004, KFUPM; doi 10.1109/ISIMP.2004.1434161), a competitor to thinning.

The ink is described by its horizontal and vertical runs.  Every ink pixel lies on exactly one horizontal run (H-run)
and one vertical run (V-run), so the pixels are the EDGES of a bipartite graph between H-runs and V-runs.  The
fewest runs that cover all the ink are a minimum vertex cover, which (Konig) has the size of a maximum matching
(Hopcroft-Karp).  A flat stroke comes out as a stack of H-runs, an upright one as a stack of V-runs, a filled head
as a block of runs; no pixel is peeled away as in thinning.

The centre line: every pixel goes to the direction of the run that covers it (to the longer run when both are in
the cover).  For each connected region of H-covered pixels, the centre line runs through the middle of its stack at
every column, and the stack's height there is the stroke's thickness; V regions likewise by rows.  Neighbouring
regions are joined at their nearest centre-line pixels.  The result goes into sig79's graph and walk unchanged.
"""
from __future__ import annotations

import cv2
import networkx as nx
import numpy as np
from networkx.algorithms import bipartite


def runs(mask: np.ndarray, axis: int) -> np.ndarray:
    """Run id of every ink pixel along rows (axis=1: H-runs) or columns (axis=0: V-runs); -1 off the ink."""
    m = mask if axis == 1 else mask.T
    ids = np.full(m.shape, -1, np.int64)
    p = np.pad(m, ((0, 0), (1, 0)))
    start = m & ~p[:, :-1]
    ids_flat = np.cumsum(start.ravel()).reshape(m.shape) - 1
    ids[m] = ids_flat[m]
    return ids if axis == 1 else ids.T


def mcr_cover(mask: np.ndarray):
    """-> (direction map: 1 = H-covered, 2 = V-covered, 0 off ink; H-run length; V-run length)."""
    h, v = runs(mask, 1), runs(mask, 0)
    ys, xs = np.where(mask)
    hid, vid = h[ys, xs], v[ys, xs]
    G = nx.Graph()
    top = [("h", int(i)) for i in np.unique(hid)]
    G.add_nodes_from(top, bipartite=0)
    G.add_nodes_from((("v", int(i)) for i in np.unique(vid)), bipartite=1)
    G.add_edges_from(((("h", int(a)), ("v", int(b))) for a, b in zip(hid, vid)))
    M = bipartite.hopcroft_karp_matching(G, top_nodes=top)
    cover = bipartite.to_vertex_cover(G, M, top_nodes=top)
    hlen = np.bincount(hid)[hid]
    vlen = np.bincount(vid)[vid]
    inH = np.array([("h", int(a)) in cover for a in hid])
    inV = np.array([("v", int(b)) in cover for b in vid])
    d = np.where(inH & ~inV, 1, np.where(inV & ~inH, 2, np.where(hlen >= vlen, 1, 2)))
    D = np.zeros(mask.shape, np.uint8)
    D[ys, xs] = d
    return D


def _segments(v: np.ndarray):
    """Split sorted integer positions into runs of consecutive values."""
    if len(v) == 0:
        return []
    cut = np.where(np.diff(v) > 1)[0] + 1
    return np.split(v, cut)


def mcr_centerline(mask: np.ndarray):
    """-> (centre line bool, thickness in pixels at centre-line pixels (0 elsewhere))."""
    mask = mask.astype(bool)
    H, W = mask.shape
    cl = np.zeros((H, W), np.uint8)
    th = np.zeros((H, W), np.float32)
    if mask.sum() < 3:
        cl[mask] = 1
        th[mask] = 1
        return cl.astype(bool), th
    D = mcr_cover(mask)
    mids = []                                                          # per region: its centre-line points
    for d in (1, 2):
        n, lab = cv2.connectedComponents((D == d).astype(np.uint8), connectivity=8)
        for k in range(1, n):
            ys, xs = np.where(lab == k)
            pts = []
            if d == 1:                                                 # H-stack: middle of each run of rows, per column
                for x in np.unique(xs):
                    for seg in _segments(np.sort(ys[xs == x])):
                        pts.append((float(seg.mean()), float(x), float(len(seg))))
            else:                                                      # V-stack: middle of each run of columns, per row
                for y in np.unique(ys):
                    for seg in _segments(np.sort(xs[ys == y])):
                        pts.append((float(y), float(seg.mean()), float(len(seg))))
            P = np.array(pts)
            for i in range(len(P)):
                y, x, t = int(round(P[i, 0])), int(round(P[i, 1])), P[i, 2]
                cl[y, x] = 1
                th[y, x] = max(th[y, x], t)
            # connect each point to its nearest point in the previous column (row): arms stay apart
            key = 1 if d == 1 else 0
            for i in range(len(P)):
                prev = P[P[:, key] == P[i, key] - 1]
                if len(prev):
                    q = prev[np.argmin(np.abs(prev[:, 1 - key] - P[i, 1 - key]))]
                    if abs(q[1 - key] - P[i, 1 - key]) <= max(2.0, 0.6 * max(q[2], P[i, 2])):
                        cv2.line(cl, (int(round(q[1])), int(round(q[0]))), (int(round(P[i, 1])), int(round(P[i, 0]))), 1, 1)
            mids.append((lab == k, P))
    # join regions that touch at their nearest centre-line points
    for i in range(len(mids)):
        grown = cv2.dilate(mids[i][0].astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        for j in range(i + 1, len(mids)):
            if (grown & mids[j][0]).any():
                a, b = mids[i][1][:, :2], mids[j][1][:, :2]
                dd = ((a[:, None, :] - b[None, :, :]) ** 2).sum(-1)
                u, v = np.unravel_index(int(np.argmin(dd)), dd.shape)
                cv2.line(cl, (int(round(a[u, 1])), int(round(a[u, 0]))), (int(round(b[v, 1])), int(round(b[v, 0]))), 1, 1)
    cl = cl.astype(bool) & cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    # the ink is one piece, so its centre line must be one: join fragments, nearest first (a spanning tree)
    n, lab = cv2.connectedComponents(cl.astype(np.uint8), connectivity=8)
    if n > 2:
        comps = [np.argwhere(lab == k) for k in range(1, n)]
        joined = [comps[0]]
        rest = comps[1:]
        while rest:
            A = np.vstack(joined)
            best = None
            for r, B in enumerate(rest):
                dd = ((A[:, None, :] - B[None, :, :]) ** 2).sum(-1)
                u, v = np.unravel_index(int(np.argmin(dd)), dd.shape)
                if best is None or dd[u, v] < best[0]:
                    best = (dd[u, v], r, A[u], B[v])
            _, r, a, b = best
            c8 = cl.astype(np.uint8)
            cv2.line(c8, (int(a[1]), int(a[0])), (int(b[1]), int(b[0])), 1, 1)
            cl = c8.astype(bool)
            joined.append(rest.pop(r))
    return cl, th

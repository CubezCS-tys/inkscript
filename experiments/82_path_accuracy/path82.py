"""Experiment 82: the pen-path rebuilders compared here, all ending in exp 79's own graph and right-to-left walk.

    rebuild(grey, method, ink=None, cl=None) -> exp 79's signal dict (strokes, M, ...), the same as sig79.line_signal

method
  skeleton  - Zhang-Suen thinning of each piece (exp 79's default, sig79.line_signal centre='skeleton')
  mcr       - Zidouri's minimum covering runs (sig79 centre='mcr')
  hybrid    - exp 79's piece-level hybrid: MCR for a whole piece when it is heavy, thinning elsewhere (centre='hybrid')
  hybrid_r  - REGIONAL hybrid (new here): inside blob regions of a piece (ink at least 1.5 x the stroke across) the
              MCR centre line, elsewhere the thinned one; the two are joined into one line
  learned   - the centre line predicted by the network (learn82.py), given as `cl` (bool map of the line); pieces are
              the connected parts of ink + predicted centre line, so a stroke the network bridges is one piece again
Everything after the centre line (graph, spur pruning, walk, marks, resampling, thickness) is exp 79's code, so the
rebuilders differ only in WHERE the centre line runs.  None of them sees letters.

The files sig79.py, synth79.py, mcr79.py, data79.py and mcrcmp79.py next to this one are frozen copies of
experiment 79's (2026-11-05, before its rung 2), so a change there cannot move these numbers.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "79_signal_reader/data/pylib"))

import sig79 as S  # noqa: E402
from sig79 import HEAVY_R, add_thickness, binarise, components, line_metrics, resample, skeleton_graph, smooth, thin, walk  # noqa: E402

cv2.setNumThreads(1)
METHODS = ["skeleton", "mcr", "hybrid", "hybrid_r"]


def _join_fragments(cl: np.ndarray) -> np.ndarray:
    """Join the pieces of a centre line nearest first (a spanning tree), as mcr79 does."""
    n, lab = cv2.connectedComponents(cl.astype(np.uint8), connectivity=8)
    if n <= 2:
        return cl
    comps = [np.argwhere(lab == k) for k in range(1, n)]
    joined, rest = [comps[0]], comps[1:]
    c8 = cl.astype(np.uint8)
    while rest:
        A = np.vstack(joined)
        best = None
        for r, B in enumerate(rest):
            dd = ((A[:, None, :] - B[None, :, :]) ** 2).sum(-1)
            u, v = np.unravel_index(int(np.argmin(dd)), dd.shape)
            if best is None or dd[u, v] < best[0]:
                best = (dd[u, v], r, A[u], B[v])
        _, r, a, b = best
        cv2.line(c8, (int(a[1]), int(a[0])), (int(b[1]), int(b[0])), 1, 1)
        joined.append(rest.pop(r))
    return c8.astype(bool)


def centre_hybrid_r(mk: np.ndarray, stroke: float) -> np.ndarray:
    """Regional hybrid centre line of one piece (cropped mask): MCR inside blob regions, thinning outside."""
    from mcr79 import mcr_centerline
    dt = cv2.distanceTransform(mk.astype(np.uint8), cv2.DIST_L2, 3)
    blob = dt >= HEAVY_R * stroke
    if not blob.any():
        return thin(mk).astype(bool)
    r = int(max(2, round(1.0 * stroke)))
    region = cv2.dilate(blob.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))).astype(bool) & mk
    sk = thin(mk).astype(bool)
    cl_m, _ = mcr_centerline(mk)
    cl = (sk & ~region) | (cl_m & region)
    cl = _join_fragments(cl)
    return thin(cl.astype(np.uint8) | 0).astype(bool) if cl.sum() > 2 else cl


def rebuild(grey: np.ndarray, method: str, ink: np.ndarray | None = None, cl: np.ndarray | None = None,
            start_rule: str = "top") -> dict:
    if method in ("skeleton", "mcr", "hybrid"):
        return S.line_signal(grey, start_rule=start_rule, ink=ink, centre=method)
    if ink is None:
        ink = binarise(grey)
    if method == "learned":
        assert cl is not None
        cl = cl.astype(bool)
        r = 1
        joined = ink | cv2.dilate(cl.astype(np.uint8), np.ones((2 * r + 1, 2 * r + 1), np.uint8)).astype(bool)
        M = line_metrics(ink)
        lab, pieces, marks = components(joined, M)
    else:
        M = line_metrics(ink)
        lab, pieces, marks = components(ink, M)
    pieces.sort(key=lambda c: -c["x1"])
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

    def add_mark(m):
        mk = lab == m["k"]
        G = skeleton_graph(mk, spur=M["stroke"])
        segs = walk(G, "baseline", dict(M, baseline=m["cy"]), 0.0)
        pts = np.vstack([s for s, _ in segs]) if segs else np.array([[m["cy"], m["cx"]]])
        if len(pts) > 1 and pts[0][1] < pts[-1][1]:
            pts = pts[::-1]
        pts = resample(pts, step)
        strokes.append(dict(kind="mark", pts=pts, retrace=np.zeros(len(pts), int), piece=owner[m["k"]],
                            above=bool(m["above"]), size=float(m["area"])))

    for j, c in enumerate(pieces):
        mk = lab == c["k"]
        ys_, xs_ = np.where(mk)
        y0, x0 = max(0, ys_.min() - 2), max(0, xs_.min() - 2)
        sub = mk[y0:ys_.max() + 3, x0:xs_.max() + 3]
        if method == "hybrid_r":
            cls = centre_hybrid_r(sub, M["stroke"])
        else:                                                          # learned: the predicted line inside this piece
            cls = cl[y0:ys_.max() + 3, x0:xs_.max() + 3] & sub
            if cls.sum() < 3:
                cls = thin(sub).astype(bool)
            else:
                cls = _join_fragments(thin(cls.astype(np.uint8)).astype(bool))
        full = np.zeros_like(mk)
        full[y0:y0 + cls.shape[0], x0:x0 + cls.shape[1]] = cls
        G = skeleton_graph(full, spur=1.6 * M["stroke"])
        segs = walk(G, start_rule, M, 0.0)
        P, R = [], []
        for s, rt in segs:
            s = resample(s, step)
            P.append(s)
            R.append(np.full(len(s), rt))
        if P:
            strokes.append(dict(kind="main", pts=smooth(np.vstack(P)), retrace=np.concatenate(R), piece=j))
        for m in sorted([m for m in marks if owner[m["k"]] == j], key=lambda m: -m["cx"]):
            add_mark(m)
    return add_thickness(dict(strokes=strokes, M=M, n_pieces=len(pieces), n_marks=len(marks)), ink)
